# Bedömningsprompt för Rison-bevakning

Detta är prompten Claude Code använder för att bedöma artiklar enligt Rison Capitals fokus.

Mellan `python3 bevakning_serper.py --hamta` och `python3 bevakning_serper.py --rendera` läser Claude Code `obedoma_artiklar.json`, bedömer artiklarna enligt denna prompt, och uppdaterar `bedomning_cache.json`.

## Prompt

```
Du ar omvarldsanalytiker for Rison Capital som finansierar energieffektivisering i fastigheter via EaaS. Bergvarme, BESS, varmepumpar, BRF, kommersiella fastigheter. Institutionellt kapital via SEB Nordic Energy Fund.

HOG relevans: bergvarme/varmepump/BESS/solceller i fastigheter, energieffektivisering BRF/kommersiella fastigheter, EPBD/energikrav byggnader, institutionellt kapital gron fastighet, EaaS-finansiering, fjarvarmebyte, energikostnad fastighet, grona obligationer fastighet, intresseorganisationer och myndigheters utspel om energikrav.

MEDEL relevans: hallbar fastighetsutveckling, energipolicy Sverige, fastighetsbolag energiarbete, energipriser fastighet.

EXKLUDERA: privatbostader/villa/konsument, datakenter, karnkraft, elbilar, sport, underhallning, fastighetsaffarer utan energikoppling.

Bedöm foljande {antal} artiklar:

{lista}

Svara med JSON-lista (ingen annan text):
[{"index": 1, "relevant": true/false, "relevansniva": "Hog"/"Medel"/"Lag", "poang": 1-10, "sammanfattning": "Rubrik max 8 ord | 5-7 punkter separerade med • enligt analytiskt format (se Sammanfattnings-format nedan)", "motivering": "En mening", "kontextsokord": ["sokord1", "sokord2", "sokord3"]}]
```

**Placeholders i prompten:**
- `{antal}` — antal artiklar i denna batch (max 10 enligt `BATCH_STORLEK`)
- `{lista}` — formaterad lista av artiklar, en post per artikel:
  ```
  1. Titel: <titel>
     Kalla: <källa>
     Text: <fulltext eller beskrivning, trunkerad till 2000 tecken>
  ```

## Batch-storlek

Bedöm **10 artiklar per batch**. Om `obedoma_artiklar.json` har fler än 10, gör flera batchar i sekvens.

## Output-format

JSON-lista med ett objekt per artikel:

```json
[{"index": 1, "relevant": true/false, "relevansniva": "Hog"/"Medel"/"Lag", "poang": 1-10, "sammanfattning": "...", "motivering": "...", "kontextsokord": [...]}]
```

## Filter-regler

Efter bedömning, applicera dessa filter på resultatet:
- `relevant=false` → skippa (markera som `null` i bedomning_cache.json)
- `relevansniva="Lag"` → skippa
- `relevansniva="Medel"` och `MIN_RELEVANS="Hog"` → skippa (just nu är `MIN_RELEVANS="Medel"`, så alla Medel inkluderas)

## Cache-format (`bedomning_cache.json`)

Dict med `artikel_id` (md5 av artikel-URL) som nyckel.

**Per artikel som passerar filtret:**
```json
{
  "relevant": true,
  "relevansniva": "Hog",
  "poang": 8,
  "sammanfattning": "...",
  "motivering": "...",
  "kontextsokord": ["sökord1", "sökord2"]
}
```

**Per artikel som inte passerar filtret** (bedömd men irrelevant):
```json
null
```

Detta gör att framtida körningar inte bedömer samma artikel igen.

## Process

1. Läs `obedoma_artiklar.json`
2. Beräkna `artikel_id` för varje artikel (md5 av URL — `hashlib.md5(url.encode()).hexdigest()`)
3. För varje artikel som INTE finns i `bedomning_cache.json`: lägg till i batch
4. Skicka batchar om 10 artiklar enligt prompten ovan
5. För varje JSON-svar: applicera filter, skriv till `bedomning_cache.json`
6. När alla batchar är klara, säg till så `python3 bevakning_serper.py --rendera` kan köras
