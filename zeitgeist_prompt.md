# Zeitgeist-prompt för Rison-bevakning

## Bakgrund

Zeitgeist är veckans tematiska översikt över vad svenska finans-, fastighets- och energimedier skriver om. Den driver sökordsgenereringen i bevakningsskriptet — 8 sökord från zeitgeist matas in i RSS+Serper-sökningen i `kor_hamtning()`.

Körs **var 7e dag** (om `zeitgeist_cache.json` är äldre än 7 dagar, eller saknas).

## Indata

Lista med upp till 150 titlar+snippets från målmedier:
fastighetstidningen.se, fastighetsnytt.se, fastighetssverige.se, fastighetsvarlden.se, byggvarlden.se, byggindustrin.se, fastighetsagarna.se, energi-miljo.se, energimyndigheten.se, bostadsratterna.se, hsb.se, riksbyggen.se, sbc.se, dagenssamhalle.se, altinget.se.

Sparas i `titlar_for_zeitgeist.json` av `python3 bevakning_serper.py --hamta` när zeitgeist behöver uppdateras.

**Format per post:**
```json
{
  "titel": "...",
  "kalla": "fastighetstidningen.se",
  "snippet": "...",
  "datum": "2026-05-10",
  "url": "https://fastighetstidningen.se/..."
}
```

**Fältöversikt:**
- `titel` — artikelns rubrik (används i analysen)
- `kalla` — målmediets domännamn (kan användas för viktning)
- `snippet` — Serper-snippet, max 100 tecken (används i analysen)
- `datum` — publiceringsdatum, ISO YYYY-MM-DD (kan användas för aktualitetsvägning)
- `url` — artikelns webbadress, ingår för spårbarhet (används inte i själva analysen)

## Risons kontext (för prompten)

Rison Capital är ett Göteborgsbaserat investmentbolag som finansierar energieffektivisering och småskalig energiproduktion i fastigheter utan fordringar på fastighetsägaren (EaaS-modell). Institutionellt kapital via SEB Nordic Energy Fund. Bergvärme, BESS/batterilager, värmepumpar, isolering, solceller. Målgrupper: kommersiella fastigheter, BRF, kommuner, industrifastigheter. Kärnbudskap: Bromsklossen är inte tekniken eller lönsamheten — det är finansieringen.

## Prompt

```
Analysera dessa titlar/snippets fran svenska malmedier inom energi och fastighet.
Identifiera dominerande teman och zeitgeist inom Risons fokusomraden.

- <titel> – <snippet>
- <titel> – <snippet>
...

Generera 8 svenska sokord (2-3 ord) som fanger aktuella amnesomraden.
Svara med JSON: {"teman": ["t1","t2","t3","t4","t5"], "sokord": ["s1","s2","s3","s4","s5","s6","s7","s8"]}
```

**Placeholders:** `<titel>` och `<snippet>` fylls in från `titlar_for_zeitgeist.json`. `url`, `datum` och `kalla` används INTE i själva prompten — men finns tillgängliga i indata-filen om Claude Code vill vikta efter aktualitet eller källkvalitet före promptgenerering.

## Output-format

```json
{
  "teman": ["t1", "t2", "t3", "t4", "t5"],
  "sokord": ["s1", "s2", "s3", "s4", "s5", "s6", "s7", "s8"]
}
```

## Cache-format (`zeitgeist_cache.json`)

```json
{
  "datum": "<ISO datetime, t.ex. 2026-05-12T10:00:00>",
  "teman": ["t1", "t2", "t3", "t4", "t5"],
  "sokord": ["s1", "s2", "s3", "s4", "s5", "s6", "s7", "s8"]
}
```

## Process (för Claude Code i wizarden)

1. Kontrollera om `titlar_for_zeitgeist.json` finns (skrivs av `--hamta` när uppdatering behövs)
2. Om filen finns: läs in
3. Bygg prompten enligt mallen ovan — ersätt `<titel> – <snippet>`-rader med faktiska titlar
4. Generera 5 teman + 8 sökord enligt prompten
5. Skriv resultat till `zeitgeist_cache.json` med format ovan (`datum` = nu, ISO)
6. (Frivilligt) Radera `titlar_for_zeitgeist.json` — den behövs inte längre
7. Säg till så `--hamta` kan köras igen för att generera dagsaktuella med färska zeitgeist-sökord
