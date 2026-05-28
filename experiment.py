"""
Experiment: LLM-generierte Versicherungssummen-Empfehlungen
Bachelorarbeit Sebastian Gößwellner — FH JOANNEUM Graz

Führt 54 API-Aufrufe pro Modell durch (18 Profile × 3 Formulierungsvarianten).
Unterstützte Modelle: GPT-4o (OpenAI), Claude Sonnet 4.6 (Anthropic), Gemini 3.1 Pro (Google).
Ausgabe: je eine CSV-Datei pro Modell (rohdaten_gpt.csv, rohdaten_claude.csv, rohdaten_gemini.csv).

Verwendung:
    python experiment.py                  # Alle drei Modelle
    python experiment.py --modell gpt     # Nur GPT-4o
    python experiment.py --modell claude  # Nur Claude
    python experiment.py --modell gemini  # Nur Gemini

Benötigte Umgebungsvariablen (je nach gewähltem Modell):
    OPENAI_API_KEY       — für GPT-4o
    ANTHROPIC_API_KEY    — für Claude
    GOOGLE_API_KEY       — für Gemini

Benötigte Pakete:
    pip install openai anthropic google-genai
"""

import csv
import json
import os
import sys
import time
from datetime import datetime, timezone

# ── Konfiguration ──────────────────────────────────────────────────────────────

TEMPERATURE   = 0
MAX_RETRIES   = 3
RETRY_DELAY_S = 10

# Modell-Definitionen: key → (api-modellname, provider)
MODELLE = {
    "gpt":    ("gpt-4o-2024-08-06",       "openai"),
    "claude": ("claude-sonnet-4-6",        "anthropic"),
    "gemini": ("gemini-3.1-pro-preview",   "google"),
}

# Modellauswahl via --modell <name>; default = alle drei
_MODELL_ARG = None
for i, arg in enumerate(sys.argv):
    if arg == "--modell" and i + 1 < len(sys.argv):
        _MODELL_ARG = sys.argv[i + 1].lower()

if _MODELL_ARG:
    if _MODELL_ARG not in MODELLE:
        print(f"Unbekanntes Modell: '{_MODELL_ARG}'. Erlaubt: {', '.join(MODELLE)}")
        sys.exit(1)
    AKTIVE_MODELLE = {_MODELL_ARG: MODELLE[_MODELL_ARG]}
else:
    AKTIVE_MODELLE = MODELLE

# ── Profilmatrix (3 Einkommensklassen × 3 Berufsrisiken × 2 Unterhaltssituationen = 18) ──

PROFILE = [
    {"id": "P01", "alter": 35, "einkommen": 1800, "beruf": "Bürotätigkeit",          "unterhalt": "ledig, keine Kinder"},
    {"id": "P02", "alter": 35, "einkommen": 1800, "beruf": "Bürotätigkeit",          "unterhalt": "verheiratet, 3 Kinder"},
    {"id": "P03", "alter": 35, "einkommen": 1800, "beruf": "Handwerker",             "unterhalt": "ledig, keine Kinder"},
    {"id": "P04", "alter": 35, "einkommen": 1800, "beruf": "Handwerker",             "unterhalt": "verheiratet, 3 Kinder"},
    {"id": "P05", "alter": 35, "einkommen": 1800, "beruf": "Dachdecker/Gerüstbauer", "unterhalt": "ledig, keine Kinder"},
    {"id": "P06", "alter": 35, "einkommen": 1800, "beruf": "Dachdecker/Gerüstbauer", "unterhalt": "verheiratet, 3 Kinder"},
    {"id": "P07", "alter": 35, "einkommen": 3000, "beruf": "Bürotätigkeit",          "unterhalt": "ledig, keine Kinder"},
    {"id": "P08", "alter": 35, "einkommen": 3000, "beruf": "Bürotätigkeit",          "unterhalt": "verheiratet, 3 Kinder"},
    {"id": "P09", "alter": 35, "einkommen": 3000, "beruf": "Handwerker",             "unterhalt": "ledig, keine Kinder"},
    {"id": "P10", "alter": 35, "einkommen": 3000, "beruf": "Handwerker",             "unterhalt": "verheiratet, 3 Kinder"},
    {"id": "P11", "alter": 35, "einkommen": 3000, "beruf": "Dachdecker/Gerüstbauer", "unterhalt": "ledig, keine Kinder"},
    {"id": "P12", "alter": 35, "einkommen": 3000, "beruf": "Dachdecker/Gerüstbauer", "unterhalt": "verheiratet, 3 Kinder"},
    {"id": "P13", "alter": 35, "einkommen": 5500, "beruf": "Bürotätigkeit",          "unterhalt": "ledig, keine Kinder"},
    {"id": "P14", "alter": 35, "einkommen": 5500, "beruf": "Bürotätigkeit",          "unterhalt": "verheiratet, 3 Kinder"},
    {"id": "P15", "alter": 35, "einkommen": 5500, "beruf": "Handwerker",             "unterhalt": "ledig, keine Kinder"},
    {"id": "P16", "alter": 35, "einkommen": 5500, "beruf": "Handwerker",             "unterhalt": "verheiratet, 3 Kinder"},
    {"id": "P17", "alter": 35, "einkommen": 5500, "beruf": "Dachdecker/Gerüstbauer", "unterhalt": "ledig, keine Kinder"},
    {"id": "P18", "alter": 35, "einkommen": 5500, "beruf": "Dachdecker/Gerüstbauer", "unterhalt": "verheiratet, 3 Kinder"},
]

