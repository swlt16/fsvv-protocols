#!/usr/bin/env ruby
# frozen_string_literal: true

require "cgi"
require "fileutils"

ROOT = File.expand_path(__dir__)
RAW_DIRS = [File.join(ROOT, "raw"), File.join(ROOT, "raw2")].select { |dir| Dir.exist?(dir) }.freeze
OUT_DIR = File.join(ROOT, "md")

APPENDIX_MARKERS = [
  "Abkürzungsverzeichnis",
  "Hilfreiche Links",
  "Nützliche Links",
  "Begriffserklärung",
  "Glossar",
  "MiniGlossar"
].freeze

def extract_content_html(source)
  match = source.match(/"content_html":"(.*?)","css_urls"/m)
  return nil unless match

  html = match[1].dup
  html.gsub!("\\u003c", "<")
  html.gsub!("\\u003e", ">")
  html.gsub!("\\u0026", "&")
  html.gsub!("\\n", "\n")
  html.gsub!("\\/", "/")
  html.gsub!("\\\"", '"')
  CGI.unescapeHTML(html)
end

def slice_document_body(content_html)
  start_match = content_html.match(/<div class="well well-document">\s*(.*)/m)
  return nil unless start_match

  body = start_match[1]
  body = body.sub(/\A<!DOCTYPE HTML>\s*/i, "")
  body = body.sub(/<div class="btn btn-emphasized[\s\S]*\z/m, "")
  body = body.sub(/",\s*scripts"\s*:\s*"[\s\S]*\z/m, "")
  body = body.sub(/\$\.htmlPrefilter\s*=\s*function\(html\)\s*\{[\s\S]*\z/m, "")
  body = body.sub(/\bvar inited_simplemde = null;[\s\S]*\z/m, "")
  body = body.sub(/\bvar init_simplemde = function\s*\(input\)\s*\{[\s\S]*\z/m, "")
  body = body.sub(/\bvar simplemde = new EasyMDE\([\s\S]*\z/m, "")
  body = body.sub(/\bspellChecker:\s*false,[\s\S]*\z/m, "")
  body = body.sub(/\s*name:\s*"disableBtn"[\s\S]*\z/m, "")
  body = body.sub(/\s*inited_simplemde = simplemde;[\s\S]*\z/m, "")
  body = body.sub(/\s*var COSINNUS_MAP_TOPICS_JSON[\s\S]*\z/m, "")
  body = body.sub(/\s*var ua = window\.navigator\.userAgent;[\s\S]*\z/m, "")
  body = body.sub(/\s*var _paq = window\._paq = window\._paq \|\| \[\];[\s\S]*\z/m, "")
  body
end

def strip_appendix(html)
  cutoff = nil

  APPENDIX_MARKERS.each do |marker|
    index = html.downcase.rindex(marker.downcase)
    next unless index
    next if index < (html.length * 0.6)

    cutoff = index if cutoff.nil? || index < cutoff
  end

  cutoff ? html[0...cutoff] : html
end

def strip_markdown_appendix(markdown)
  appendix_start = markdown.lines.find_index do |line|
    stripped = line.strip
    stripped.match?(/\A\#{1,3}\s*MiniGlossar:?\s*\z/i) ||
      stripped.match?(/\A\#{1,3}\s*Glossar:?\s*\z/i) ||
      stripped.match?(/\ANützliche Links:?\s*\z/i) ||
      stripped.match?(/\AHilfreich ist außerdem sicher dieses Abkürzungsverzeichnis:?\s*\z/i) ||
      stripped.match?(/\AAbkürzungsverzeichnis:?\s*\z/i)
  end

  return markdown unless appendix_start

  markdown.lines[0...appendix_start].join.rstrip + "\n"
end

def to_markdown(html)
  md = html.dup

  md.gsub!(%r{<(strong|b)[^>]*>\s*(TOP\s+\d+[^\n<]*)\s*</\1>}im, "## \\2")
  md.gsub!(%r{<h1[^>]*>(.*?)</h1>}im, "# \\1\n\n")
  md.gsub!(%r{<h2[^>]*>(.*?)</h2>}im, "# \\1\n\n")
  md.gsub!(%r{<h3[^>]*>(.*?)</h3>}im, "## \\1\n\n")
  md.gsub!(%r{<h4[^>]*>(.*?)</h4>}im, "### \\1\n\n")
  md.gsub!(%r{<h5[^>]*>(.*?)</h5>}im, "### \\1\n\n")
  md.gsub!(%r{<h6[^>]*>(.*?)</h6>}im, "### \\1\n\n")

  md.gsub!(%r{<li[^>]*>\s*}i, "- ")
  md.gsub!(%r{</li>}i, "\n")
  md.gsub!(%r{</ul>|</ol>}i, "\n")
  md.gsub!(%r{<br\s*/?>}i, "\n")
  md.gsub!(%r{</p>}i, "\n\n")
  md.gsub!(%r{<p[^>]*>}i, "")

  md.gsub!(%r{<(strong|b)[^>]*>(.*?)</\1>}im, "**\\2**")
  md.gsub!(%r{<(em|i)[^>]*>(.*?)</\1>}im, "*\\2*")
  md.gsub!(%r{<u[^>]*>(.*?)</u>}im, "\\1")
  md.gsub!(%r{<a [^>]*href="([^"]+)"[^>]*>(.*?)</a>}im, "[\\2](\\1)")

  md.gsub!(%r{<[^>]+>}m, "")

  md.gsub!(/\r/, "")
  md.gsub!(/\u00A0/, " ")
  md.gsub!(/[ \t]+\n/, "\n")
  md.gsub!(/\n{3,}/, "\n\n")

  lines = md.lines.map(&:rstrip)
  cleaned = lines.map do |line|
    line
      .gsub(/\s{2,}/, " ")
      .gsub(/^- +/, "- ")
      .sub(/^##\s*\*\*(TOP\s+\d+.*)\*\*$/i, '## \1')
      .sub(/^#\s*\*\*(.*)\*\*$/, '# \1')
  end

  cleaned.reject! { |line| line.match?(/\A\#{1,6}\s*\z/) }

  strip_markdown_appendix(cleaned.join("\n").strip + "\n")
end

def canonical_date(path)
  base = File.basename(path, ".html")
  date = base[/\d{4}-\d{2}-\d{2}|\d{4}-\d{4}/]
  return unless date

  if date.match?(/\A\d{4}-\d{4}\z/)
    date = date.sub(/\A(\d{4})-(\d{2})(\d{2})\z/, '\1-\2-\3')
  end

  date
end

def output_name(path)
  "#{canonical_date(path) || File.basename(path, '.html')}.md"
end

FileUtils.rm_rf(OUT_DIR)
FileUtils.mkdir_p(OUT_DIR)

converted = []
skipped = []
seen_dates = {}

RAW_DIRS.flat_map { |dir| Dir.glob(File.join(dir, "*.html")) }.sort.each do |path|
  date = canonical_date(path)
  next if date && seen_dates[date]

  source = File.binread(path).force_encoding("UTF-8")
  content_html = extract_content_html(source)
  unless content_html
    skipped << [path, "content_html not found"]
    next
  end

  body_html = slice_document_body(content_html)
  unless body_html
    skipped << [path, "document body not found"]
    next
  end

  body_html = strip_appendix(body_html)
  markdown = to_markdown(body_html)
  out_path = File.join(OUT_DIR, output_name(path))
  File.write(out_path, markdown)
  seen_dates[date] = path if date
  converted << out_path
end

puts "Converted #{converted.size} files into #{OUT_DIR}"
unless skipped.empty?
  warn "Skipped #{skipped.size} files:"
  skipped.each { |path, reason| warn "- #{File.basename(path)}: #{reason}" }
end
