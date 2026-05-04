#!/usr/bin/env python3
"""
Rison Capital – Proaktiv modul
Bygger prompt för proaktiva inläggsförslag (teser + bevakningsbild) och sparar
färdiga förslag i proaktiv_cache.json. Genereringen görs av Claude i sessionen
via wizard-promptar – denna modul innehåller ingen modellanropslogik.
"""

import json
import re
import uuid
import html as _html
from datetime import datetime
from pathlib import Path

TESER_FILE          = Path(__file__).parent / "teser_med_underlag.md"
INDEX_HTML          = Path(__file__).parent / "index.html"
PROAKTIV_CACHE_FILE = Path(__file__).parent / "proaktiv_cache.json"
MAX_FORSLAG         = 30
TEXT_MIN            = 500
TEXT_MAX            = 3000

# ── Läsare ────────────────────────────────────────────────────────────────────

def _las_teser():
    if not TESER_FILE.exists():
        return ""
    return TESER_FILE.read_text(encoding="utf-8")

def _las_bevakningsbild():
    """Parsar index.html och returnerar lista med relevanta artiklar (max 25)."""
    if not INDEX_HTML.exists():
        return []
    try:
        raw = INDEX_HTML.read_text(encoding="utf-8")
    except Exception:
        return []

    delare = '<div style="background:#fff;border:1px solid #e8e8e8;border-radius:10px;padding:22px;'
    blocks = raw.split(delare)
    if len(blocks) < 2:
        return []

    artiklar = []
    for blk in blocks[1:]:
        mr = re.search(r'<span[^>]*>(Hog|Medel)</span>', blk)
        if not mr:
            continue
        relevansniva = "Hög" if mr.group(1) == "Hog" else "Medel"

        mp = re.search(r'<span[^>]*>(\d+)/10</span>', blk)
        poang = int(mp.group(1)) if mp else 0

        mk = re.search(r"kopiera_prompt\(this,\s*'([^']*)',\s*'([^']*)'", blk)
        if not mk:
            continue
        rubrik = _html.unescape(mk.group(1)).strip()
        url    = mk.group(2).strip()
        if not (rubrik and url):
            continue

        datum_relativt = ""
        kandidater = re.findall(
            r'<span style="font-size:13px;color:#666;">([^<]+)</span>',
            blk,
        )
        for k in kandidater:
            t = k.strip()
            if t in ("Hog", "Medel"):
                continue
            datum_relativt = _html.unescape(t)
            break

        sammanfattning = ""
        mu = re.search(r'<ul[^>]*>(.*?)</ul>', blk, flags=re.DOTALL)
        if mu:
            li_texts = re.findall(r'<li[^>]*>(.*?)</li>', mu.group(1), flags=re.DOTALL)
            ren = [re.sub(r'<[^>]+>', '', t) for t in li_texts]
            sammanfattning = _html.unescape(" ".join(s.strip() for s in ren if s.strip()))
            sammanfattning = re.sub(r'\s+', ' ', sammanfattning).strip()[:600]

        artiklar.append({
            "rubrik":         rubrik,
            "url":            url,
            "sammanfattning": sammanfattning,
            "relevansniva":   relevansniva,
            "poang":          poang,
            "datum_relativt": datum_relativt,
        })

    artiklar.sort(key=lambda x: (0 if x["relevansniva"] == "Hög" else 1, -x["poang"]))
    return artiklar[:25]

# ── Cache ─────────────────────────────────────────────────────────────────────

def _las_cache():
    if not PROAKTIV_CACHE_FILE.exists():
        return []
    try:
        d = json.loads(PROAKTIV_CACHE_FILE.read_text(encoding="utf-8"))
        return d if isinstance(d, list) else []
    except Exception:
        return []