# ── Lookup-Tabellen für V2 (Fließtext) ────────────────────────────────────────

BERUF_V2 = {
    "Bürotätigkeit":          "in einer Bürotätigkeit beschäftigt",
    "Handwerker":             "als Handwerker tätig",
    "Dachdecker/Gerüstbauer": "als Dachdecker bzw. Gerüstbauer tätig",
}

UNTERHALT_V2 = {
    "ledig, keine Kinder":   "Er ist ledig und hat keine Kinder; Unterhaltspflichten bestehen nicht.",
    "verheiratet, 3 Kinder": "Er ist verheiratet und hat drei Kinder; es bestehen Unterhaltspflichten.",
}

# ── Hilfsfunktion ──────────────────────────────────────────────────────────────

def fmt(n):
    """Formatiert eine Zahl mit Tausenderpunkt: 1800 → '1.800'"""
    return f"{n:,}".replace(",", ".")

# ── Prompt-Generierung ─────────────────────────────────────────────────────────

def prompt_v1(p):
    """V1: Strukturierte Tabelle"""
    return (
        "Kundenprofil:\n\n"
        f"| Merkmal             | Ausprägung                    |\n"
        f"|---------------------|-------------------------------|\n"
        f"| Alter               | {p['alter']} Jahre            |\n"
        f"| Nettoeinkommen      | {fmt(p['einkommen'])} €/Monat |\n"
        f"| Berufsrisiko        | {p['beruf']}                  |\n"
        f"| Unterhaltspflichten | {p['unterhalt']}              |"
    )

def prompt_v2(p):
    """V2: Fließtext (narrativ)"""
    return (
        f"Der Kunde ist {p['alter']} Jahre alt und erzielt ein monatliches "
        f"Nettoeinkommen von {fmt(p['einkommen'])} Euro. "
        f"Er ist {BERUF_V2[p['beruf']]}. "
        f"{UNTERHALT_V2[p['unterhalt']]}"
    )

def prompt_v3(p):
    """V3: Stichpunktliste (komprimiert)"""
    return (
        f"- Alter: {p['alter']} Jahre\n"
        f"- Nettoeinkommen: {fmt(p['einkommen'])} €/Monat\n"
        f"- Berufsrisiko: {p['beruf']}\n"
        f"- Unterhaltspflichten: {p['unterhalt']}"
    )

VARIANTEN = {
    "V1": prompt_v1,
    "V2": prompt_v2,
    "V3": prompt_v3,
}

# ── System-Prompt ──────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """Sie sind ein Fachberater für österreichische Privatversicherungen, \
spezialisiert auf Unfallversicherung. Ihre Aufgabe ist es, auf Basis eines Kundenprofils \
eine konkrete Empfehlung für eine angemessene Versicherungssumme zu erarbeiten.

Beratungskontext:
Die österreichische private Unfallversicherung wird als Summenversicherung abgeschlossen. \
Die Versicherungssumme ist präventiv — vor dem Schadenfall — festzulegen und soll jene \
finanziellen Folgen abdecken, die im Fall einer dauernden Invalidität durch Unfall entstehen.

