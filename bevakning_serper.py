#!/usr/bin/env python3
"""
Rison Capital - Daglig omvarldsbevakning
v4: RSS + Serper parallellt, cachade testart-artiklar, dagsaktuella sokord cachade,
    organisationssokord, hashtagforslag, web search i prompt, minskad referatgrad
"""

import os, json, hashlib, time, re, requests, xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path

ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
SERPER_API_KEY    = os.environ.get("SERPER_API_KEY", "")
OUTPUT_FILE       = Path(__file__).parent / "index.html"
SEEN_FILE         = Path(__file__).parent / "sedda_artiklar.json"
ZEITGEIST_FILE    = Path(__file__).parent / "zeitgeist_cache.json"
DAGSAKTUELLA_FILE = Path(__file__).parent / "dagsaktuella_cache.json"
TESTART_FILE      = Path(__file__).parent / "testart_artiklar.json"
BEDOMNING_CACHE_FILE = Path(__file__).parent / "bedomning_cache.json"
MIN_RELEVANS      = "Medel"
LINKEDIN_STIL_FIL = Path(__file__).parent / "linkedin_stil.txt"
BATCH_STORLEK     = 10
TESTLAGE          = TESTART_FILE.exists()  # Kör i testläge om cachefil finns

# ── Källor ────────────────────────────────────────────────────────────────────

RSS_FLODEN = [
    # Fastighet
    {"namn": "Fastighetstidningen",  "url": "https://www.fastighetstidningen.se/feed/"},
    {"namn": "Fastighetsnytt",       "url": "https://www.fastighetsnytt.se/feed/"},
    {"namn": "Fastighetssverige",    "url": "https://www.fastighetssverige.se/rss/"},
    {"namn": "Byggvarlden",          "url": "https://www.byggvarlden.se/feed/"},
    {"namn": "Fastighetsvarlden",    "url": "https://www.fastighetsvarlden.se/feed/"},
    {"namn": "Byggindustrin",        "url": "https://www.byggindustrin.se/feed/"},
    # BRF
    {"namn": "Bostadsratterna",      "url": "https://www.bostadsratterna.se/feed/"},
    {"namn": "HSB",                  "url": "https://www.hsb.se/nyheter-och-tips/nyheter/feed/"},
    {"namn": "Riksbyggen",           "url": "https://www.riksbyggen.se/nyheter/feed/"},
    {"namn": "SBC",                  "url": "https://www.sbc.se/nyheter/feed/"},
    {"namn": "Styrelseguiden",       "url": "https://www.styrelseguiden.se/feed/"},
    # Energi
    {"namn": "Energi och Miljo",     "url": "https://www.energi-miljo.se/feed/"},
    {"namn": "Energimyndigheten",    "url": "https://www.energimyndigheten.se/om-oss/nyheter/rss/"},
    {"namn": "Energiforetagen",      "url": "https://www.energiforetagen.se/feed/"},
    # Hallbarhet
    {"namn": "Miljoaktuellt",        "url": "https://www.miljoaktuellt.se/feed/"},
    # Offentlig sektor
    {"namn": "Dagens Samhalle",      "url": "https://www.dagenssamhalle.se/feed/"},
    {"namn": "Altinget",             "url": "https://www.altinget.se/rss/seneste"},
    # Dagstidningar
    {"namn": "Di",                   "url": "https://www.di.se/rss/"},
    {"namn": "SvD",                  "url": "https://www.svd.se/feed/articles.rss"},
    {"namn": "DN",                   "url": "https://www.dn.se/rss/ekonomi"},
]

FASTA_SOKORD = [
    # Teknik – med och utan "fastighet"
    "bergvärme flerbostadshus", "bergvärme BRF", "bergvärme kommersiell",
    "värmepump byggnad", "värmepump BRF", "batterilager byggnad",
    "solceller BRF", "solceller flerbostadshus", "energilagring byggnad",
    "geotermisk energi Sverige",
    # Energieffektivisering
    "energieffektivisering byggnad", "energieffektivisering BRF",
    "energieffektivisering flerbostadshus", "energirenovering fastighet",
    "energideklaration fastighet", "energikostnad fastighet",
    "energiprestanda byggnad",
    # Finansiering
    "gröna obligationer fastighet", "fastighetsinvestering energi",
    "EaaS energi tjänst",
    # Regelverk
    "EPBD byggnader Sverige", "energikrav byggnader",
    "Boverket energi", "klimatkrav fastighet",
    # Marknad
    "fastighetsbolag energiomställning", "stranded assets fastighet",
    "fjärrvärme alternativ byggnad",
    # Intresseorganisationer och myndigheter
    "Fastighetsägarna energikrav", "Riksbyggen energi",
    "HSB energieffektivisering", "Energimyndigheten byggnader",
    "Boverket byggregler", "Naturvårdsverket klimat",
    "Hyresgästföreningen energi", "Sveriges Allmännytta energi",
]