def _spara_cache(lista):
    PROAKTIV_CACHE_FILE.write_text(
        json.dumps(lista, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

# ── Prompt-byggare ────────────────────────────────────────────────────────────

def _formatera_bevakning(bevakning):
    if not bevakning:
        return "(Ingen bevakningsbild tillgänglig.)"
    rader = []
    for i, a in enumerate(bevakning, 1):
        rader.append(
            f"{i}. [{a['relevansniva']} {a['poang']}/10 · {a.get('datum_relativt') or 'okänt datum'}] "
            f"{a['rubrik']}\n"
            f"   URL: {a['url']}\n"
            f"   Sammanfattning: {a['sammanfattning']}"
        )
    return "\n\n".join(rader)

def bygg_prompt():
    teser = _las_teser()
    bevakning = _las_bevakningsbild()

    if not teser:
        return None, {"error": "teser_med_underlag.md saknas eller är tom"}

    prompt = f"""# Proaktivt inläggsförslag – Rison Capital

Generera ett LinkedIn-inlägg som driver en av de tre bärande teserna med stöd
av aktuell bevakningsbild. Sök kompletterande källor på webben vid behov.

## Tre bärande teser med underlag

{teser}

## Aktuell bevakningsbild (parsad från index.html)

{_formatera_bevakning(bevakning)}

## Instruktion

1. Välj den tes (1, 2 eller 3) som har starkast stöd i bevakningsbilden just nu.

2. Skriv ett LinkedIn-inlägg på 500-3000 tecken inkl. mellanslag, hashtags och URL. Hård gräns: 3000 tecken.

3. Struktur:
   - Rubrik på max 8 ord
   - Brödtext i prosa – inga punktlistor
   - Hashtags på sista raden (max 5)
   - Eventuell artikel-URL på samma sista rad

4. Ton:
   - Direkt och analytisk – kommentera situationen, beskriv inte lösningen
   - Undvik säljig produktbeskrivning av Risons modell. Om Risons modell nämns: en mening, integrerad i analysen, inte som broschyr
   - Avsluta med påstående, inte engagemangsfråga
   - Stilreferens: linkedin_stil.txt om relevant

5. Källor:
   - Sök på webben efter 1-3 oberoende, institutionella källor: myndigheter (Boverket, Energimyndigheten, Naturvårdsverket, Riksdagen), akademiska studier, internationella institutioner (IEA, ADB, IPCC, OECD, IMF), kvalificerade branschpublikationer
   - Inte bara nyhetsartiklar
   - Minst en källa bör komma från bevakningsbilden om relevant

6. Artikelreferens:
   - Om en artikel i bevakningen är väldigt direkt relaterad till tesen: skriv inlägget som svar/kommentar på den artikeln, ange dess URL i refererar_till_artikel
   - Annars fristående resonemang, refererar_till_artikel = None

7. När förslaget är klart: spara via proaktiv.spara_forslag(tes=..., rubrik=..., text=..., kallor=[...], refererar_till_artikel=...). Anropa funktionen direkt i denna Claude Code-session – inte via separat python3 -c-kommando.
"""
    return prompt, None

# ── Publikt API ───────────────────────────────────────────────────────────────

def generera_proaktivt_forslag():
    """Bygger och printar prompten. Returnerar prompt-strängen (eller error-dict)."""
    prompt, err = bygg_prompt()
    if err:
        print(json.dumps(err, ensure_ascii=False, indent=2))
        return err
    print(prompt)
    return prompt

def spara_forslag(tes, rubrik, text, kallor=None, refererar_till_artikel=None):
    """Sparar ett färdigt förslag i proaktiv_cache.json (rullande, max 30).

    Returnerar den sparade dicten. Om text är utanför 500–3000 tecken läggs
    fältet 'varning' till i den returnerade dicten – förslaget sparas ändå.
    """
    if tes not in (1, 2, 3):
        return {"error": "tes måste vara 1, 2 eller 3", "fick": tes}
    if not isinstance(rubrik, str) or not rubrik.strip():
        return {"error": "rubrik måste vara en icke-tom sträng"}
    if not isinstance(text, str) or not text.strip():
        return {"error": "text måste vara en icke-tom sträng"}

    rena_kallor = []
    if kallor:
        rena_kallor = [k for k in kallor if isinstance(k, str) and k.strip()]

    text_ren = text.strip()
    forslag = {
        "id":     str(uuid.uuid4()),
        "datum":  datetime.now().isoformat(timespec="seconds"),
        "tes":    int(tes),
        "rubrik": rubrik.strip(),
        "text":   text_ren,
        "kallor": rena_kallor,
        "refererar_till_artikel": refererar_till_artikel if isinstance(refererar_till_artikel, str) else None,
    }

    n = len(text_ren)
    if n < TEXT_MIN or n > TEXT_MAX:
        forslag["varning"] = f"text utanför {TEXT_MIN}-{TEXT_MAX} tecken (faktisk: {n})"

    cache = _las_cache()
    cache.append(forslag)
    cache = cache[-MAX_FORSLAG:]
    _spara_cache(cache)
    return forslag

def las_senaste_forslag(antal=10):
    cache = _las_cache()
    return list(reversed(cache[-antal:]))

# ── CLI ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    generera_proaktivt_forslag()
