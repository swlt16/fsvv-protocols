from __future__ import annotations

import re
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path('/Users/sebastian/FSVV-Protokolle')
RAW3 = ROOT / 'raw3'
OUT = ROOT / 'md'
PROTECTED_DIRS = [ROOT / 'raw', ROOT / 'raw2']
PDFTOHTML = '/opt/homebrew/bin/pdftohtml'
PANDOC = '/opt/homebrew/bin/pandoc'

DATE_PATTERNS = {
    'iso': re.compile(r'(20\d{2})[-_.](\d{2})[-_.](\d{2})'),
    'yy_mm_dd': re.compile(r'(?<!\d)(\d{2})[-_](\d{2})[-_](\d{2})(?!\d)'),
    'dd_mm_yy_dots': re.compile(r'(\d{2})\.(\d{2})\.(\d{2,4})'),
    'ddmmyy': re.compile(r'(?<!\d)(\d{2})(\d{2})(\d{2})(?!\d)'),
}


def canonical_date_from_stem(stem: str) -> str | None:
    m = DATE_PATTERNS['iso'].search(stem)
    if m:
        year, month, day = m.groups()
        return f"{year}-{month}-{day}"

    m = DATE_PATTERNS['yy_mm_dd'].search(stem)
    if m:
        year, month, day = m.groups()
        year = ('20' if int(year) < 70 else '19') + year
        return f"{year}-{month}-{day}"

    m = DATE_PATTERNS['dd_mm_yy_dots'].search(stem)
    if m:
        day, month, year = m.groups()
        if len(year) == 2:
            year = ('20' if int(year) < 70 else '19') + year
        return f"{year}-{month}-{day}"

    m = DATE_PATTERNS['ddmmyy'].search(stem)
    if m:
        day, month, year = m.groups()
        year = ('20' if int(year) < 70 else '19') + year
        return f"{year}-{month}-{day}"

    return None


def canonical_name(path: Path) -> str:
    date = canonical_date_from_stem(path.stem)
    if date:
        return f"{date}.md"
    safe = re.sub(r'[^A-Za-z0-9._()-]+', '-', path.stem).strip('-')
    return f"{safe}.md"


def protected_dates() -> set[str]:
    dates: set[str] = set()
    for directory in PROTECTED_DIRS:
        if not directory.exists():
            continue
        for path in directory.glob('*.html'):
            date = canonical_date_from_stem(path.stem)
            if date:
                dates.add(date)
    return dates


def previous_targets_for(path: Path, protected: set[str]) -> list[Path]:
    date = canonical_date_from_stem(path.stem)
    if date:
        if date in protected:
            pattern = f'{date}--dup*.md'
            return sorted(OUT.glob(pattern))
        targets = [OUT / f'{date}.md']
        targets.extend(sorted(OUT.glob(f'{date}--dup*.md')))
        return targets

    stem = canonical_name(path)[:-3]
    targets = [OUT / f'{stem}.md']
    targets.extend(sorted(OUT.glob(f'{stem}--dup*.md')))
    return targets


def clear_previous_outputs(protected: set[str]) -> None:
    seen: set[Path] = set()
    for path in sorted(RAW3.iterdir()):
        if not path.is_file():
            continue
        for target in previous_targets_for(path, protected):
            if target in seen or not target.exists():
                continue
            target.unlink()
            seen.add(target)


def target_for(path: Path, protected: set[str], seen_raw3: set[str]) -> Path:
    date = canonical_date_from_stem(path.stem)
    base = OUT / canonical_name(path)
    if date and date not in protected and date not in seen_raw3:
        seen_raw3.add(date)
        return base
    if date:
        stem = date
    else:
        stem = base.stem
    n = 2
    while True:
        cand = OUT / f"{stem}--dup{n}.md"
        if not cand.exists():
            return cand
        n += 1


def row_to_text(row: list[dict[str, int | str]]) -> str:
    row = sorted(row, key=lambda item: int(item['left']))
    parts: list[str] = []
    prev: dict[str, int | str] | None = None
    for item in row:
        if prev is not None:
            prev_right = int(prev['left']) + int(prev['width'])
            gap = int(item['left']) - prev_right
            if gap > 12:
                parts.append(' ')
        parts.append(str(item['text']))
        prev = item
    return re.sub(r'\s+', ' ', ' '.join(parts)).strip()


