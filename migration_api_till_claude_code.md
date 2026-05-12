# Migration: bevakning_serper.py från API till Claude Code

## Bakgrund
2026-05-12 upptäcktes att Anthropic API-kontot har slut på krediter (HTTP 400 "Your credit balance is too low"). Jesper har Pro/Max-abonnemang som täcker Claude Code men inte direkt API-användning. Beslut: gör bevakning_serper.py helt API-oberoende.

## Beslutade arkitekturval (2026-05-12)
1. En wizard: wizard_bevakning.md
2. En fil: bevakning_serper.py med CLI-flaggor
3. Default är fil-baserad. Inget API-anrop någonsin i normalt flöde
4. Skript som datapump, Claude Code som hjärna
5. Synk via JSON-filer på disk (--hamta producerar, --rendera konsumerar)

## Nytt flöde

```
Steg 1: Claude Code säger "Kör wizard_bevakning"
Steg 2: Wizard kör python3 bevakning_serper.py --hamta
        - Hämtar artiklar från RSS + Serper (normalt)
        - Skippar ALLT som behöver API: zeitgeist, dagsaktuella, bedömning
        - Skriver obedoma_artiklar.json med nya artiklar
        - Skriver eventuella status-filer (t.ex. zeitgeist_behovs_uppdateras.flag)
Steg 3: Wizard läser obedoma_artiklar.json + checkar flaggor
Steg 4: Om zeitgeist-uppdatering behövs (var 7e dag):
        - Claude Code läser 150 titlar från titlar_for_zeitgeist.json
        - Bedömer i sessionen, skriver zeitgeist_cache.json
Steg 5: Om dagsaktuella behövs (varje körning):
        - Claude Code läser zeitgeist_cache.json + säsongsinfo
        - Genererar 3 sökord, skriver dagsaktuella_cache.json
Steg 6: Bedömning av nya artiklar:
        - Claude Code läser obedoma_artiklar.json
        - För varje batch om 10: bedömer enligt prompt, uppdaterar bedomning_cache.json
Steg 7: Wizard kör python3 bevakning_serper.py --rendera
        - Läser alla caches
        - Renderar index.html med tab-UI för bevakning + proaktiv
Steg 8: Wizard kör proaktiv.uppdatera_html_med_forslag()
Steg 9: Rapporterar tillbaka till Jesper
```

## Filer som skapas/förändras

### Nya filer
- `obedoma_artiklar.json` – RSS+Serper-resultat efter dubblettfiltrering, väntar på bedömning
- `titlar_for_zeitgeist.json` – 150 titlar+snippets för zeitgeist-analys (om uppdatering behövs)
- `wizard_bevakning.md` – instruktion för Claude Code
- `migration_api_till_claude_code.md` – detta dokument

### Förändrade filer
- `bevakning_serper.py` – får --hamta och --rendera flaggor, AI-stegen tas bort
- `bedomning_cache.json` – uppdateras av Claude Code istället för bedom_batch
- `zeitgeist_cache.json` – uppdateras av Claude Code istället för uppdatera_zeitgeist
- `dagsaktuella_cache.json` – uppdateras av Claude Code istället för hamta_dagsaktuella

### Filer som inte ändras
- `proaktiv.py` (klart sedan tidigare)
- `index.html` (genereras som idag)
- `teser.md`, `teser_med_underlag.md`
- `wizard_proaktiv.md`

## Implementeringsordning

Vi gör en migrering i taget och testar mellan varje. Riv inte gammal kod förrän nytt fungerar.

### Fas A: Förbered CLI-skelett (30 min)
1. Lägg till argparse i bevakning_serper.py – tre flaggor: --hamta, --rendera, ingen flagga ger felmeddelande
2. main() splittas i `kor_hamtning()` och `kor_rendering()`
3. claude_anrop() finns kvar, används inte ännu
4. TEST: python3 bevakning_serper.py --hamta körs utan crash, skriver obedoma_artiklar.json

### Fas B: Migrera bedömning (60 min)
1. bedom_med_cache() i --hamta-läget skippas helt
2. Wizard läser obedoma_artiklar.json, bedömer i Claude Code, skriver bedomning_cache.json
3. TEST: bedömning ger antal relevanta i samma härad som tidigare (4 Hög + 3 Medel ± 1)
4. Behåll bedom_batch() i koden men markera som DEAD CODE

### Fas C: Migrera zeitgeist (30 min)
1. uppdatera_zeitgeist() i --hamta-läget skippas
2. Skriptet skriver titlar_for_zeitgeist.json om uppdatering behövs
3. Wizard läser, gör zeitgeist-analys, skriver zeitgeist_cache.json
4. TEST: zeitgeist genereras med 5 teman + 8 sökord

### Fas D: Migrera dagsaktuella (30 min)
1. hamta_dagsaktuella() i --hamta-läget skippas
2. Wizard läser zeitgeist + säsongsinfo, genererar 3 sökord, skriver dagsaktuella_cache.json
3. TEST: dagsaktuella ger 3 rimliga svenska sökord

### Fas E: Rendering-läget (15 min)
1. --rendera-läget läser alla caches och skapar HTML
2. TEST: index.html innehåller alla bedömda artiklar korrekt

### Fas F: Wizard-fil (30 min)
1. Skapa wizard_bevakning.md med alla steg
2. TEST: full körning "Kör wizard_bevakning" från noll

### Fas G: Rensa upp (15 min)
1. Ta bort claude_anrop()-funktionen helt
2. Ta bort ANTHROPIC_API_KEY-användning från koden
3. Behåll i .env-filen för referens men markera som unused
4. Commita

## Säkerhet under migrering
- Autopush stoppad under hela migreringen
- Manuella commits efter varje fas som passerar test
- Snapshot kvar på disk: ~/rison-bevakning-snapshot-20260512-094330
- Tag pre-migration-api kvar i git

## Återställningsväg vid haveri
git -C ~/rison-bevakning checkout pre-migration-api -- bevakning_serper.py
git -C ~/rison-bevakning commit -m "[code] Rulla tillbaka till pre-migration-api"

eller hela katalogen:
rm -rf ~/rison-bevakning
mv ~/rison-bevakning-snapshot-20260512-094330 ~/rison-bevakning

## Estimerad total tid: 3-4 timmar
