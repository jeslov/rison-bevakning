#!/usr/bin/env python3
"""
Rison Capital - Daglig omvarldsbevakning via Serper (Google Search)
v2: Dubblettfiltrering fore bedomning, batch-bedomning (50/anrop),
    annonsfilter, publiceringsdatum, sortering pa datum
"""

import os, json, hashlib, time, re, requests
from datetime import datetime, timezone
from pathlib import Path

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
SERPER_API_KEY    = os.environ["SERPER_API_KEY"]
OUTPUT_FILE       = Path(__file__).parent / "bevakning.html"
SEEN_FILE         = Path(__file__).parent / "sedda_artiklar.json"
MIN_RELEVANS      = "Medel"
BATCH_STORLEK     = 50

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

def generera_dynamiska_sokord():
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

Generera 5 svenska Google-sokord (2-3 naturliga svenska ord per sokning) som
kompletterar de fasta sokorden. Fanga dagsaktuella nyheter inom energieffektivisering
och fastighetssektorn. Format: korta naturliga ordkombinationer som "bergvärme BRF".

Svara ENDAST med JSON-lista: ["sokord 1", "sokord 2", "sokord 3", "sokord 4", "sokord 5"]"""

    svar = claude_anrop(prompt, max_tokens=200)
    if not svar:
        return []
    try:
        sokord = json.loads(svar)
        return sokord if isinstance(sokord, list) else []
    except Exception:
        return []

def sok_serper(sokord, antal=10):
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
                "tbs": "qdr:3d",
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
               and "ANNONS:" not in n.get("title", "")
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

# ── Dubblettgruppering ────────────────────────────────────────────────────────

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
    """Steg 1: Textlikhet. Steg 2: Claude slår ihop grupper om samma händelse."""
    # Steg 1
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

    if len(grupper) == len(artiklar):
        return grupper  # Inga uppenbara dubletter, skippa Claude-steget

    # Steg 2: Claude
    titlar = [g[0]["titel"] for g in grupper]
    prompt = f"""Du ar redaktor. Nedan ar numrerade artikelrubriker.
Identifiera vilka som handlar om exakt samma nyhetshändelse (inte bara samma amne).

{chr(10).join(f"{i+1}. {t}" for i, t in enumerate(titlar))}

Svara med JSON dar varje element ar en lista av 1-baserade index som ska grupperas.
Artiklar utan dubbletter ar egna grupper. Exempel: [[1,3],[2],[4,5]]
Svara ENDAST med JSON-lista, ingen annan text."""

    svar = claude_anrop(prompt, max_tokens=500)
    if not svar:
        return grupper
    try:
        gruppindex = json.loads(svar)
        nya = []
        for idxlista in gruppindex:
            sammanslagen = []
            for idx in idxlista:
                if 1 <= idx <= len(grupper):
                    sammanslagen.extend(grupper[idx - 1])
            if sammanslagen:
                nya.append(sammanslagen)
        return nya if nya else grupper
    except Exception:
        return grupper

def basta_i_grupp(grupp):
    """Väljer representant per grupp – longest beskrivning."""
    return max(grupp, key=lambda a: len(a.get("beskrivning", "")))

# ── Batch-bedomning ───────────────────────────────────────────────────────────

def bedom_batch(artiklar):
    """Bedömer upp till 50 artiklar i ett enda Claude-anrop."""
    lista = "\n".join(
        f"{i+1}. Titel: {a['titel']}\n   Kalla: {a['kalla']}\n   Text: {a.get('fulltext', a.get('beskrivning',''))[:800]}"
        for i, a in enumerate(artiklar)
    )

    prompt = f"""Du ar omvarldsanalytiker for Rison Capital.

{RISON_KONTEXT}

HOG relevans: finansiering/affarsmodeller energiomstallning kommersiella fastigheter,
regulatorisk utveckling energikrav byggnader (EPBD, taxonomi, energideklarationer),
teknologigenombrott geotermisk/BESS/varmepump for fastigheter,
institutionellt kapital gron fastighetsutveckling, stranded assets-risk, EaaS-modeller,
energikostnader och energiomstallning i BRF/hyresfastigheter/kommunala fastigheter.

MEDEL relevans: trender hallbar fastighetsutveckling Sverige/Norden, policy energikrav,
fastighetsbolag energiarbete, grona obligationer fastigheter, kommunal energiplanering,
energipriser och deras effekt pa fastigheter.

EXKLUDERA: privatbostader/villa/konsument, datakenter, karnkraft, elbilar,
allman klimatpolitik utan fastighetskoppling, sport, underhallning, fastighetsaffarer
utan energikoppling, annonser/pressmeddelanden utan nyhetsvardet.