def lines_for_items(items: list[dict[str, int | str]], top_threshold: int = 3) -> list[str]:
    if not items:
        return []
    items = sorted(items, key=lambda item: (int(item['top']), int(item['left'])))
    rows: list[list[dict[str, int | str]]] = []
    for item in items:
        if not rows or abs(int(item['top']) - int(rows[-1][0]['top'])) > top_threshold:
            rows.append([item])
        else:
            rows[-1].append(item)

    lines: list[str] = []
    for row in rows:
        text = row_to_text(row)
        if text:
            lines.append(text)
    return lines


def extract_pdf_page_lines(page: ET.Element) -> list[str]:
    width = int(page.attrib['width'])
    height = int(page.attrib['height'])
    items: list[dict[str, int | str]] = []
    for node in page.findall('text'):
        text = ''.join(node.itertext()).replace('\xa0', ' ')
        if not text.strip():
            continue
        items.append({
            'top': int(node.attrib['top']),
            'left': int(node.attrib['left']),
            'width': int(node.attrib['width']),
            'text': text.strip(),
        })

    if not items:
        return []

    left_items = [item for item in items if int(item['left']) < width * 0.5]
    right_items = [item for item in items if int(item['left']) >= width * 0.5]

    left_positions = sorted(int(item['left']) for item in left_items)
    right_positions = sorted(int(item['left']) for item in right_items)
    left_p90 = left_positions[min(len(left_positions) - 1, int(len(left_positions) * 0.9))] if left_positions else 0
    right_p10 = right_positions[min(len(right_positions) - 1, max(0, len(right_positions) // 10))] if right_positions else width

    is_two_column = (
        width > height
        and len(left_items) >= 12
        and len(right_items) >= 12
        and (right_p10 - left_p90) >= width * 0.12
    )

    if not is_two_column:
        return lines_for_items(items)

    left_lines = lines_for_items(left_items)
    right_lines = lines_for_items(right_items)
    if left_lines and right_lines:
        return left_lines + [''] + right_lines
    return left_lines + right_lines


def extract_pdf(path: Path) -> str:
    xml_base = Path('/tmp') / f'raw3_{path.stem}'
    subprocess.run([
        PDFTOHTML, '-xml', '-i', str(path), str(xml_base)
    ], check=True, capture_output=True)
    xml_path = Path(f'{xml_base}.xml')
    root = ET.parse(xml_path).getroot()

    page_chunks: list[str] = []
    for page in root.findall('page'):
        page_lines = extract_pdf_page_lines(page)
        if page_lines:
            page_chunks.append('\n'.join(page_lines).strip())

    return '\n\n'.join(chunk for chunk in page_chunks if chunk).strip() + '\n'


def extract_odt(path: Path) -> str:
    result = subprocess.run([
        PANDOC, str(path), '-t', 'gfm'
    ], check=True, capture_output=True)
    return result.stdout.decode('utf-8', 'replace')


def clean_text(text: str) -> str:
    text = text.replace('\f', '\n')
    text = text.replace('\r', '')
    lines = [line.rstrip() for line in text.split('\n')]
    cleaned: list[str] = []
    blank_run = 0
    for line in lines:
        if not line.strip():
            blank_run += 1
            if blank_run <= 1:
                cleaned.append('')
            continue
        blank_run = 0
        line = re.sub(r'[ \t]{2,}', ' ', line).strip()
        if line in {'/', '|'}:
            continue
        cleaned.append(line)
    text = '\n'.join(cleaned)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip() + '\n'


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    protected = protected_dates()
    clear_previous_outputs(protected)
    seen_raw3_dates: set[str] = set()
    converted = 0
    skipped: list[tuple[str, str]] = []

    for path in sorted(RAW3.iterdir()):
        if not path.is_file():
            continue
        ext = path.suffix.lower()
        if ext == '.pdf':
            text = extract_pdf(path)
        elif ext == '.odt':
            text = extract_odt(path)
        else:
            skipped.append((path.name, 'unsupported'))
            continue

        cleaned = clean_text(text)
        target = target_for(path, protected, seen_raw3_dates)
        target.write_text(cleaned, encoding='utf-8')
        converted += 1

    print(f'Converted {converted} files from raw3 into {OUT}')
    if skipped:
        print('Skipped:')
        for name, reason in skipped:
            print(f'- {name}: {reason}')


if __name__ == '__main__':
    main()
