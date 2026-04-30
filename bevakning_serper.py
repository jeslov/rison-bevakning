#!/usr/bin/env python3
"""
Rison Capital - Daglig omvarldsbevakning via Serper (Google Search)
v3: Reducerad fulltext i batch (400 tecken), Claude-steget i dubblettfiltrering
    borttaget, zeitgeist-analys (veckovis cachad)
"""

import os, json, hashlib, time, re, requests
from datetime import datetime, timedelta
from pathlib import Path

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
SERPER_API_KEY    = os.environ["SERPER_API_KEY"]
OUTPUT_FILE       = Path(__file__).parent / "index.html"
SEEN_FILE         = Path(__file__).parent / "sedda_artiklar.json"
ZEITGEIST_FILE    = Path(__file__).parent / "zeitgeist_cache.json"
MIN_RELEVANS      = "Medel"
BATCH_STORLEK     = 10

# Målmedier för zeitgeist-analys
MALMEDIER = [
    "fastighetstidningen.se", "fastighetsnytt.se", "fastighetssverige.se",
    "fastighetsvarlden.se", "byggvarlden.se", "byggindustrin.se",
    "fastighetsagarna.se", "energi-miljo.se", "energi.se",
    "energinyheter.se", "energimyndigheten.se", "aktuellhallbarhet.se",
    "bostadsratterna.se", "hsb.se", "riksbyggen.se", "sbc.se",
    "dagenssamhalle.se", "nyteknik.se",
]

FASTA_SOKORD = [
    "bergvärme fastighet",
    "värmepump fastighet",
    "batterilager fastighet",
    "solceller fastighet",
    "energilagring fastighet",
    "geotermisk fastighet",
    "energieffektivisering fastighet",
    "energirenovering fastighet",
    "energideklaration fastighet",
    "energikostnad fastighet",
    "energiprestanda byggnad",
    "energieffektivisering BRF",
    "bergvärme BRF",
    "energikostnad BRF",
    "fjärrvärme BRF",
    "gröna obligationer fastighet",
    "hållbarhetsobligation fastighet",
    "fastighetsinvestering energi",
    "EPBD fastighet",
    "energikrav byggnad",
    "Boverket energi",
    "klimatkrav fastighet",
    "Riksbyggen energi",
    "Fastighetsägarna energi",
    "fastighetsbolag energiomställning",
    "stranded assets fastighet",
]

RISON_KONTEXT = """
Rison Capital ar ett Goteborgsbaserat investmentbolag som finansierar energieffektivisering
och smaskalig energiproduktion i fastigheter utan fordringar pa fastighetsagaren (EaaS-modell).
Institutionellt kapital via SEB Nordic Energy Fund. Bergvarme, BESS/batterilager, varmepumpar,
isolering, solceller. Malgrupper: kommersiella fastigheter, BRF, kommuner, industrifastigheter.

Karnbudskap: Bromsklossen for energieffektivisering ar inte tekniken eller lonsamheten - det ar
finansieringen. Rison kopplar ihop fastighetsagare med energiprojekt de inte kan finansiera,
med institutionella investerare med gront kapital som soker stabila projekt.
""".strip()

LINKEDIN_KONTEXT = """
Risons LinkedIn har en insiktsfull, direkt och latt provocerande rost. Lyfter strukturella
problem och visar hur Risons modell loser dem. Mal: CFO/VD pa fastighetsbolag, BRF-styrelser,
kommunala fastighetschefer, institutionella investerare.

Effektiva inlagg: borjar med ovantad fraga eller pakstande, kopplar omvarlden till Risons
strukturella losning, avslutar med dialog-fraga. Ton: professionell men aldrig torr.
""".strip()

# ── Grundfunktioner ───────────────────────────────────────────────────────────

def ladda_sedda():
    if SEEN_FILE.exists():
        return set(json.loads(SEEN_FILE.read_text()))
    return set()

def spara_sedda(s):
    SEEN_FILE.write_text(json.dumps(list(s)))

def artikel_id(url):
    return hashlib.md5(url.encode()).hexdigest()

def claude_anrop(prompt, max_tokens=1000):
    for forsok in range(4):
        try:
            r = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": ANTHROPIC_API_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-sonnet-4-6",
                    "max_tokens": max_tokens,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=60,
            )
            if r.status_code == 429:
                vantetid = 20 + forsok * 20
                print(f"    [429 rate limit, vantar {vantetid}s...]")
                time.sleep(vantetid)
                continue
            if r.status_code != 200:
                return None
            text = r.json()["content"][0]["text"].strip()
            text = re.sub(r'^```(?:json)?\s*', '', text)
            text = re.sub(r'\s*```$', '', text)
            return text.strip()
        except Exception:
            if forsok < 3:
                time.sleep(5)
    return None

