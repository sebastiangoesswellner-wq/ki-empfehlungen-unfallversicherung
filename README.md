# Begleitmaterial zur Bachelorarbeit

**Titel:** Analyse von KI-generierten Vorschlägen zur Versicherungssumme in der Unfallversicherung bei Variation von Eingabeparametern — Bewertung hinsichtlich Konsistenz, Nachvollziehbarkeit und fachlicher Angemessenheit

**Autor:** Sebastian Gößwellner
**Institution:** FH JOANNEUM Graz, Studiengang Bank- und Versicherungsmanagement
**Jahr:** 2026

---

## Inhalt des Repositories

| Datei | Beschreibung |
|---|---|
| `experiment.py` | Erhebungsskript: führt 54 API-Aufrufe pro Modell durch (18 Profile × 3 Formulierungsvarianten) |
| `rohdaten_gpt.csv` | Rohdaten GPT-4o (54 Antworten) |
| `rohdaten_claude.csv` | Rohdaten Claude Sonnet 4.6 (54 Antworten) |
| `rohdaten_gemini.csv` | Rohdaten Gemini 3.1 Pro (54 Antworten) |
| `auswertung_ergebnisse_neu.xlsx` | Auswertungs-Arbeitsmappe (H1, H3, H4 Berechnungen, H2 Codierung) |

---

## Methodik im Überblick

- **Modelle:** GPT-4o (`gpt-4o-2024-08-06`), Claude Sonnet 4.6 (`claude-sonnet-4-6`), Gemini 3.1 Pro (`gemini-3.1-pro-preview`)
- **Sampling-Temperature:** 0 (Eliminierung der stochastischen Variabilität)
- **Profile:** 18 Kundenprofile aus den Faktoren Einkommen (3 Stufen) × Berufsrisiko (3 Stufen) × Unterhaltspflichten (2 Stufen)
- **Formulierungsvarianten:** V1 strukturierte Tabelle, V2 Fließtext, V3 Stichpunktliste
- **Bewertungsdimensionen und Hypothesen:**
  - Konsistenz (H1) — Variationskoeffizient über Formulierungsvarianten
  - Nachvollziehbarkeit (H2) — qualitative Codierung der Begründungen
  - Richtungskonformität (H3a/H3b/H3c) — monotone Reaktion auf Einkommens-, Berufsrisiko- bzw. Unterhaltsvariation
  - Referenzwertadäquanz (H4) — MAPE gegen normatives Referenzmodell

Detaillierte Methodik siehe Bachelorarbeit, Kapitel 3.

---

## Reproduktion

### Voraussetzungen

- Python 3.10 oder höher
- API-Schlüssel für OpenAI, Anthropic und Google AI Studio
- Installierte Pakete (siehe `requirements.txt`)

### Installation

```bash
pip install -r requirements.txt
```

### API-Schlüssel als Umgebungsvariablen setzen

**Windows (PowerShell):**
```powershell
$env:OPENAI_API_KEY = "dein-openai-key"
$env:ANTHROPIC_API_KEY = "dein-anthropic-key"
$env:GOOGLE_API_KEY = "dein-google-key"
```

**macOS / Linux (bash/zsh):**
```bash
export OPENAI_API_KEY="dein-openai-key"
export ANTHROPIC_API_KEY="dein-anthropic-key"
export GOOGLE_API_KEY="dein-google-key"
```

### Skript ausführen

Alle drei Modelle in einem Lauf:
```bash
python experiment.py
```

Einzelnes Modell:
```bash
python experiment.py --modell gpt
python experiment.py --modell claude
python experiment.py --modell gemini
```

Das Skript schreibt je Modell eine CSV-Datei (`rohdaten_gpt.csv`, `rohdaten_claude.csv`, `rohdaten_gemini.csv`) mit allen 54 Antworten samt Zeitstempel, Modellversion und Variantenkennung.

---

## Hinweise zur Reproduzierbarkeit

- **Modellversionen:** Die in der Arbeit getesteten Modellversionen sind in `experiment.py` (Konstante `MODELLE`) festgeschrieben. Spätere Modellversionen können abweichende Ergebnisse liefern.
- **Temperature = 0:** Reduziert die stochastische Variabilität, eliminiert sie aber nicht vollständig. Wiederholte Läufe können geringfügige Abweichungen zeigen, insbesondere bei Gemini.
- **Strukturierte Ausgabe:** Alle drei Modelle werden mit erzwungenem JSON-Schema befragt (OpenAI Structured Outputs, Anthropic Tool-Use, Gemini Response-Schema), um eine einheitliche Auswertung zu ermöglichen.
- **Kosten:** Ein vollständiger Lauf über alle drei Modelle erzeugt rund 162 API-Aufrufe. Die anfallenden Kosten richten sich nach den Tarifen der jeweiligen Anbieter.

---

## KI-Assistenz bei der Skriptentwicklung

Das Skript `experiment.py` wurde mit Unterstützung von ChatGPT (GPT-5) erstellt. Eine vollständige Dokumentation gemäß den FH-Regeln zur KI-Assistenz bei Abschlussarbeiten findet sich in der Bachelorarbeit, Kapitel 5.6 „Transparenz zur KI-Nutzung".

