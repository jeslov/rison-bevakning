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

# ── HTML-injektion ────────────────────────────────────────────────────────────

_INSTALL_MARKER  = "<!-- PROAKTIV_TABS_INSTALLED -->"
_BEGIN_PROAKTIV  = "<!-- BEGIN tab-proaktiv -->"
_END_PROAKTIV    = "<!-- END tab-proaktiv -->"

def _bygg_proaktiv_card(forslag):
    """Bygger HTML för ett proaktiv-card."""
    rubrik = _html.escape(forslag.get("rubrik", "") or "", quote=True)
    raw_datum = forslag.get("datum", "") or ""
    datum_kort = raw_datum[:16].replace("T", " ") if raw_datum else ""
    datum = _html.escape(datum_kort, quote=True)
    tes = forslag.get("tes", "?")
    raw_text = forslag.get("text", "") or ""
    text_html = _html.escape(raw_text, quote=True)
    text_attr = text_html.replace("\n", "&#10;")
    kallor = forslag.get("kallor", []) or []
    referens = forslag.get("refererar_till_artikel")

    kallor_html = ""
    if kallor:
        kallor_html = (
            '<div style="font-size:11px;color:#888;font-weight:600;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;">Källor</div>\n'
            '  <ul style="font-size:13px;color:#3a3a3a;margin-bottom:14px;padding-left:18px;line-height:1.6;">\n'
        )
        for k in kallor:
            url = _html.escape(k or "", quote=True)
            kallor_html += f'    <li><a href="{url}" target="_blank" style="color:#293244;">{url}</a></li>\n'
        kallor_html += '  </ul>'

    referens_html = ""
    if referens and isinstance(referens, str):
        url = _html.escape(referens, quote=True)
        referens_html = (
            '\n  <div style="font-size:11px;color:#888;font-weight:600;text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;">Refererar till artikel</div>'
            f'\n  <a href="{url}" target="_blank" style="font-size:13px;color:#293244;font-weight:600;text-decoration:none;display:block;margin-bottom:14px;">{url}</a>'
        )

    return (
        f'<div class="tab-proaktiv-card">\n'
        f'  <div style="display:flex;gap:8px;margin-bottom:10px;flex-wrap:wrap;align-items:center;">\n'
        f'    <span style="font-size:10px;color:#fff;background:#293244;padding:2px 8px;border-radius:20px;font-weight:600;">Tes {tes}</span>\n'
        f'    <span style="font-size:13px;color:#666;">{datum}</span>\n'
        f'  </div>\n'
        f'  <h2 style="font-family:\'Cormorant Garamond\',Georgia,serif;font-size:22px;font-weight:500;margin-bottom:14px;line-height:1.3;color:#1a1a1a;">{rubrik}</h2>\n'
        f'  <div style="font-size:14px;color:#3a3a3a;line-height:1.7;font-weight:300;white-space:pre-wrap;margin-bottom:14px;">{text_html}</div>\n'
        f'  {kallor_html}{referens_html}\n'
        f'  <button onclick="kopiera_proaktiv(this)" data-text="{text_attr}" style="font-size:12px;background:#293244;color:#EFEDE0;border:none;padding:6px 14px;border-radius:2px;cursor:pointer;font-weight:500;letter-spacing:0.5px;margin-top:6px;">Kopiera</button>\n'
        f'</div>'
    )

def _bygg_proaktiv_block(forslag_lista):
    """Bygger hela <div id='tab-proaktiv'>-blocket inkl. start/slut-markörer."""
    if forslag_lista:
        cards_html = "\n".join(_bygg_proaktiv_card(f) for f in forslag_lista)
        inner = (
            '<h2 style="font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:2.5px;'
            'color:#EFEDE0;margin:28px 0 12px;padding-bottom:10px;border-bottom:2px solid rgba(255,255,255,0.25);'
            'background:#293244;padding:10px 16px;border-radius:2px;">Proaktiva förslag</h2>\n'
            f'    {cards_html}'
        )
    else:
        inner = (
            '<div style="background:#fff;border:1px solid #e8e8e8;border-radius:10px;'
            'padding:32px;margin-top:28px;text-align:center;color:#888;font-size:14px;line-height:1.6;">'
            'Inga proaktiva förslag genererade ännu.<br>'
            'Kör wizard_proaktiv.md i Claude Code för att generera ett förslag.'
            '</div>'
        )
    return (
        f'{_BEGIN_PROAKTIV}\n'
        f'<div id="tab-proaktiv" style="display:none">\n'
        f'  <div class="content">\n'
        f'    {inner}\n'
        f'  </div>\n'
        f'</div>\n'
        f'{_END_PROAKTIV}'
    )