Bedöm foljande {len(artiklar)} artiklar:

{lista}

Svara med en JSON-lista med ett objekt per artikel i samma ordning (ingen annan text):
[
  {{
    "index": 1,
    "relevant": true eller false,
    "relevansniva": "Hog" eller "Medel" eller "Lag",
    "poang": 1-10,
    "sammanfattning": "2-3 meningar om vad artikeln handlar om och varfor relevant for Rison",
    "motivering": "En mening om relevansniva"
  }},
  ...
]"""

    svar = claude_anrop(prompt, max_tokens=4000)
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

def bygg_html(grupper_relevanta, stat, dynamiska_sokord):
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
        items = "".join(
            f'<div style="padding:7px 0;border-bottom:1px solid #f0f0f0;">'
            f'<span style="font-size:11px;color:#aaa;">{escape_html(a["kalla"])}</span>'
            f'{"&nbsp;·&nbsp;<span style=\"font-size:10px;color:#bbb;\">"+escape_html(a.get("datum",""))+"</span>" if a.get("datum") else ""}'
            f' &nbsp;<a href="{escape_html(a["url"])}" target="_blank" style="font-size:13px;color:#666;">{escape_html(a["titel"])}</a>'
            f'</div>'
            for a in ovriga
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
        li    = r.get("linkedin")
        datum_str = f'<span style="font-size:11px;color:#aaa;">{escape_html(r.get("datum",""))}</span>' if r.get("datum") else ""
        sokord_str = f'<span style="font-size:10px;color:#ccc;">via: {escape_html(r.get("sokord",""))}</span>' if r.get("sokord") else ""
        knapp = (f'<button onclick="var e=document.getElementById(\'li-{idx}\'),'
                 f'btn=this;e.style.display=e.style.display===\'none\'?\'block\':\'none\';'
                 f'btn.textContent=e.style.display===\'none\'?\'&#128188; LinkedIn-forslag\':\'Stang\'"'
                 f' style="font-size:12px;background:#0077b5;color:#fff;border:none;'
                 f'padding:5px 14px;border-radius:20px;cursor:pointer;font-weight:600;">'
                 f'&#128188; LinkedIn-forslag</button>') if li else ""
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
  <div style="font-size:13px;color:#555;line-height:1.6;margin-bottom:8px;">{escape_html(r.get('sammanfattning',''))}</div>
  <div style="font-size:11px;color:#999;font-style:italic;margin-bottom:12px;">{escape_html(r.get('motivering',''))}</div>
  <div style="display:flex;gap:12px;align-items:center;flex-wrap:wrap;">
    <a href="{escape_html(r['url'])}" target="_blank" style="font-size:12px;color:{faerg};font-weight:600;text-decoration:none;">Las artikel &rarr;</a>
    {knapp}
  </div>
  {dubbletter_panel(grupp, idx)}
  <div id="li-{idx}" style="display:none;margin-top:14px;">{li_panel(li) if li else ''}</div>
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

    alla_sokord = FASTA_SOKORD + dynamiska_sokord
    sokord_html = "".join(
        f'<span style="display:inline-block;background:#f0f0f0;border-radius:20px;padding:3px 10px;font-size:12px;color:#555;margin:3px;">{"✨" if s in dynamiska_sokord else "🔍"} {escape_html(s)}</span>'
        for s in alla_sokord
    )

    return f"""<!DOCTYPE html>
<html lang="sv">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Rison Bevakning {datum}</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:Georgia,serif;background:#f5f4f0;color:#1a1a1a;min-height:100vh}}
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
<div class="header">
  <h1>Rison Capital &middot; Omvarldsbevakning</h1>
  <p>{datum} &middot; {len(hoga)+len(medel)} relevanta artiklar &middot; Google News via Serper</p>
</div>
<div class="stats">
  <span><b>{stat['sokord']}</b> sokord ({stat['fasta']} fasta + {stat['dynamiska']} dynamiska)</span>
  <span><b>{stat['hittade']}</b> artiklar hittades</span>
  <span><b>{stat['efter_dubbletter']}</b> efter dubblettfiltrering</span>
  <span><b>{stat['relevanta']}</b> relevanta</span>
  <span><b>{len(hoga)}</b> hog &middot; <b>{len(medel)}</b> medel</span>
</div>
<div class="content">
  {innehall}
</div>
<div class="sokord-panel">
  <div style="font-size:11px;font-weight:700;color:#888;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px;cursor:pointer;"
       onclick="var e=document.getElementById('sp');e.style.display=e.style.display==='none'?'block':'none'">
    Dagens sokord (klicka for att visa)
  </div>
  <div id="sp" style="display:none;">
    <div style="font-size:11px;color:#aaa;margin-bottom:8px;">🔍 = fast karna &nbsp; ✨ = dynamisk</div>
    {sokord_html}
  </div>