Bei dauernder Erwerbsminderung besteht nach österreichischem Recht ein gesetzlicher Anspruch \
auf Invaliditätspension nach dem ASVG. Private Unfallversicherungsleistungen werden üblicherweise \
ab einem Invaliditätsgrad von 50 % ausgelöst. Die Aufgabe der privaten Unfallversicherung ist es, \
die Versorgungslücke zwischen dem individuellen Bedarf des Kunden und der gesetzlichen Grundleistung \
zu schließen.

Leistungsbausteine:
- Baustein 1 – Einmalige Invaliditätsleistung: Eine Kapitalzahlung zur Deckung einmaliger Kosten \
im Invaliditätsfall (z. B. Wohnungsadaptierung, Rehabilitation, Hilfsmittel).
- Baustein 2 – Monatliche Unfallrente: Eine regelmäßige monatliche Leistung zum dauerhaften \
Ausgleich des Einkommensausfalls, ausgedrückt als monatlicher EUR-Betrag.

Ausgabeanforderungen:
- Geben Sie für jeden Baustein exakt einen ganzzahligen EUR-Betrag an — keine Bandbreiten, \
keine Formulierungen wie "mindestens X" oder "zwischen X und Y".
- Begründen Sie Ihre Empfehlung für jeden Baustein so, dass ein fachkundiger Dritter den \
Rechenweg und die verwendeten Faktoren vollständig nachvollziehen kann: Welche Faktoren des \
Kundenprofils haben Sie berücksichtigt, wie haben Sie gerechnet, welche Referenzwerte haben \
Sie herangezogen?
- Verwenden Sie ausschließlich die im Kundenprofil angegebenen Daten als Grundlage. Treffen \
Sie keine Annahmen über Eigenschaften des Kunden, die nicht explizit im Profil enthalten sind.
- Machen Sie alle Rechenannahmen explizit sichtbar — insbesondere verwendete Referenzwerte \
für die gesetzliche Grundleistung sowie sonstige angenommene Größen.