def sok_serper(sokord, antal=10, tidsfilter="qdr:w"):
    try:
        r = requests.post(
            "https://google.serper.dev/news",
            headers={
                "X-API-KEY": SERPER_API_KEY,
                "Content-Type": "application/json",
            },
            json={
                "q": sokord,
                "gl": "se",
                "hl": "sv",
                "num": antal,
                "tbs": tidsfilter,
            },
            timeout=10,
        )
        if r.status_code != 200:
            return []
        nyheter = r.json().get("news", [])
        return [
            {
                "titel":       n.get("title", "").strip(),
                "url":         n.get("link", "").strip(),
                "beskrivning": n.get("snippet", "").strip()[:300],
                "kalla":       n.get("source", "").strip(),
                "datum":       n.get("date", ""),
                "sokord":      sokord,
            }
            for n in nyheter
            if n.get("title") and n.get("link")
               and "ANNONS" not in n.get("title", "").upper()
        ]
    except Exception:
        return []

def hamta_text(url):
    try:
        r = requests.get(url, timeout=5,
                         headers={"User-Agent": "Mozilla/5.0"},
                         stream=True)
        if r.status_code not in (200, 203):
            return ""
        chunks = []
        size = 0
        for chunk in r.iter_content(8192):
            chunks.append(chunk)
            size += len(chunk)
            if size > 60000:
                break
        raw = b"".join(chunks).decode("utf-8", errors="ignore")
        raw = re.sub(r'<script[^>]*>.*?</script>', '', raw, flags=re.DOTALL)
        raw = re.sub(r'<style[^>]*>.*?</style>', '', raw, flags=re.DOTALL)
        raw = re.sub(r'<[^>]+>', ' ', raw)
        return re.sub(r'\s+', ' ', raw).strip()[:5000]
    except Exception:
        return ""

# ── Zeitgeist-analys ──────────────────────────────────────────────────────────

def zeitgeist_behovs_uppdatering():
    """Kontrollerar om zeitgeist-cachen ar aldre an 7 dagar."""
    if not ZEITGEIST_FILE.exists():
        return True
    try:
        cache = json.loads(ZEITGEIST_FILE.read_text())
        sparad = datetime.fromisoformat(cache.get("datum", "2000-01-01"))
        return (datetime.now() - sparad).days >= 7
    except Exception:
        return True

def uppdatera_zeitgeist():
    """
    Hamtar artiklar fran malmedier senaste 30 dagarna och
    ber Claude identifiera dominerande teman och begrepp.
    Sparar resultatet i zeitgeist_cache.json.
    """
    print("  Uppdaterar zeitgeist-analys (kors var 7e dag)...")

    # Hamta titlar och snippets fran malmedier
    titlar = []
    for medium in MALMEDIER:
        sokord = f"site:{medium} energi fastighet"
        traff = sok_serper(sokord, antal=10, tidsfilter="qdr:m")
        for a in traff:
            titlar.append(f"{a['titel']} – {a['beskrivning'][:100]}")
        time.sleep(0.2)

    if not titlar:
        print("  Inga artiklar hittades for zeitgeist-analys")
        return []

    print(f"  {len(titlar)} artiklar fran malmedier analyseras...")

    prompt = f"""Du ar omvarldsanalytiker for Rison Capital.

{RISON_KONTEXT}

Nedan ar titlar och snippets fran svenska malmedier inom energi och fastighet
fran de senaste 30 dagarna. Analysera vilka teman, begrepp, aktorer och
diskussioner som dominerar just nu – zeitgeist inom Risons fokusomraden.

ARTIKLAR:
{chr(10).join(f"- {t}" for t in titlar[:150])}

Baserat pa denna analys, generera 8 svenska Google-sokord (2-3 ord per sokning)
som fanger de mest aktuella och relevanta amnesomradena for Rison just nu.
Sokorden ska komplettera de fasta sokorden och fanga det som ar i rorelsen.

Svara med JSON:
{{
  "teman": ["tema 1", "tema 2", "tema 3", "tema 4", "tema 5"],
  "sokord": ["sokord 1", "sokord 2", "sokord 3", "sokord 4", "sokord 5", "sokord 6", "sokord 7", "sokord 8"]
}}"""

    svar = claude_anrop(prompt, max_tokens=500)
    if not svar:
        return []

    try:
        data = json.loads(svar)
        teman  = data.get("teman", [])
        sokord = data.get("sokord", [])

        # Spara cache
        ZEITGEIST_FILE.write_text(json.dumps({
            "datum":  datetime.now().isoformat(),
            "teman":  teman,
            "sokord": sokord,
        }, ensure_ascii=False, indent=2))

        print(f"  Zeitgeist-teman: {', '.join(teman)}")
        return sokord
    except Exception:
        return []