</div>
</body>
</html>"""

def main():
    print(f"[{datetime.now():%H:%M}] Startar Rison bevakning via Serper v2")
    sedda = ladda_sedda()

    # Steg 1: Dynamiska sökord
    print("\n  [1/5] Genererar dynamiska sokord...")
    time.sleep(1.0)
    dynamiska = generera_dynamiska_sokord()
    if dynamiska:
        print(f"  {len(dynamiska)} dynamiska sokord:")
        for s in dynamiska:
            print(f"    ✨ {s}")

    alla_sokord = FASTA_SOKORD + dynamiska

    # Steg 2: Sök via Serper
    print(f"\n  [2/5] Soker ({len(alla_sokord)} sokord)...")
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
    print(f"\n  {len(nya)} unika nya artiklar (annonser borttagna)")

    if not nya:
        print("  Inga nya artiklar.")
        OUTPUT_FILE.write_text(bygg_html([], {"sokord":len(alla_sokord),"fasta":len(FASTA_SOKORD),"dynamiska":len(dynamiska),"hittade":0,"efter_dubbletter":0,"relevanta":0}, dynamiska), encoding="utf-8")
        return

    # Steg 3: Dubblettgruppering före bedömning
    print(f"\n  [3/5] Grupperar dubletter...")
    grupper_alla = gruppera_dubletter(nya)
    representanter = [basta_i_grupp(g) for g in grupper_alla]
    print(f"  {len(nya)} -> {len(representanter)} representanter efter dubblettfiltrering")

    # Steg 4: Hämta fulltext för representanter
    print(f"\n  [4/5] Hamtar fulltext och bedomer {len(representanter)} artiklar i batchar om {BATCH_STORLEK}...")
    for a in representanter:
        a["fulltext"] = hamta_text(a["url"])

    # Batch-bedömning
    relevanta_repr = []
    for i in range(0, len(representanter), BATCH_STORLEK):
        batch = representanter[i:i + BATCH_STORLEK]
        print(f"  Batch {i//BATCH_STORLEK + 1}: bedomer {len(batch)} artiklar...")
        tid_start = time.time()
        resultat = bedom_batch(batch)
        elapsed = time.time() - tid_start
        print(f"    -> {len(resultat)} relevanta ({elapsed:.1f}s)")
        relevanta_repr.extend(resultat)
        if i + BATCH_STORLEK < len(representanter):
            time.sleep(2.0)

    # Koppla relevanta representanter tillbaka till sina grupper
    repr_url_till_grupp = {basta_i_grupp(g)["url"]: g for g in grupper_alla}
    grupper_relevanta = []
    for r in relevanta_repr:
        grupp = repr_url_till_grupp.get(r["url"], [r])
        grupp[0] = r  # Ersätt representanten med berikad version
        grupper_relevanta.append(grupp)

    # Sortera: relevansnivå -> datum (nyast först) -> poäng
    grupper_relevanta.sort(key=lambda g: (
        {"Hog": 0, "Medel": 1, "Lag": 2}.get(g[0].get("relevansniva", "Lag"), 2),
        -g[0].get("poang", 0)
    ))

    # Steg 5: LinkedIn-förslag för Hög-artiklar
    hoga_grupper = [g for g in grupper_relevanta if g[0].get("relevansniva") == "Hog"]
    if hoga_grupper:
        print(f"\n  [5/5] LinkedIn-forslag for {len(hoga_grupper)} hoga artiklar...")
        for g in hoga_grupper:
            time.sleep(1.5)
            print(f"  LI: {g[0]['titel'][:60]}")
            g[0]["linkedin"] = linkedin_forslag(g[0])

    hog_n = sum(1 for g in grupper_relevanta if g[0].get("relevansniva") == "Hog")
    med_n = sum(1 for g in grupper_relevanta if g[0].get("relevansniva") == "Medel")
    print(f"\n  Resultat: {len(grupper_relevanta)} grupper ({hog_n} hoga, {med_n} medel)")

    stat = {
        "sokord":           len(alla_sokord),
        "fasta":            len(FASTA_SOKORD),
        "dynamiska":        len(dynamiska),
        "hittade":          len(nya),
        "efter_dubbletter": len(representanter),
        "relevanta":        len(grupper_relevanta),
    }

    OUTPUT_FILE.write_text(bygg_html(grupper_relevanta, stat, dynamiska), encoding="utf-8")
    print(f"  Rapport sparad: {OUTPUT_FILE}")
    spara_sedda(sedda)
    print("  Klar. Oppna bevakning.html i webblasaren.")

if __name__ == "__main__":
    main()