MALMEDIER = [
    "fastighetstidningen.se", "fastighetsnytt.se", "fastighetssverige.se",
    "fastighetsvarlden.se", "byggvarlden.se", "byggindustrin.se",
    "fastighetsagarna.se", "energi-miljo.se", "energimyndigheten.se",
    "bostadsratterna.se", "hsb.se", "riksbyggen.se", "sbc.se",
    "dagenssamhalle.se", "altinget.se",
]

RISON_KONTEXT = """
Rison Capital ar ett Goteborgsbaserat investmentbolag som finansierar energieffektivisering
och smaskalig energiproduktion i fastigheter utan fordringar pa fastighetsagaren (EaaS-modell).
Institutionellt kapital via SEB Nordic Energy Fund. Bergvarme, BESS/batterilager, varmepumpar,
isolering, solceller. Malgrupper: kommersiella fastigheter, BRF, kommuner, industrifastigheter.
Karnbudskap: Bromsklossen ar inte tekniken eller lonsamheten - det ar finansieringen.
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
                headers={"x-api-key": ANTHROPIC_API_KEY, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                json={"model": "claude-sonnet-4-6", "max_tokens": max_tokens, "messages": [{"role": "user", "content": prompt}]},
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

# ── RSS ───────────────────────────────────────────────────────────────────────

def hamta_rss(flode):
    try:
        r = requests.get(flode["url"], timeout=8, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code != 200:
            return []
        root = ET.fromstring(r.content)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        items = root.findall(".//item") or root.findall(".//atom:entry", ns)
        result = []
        for item in items[:10]:
            titel = (item.findtext("title") or item.findtext("atom:title", namespaces=ns) or "").strip()
            url   = (item.findtext("link") or
                     (item.find("atom:link", ns).get("href") if item.find("atom:link", ns) is not None else "") or "").strip()
            besk  = (item.findtext("description") or item.findtext("atom:summary", namespaces=ns) or "").strip()[:300]
            pub   = (item.findtext("pubDate") or item.findtext("atom:published", namespaces=ns) or "").strip()
            if titel and url and "ANNONS" not in titel.upper():
                result.append({"titel": titel, "url": url, "beskrivning": besk,
                                "kalla": flode["namn"], "datum": pub, "kalla_typ": "rss"})
        return result
    except Exception:
        return []

# ── Serper ────────────────────────────────────────────────────────────────────

def sok_serper(sokord, antal=10):
    if not SERPER_API_KEY:
        return []
    try:
        r = requests.post(
            "https://google.serper.dev/news",
            headers={"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"},
            json={"q": sokord, "gl": "se", "hl": "sv", "num": antal, "tbs": "qdr:w"},
            timeout=10,
        )
        if r.status_code != 200:
            return []
        return [
            {"titel": n.get("title", "").strip(), "url": n.get("link", "").strip(),
             "beskrivning": n.get("snippet", "").strip()[:300], "kalla": n.get("source", "").strip(),
             "datum": n.get("date", ""), "sokord": sokord, "kalla_typ": "serper"}
            for n in r.json().get("news", [])
            if n.get("title") and n.get("link") and "ANNONS" not in n.get("title", "").upper()
        ]
    except Exception:
        return []

def hamta_text(url):
    try:
        r = requests.get(url, timeout=5, headers={"User-Agent": "Mozilla/5.0"}, stream=True)
        if r.status_code not in (200, 203):
            return ""
        chunks, size = [], 0
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

# ── Zeitgeist ────────────────────────────────────────────────────────────────

def zeitgeist_behovs():
    if not ZEITGEIST_FILE.exists():
        return True
    try:
        cache = json.loads(ZEITGEIST_FILE.read_text())
        sparad = datetime.fromisoformat(cache.get("datum", "2000-01-01"))
        return (datetime.now() - sparad).days >= 7
    except Exception:
        return True

def uppdatera_zeitgeist():
    print("  Uppdaterar zeitgeist (var 7e dag)...")
    titlar = []
    for medium in MALMEDIER:
        traff = sok_serper(f"site:{medium} energi fastighet", antal=10)
        for a in traff:
            titlar.append(f"{a['titel']} – {a['beskrivning'][:100]}")
        time.sleep(0.2)
    if not titlar:
        return []
    print(f"  Analyserar {len(titlar)} artiklar...")
    prompt = f"""Analysera dessa titlar/snippets fran svenska malmedier inom energi och fastighet.