def hamta_zeitgeist_sokord():
    """Returnerar cachade zeitgeist-sokord, uppdaterar om nodvandigt."""
    if zeitgeist_behovs_uppdatering():
        return uppdatera_zeitgeist()
    try:
        cache = json.loads(ZEITGEIST_FILE.read_text())
        sokord = cache.get("sokord", [])
        sparad = cache.get("datum", "")[:10]
        print(f"  Anvander cachad zeitgeist fran {sparad} ({len(sokord)} sokord)")
        return sokord
    except Exception:
        return uppdatera_zeitgeist()

# ── Dagsaktuella dynamiska sokord ─────────────────────────────────────────────

def generera_dagsaktuella_sokord(zeitgeist_sokord):
    """Genererar 3 dagsaktuella sokord baserat pa datum och zeitgeist."""
    datum = datetime.now().strftime("%d %B %Y")
    manad = datetime.now().month
    if manad in (3, 4, 5):
        sasong = "Var: BRF-stammer vanliga, energideklarationer i fokus"
    elif manad in (6, 7, 8):
        sasong = "Sommar: Planering av hostinstallationer, solcellsprojekt aktiva"
    elif manad in (9, 10, 11):
        sasong = "Host: Uppvarmningssasong, varmepumpar och fjarvarmebyte aktuella"
    else:
        sasong = "Vinter: Energikostnader i fokus, arsbokslut fastighetsbolag"

    prompt = f"""Du ar omvarldsanalytiker for Rison Capital. Idag ar det {datum}.
Sasong: {sasong}

Zeitgeist-sokord som redan anvands denna vecka: {', '.join(zeitgeist_sokord)}

Generera 3 dagsaktuella svenska Google-sokord (2-3 ord) som fanger
vad som hander just idag. Ska skilja sig fran zeitgeist-sokorden ovan.

Svara ENDAST med JSON-lista: ["sokord 1", "sokord 2", "sokord 3"]"""

    svar = claude_anrop(prompt, max_tokens=100)
    if not svar:
        return []
    try:
        sokord = json.loads(svar)
        return sokord if isinstance(sokord, list) else []
    except Exception:
        return []

# ── Dubblettgruppering (bara textlikhet) ──────────────────────────────────────

def titel_likhet(a, b):
    stoppord = {"och","i","på","av","för","med","som","en","ett","är","det","de",
                "den","att","till","om","men","har","kan","vi","du","han","hon",
                "inte","från","sin","sig","var","vid","mot","så","nu","när","hur"}
    def ord(t):
        return set(re.sub(r'[^\w\s]', '', t.lower()).split()) - stoppord
    a_ord, b_ord = ord(a), ord(b)
    if not a_ord or not b_ord:
        return 0.0
    return len(a_ord & b_ord) / max(len(a_ord), len(b_ord))

def gruppera_dubletter(artiklar):
    """Grupperar dubletter med textlikhet – inget Claude-anrop."""
    grupper = []
    anvanda = set()
    for i, a in enumerate(artiklar):
        if i in anvanda:
            continue
        grupp = [a]
        anvanda.add(i)
        for j, b in enumerate(artiklar):
            if j in anvanda:
                continue
            if titel_likhet(a["titel"], b["titel"]) >= 0.5:
                grupp.append(b)
                anvanda.add(j)
        grupper.append(grupp)
    return grupper

def basta_i_grupp(grupp):
    return max(grupp, key=lambda a: len(a.get("beskrivning", "")))

# ── Batch-bedomning ───────────────────────────────────────────────────────────

