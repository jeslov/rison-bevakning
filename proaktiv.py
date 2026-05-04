#!/usr/bin/env python3
"""
Rison Capital – Proaktiv modul
Genererar förslag på nya inlägg utifrån de tre bärande teserna och aktuell
bevakningsbild. Anropar Cloudflare Worker (action='proaktiv').
Datalagring: proaktiv_cache.json (rullande, max 30).
"""

import json
import re
import time
import uuid
import html as _html
import requests
from datetime import datetime
from pathlib import Path

WORKER_URL          = "https://risonbevakning.jesper-75b.workers.dev"
TESER_FILE          = Path(__file__).parent / "teser_med_underlag.md"
INDEX_HTML          = Path(__file__).parent / "index.html"
PROAKTIV_CACHE_FILE = Path(__file__).parent / "proaktiv_cache.json"
MAX_FORSLAG         = 30

# ── Hjälpare ──────────────────────────────────────────────────────────────────

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

    # Splitta på artikel-card divs (samma stil för Hög- och Medel-block)
    delare = '<div style="background:#fff;border:1px solid #e8e8e8;border-radius:10px;padding:22px;'
    blocks = raw.split(delare)
    if len(blocks) < 2:
        return []

    artiklar = []
    for blk in blocks[1:]:
        # Relevansnivå (text "Hog" eller "Medel" – HTML har detta utan å)
        mr = re.search(r'<span[^>]*>(Hog|Medel)</span>', blk)
        if not mr:
            continue
        relevansniva = "Hög" if mr.group(1) == "Hog" else "Medel"

        # Poäng
        mp = re.search(r'<span[^>]*>(\d+)/10</span>', blk)
        poang = int(mp.group(1)) if mp else 0

        # Rubrik + URL från första kopiera_prompt-anropet
        mk = re.search(r"kopiera_prompt\(this,\s*'([^']*)',\s*'([^']*)'", blk)
        if not mk:
            continue
        rubrik = _html.unescape(mk.group(1)).strip()
        url    = mk.group(2).strip()
        if not (rubrik and url):
            continue

        # Relativt datum: leta i alla <span style="font-size:13px;color:#666;">...</span>
        # Filtrera bort eventuella träffar som bara innehåller relevansnivå-text
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

        # Sammanfattning: första <ul>...</ul> i blocket, li-texter ihopslagna
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

    # Sortera: Hög före Medel, sedan högst poäng först
    artiklar.sort(key=lambda x: (0 if x["relevansniva"] == "Hög" else 1, -x["poang"]))
    return artiklar[:25]

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

# ── Worker-anrop ──────────────────────────────────────────────────────────────

def _worker_anrop(payload, max_forsok=3):
    for forsok in range(max_forsok):
        try:
            r = requests.post(
                WORKER_URL,
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=60,
            )
            if r.status_code == 429:
                time.sleep(20 + forsok * 20)
                continue
            if r.status_code != 200:
                return {"error": f"HTTP {r.status_code}", "body": r.text[:500]}
            try:
                return r.json()
            except Exception:
                return {"error": "Ogiltig JSON", "body": r.text[:500]}
        except Exception as e:
            if forsok < max_forsok - 1:
                time.sleep(5)
            else:
                return {"error": f"Exception: {e}"}
    return {"error": "Inga försök lyckades"}

# ── Publikt API ───────────────────────────────────────────────────────────────

def generera_proaktivt_forslag():
    teser = _las_teser()
    bevakning = _las_bevakningsbild()

    if not teser:
        return {"error": "teser_med_underlag.md saknas eller är tom"}

    payload = {
        "action": "proaktiv",
        "teser": teser,
        "bevakning": bevakning,
    }

    svar = _worker_anrop(payload)
    if not isinstance(svar, dict) or svar.get("error"):
        return svar if isinstance(svar, dict) else {"error": "Okänt svar"}

    # Förväntade fält från Worker
    tes      = svar.get("tes")
    rubrik   = (svar.get("rubrik") or "").strip()
    text     = (svar.get("text") or "").strip()
    kallor   = svar.get("kallor") or []
    referens = svar.get("refererar_till_artikel")

    if not (tes and rubrik and text):
        return {"error": "Ofullständigt Worker-svar", "raw": svar}

    forslag = {
        "id":     str(uuid.uuid4()),
        "datum":  datetime.now().isoformat(timespec="seconds"),
        "tes":    int(tes) if str(tes).isdigit() else tes,
        "rubrik": rubrik,
        "text":   text,
        "kallor": [k for k in kallor if isinstance(k, str)],
        "refererar_till_artikel": referens if isinstance(referens, str) else None,
    }

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
    res = generera_proaktivt_forslag()
    print(json.dumps(res, ensure_ascii=False, indent=2))