Identifiera dominerande teman och zeitgeist inom Risons fokusomraden.

{chr(10).join(f"- {t}" for t in titlar[:150])}

Generera 8 svenska sokord (2-3 ord) som fanger aktuella amnesomraden.
Svara med JSON: {{"teman": ["t1","t2","t3","t4","t5"], "sokord": ["s1","s2","s3","s4","s5","s6","s7","s8"]}}"""
    svar = claude_anrop(prompt, max_tokens=400)
    if not svar:
        return []
    try:
        data = json.loads(svar)
        ZEITGEIST_FILE.write_text(json.dumps({"datum": datetime.now().isoformat(),
            "teman": data.get("teman", []), "sokord": data.get("sokord", [])},
            ensure_ascii=False, indent=2))
        print(f"  Teman: {', '.join(data.get('teman', []))}")
        return data.get("sokord", [])
    except Exception:
        return []

def hamta_zeitgeist():
    if zeitgeist_behovs():
        return uppdatera_zeitgeist()
    try:
        cache = json.loads(ZEITGEIST_FILE.read_text())
        sokord = cache.get("sokord", [])
        sparad = cache.get("datum", "")[:10]
        print(f"  Cachad zeitgeist fran {sparad} ({len(sokord)} sokord)")
        return sokord
    except Exception:
        return uppdatera_zeitgeist()

# ── Dagsaktuella sokord (cachade per dag) ─────────────────────────────────────

def dagsaktuella_behovs():
    if not DAGSAKTUELLA_FILE.exists():
        return True
    try:
        cache = json.loads(DAGSAKTUELLA_FILE.read_text())
        return cache.get("datum", "")[:10] != datetime.now().strftime("%Y-%m-%d")
    except Exception:
        return True

def hamta_dagsaktuella(zeitgeist_sokord):
    if not dagsaktuella_behovs():
        try:
            cache = json.loads(DAGSAKTUELLA_FILE.read_text())
            sokord = cache.get("sokord", [])
            print(f"  Cachade dagsaktuella sokord ({len(sokord)} st)")
            return sokord
        except Exception:
            pass
    manad = datetime.now().month
    if manad in (3, 4, 5): sasong = "Var: BRF-stammer, energideklarationer"
    elif manad in (6, 7, 8): sasong = "Sommar: Planering hostinstallationer"
    elif manad in (9, 10, 11): sasong = "Host: Uppvarmningssasong, varmepumpar"
    else: sasong = "Vinter: Energikostnader, arsbokslut"
    prompt = f"""Datum: {datetime.now().strftime('%d %B %Y')}. Sasong: {sasong}
Zeitgeist-sokord denna vecka: {', '.join(zeitgeist_sokord)}
Generera 3 dagsaktuella svenska Google-sokord (2-3 ord) som skiljer sig fran zeitgeist-sokorden.
Svara ENDAST med JSON-lista: ["s1", "s2", "s3"]"""
    svar = claude_anrop(prompt, max_tokens=100)
    sokord = []
    if svar:
        try:
            sokord = json.loads(svar)
            if not isinstance(sokord, list):
                sokord = []
        except Exception:
            sokord = []
    DAGSAKTUELLA_FILE.write_text(json.dumps({"datum": datetime.now().strftime("%Y-%m-%d"), "sokord": sokord},
        ensure_ascii=False))
    return sokord

# ── Dubblettgruppering ────────────────────────────────────────────────────────

def titel_likhet(a, b):
    stoppord = {"och","i","pa","av","for","med","som","en","ett","ar","det","de",
                "den","att","till","om","men","har","kan","vi","du","fran","sin","sig"}
    def ord(t):
        return set(re.sub(r'[^\w\s]', '', t.lower()).split()) - stoppord
    a_ord, b_ord = ord(a), ord(b)
    if not a_ord or not b_ord: return 0.0
    return len(a_ord & b_ord) / max(len(a_ord), len(b_ord))

def gruppera_dubletter(artiklar):
    grupper, anvanda = [], set()
    for i, a in enumerate(artiklar):
        if i in anvanda: continue
        grupp = [a]; anvanda.add(i)
        for j, b in enumerate(artiklar):
            if j in anvanda: continue
            if titel_likhet(a["titel"], b["titel"]) >= 0.5:
                grupp.append(b); anvanda.add(j)
        grupper.append(grupp)
    return grupper

def basta_i_grupp(grupp):
    return max(grupp, key=lambda a: len(a.get("beskrivning", "")))

# ── Batch-bedomning ───────────────────────────────────────────────────────────

def bedom_batch(artiklar):
    lista = "\n".join(
        f"{i+1}. Titel: {a['titel']}\n   Kalla: {a['kalla']}\n   Snippet: {a.get('beskrivning','')[:300]}"
        for i, a in enumerate(artiklar)
    )
    prompt = f"""Du ar omvarldsanalytiker for Rison Capital som finansierar energieffektivisering i fastigheter via EaaS. Bergvarme, BESS, varmepumpar, BRF, kommersiella fastigheter. Institutionellt kapital via SEB Nordic Energy Fund.

