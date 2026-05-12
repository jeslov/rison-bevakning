# Dagsaktuella-prompt för Rison-bevakning

## Bakgrund

Dagsaktuella sökord är 3 svenska Google-sökord (2-3 ord) som fångar dagens nyhetsläge inom Risons fokusområden, kompletterande till veckans zeitgeist-sökord. De matas in i Serper-sökningen i `kor_hamtning()` tillsammans med FASTA_SOKORD och zeitgeist-sökord.

Körs **varje dag** (om `dagsaktuella_cache.json` har äldre datum än idag, saknas, eller har `sokord=[]`).

## Indata

- `zeitgeist_cache.json` — innehåller veckans 8 zeitgeist-sökord (dagsaktuella ska skilja sig från dessa)
- Dagens datum (för säsongsinfo)

## Risons kontext (för prompten)

Rison Capital är ett Göteborgsbaserat investmentbolag som finansierar energieffektivisering och småskalig energiproduktion i fastigheter utan fordringar på fastighetsägaren (EaaS-modell). Institutionellt kapital via SEB Nordic Energy Fund. Bergvärme, BESS/batterilager, värmepumpar, isolering, solceller. Målgrupper: kommersiella fastigheter, BRF, kommuner, industrifastigheter. Kärnbudskap: Bromsklossen är inte tekniken eller lönsamheten — det är finansieringen.

## Säsongsmappning

| Månad | Säsong |
|-------|--------|
| 3, 4, 5 | Vår: BRF-stämmer, energideklarationer |
| 6, 7, 8 | Sommar: Planering höstinstallationer |
| 9, 10, 11 | Höst: Uppvärmningssäsong, värmepumpar |
| 12, 1, 2 | Vinter: Energikostnader, årsbokslut |

## Prompt

```
Datum: <DD månad YYYY>. Sasong: <säsongstext>
Zeitgeist-sokord denna vecka: <zeitgeist-sökord, komma-separerade>
Generera 3 dagsaktuella svenska Google-sokord (2-3 ord) som skiljer sig fran zeitgeist-sokorden.
Svara ENDAST med JSON-lista: ["s1", "s2", "s3"]
```

**Placeholders:** Datum, säsong och zeitgeist-sökord fylls in från `zeitgeist_cache.json` och systemets datum.

## Output-format

```json
["sokord1", "sokord2", "sokord3"]
```

## Cache-format (`dagsaktuella_cache.json`)

```json
{
  "datum": "<YYYY-MM-DD, t.ex. 2026-05-12>",
  "sokord": ["sokord1", "sokord2", "sokord3"]
}
```

## Process (för Claude Code i wizarden)

1. Läs `dagsaktuella_cache.json` om filen finns
2. Avgör om uppdatering behövs:
   - Om filen saknas → UPPDATERA
   - Om `datum` ≠ idag → UPPDATERA
   - **Om `datum` = idag men `sokord` = [] → UPPDATERA ÄNDÅ** (det är spår av misslyckad tidigare körning)
   - Annars → hoppa över (cache är giltig)
3. Läs `zeitgeist_cache.json` och plocka ut `sokord`-listan
4. Bestäm säsong utifrån dagens månad (tabell ovan)
5. Bygg prompten enligt mallen ovan — ersätt placeholders med faktiska värden
6. Generera 3 sökord som ska:
   - Vara på svenska, 2-3 ord
   - Skilja sig från zeitgeist-sökorden
   - Vara dagsaktuella (fånga aktuell nyhetsbild)
7. Skriv resultat till `dagsaktuella_cache.json` med format ovan (`datum` = idag, YYYY-MM-DD)
8. Säg till så `--hamta` kan köras igen för att inkludera dagsaktuella i sökningen
