# FSVV-Protokolle

Dieses Repository sammelt und vereinheitlicht Protokolle der Fachschaftsrätevollversammlung (FSVV) in ein gut durchsuchbares Markdown-Format.

## Ziel

Die Protokolle liegen aus verschiedenen Quellen und in unterschiedlichen Formaten vor. Dieses Projekt führt sie in einem gemeinsamen Bestand zusammen, damit sie leichter gelesen, durchsucht und weiterverarbeitet werden können.

## Inhalt

- `md/`: bereinigte Markdown-Dateien, nach Datum benannt
- `index.md`: Bestandsindex mit vorhandenen Protokollen, auffälligen Datumsangaben und plausiblen Lücken

## Aufbereitung

- Protokolle werden aus den verfügbaren Quelldateien in Markdown übertragen.
- HTML-Exporte werden von Portal- und JavaScript-Resten bereinigt.
- PDF-Protokolle mit zweispaltigem Layout werden spaltenbewusst extrahiert, damit die Lesereihenfolge möglichst sauber erhalten bleibt.
- Offensichtliche Dubletten werden entfernt oder zusammengeführt.

## Hinweise

- Nicht jede Datumsangabe in den Quelldateien ist konsistent. Bekannte Auffälligkeiten bleiben im Index dokumentiert.
- Lücken im Bestand sind nicht automatisch fehlende Sitzungen: In der vorlesungsfreien Zeit finden FSVV-Sitzungen nicht zwingend wöchentlich statt.
- Einige Altdateien sind bereits an der Quelle defekt oder nicht mehr abrufbar.

## Struktur

- `convert_raw_to_md.rb`: Konvertierung der HTML-Exporte
- `convert_raw3_to_md.py`: Konvertierung weiterer Quelldateien, insbesondere PDF- und ODT-Bestände
- `md/`: Zielverzeichnis für die vereinheitlichten Markdown-Protokolle
- `index.md`: Index des aktuellen Bestands