HOG relevans: bergvarme/varmepump/BESS/solceller i fastigheter, energieffektivisering BRF/kommersiella fastigheter, EPBD/energikrav byggnader, institutionellt kapital gron fastighet, EaaS-finansiering, fjarvarmebyte, energikostnad fastighet, grona obligationer fastighet, intresseorganisationer och myndigheters utspel om energikrav.

MEDEL relevans: hallbar fastighetsutveckling, energipolicy Sverige, fastighetsbolag energiarbete, energipriser fastighet.

EXKLUDERA: privatbostader/villa/konsument, datakenter, karnkraft, elbilar, sport, underhallning, fastighetsaffarer utan energikoppling.

Bedöm foljande {len(artiklar)} artiklar:

{lista}

Svara med JSON-lista (ingen annan text):
[{{"index": 1, "relevant": true/false, "relevansniva": "Hog"/"Medel"/"Lag", "poang": 1-10, "sammanfattning": "En mening om vad artikeln handlar om", "motivering": "En mening"}}]"""

    svar = claude_anrop(prompt, max_tokens=3000)
    if not svar: return []
    try:
        resultat = json.loads(svar)
        if not isinstance(resultat, list): return []
        relevanta = []
        for b in resultat:
            idx = b.get("index", 0) - 1
            if not (0 <= idx < len(artiklar)): continue
            if not b.get("relevant"): continue
            if b.get("relevansniva") == "Lag": continue
            if b.get("relevansniva") == "Medel" and MIN_RELEVANS == "Hog": continue
            relevanta.append({**artiklar[idx], **b})
        return relevanta
    except Exception:
        return []

# ── Testlage ──────────────────────────────────────────────────────────────────

def spara_testart_artiklar(artiklar):
    """Sparar 30 Serper-artiklar med hogst ranking for testkorning."""
    serper_artiklar = [a for a in artiklar if a.get("kalla_typ") == "serper"]
    urval = serper_artiklar[:30]
    TESTART_FILE.write_text(json.dumps(urval, ensure_ascii=False, indent=2))
    print(f"  Sparade {len(urval)} Serper-testart-artiklar till {TESTART_FILE.name}")

def ladda_testart_artiklar():
    """Laddar cachade testart-artiklar."""
    return json.loads(TESTART_FILE.read_text())

# ── Bedömningscache ───────────────────────────────────────────────────────────

def ladda_bedomning_cache():
    """Laddar cachade bedömningar. Returnerar dict med artikel_id -> bedomning."""
    if BEDOMNING_CACHE_FILE.exists():
        try:
            return json.loads(BEDOMNING_CACHE_FILE.read_text())
        except Exception:
            return {}
    return {}

def spara_bedomning_cache(cache):
    BEDOMNING_CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=2))

def bedom_med_cache(representanter):
    """
    Bedömer artiklar med cache – kör bara Claude på artiklar som inte redan bedömts.
    Returnerar lista med relevanta artiklar.
    """
    cache = ladda_bedomning_cache()
    att_bedomma = []
    relevanta = []

    # Dela upp i cachade och nya
    for a in representanter:
        aid = artikel_id(a["url"])
        if aid in cache:
            bedomning = cache[aid]
            if bedomning:  # None = tidigare bedömd som irrelevant
                relevanta.append({**a, **bedomning})
        else:
            att_bedomma.append(a)

    cachade = len(representanter) - len(att_bedomma)
    if cachade:
        print(f"  {cachade} artiklar hämtade från cache")
    if att_bedomma:
        print(f"  {len(att_bedomma)} nya artiklar skickas till Claude...")

    # Bedöm nya artiklar i batchar
    for i in range(0, len(att_bedomma), BATCH_STORLEK):
        batch = att_bedomma[i:i + BATCH_STORLEK]
        print(f"  Batch {i//BATCH_STORLEK + 1}: {len(batch)} artiklar...")
        tid = time.time()
        resultat = bedom_batch(batch)
        elapsed = time.time() - tid
        print(f"    -> {len(resultat)} relevanta ({elapsed:.1f}s)")

        # Bygg lookup för snabb sökning
        relevanta_urls = {r["url"]: r for r in resultat}

        # Uppdatera cache för alla i batchen
        for a in batch:
            aid = artikel_id(a["url"])
            if a["url"] in relevanta_urls:
                b = relevanta_urls[a["url"]]
                # Spara bara bedömningsfälten, inte hela artikeln
                cache[aid] = {
                    "relevant": b.get("relevant"),
                    "relevansniva": b.get("relevansniva"),
                    "poang": b.get("poang"),
                    "sammanfattning": b.get("sammanfattning"),
                    "motivering": b.get("motivering"),
                }
                relevanta.append(b)
            else:
                cache[aid] = None  # Markera som bedömd men irrelevant

    spara_bedomning_cache(cache)
    return relevanta

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

    stil_text = ""
    if LINKEDIN_STIL_FIL.exists():
        stil_text = LINKEDIN_STIL_FIL.read_text(encoding="utf-8").replace("`", "'").replace("\\", "\\\\")

    def dubbletter_panel(grupp, idx):
        if len(grupp) <= 1: return ""
        ovriga = grupp[1:]
        items = ""
        for a in ovriga:
            datum_tag = f'&nbsp;·&nbsp;<span style="font-size:10px;color:#bbb;">{escape_html(a.get("datum",""))}</span>' if a.get("datum") else ""
            items += (f'<div style="padding:7px 0;border-bottom:1px solid #f0f0f0;">'
                      f'<span style="font-size:13px;color:#666;">{escape_html(a["kalla"])}</span>{datum_tag}'
                      f' &nbsp;<a href="{escape_html(a["url"])}" target="_blank" style="font-size:13px;color:#666;">{escape_html(a["titel"])}</a></div>')
        return f"""<div style="margin-top:8px;">
  <button onclick="var e=document.getElementById('dup-{idx}');e.style.display=e.style.display==='none'?'block':'none'"
    style="font-size:11px;background:none;border:1px solid #ddd;padding:3px 10px;border-radius:20px;cursor:pointer;color:#999;">
    +{len(ovriga)} liknande artikel{'er' if len(ovriga)>1 else ''}
  </button>
  <div id="dup-{idx}" style="display:none;margin-top:8px;background:#fafafa;border-radius:6px;padding:8px 12px;">{items}</div>