def bedom_batch(artiklar):
    """Bedömer upp till 10 artiklar med kort skarp prompt."""
    lista = "\n".join(
        f"{i+1}. Titel: {a['titel']}\n   Kalla: {a['kalla']}\n   Snippet: {a.get('beskrivning','')[:300]}"
        for i, a in enumerate(artiklar)
    )

    prompt = f"""Du ar omvarldsanalytiker for Rison Capital som finansierar energieffektivisering i fastigheter via EaaS-modell. Institutionellt kapital via SEB Nordic Energy Fund. Bergvarme, BESS/batterilager, varmepumpar, solceller, isolering. Malgrupper: BRF, kommersiella fastigheter, kommuner, industri.

HOG relevans: bergvarme/varmepump/BESS/solceller i fastigheter, energieffektivisering BRF/kommersiella fastigheter, EPBD/energikrav byggnader, institutionellt kapital gron fastighet, EaaS-finansiering, fjarvarmebyte, energikostnad fastighet, grona obligationer fastighet.

MEDEL relevans: hallbar fastighetsutveckling, energipolicy Sverige, fastighetsbolag energiarbete, energipriser fastighet.

EXKLUDERA: privatbostader/villa/konsument, datakenter, karnkraft, elbilar, sport, underhallning, fastighetsaffarer utan energikoppling.

Bedöm foljande {len(artiklar)} artiklar:

{lista}

Svara med JSON-lista (ingen annan text):
[{{"index": 1, "relevant": true/false, "relevansniva": "Hog"/"Medel"/"Lag", "poang": 1-10, "sammanfattning": "En mening", "motivering": "En mening"}}]"""

    svar = claude_anrop(prompt, max_tokens=3000)
    if not svar:
        return []
    try:
        resultat = json.loads(svar)
        if not isinstance(resultat, list):
            return []
        relevanta = []
        for b in resultat:
            idx = b.get("index", 0) - 1
            if not (0 <= idx < len(artiklar)):
                continue
            if not b.get("relevant"):
                continue
            if b.get("relevansniva") == "Lag":
                continue
            if b.get("relevansniva") == "Medel" and MIN_RELEVANS == "Hog":
                continue
            artikel = {**artiklar[idx], **b}
            relevanta.append(artikel)
        return relevanta
    except Exception:
        return []

def linkedin_forslag(artikel):
    fulltext = artikel.get("fulltext", artikel.get("beskrivning", ""))
    prompt = f"""Du ar kommunikationsansvarig pa Rison Capital och skriver LinkedIn-inlagg
for Jesper Lovkvist, delagare och kommunikationsansvarig.

{RISON_KONTEXT}

{LINKEDIN_KONTEXT}

ARTIKEL:
Titel: {artikel['titel']}
Kalla: {artikel['kalla']}
Text: {fulltext[:4000]}

Svara ENDAST med JSON (ingen annan text, inga kodblock):
{{
  "nyckelpoanger": ["punkt 1", "punkt 2", "punkt 3"],
  "hook": "En oppningsmening som fangar uppmarksamhet",
  "vinkel": "Vilken aspekt som ar mest intressant for Risors malgrupp",
  "koppling_till_rison": "Hur artikeln direkt relaterar till Risons erbjudande",
  "innehallspunkter": ["poang 1", "poang 2", "poang 3"],
  "avslutning": "Avslutande fraga eller uppmaning"
}}"""

    svar = claude_anrop(prompt, max_tokens=800)
    if not svar:
        return None
    try:
        return json.loads(svar)
    except Exception:
        return None

def sorteringsnyckel(r):
    niva = {"Hog": 0, "Medel": 1, "Lag": 2}
    return (niva.get(r.get("relevansniva", "Lag"), 2), -r.get("poang", 0))