Antworten Sie ausschließlich im vorgegebenen JSON-Format."""

# ── JSON-Schema-Definition (modellneutral) ─────────────────────────────────────

SCHEMA_PROPERTIES = {
    "baustein_1_einmalzahlung_eur":        {"type": "integer"},
    "baustein_2_unfallrente_monatlich_eur": {"type": "integer"},
    "beruecksichtigte_faktoren":           {"type": "array", "items": {"type": "string"}},
    "berechnungslogik_baustein_1":         {"type": "string"},
    "berechnungslogik_baustein_2":         {"type": "string"},
    "getroffene_annahmen":                 {"type": "string"},
}
SCHEMA_REQUIRED = list(SCHEMA_PROPERTIES.keys())

# ── CSV-Spalten ────────────────────────────────────────────────────────────────

CSV_FELDER = [
    "profil_id",
    "variante",
    "timestamp",
    "modell",
    "temperature",
    "baustein_1_einmalzahlung_eur",
    "baustein_2_unfallrente_monatlich_eur",
    "beruecksichtigte_faktoren",
    "berechnungslogik_baustein_1",
    "berechnungslogik_baustein_2",
    "getroffene_annahmen",
    "raw_response",
    "status",
    "fehler",
]

# ── Modell-Adapter ─────────────────────────────────────────────────────────────

def call_openai(client, modell_name, user_prompt):
    """Ruft die OpenAI API auf und gibt das geparste JSON-Dict zurück."""
    json_schema = {
        "type": "json_schema",
        "json_schema": {
            "name": "versicherungsempfehlung",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": SCHEMA_PROPERTIES,
                "required": SCHEMA_REQUIRED,
                "additionalProperties": False,
            },
        },
    }
    response = client.chat.completions.create(
        model=modell_name,
        temperature=TEMPERATURE,
        response_format=json_schema,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_prompt},
        ],
    )
    raw = response.choices[0].message.content
    return json.loads(raw), raw


def call_anthropic(client, modell_name, user_prompt):
    """Ruft die Anthropic API auf (Tool-Use für strukturierte Ausgabe)."""
    tool_schema = {
        "name": "versicherungsempfehlung",
        "description": "Strukturierte Versicherungsempfehlung für österreichische Unfallversicherung",
        "input_schema": {
            "type": "object",
            "properties": SCHEMA_PROPERTIES,
            "required": SCHEMA_REQUIRED,
        },
    }
    response = client.messages.create(
        model=modell_name,
        max_tokens=4096,
        temperature=TEMPERATURE,
        system=SYSTEM_PROMPT,
        tools=[tool_schema],
        tool_choice={"type": "tool", "name": "versicherungsempfehlung"},
        messages=[{"role": "user", "content": user_prompt}],
    )
    tool_use = next(b for b in response.content if b.type == "tool_use")
    parsed = tool_use.input
    raw = json.dumps(parsed, ensure_ascii=False)
    return parsed, raw


def call_gemini(client_tuple, user_prompt):
    """Ruft die Google Gemini API auf (google-genai SDK, JSON-Response-Schema)."""
    from google.genai import types as google_genai_types
    client, modell_name = client_tuple

    gemini_schema = {
        "type": "object",
        "properties": {
            "baustein_1_einmalzahlung_eur":        {"type": "integer"},
            "baustein_2_unfallrente_monatlich_eur": {"type": "integer"},
            "beruecksichtigte_faktoren":           {"type": "array", "items": {"type": "string"}},
            "berechnungslogik_baustein_1":         {"type": "string"},
            "berechnungslogik_baustein_2":         {"type": "string"},
            "getroffene_annahmen":                 {"type": "string"},
        },
        "required": SCHEMA_REQUIRED,
    }

    response = client.models.generate_content(
        model=modell_name,
        contents=user_prompt,
        config=google_genai_types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=TEMPERATURE,
            response_mime_type="application/json",
            response_schema=gemini_schema,
        ),
    )
    raw = response.text
    parsed = json.loads(raw)
    return parsed, raw

# ── Ergebnis-Hilfsfunktionen ───────────────────────────────────────────────────

def _build_ergebnis(profil_id, variante, timestamp, modell_name, parsed, raw):
    return {
        "profil_id":                           profil_id,
        "variante":                            variante,
        "timestamp":                           timestamp,
        "modell":                              modell_name,
        "temperature":                         TEMPERATURE,
        "baustein_1_einmalzahlung_eur":         parsed["baustein_1_einmalzahlung_eur"],
        "baustein_2_unfallrente_monatlich_eur": parsed["baustein_2_unfallrente_monatlich_eur"],
        "beruecksichtigte_faktoren":           json.dumps(parsed["beruecksichtigte_faktoren"], ensure_ascii=False),
        "berechnungslogik_baustein_1":         parsed["berechnungslogik_baustein_1"],
        "berechnungslogik_baustein_2":         parsed["berechnungslogik_baustein_2"],
        "getroffene_annahmen":                 parsed["getroffene_annahmen"],
        "raw_response":                        raw,
        "status":                              "ok",
        "fehler":                              "",
    }


def _ergebnis_fehler(profil_id, variante, timestamp, modell_name, fehler_msg):
    return {
        "profil_id":                           profil_id,
        "variante":                            variante,
        "timestamp":                           timestamp,
        "modell":                              modell_name,
        "temperature":                         TEMPERATURE,
        "baustein_1_einmalzahlung_eur":         "",
        "baustein_2_unfallrente_monatlich_eur": "",
        "beruecksichtigte_faktoren":           "",
        "berechnungslogik_baustein_1":         "",
        "berechnungslogik_baustein_2":         "",
        "getroffene_annahmen":                 "",
        "raw_response":                        "",
        "status":                              "fehler",
        "fehler":                              fehler_msg,
    }

# ── API-Aufruf mit Retry ───────────────────────────────────────────────────────

def api_call(provider_ctx, profil_id, variante, user_prompt, modell_name, provider):
    """
    Führt einen API-Aufruf durch (mit bis zu MAX_RETRIES Wiederholungen bei 429).
    provider_ctx: für openai/anthropic der Client, für google ein (client, model_name)-Tuple.
    """
    timestamp = datetime.now(timezone.utc).isoformat()
    last_error = None

    for versuch in range(1, MAX_RETRIES + 1):
        try:
            if provider == "openai":
                parsed, raw = call_openai(provider_ctx, modell_name, user_prompt)
            elif provider == "anthropic":
                parsed, raw = call_anthropic(provider_ctx, modell_name, user_prompt)
            elif provider == "google":
                parsed, raw = call_gemini(provider_ctx, user_prompt)
            else:
                raise ValueError(f"Unbekannter Provider: {provider}")

            return _build_ergebnis(profil_id, variante, timestamp, modell_name, parsed, raw)

        except Exception as e:
            last_error = str(e)
            if "429" in last_error and versuch < MAX_RETRIES:
                print(f"\n  ⚠ Rate-Limit (429), Versuch {versuch}/{MAX_RETRIES}. "
                      f"Warte {RETRY_DELAY_S}s ...", end=" ", flush=True)
                time.sleep(RETRY_DELAY_S)
            elif versuch < MAX_RETRIES:
                break

    return _ergebnis_fehler(profil_id, variante, timestamp, modell_name, last_error)

# ── Client-Initialisierung ─────────────────────────────────────────────────────

def init_clients():
    """Initialisiert alle benötigten API-Clients."""
    clients = {}

    for key, (modell_name, provider) in AKTIVE_MODELLE.items():

        if provider == "openai":
            from openai import OpenAI
            api_key = os.environ.get("OPENAI_API_KEY")
            if not api_key:
                print(f"Fehler: OPENAI_API_KEY nicht gesetzt (benötigt für {modell_name}).")
                sys.exit(1)
            clients[key] = OpenAI(api_key=api_key)

        elif provider == "anthropic":
            import anthropic
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                print(f"Fehler: ANTHROPIC_API_KEY nicht gesetzt (benötigt für {modell_name}).")
                sys.exit(1)
            clients[key] = anthropic.Anthropic(api_key=api_key)

        elif provider == "google":
            from google import genai as google_genai
            api_key = os.environ.get("GOOGLE_API_KEY")
            if not api_key:
                print(f"Fehler: GOOGLE_API_KEY nicht gesetzt (benötigt für {modell_name}).")
                sys.exit(1)
            clients[key] = (google_genai.Client(api_key=api_key), modell_name)

    return clients

# ── Hauptprogramm ──────────────────────────────────────────────────────────────

def main():
    clients        = init_clients()
    modell_keys    = list(AKTIVE_MODELLE.keys())
    aufrufe_modell = len(PROFILE) * len(VARIANTEN)          # 18 × 3 = 54
    aufrufe_total  = aufrufe_modell * len(modell_keys)
    fehler_gesamt  = 0

    print(f"Aktive Modelle : {', '.join(modell_keys)}")
    print(f"Aufrufe gesamt : {aufrufe_total} "
          f"({aufrufe_modell} pro Modell × {len(modell_keys)} Modelle)\n")

    for modell_key in modell_keys:
        modell_name, provider = AKTIVE_MODELLE[modell_key]
        client      = clients[modell_key]
        ausgabe_csv = f"rohdaten_{modell_key}.csv"
        zaehler     = 0
        fehler_mod  = 0

        print(f"\n{'━'*60}")
        print(f"  Modell : {modell_name}")
        print(f"  Output : {ausgabe_csv}")
        print(f"{'━'*60}")

        with open(ausgabe_csv, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FELDER)
            writer.writeheader()

            for profil in PROFILE:
                for variante, prompt_fn in VARIANTEN.items():
                    zaehler += 1
                    user_prompt = prompt_fn(profil)

                    print(f"  [{zaehler:02d}/{aufrufe_modell}] "
                          f"{profil['id']}/{variante} ...",
                          end=" ", flush=True)

                    ergebnis = api_call(
                        client, profil["id"], variante, user_prompt,
                        modell_name, provider
                    )
                    writer.writerow(ergebnis)
                    f.flush()

                    if ergebnis["status"] == "fehler":
                        print(f"FEHLER: {ergebnis['fehler'][:80]}")
                        fehler_mod += 1
                    else:
                        b1 = ergebnis["baustein_1_einmalzahlung_eur"]
                        b2 = ergebnis["baustein_2_unfallrente_monatlich_eur"]
                        print(f"B1={b1} EUR  |  B2={b2} EUR/Monat")

                    time.sleep(1)

        print(f"\n  → {ausgabe_csv}: {zaehler} Aufrufe, {fehler_mod} Fehler")
        fehler_gesamt += fehler_mod

    print("\n" + "=" * 60)
    ausgabe_liste = ", ".join(f"rohdaten_{k}.csv" for k in modell_keys)
    print(f"Abgeschlossen: {aufrufe_total} Aufrufe, {fehler_gesamt} Fehler")
    print(f"Ausgabedateien: {ausgabe_liste}")


if __name__ == "__main__":
    main()