</div>"""

    def artikel_html(grupp, idx):
        r = grupp[0]
        niva  = r.get("relevansniva", "Medel")
        poang = r.get("poang", 0)
        faerg = "#293244" if niva == "Hog" else "#3d5a80"
        kalla_typ_ikon = "📡" if r.get("kalla_typ") == "rss" else "🔍"
        datum_str  = f'<span style="font-size:13px;color:#666;">{escape_html(r.get("datum",""))}</span>' if r.get("datum") else ""
        sokord_str = f'<span style="font-size:12px;color:#888;">via: {escape_html(r.get("sokord",""))}</span>' if r.get("sokord") else ""
        titel_esc = escape_html(r.get('titel','')).replace("'", "\\'")
        url_esc   = escape_html(r.get('url',''))
        return f"""<div style="background:#fff;border:1px solid #e8e8e8;border-radius:10px;padding:22px;margin-bottom:16px;box-shadow:0 1px 4px rgba(0,0,0,0.04);">
  <div style="display:flex;gap:8px;margin-bottom:10px;flex-wrap:wrap;align-items:center;">
    <span style="font-size:13px;color:#444;font-weight:600;">{kalla_typ_ikon} {escape_html(r['kalla'])}</span>
    <span style="font-size:10px;color:#fff;background:{faerg};padding:2px 8px;border-radius:20px;font-weight:600;">{niva}</span>
    <span style="font-size:10px;color:#fff;background:#555;padding:2px 8px;border-radius:20px;">{poang}/10</span>
    {datum_str} {sokord_str}
  </div>
  <div style="font-family:'EB Garamond',Georgia,serif;font-size:22px;font-weight:500;margin-bottom:8px;line-height:1.3;">
    <a href="{url_esc}" target="_blank" style="color:#1a1a1a;text-decoration:none;">{escape_html(r['titel'])}</a>
  </div>
  <div style="font-size:15px;color:#3a3a3a;line-height:1.7;margin-bottom:8px;font-weight:300;">{escape_html(r.get('sammanfattning',''))}</div>
  <div style="font-size:13px;color:#888;font-style:italic;margin-bottom:12px;">{escape_html(r.get('motivering',''))}</div>
  <div style="display:flex;gap:12px;align-items:center;flex-wrap:wrap;">
    <a href="{url_esc}" target="_blank" style="font-size:14px;color:{faerg};font-weight:600;text-decoration:none;">Läs artikel &rarr;</a>
    <button onclick="kopiera_prompt(this, '{titel_esc}', '{url_esc}')"
      style="font-size:12px;background:#293244;color:#EFEDE0;border:none;padding:5px 14px;border-radius:2px;cursor:pointer;font-weight:500;letter-spacing:0.3px;">
      Kopiera LinkedIn-prompt
    </button>
    <button onclick="kopiera_kort_prompt(this, '{url_esc}')"
      style="font-size:12px;background:#444;color:#fff;border:none;padding:5px 14px;border-radius:20px;cursor:pointer;font-weight:600;">
      Kort kommentar
    </button>
    <button onclick="radera_artikel(this, '{url_esc}')"
      style="font-size:12px;background:none;border:1px solid #ccc;color:#999;cursor:pointer;padding:5px 12px;border-radius:2px;margin-left:auto;letter-spacing:0.3px;">
      Ta bort
    </button>
  </div>
  {dubbletter_panel(grupp, idx)}