def escape_html(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")

# ── HTML ──────────────────────────────────────────────────────────────────────

def bygg_html(grupper_relevanta, stat, dynamiska_sokord, zeitgeist_sokord):
    datum = datetime.now().strftime("%d %B %Y, %H:%M")
    hoga  = [g for g in grupper_relevanta if g[0].get("relevansniva") == "Hog"]
    medel = [g for g in grupper_relevanta if g[0].get("relevansniva") == "Medel"]

    def li_panel(li):
        if not li:
            return "<p style='color:#888;font-style:italic;padding:16px;'>Forslag kunde inte genereras.</p>"
        nyckel  = "".join(f"<li style='margin-bottom:6px;'>{escape_html(p)}</li>" for p in li.get("nyckelpoanger", []))
        punkter = "".join(f"<li style='margin-bottom:6px;'>{escape_html(p)}</li>" for p in li.get("innehallspunkter", []))
        return f"""<div style="background:#f7f9fc;border-radius:8px;padding:20px;border:1px solid #dde8f5;">
  <div style="font-size:10px;color:#444;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin-bottom:10px;">Artikelns nyckelpoanger</div>
  <ul style="font-size:13px;color:#333;line-height:1.7;margin:0 0 16px;padding-left:20px;">{nyckel}</ul>
  <div style="border-top:1px solid #dde8f5;margin:14px 0;"></div>
  <div style="font-size:10px;color:#0077b5;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin-bottom:14px;">LinkedIn-forslag</div>
  <div style="margin-bottom:10px;"><div style="font-size:10px;color:#888;font-weight:700;text-transform:uppercase;margin-bottom:4px;">Hook</div>
  <div style="font-size:14px;font-style:italic;color:#1a1a1a;">"{escape_html(li.get('hook',''))}"</div></div>
  <div style="margin-bottom:10px;"><div style="font-size:10px;color:#888;font-weight:700;text-transform:uppercase;margin-bottom:4px;">Vinkel</div>
  <div style="font-size:13px;color:#333;">{escape_html(li.get('vinkel',''))}</div></div>
  <div style="margin-bottom:10px;"><div style="font-size:10px;color:#888;font-weight:700;text-transform:uppercase;margin-bottom:4px;">Koppling till Rison</div>
  <div style="font-size:13px;color:#333;">{escape_html(li.get('koppling_till_rison',''))}</div></div>
  <div style="margin-bottom:10px;"><div style="font-size:10px;color:#888;font-weight:700;text-transform:uppercase;margin-bottom:4px;">Innehallspunkter</div>
  <ul style="font-size:13px;color:#333;line-height:1.7;margin:0;padding-left:20px;">{punkter}</ul></div>
  <div><div style="font-size:10px;color:#888;font-weight:700;text-transform:uppercase;margin-bottom:4px;">Avslutning</div>
  <div style="font-size:13px;color:#333;">{escape_html(li.get('avslutning',''))}</div></div>
</div>"""

    def dubbletter_panel(grupp, idx):
        if len(grupp) <= 1:
            return ""
        ovriga = grupp[1:]
        items = ""
        for a in ovriga:
            datum_tag = f'&nbsp;·&nbsp;<span style="font-size:10px;color:#bbb;">{escape_html(a.get("datum",""))}</span>' if a.get("datum") else ""
            items += (
                f'<div style="padding:7px 0;border-bottom:1px solid #f0f0f0;">'
                f'<span style="font-size:11px;color:#aaa;">{escape_html(a["kalla"])}</span>'
                f'{datum_tag}'
                f' &nbsp;<a href="{escape_html(a["url"])}" target="_blank" style="font-size:13px;color:#666;">{escape_html(a["titel"])}</a>'
                f'</div>'
            )
        return f"""<div style="margin-top:8px;">
  <button onclick="var e=document.getElementById('dup-{idx}');e.style.display=e.style.display==='none'?'block':'none'"
    style="font-size:11px;background:none;border:1px solid #ddd;padding:3px 10px;border-radius:20px;cursor:pointer;color:#999;">
    +{len(ovriga)} liknande artikel{'er' if len(ovriga)>1 else ''}
  </button>
  <div id="dup-{idx}" style="display:none;margin-top:8px;background:#fafafa;border-radius:6px;padding:8px 12px;">
    {items}
  </div>
</div>"""

    def artikel_html(grupp, idx):
        r     = grupp[0]
        niva  = r.get("relevansniva", "Medel")
        poang = r.get("poang", 0)
        faerg = "#1a7a3f" if niva == "Hog" else "#1a4a7a"
        datum_str  = f'<span style="font-size:11px;color:#aaa;">{escape_html(r.get("datum",""))}</span>' if r.get("datum") else ""
        sokord_str = f'<span style="font-size:10px;color:#ccc;">via: {escape_html(r.get("sokord",""))}</span>' if r.get("sokord") else ""
        return f"""<div style="background:#fff;border:1px solid #e8e8e8;border-radius:10px;padding:22px;margin-bottom:16px;box-shadow:0 1px 4px rgba(0,0,0,0.04);">
  <div style="display:flex;gap:8px;margin-bottom:10px;flex-wrap:wrap;align-items:center;">
    <span style="font-size:11px;color:#666;font-weight:600;">{escape_html(r['kalla'])}</span>
    <span style="font-size:10px;color:#fff;background:{faerg};padding:2px 8px;border-radius:20px;font-weight:600;">{niva}</span>
    <span style="font-size:10px;color:#fff;background:#555;padding:2px 8px;border-radius:20px;">{poang}/10</span>
    {datum_str}
    {sokord_str}
  </div>
  <div style="font-size:17px;font-weight:700;margin-bottom:8px;line-height:1.3;">
    <a href="{escape_html(r['url'])}" target="_blank" style="color:#1a1a1a;text-decoration:none;">{escape_html(r['titel'])}</a>
  </div>
  <div style="font-size:15px;color:#444;line-height:1.7;margin-bottom:8px;">{escape_html(r.get('sammanfattning',''))}</div>
  <div style="font-size:13px;color:#888;font-style:italic;margin-bottom:12px;">{escape_html(r.get('motivering',''))}</div>
  <div style="display:flex;gap:12px;align-items:center;flex-wrap:wrap;">
    <a href="{escape_html(r['url'])}" target="_blank" style="font-size:12px;color:{faerg};font-weight:600;text-decoration:none;">Las artikel &rarr;</a>
    <button onclick="kopiera_prompt(this, '{escape_html(r.get('titel','').replace(chr(39), ''))}')"
      style="font-size:12px;background:#0077b5;color:#fff;border:none;padding:5px 14px;border-radius:20px;cursor:pointer;font-weight:600;">
      &#128188; Kopiera LinkedIn-prompt
    </button>
  </div>
  {dubbletter_panel(grupp, idx)}
</div>"""

    def sektion_html(rubrik, grupper, start_idx, faerg):
        if not grupper:
            return "", start_idx
        h = f'<h2 style="font-size:13px;font-weight:700;text-transform:uppercase;letter-spacing:1.5px;color:{faerg};margin:28px 0 12px;padding-bottom:8px;border-bottom:2px solid {faerg};">{rubrik} &mdash; {len(grupper)} artiklar</h2>'
        for i, g in enumerate(grupper):
            h += artikel_html(g, start_idx + i)
        return h, start_idx + len(grupper)

    hog_html, idx = sektion_html("Hog relevans", hoga, 0, "#1a7a3f")
    med_html, _   = sektion_html("Medel relevans", medel, idx, "#1a4a7a")
    innehall = hog_html + med_html or '<p style="color:#888;text-align:center;padding:60px 0;font-size:15px;">Inga relevanta artiklar hittades idag.</p>'

    alla_sokord = FASTA_SOKORD + zeitgeist_sokord + dynamiska_sokord
    sokord_html = "".join(
        f'<span style="display:inline-block;background:#f0f0f0;border-radius:20px;padding:3px 10px;font-size:12px;color:#555;margin:3px;">'
        f'{"🌐" if s in zeitgeist_sokord else "✨" if s in dynamiska_sokord else "🔍"} {escape_html(s)}</span>'
        for s in alla_sokord
    )

    # Zeitgeist-teman om de finns
    zeitgeist_teman = ""
    if ZEITGEIST_FILE.exists():
        try:
            cache = json.loads(ZEITGEIST_FILE.read_text())
            teman = cache.get("teman", [])
            sparad = cache.get("datum", "")[:10]
            if teman:
                teman_html = "".join(f'<span style="display:inline-block;background:#1a1a1a;color:#fff;border-radius:20px;padding:3px 10px;font-size:12px;margin:3px;">{escape_html(t)}</span>' for t in teman)
                zeitgeist_teman = f"""<div style="max-width:760px;margin:0 auto;padding:0 40px 16px;">
  <div style="font-size:11px;font-weight:700;color:#888;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px;">
    Veckans zeitgeist-teman (uppdaterad {sparad})
  </div>
  <div>{teman_html}</div>
</div>"""
        except Exception:
            pass

    return f"""<!DOCTYPE html>
<html lang="sv">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Rison Bevakning</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:Georgia,serif;background:#f5f4f0;color:#1a1a1a;min-height:100vh}}
#login{{display:flex;align-items:center;justify-content:center;min-height:100vh;background:#f5f4f0}}
#login-box{{background:#fff;padding:48px 40px;border-radius:12px;box-shadow:0 2px 12px rgba(0,0,0,0.08);text-align:center;width:320px}}
#login-box h2{{font-size:18px;font-weight:700;margin-bottom:8px}}
#login-box p{{font-size:13px;color:#888;margin-bottom:24px}}
#pw{{width:100%;padding:10px 14px;font-size:14px;border:1px solid #ddd;border-radius:6px;outline:none;margin-bottom:12px}}
#login-btn{{width:100%;padding:10px;background:#1a1a1a;color:#fff;border:none;border-radius:6px;font-size:14px;cursor:pointer;font-weight:600}}
#login-btn:hover{{opacity:0.85}}
#fel{{color:#c0392b;font-size:13px;margin-top:8px;display:none}}
#rapport{{display:none}}
.header{{background:#1a1a1a;color:#fff;padding:28px 40px}}
.header h1{{font-size:22px;font-weight:700;letter-spacing:-0.5px}}
.header p{{font-size:13px;color:#999;margin-top:5px}}
.stats{{background:#fff;border-bottom:1px solid #e8e8e8;padding:10px 40px;display:flex;gap:24px;font-size:12px;color:#666;flex-wrap:wrap}}
.stats b{{color:#1a1a1a}}
.content{{max-width:760px;margin:0 auto;padding:24px 40px 32px}}
.sokord-panel{{max-width:760px;margin:0 auto;padding:0 40px 40px}}
a:hover{{opacity:0.75}}
button:hover{{opacity:0.85}}
</style>
</head>
<body>

<div id="login">
  <div id="login-box">
    <h2>Rison Bevakning</h2>
    <p>Ange lösenord för att fortsätta</p>
    <input type="password" id="pw" placeholder="Lösenord" onkeydown="if(event.key==='Enter')logga_in()">
    <button id="login-btn" onclick="logga_in()">Logga in</button>
    <div id="fel">Fel lösenord</div>
  </div>
</div>

<div id="rapport">
  <div class="header">
    <h1>Rison Capital &middot; Omvarldsbevakning</h1>
    <p>{datum} &middot; {len(hoga)+len(medel)} relevanta artiklar &middot; Google News via Serper</p>
  </div>
  <div class="stats">
    <span><b>{stat['sokord']}</b> sokord ({stat['fasta']} fasta + {stat['zeitgeist']} zeitgeist + {stat['dagsaktuella']} dagsaktuella)</span>
    <span><b>{stat['hittade']}</b> artiklar hittades</span>
    <span><b>{stat['efter_dubbletter']}</b> efter dubblettfiltrering</span>
    <span><b>{stat['relevanta']}</b> relevanta</span>
    <span><b>{len(hoga)}</b> hog &middot; <b>{len(medel)}</b> medel</span>
  </div>
  {zeitgeist_teman}
  <div class="content">
    {innehall}
  </div>
  <div class="sokord-panel">
    <div style="font-size:11px;font-weight:700;color:#888;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px;cursor:pointer;"
         onclick="var e=document.getElementById('sp');e.style.display=e.style.display==='none'?'block':'none'">
      Dagens sokord (klicka for att visa)
    </div>
    <div id="sp" style="display:none;">
      <div style="font-size:11px;color:#aaa;margin-bottom:8px;">🔍 = fast karna &nbsp; 🌐 = zeitgeist &nbsp; ✨ = dagsaktuell</div>
      {sokord_html}
    </div>
  </div>
</div>

<script>
window.artiklar = window.artiklar || {{}};

function kopiera_prompt(btn, titel) {{
  const prompt = `Du ar kommunikationsansvarig pa Rison Capital och skriver ett LinkedIn-inlagg for Jesper Lovkvist, delagare.

Rison Capital finansierar energieffektivisering i fastigheter via EaaS-modell utan fordringar pa fastighetsagaren. Bergvarme, BESS, varmepumpar, BRF, kommersiella fastigheter. Institutionellt kapital via SEB Nordic Energy Fund.

Ton: insiktsfull, direkt, latt provocerande. Borjar med ovantad fraga eller pastande. Kopplar till Risons strukturella losning. Avslutar med dialog-fraga. Mal: CFO fastighetsbolag, BRF-styrelser, kommunala fastighetschefer.

ARTIKEL: ${{titel}}

Generera ett LinkedIn-inlagg med:
- Hook (oppningsmening)
- 3 nyckelpoanger fran artikeln
- Koppling till Risons erbjudande
- Avslutande fraga`;

  navigator.clipboard.writeText(prompt).then(() => {{
    const orig = btn.textContent;
    btn.textContent = '✓ Kopierad!';
    btn.style.background = '#1a7a3f';
    setTimeout(() => {{
      btn.textContent = orig;
      btn.style.background = '#0077b5';
    }}, 2000);
  }}).catch(() => {{
    alert('Kunde inte kopiera. Prova igen.');
  }});
}}

async function sha256(text) {{
  const buf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text));
  return Array.from(new Uint8Array(buf)).map(b => b.toString(16).padStart(2,'0')).join('');
}}
async function logga_in() {{
  const pw = document.getElementById('pw').value;
  const hash = await sha256(pw);
  if (hash === '8d13224db15d8e30881ae4fe4f030228cdcd5de58692f72d481a0a3df89d939f') {{
    document.getElementById('login').style.display = 'none';
    document.getElementById('rapport').style.display = 'block';
    sessionStorage.setItem('auth', '1');
  }} else {{
    document.getElementById('fel').style.display = 'block';
  }}
}}
if (sessionStorage.getItem('auth') === '1') {{
  document.getElementById('login').style.display = 'none';
  document.getElementById('rapport').style.display = 'block';
}}
</script>
</body>
</html>"""

# ── Huvudflode ────────────────────────────────────────────────────────────────

def main():
    print(f"[{datetime.now():%H:%M}] Startar Rison bevakning via Serper v3")
    sedda = ladda_sedda()

    # Steg 1: Zeitgeist-sokord (veckovis cachade)
    print("\n  [1/6] Zeitgeist-analys...")
    zeitgeist_sokord = hamta_zeitgeist_sokord()
    print(f"  {len(zeitgeist_sokord)} zeitgeist-sokord")

    # Steg 2: Dagsaktuella sokord
    print("\n  [2/6] Dagsaktuella sokord...")
    dagsaktuella = generera_dagsaktuella_sokord(zeitgeist_sokord)
    if dagsaktuella:
        for s in dagsaktuella:
            print(f"    ✨ {s}")

    alla_sokord = FASTA_SOKORD + zeitgeist_sokord + dagsaktuella

    # Steg 3: Sok via Serper
    print(f"\n  [3/6] Soker ({len(alla_sokord)} sokord)...")
    kandidater = {}
    for sokord in alla_sokord:
        time.sleep(0.3)
        traff = sok_serper(sokord, antal=10)
        for a in traff:
            aid = artikel_id(a["url"])
            if aid not in sedda and aid not in kandidater:
                kandidater[aid] = a
        print(f"  '{sokord}': {len(traff)} traff")

    nya = list(kandidater.values())
    print(f"\n  {len(nya)} unika nya artiklar")

    if not nya:
        print("  Inga nya artiklar.")
        OUTPUT_FILE.write_text(bygg_html([], {
            "sokord": len(alla_sokord), "fasta": len(FASTA_SOKORD),
            "zeitgeist": len(zeitgeist_sokord), "dagsaktuella": len(dagsaktuella),
            "hittade": 0, "efter_dubbletter": 0, "relevanta": 0
        }, dagsaktuella, zeitgeist_sokord), encoding="utf-8")
        return

    # Steg 4: Dubblettgruppering (bara textlikhet)
    print(f"\n  [4/6] Grupperar dubletter...")
    grupper_alla = gruppera_dubletter(nya)
    representanter = [basta_i_grupp(g) for g in grupper_alla]
    print(f"  {len(nya)} -> {len(representanter)} efter dubblettfiltrering")
    # Begränsa till 25 hogst rankade under testperiod
    representanter = representanter[:25]
    print(f"  Begransar till {len(representanter)} hogst rankade for testkorning")

    # Fulltext-hamtning avstangd under testperiod – anvander snippet fran Serper
    # for a in representanter:
    #     a["fulltext"] = hamta_text(a["url"])

    print(f"\n  [5/6] Bedomer {len(representanter)} artiklar pa snippet (testlage, batchar om {BATCH_STORLEK})...")

    relevanta_repr = []
    for i in range(0, len(representanter), BATCH_STORLEK):
        batch = representanter[i:i + BATCH_STORLEK]
        print(f"  Batch {i//BATCH_STORLEK + 1}: {len(batch)} artiklar...")
        tid_start = time.time()
        resultat = bedom_batch(batch)
        elapsed = time.time() - tid_start
        print(f"    -> {len(resultat)} relevanta ({elapsed:.1f}s)")
        relevanta_repr.extend(resultat)

    # Koppla tillbaka till grupper
    repr_url_till_grupp = {basta_i_grupp(g)["url"]: g for g in grupper_alla}
    grupper_relevanta = []
    for r in relevanta_repr:
        grupp = repr_url_till_grupp.get(r["url"], [r])
        grupp[0] = r
        grupper_relevanta.append(grupp)

    grupper_relevanta.sort(key=lambda g: sorteringsnyckel(g[0]))

    hog_n = sum(1 for g in grupper_relevanta if g[0].get("relevansniva") == "Hog")
    med_n = sum(1 for g in grupper_relevanta if g[0].get("relevansniva") == "Medel")
    print(f"\n  Resultat: {len(grupper_relevanta)} grupper ({hog_n} hoga, {med_n} medel)")

    stat = {
        "sokord":           len(alla_sokord),
        "fasta":            len(FASTA_SOKORD),
        "zeitgeist":        len(zeitgeist_sokord),
        "dagsaktuella":     len(dagsaktuella),
        "hittade":          len(nya),
        "efter_dubbletter": len(representanter),
        "relevanta":        len(grupper_relevanta),
    }

    html = bygg_html(grupper_relevanta, stat, dagsaktuella, zeitgeist_sokord)
    OUTPUT_FILE.write_text(html, encoding="utf-8")
    print(f"  Rapport sparad: {OUTPUT_FILE}")
    spara_sedda(sedda)
    print("  Klar. Oppna index.html i webblasaren.")

if __name__ == "__main__":
    main()