def _forsta_installation(html_content, proaktiv_block):
    """Första gångens injektion: CSS, JS, tab-meny, wrap, proaktiv-block."""
    css = (
        ".tabs{display:flex;background:#181D27;border-bottom:1px solid rgba(255,255,255,0.2)}\n"
        ".tab{padding:14px 28px;font-size:12px;color:#8892a4;cursor:pointer;letter-spacing:1.5px;text-transform:uppercase;border:none;background:transparent;font-family:Georgia,serif;font-weight:600}\n"
        ".tab:hover{color:#EFEDE0}\n"
        ".tab.active{color:#EFEDE0;border-bottom:2px solid #EFEDE0;margin-bottom:-1px}\n"
        ".tab-proaktiv-card{background:#fff;border:1px solid #e8e8e8;border-radius:10px;padding:22px;margin-bottom:16px;box-shadow:0 1px 4px rgba(0,0,0,0.04)}\n"
    )
    if "</style>" not in html_content:
        return None
    html_content = html_content.replace("</style>", css + "</style>", 1)

    js_block = (
        "<script>\n"
        "function visa_tab(name) {\n"
        "  document.getElementById('tab-bevakning').style.display = (name === 'bevakning') ? '' : 'none';\n"
        "  document.getElementById('tab-proaktiv').style.display = (name === 'proaktiv') ? '' : 'none';\n"
        "  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));\n"
        "  document.getElementById('tab-btn-' + name).classList.add('active');\n"
        "}\n"
        "function kopiera_proaktiv(btn) {\n"
        "  const text = btn.getAttribute('data-text');\n"
        "  navigator.clipboard.writeText(text).then(() => {\n"
        "    const orig = btn.textContent;\n"
        "    btn.textContent = 'Kopierat!';\n"
        "    setTimeout(() => { btn.textContent = orig; }, 1500);\n"
        "  });\n"
        "}\n"
        "</script>\n"
    )
    if "</body>" not in html_content:
        return None
    html_content = html_content.replace("</body>", js_block + "</body>", 1)

    tabs_open = (
        f"\n  {_INSTALL_MARKER}\n"
        '  <div class="tabs">\n'
        '    <button class="tab active" id="tab-btn-bevakning" onclick="visa_tab(\'bevakning\')">Bevakning</button>\n'
        '    <button class="tab" id="tab-btn-proaktiv" onclick="visa_tab(\'proaktiv\')">Proaktiva förslag</button>\n'
        '  </div>\n'
        '  <div id="tab-bevakning">\n'
    )
    header_anchor = '</p>\n  </div>\n  <div class="stats">'
    if header_anchor not in html_content:
        return None
    html_content = html_content.replace(
        header_anchor,
        '</p>\n  </div>' + tabs_open + '  <div class="stats">',
        1,
    )

    rapport_anchor = "</div>\n\n<script>"
    if rapport_anchor not in html_content:
        return None
    html_content = html_content.replace(
        rapport_anchor,
        "  </div>\n  " + proaktiv_block + "\n</div>\n\n<script>",
        1,
    )

    return html_content

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
   - Beskriv ALDRIG mekaniken i Risons modell eller EaaS. Det vill säga: undvik formuleringar som "tredje part står för investeringen", "fastighetsägaren betalar utifrån faktisk besparing", "kassaflödet är positivt från första månaden", eller liknande beskrivningar av HUR finansieringsstrukturen fungerar. Inläggets uppgift är att kommentera SITUATIONEN. Om finansieringsstrukturer ska nämnas: hänvisa till externa institutioner som benämner dem (EU Article 17-paketet, IEA, etc.), inte till Risons egen produkt.
   - Avsluta med påstående, inte engagemangsfråga
   - Stilreferens: linkedin_stil.txt om relevant
   - Skriv för en intelligent läsare som inte är finansspecialist. Undvik finansjargong som "hurdle rate", "payback-period", "investeringskalkyl", "ROI", "capex", "diskonteringsränta", "internränta" om det inte är absolut nödvändigt. Om en branschterm ändå måste användas: förklara den i samma mening eller ersätt med vardagligt språk. Exempel: "kraven på avkastning sattes för att jämföra med tillväxtinvesteringar" istället för "hurdle rates är designade för expansion"; "kostnaden blir lägre från månad ett" istället för "kassaflödet är positivt från dag ett"; "två fastighetsägare kan ha helt olika månadskostnader för samma renovering" istället för "samma asset, olika balansräkningseffekt". Skriv som du skulle tala med en intresserad läsare som inte är ekonom – inte som du skulle tala med en CFO.
   - Använd minst en konkret liknelse eller skarp omramning som vänder läsarens förväntan. Hitta din egen liknelse – exemplen nedan är illustrationer, inte mallar att kopiera. Exempel: "Det är som att ge en hungrig människa ett recept", "X-problemet löstes 2023 – men ingen märkte det", "Lösningen finns sedan länge – det är efterfrågan som saknas". Liknelsen är obligatorisk.
   - Undvik AI-rapportstil: meningar som börjar "Forskare visar...", "IEA rapporterar...", "Energimyndigheten konstaterar..." får inte upprepas mer än tre gånger totalt i texten. Variera språket: "siffrorna säger", "i den senaste rapporten framgår", "verkligheten ser annorlunda ut", etc.

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