</div>"""

    def sektion_html(rubrik, grupper, start_idx, faerg):
        if not grupper: return "", start_idx
        h = f'<h2 style="font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:2.5px;color:#EFEDE0;margin:28px 0 12px;padding-bottom:10px;border-bottom:2px solid rgba(255,255,255,0.25);background:#293244;padding:10px 16px;border-radius:2px;">{rubrik} &mdash; {len(grupper)} artiklar</h2>'
        for i, g in enumerate(grupper):
            h += artikel_html(g, start_idx + i)
        return h, start_idx + len(grupper)

    hog_html, idx = sektion_html("Hög relevans", hoga, 0, "#293244")
    med_html, _   = sektion_html("Medel relevans", medel, idx, "#1a4a7a")
    innehall = hog_html + med_html or '<p style="color:#888;text-align:center;padding:60px 0;font-size:15px;">Inga relevanta artiklar hittades idag.</p>'

    alla_sokord = FASTA_SOKORD + zeitgeist_sokord + dynamiska_sokord
    sokord_html = "".join(
        f'<span style="display:inline-block;background:#f0f0f0;border-radius:20px;padding:3px 10px;font-size:12px;color:#555;margin:3px;">{"🌐" if s in zeitgeist_sokord else "✨" if s in dynamiska_sokord else "🔍"} {escape_html(s)}</span>'
        for s in alla_sokord
    )

    zeitgeist_teman_html = ""
    if ZEITGEIST_FILE.exists():
        try:
            cache = json.loads(ZEITGEIST_FILE.read_text())
            teman = cache.get("teman", [])
            sparad = cache.get("datum", "")[:10]
            if teman:
                teman_tags = "".join(f'<span style="display:inline-block;background:#1a1a1a;color:#fff;border-radius:20px;padding:3px 10px;font-size:12px;margin:3px;">{escape_html(t)}</span>' for t in teman)
                zeitgeist_teman_html = f'<div style="max-width:760px;margin:0 auto;padding:20px 40px 24px;"><div style="font-size:11px;font-weight:700;color:#888;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px;">Veckans zeitgeist-teman (uppdaterad {sparad})</div><div>{teman_tags}</div></div>'
        except Exception:
            pass

    testlage_banner = ""
    if TESTLAGE:
        cache_storlek = len(ladda_bedomning_cache())
        testlage_banner = f'<div style="background:#f59e0b;color:#fff;text-align:center;padding:6px;font-size:12px;font-weight:700;">TESTLÄGE – cachade artiklar används · {cache_storlek} bedömningar i cache</div>'

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
#fel{{color:#c0392b;font-size:13px;margin-top:8px;display:none}}
#rapport{{display:none}}
.header{{background:#181D27;color:#fff;padding:24px 40px;border-bottom:1px solid rgba(255,255,255,0.4)}}
.header h1{{font-family:'EB Garamond',Georgia,serif;font-size:28px;font-weight:500;letter-spacing:0.5px}}
.header p{{font-size:13px;color:#8892a4;margin-top:5px;letter-spacing:0.5px;text-transform:uppercase}}
.stats{{background:#181D27;border-bottom:2px solid rgba(255,255,255,0.2);padding:12px 40px;display:flex;gap:24px;font-size:13px;color:#8892a4;flex-wrap:wrap}}
.stats b{{color:#EFEDE0}}
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
  {testlage_banner}
  <div class="header">
    <h1>Rison &middot; Omvärldsbevakning</h1>
    <p>{datum} &middot; {len(hoga)+len(medel)} relevanta artiklar &middot; RSS + Google News via Serper</p>
  </div>
  <div class="stats">
    <span><b>{stat.get('rss_artiklar',0)}</b> RSS</span>
    <span><b>{stat.get('serper_artiklar',0)}</b> Serper</span>
    <span><b>{stat.get('efter_dubbletter',0)}</b> efter dubblettfiltrering</span>
    <span><b>{stat.get('relevanta',0)}</b> relevanta</span>
    <span><b>{len(hoga)}</b> hög &middot; <b>{len(medel)}</b> medel</span>
  </div>
  {zeitgeist_teman_html}
  <div class="content">{innehall}</div>
  <div class="sokord-panel">
    <div style="font-size:11px;font-weight:700;color:#888;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px;cursor:pointer;"
         onclick="var e=document.getElementById('sp');e.style.display=e.style.display==='none'?'block':'none'">
      Sökord (klicka för att visa)
    </div>
    <div id="sp" style="display:none;">
      <div style="font-size:11px;color:#666;margin-bottom:8px;">🔍 = fast kärna &nbsp; 🌐 = zeitgeist &nbsp; ✨ = dagsaktuell</div>
      {sokord_html}
    </div>
  </div>
</div>

<script>
function kopiera_prompt(btn, titel, url) {{
  const stilref = `{stil_text}`;
  const prompt = `Du är kommunikationsansvarig på Rison Capital och skriver ett LinkedIn-inlägg för Jesper Lövkvist, delägare.

Rison Capital finansierar energieffektivisering i fastigheter via EaaS-modell utan fordringar på fastighetsägaren. Bergvärme, BESS, värmepumpar, BRF, kommersiella fastigheter. Institutionellt kapital via SEB Nordic Energy Fund.

Här är exempel på tidigare inlägg som visar Jespers ton och stil – följ den noga:

${{stilref}}

Läs först hela artikeln på denna URL: ${{url}}

Skriv sedan ett LinkedIn-inlägg baserat på artikelns faktiska innehåll. Följ stilen i exemplen – direkt och analytisk. Inlägget ska analysera och kommentera, inte referera artikeln. Undvik säljiga fraser. Avsluta med ett påstående eller en retorisk fråga, aldrig en generisk engagemangsfråga.

Väv naturligt in referenser till relevanta intresseorganisationer, myndigheter eller studier i texten när det stärker ett argument – inte som en lista i slutet.

Avsluta med max 5 relevanta LinkedIn-hashtags på en egen rad.`;

  navigator.clipboard.writeText(prompt).then(() => {{
    const orig = btn.textContent;
    btn.textContent = '✓ Kopierad!';
    btn.style.background = '#293244';
    setTimeout(() => {{ btn.textContent = orig; btn.style.background = '#293244'; }}, 2000);
  }}).catch(() => alert('Kunde inte kopiera. Prova igen.'));
}}

function kopiera_kort_prompt(btn, url) {{
  const prompt = `Läs artikeln på denna URL: ${{url}}

Skriv en kort, kärnfull LinkedIn-kommentar på 2-4 meningar som:
- Fångar artikelns viktigaste poäng i ett analytiskt perspektiv
- Förklarar varför den är värd att läsa för någon i fastighetsbranschen
- Är skriven i en direkt, icke-säljig ton

Avsluta med: "Läs artikeln: ${{url}}"`;

  navigator.clipboard.writeText(prompt).then(() => {{
    const orig = btn.textContent;
    btn.textContent = '✓ Kopierad!';
    btn.style.background = '#555';
    setTimeout(() => {{ btn.textContent = orig; btn.style.background = '#444'; }}, 2000);
  }}).catch(() => alert('Kunde inte kopiera. Prova igen.'));
}}

function radera_artikel(btn, url) {{
  const kort = btn.closest('div[style*="border:1px solid"]');
  if (kort) {{
    kort.style.transition = 'opacity 0.3s';
    kort.style.opacity = '0';
    setTimeout(() => kort.style.display = 'none', 300);
  }}
  const raderade = JSON.parse(localStorage.getItem('raderade_artiklar') || '[]');
  if (!raderade.includes(url)) {{
    raderade.push(url);
    localStorage.setItem('raderade_artiklar', JSON.stringify(raderade));
  }}
}}

// Dölj tidigare raderade artiklar vid sidladdning
document.addEventListener('DOMContentLoaded', function() {{
  const raderade = JSON.parse(localStorage.getItem('raderade_artiklar') || '[]');
  document.querySelectorAll('[onclick*="radera_artikel"]').forEach(btn => {{
    const url = btn.getAttribute('onclick').match(/'([^']+)'\)$/)?.[1];
    if (url && raderade.includes(url)) {{
      const kort = btn.closest('div[style*="border:1px solid"]');
      if (kort) kort.style.display = 'none';
    }}
  }});
}});

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

# ── Huvudflöde ────────────────────────────────────────────────────────────────

def main():
    print(f"[{datetime.now():%H:%M}] Startar Rison bevakning v4")
    sedda = ladda_sedda()

    # Testläge: använd cachade artiklar
    if TESTLAGE:
        print("\n  TESTLAGE: Laddar cachade artiklar...")
        nya = ladda_testart_artiklar()
        print(f"  {len(nya)} cachade artiklar laddade")
        zeitgeist_sokord = []
        dagsaktuella = []
        stat_rss = 0
        stat_serper = len(nya)
    else:
        # Steg 1: Zeitgeist
        print("\n  [1/5] Zeitgeist-analys...")
        zeitgeist_sokord = hamta_zeitgeist()

        # Steg 2: Dagsaktuella sökord
        print("\n  [2/5] Dagsaktuella sökord...")
        dagsaktuella = hamta_dagsaktuella(zeitgeist_sokord)
        for s in dagsaktuella:
            print(f"    ✨ {s}")

        alla_sokord = FASTA_SOKORD + zeitgeist_sokord + dagsaktuella
        kandidater = {}

        # Steg 3a: RSS
        print(f"\n  [3/5] Hämtar RSS ({len(RSS_FLODEN)} källor)...")
        for flode in RSS_FLODEN:
            arts = hamta_rss(flode)
            nya_rss = 0
            for a in arts:
                aid = artikel_id(a["url"])
                if aid not in sedda and aid not in kandidater:
                    kandidater[aid] = a
                    nya_rss += 1
            if nya_rss:
                print(f"  {flode['namn']}: {nya_rss}")

        # Steg 3b: Serper
        print(f"\n  [3/5] Söker Serper ({len(alla_sokord)} sökord)...")
        for sokord in alla_sokord:
            time.sleep(0.3)
            traff = sok_serper(sokord, antal=10)
            for a in traff:
                aid = artikel_id(a["url"])
                if aid not in sedda and aid not in kandidater:
                    kandidater[aid] = a
            if traff:
                print(f"  '{sokord}': {len(traff)}")

        nya = list(kandidater.values())
        stat_rss = sum(1 for a in nya if a.get("kalla_typ") == "rss")
        stat_serper = sum(1 for a in nya if a.get("kalla_typ") == "serper")
        print(f"\n  {len(nya)} unika artiklar ({stat_rss} RSS, {stat_serper} Serper)")

        # Spara testart-cache om den inte finns
        if not TESTART_FILE.exists() and nya:
            spara_testart_artiklar(nya)

    if not nya:
        print("  Inga artiklar.")
        OUTPUT_FILE.write_text(bygg_html([], {"rss_artiklar":0,"serper_artiklar":0,"efter_dubbletter":0,"relevanta":0},
            [], []), encoding="utf-8")
        return

    # Steg 4: Dubblettgruppering
    print(f"\n  [4/5] Grupperar dubletter...")
    grupper_alla = gruppera_dubletter(nya)
    representanter = [basta_i_grupp(g) for g in grupper_alla]
    print(f"  {len(nya)} -> {len(representanter)} efter dubblettfiltrering")

    if TESTLAGE:
        representanter = representanter[:30]

    # Steg 5: Bedömning med cache
    print(f"\n  [5/5] Bedömer {len(representanter)} artiklar...")
    relevanta_repr = bedom_med_cache(representanter)

    repr_url_till_grupp = {basta_i_grupp(g)["url"]: g for g in grupper_alla}
    grupper_relevanta = []
    for r in relevanta_repr:
        grupp = repr_url_till_grupp.get(r["url"], [r])
        grupp[0] = r
        grupper_relevanta.append(grupp)

    grupper_relevanta.sort(key=lambda g: sorteringsnyckel(g[0]))

    hog_n = sum(1 for g in grupper_relevanta if g[0].get("relevansniva") == "Hog")
    med_n = sum(1 for g in grupper_relevanta if g[0].get("relevansniva") == "Medel")
    print(f"\n  Resultat: {len(grupper_relevanta)} grupper ({hog_n} höga, {med_n} medel)")

    stat = {
        "rss_artiklar":     stat_rss if not TESTLAGE else 0,
        "serper_artiklar":  stat_serper if not TESTLAGE else len(nya),
        "efter_dubbletter": len(representanter),
        "relevanta":        len(grupper_relevanta),
    }

    html = bygg_html(grupper_relevanta, stat, dagsaktuella, zeitgeist_sokord)
    OUTPUT_FILE.write_text(html, encoding="utf-8")
    print(f"  Rapport sparad: {OUTPUT_FILE}")
    if not TESTLAGE:
        spara_sedda(sedda)
    print("  Klar.")

if __name__ == "__main__":
    main()
