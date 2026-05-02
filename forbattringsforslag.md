---

# Förbättringsförslag – Rison Bevakning

*Skapad 2026-05-02 av Claude (chat-session)*
*Syfte: löpande publicera inlägg som genererar stort intresse, bygger kännedom och positiva varumärkeskonotationer.*

## Förutsättning
Förslagen är baserade på vad jag sett i sessionen (autopush, JavaScript-bug i kopiera_prompt, allmän struktur) – inte fullständig insyn i tjänsten. Vissa kan redan finnas, andra kan vara orelevanta.

## Konceptuella förbättringar

### 1. Vinkel före kopiering
Idag genererar prompten ett färdigt utkast på ett standardiserat sätt. För riktigt delningsbara inlägg behöver man välja vinkel medvetet: kontroversiell take, branschinsikt, personlig story, datapunkt som överraskar, motargument mot konsensus. Lägg till ett vinkelval i UI:t innan kopiering – tre–fyra vinklar per artikel som genereras parallellt, du väljer den som ger mest energi just den dagen. *Genererar mer variation, undviker att alla inlägg låter likadana.*

### 2. Kontext som bygger kännedom över tid
Ett inlägg som står ensamt landar svagare än ett som bygger på det förra. Lägg till en "tråd-medvetenhet" – tjänsten vet vad du publicerat senaste 30 dagarna och föreslår vinklar som bygger vidare på eller medvetet bryter mot tidigare positioner. *Skapar narrativ över tid, vilket är vad varumärkesbyggande faktiskt är.*

### 3. Engagemangsåterkoppling
Idag är flödet en envägsgata: artikel → utkast → publicering. Inga signaler kommer tillbaka. Lägg till en lätt registrering av hur varje publicerat inlägg presterade (gillanden, kommentarer, visningar – manuellt eller via LinkedIn-API om det är realistiskt). Använd det till att träna prompten över tid: "vinklar som funkat tidigare för dig". *Tjänsten lär sig din röst och din publik.*

### 4. Förlängningar utöver LinkedIn
Ett intressant inlägg kan återanvändas som nyhetsbrev, kort video-script, citattavla för Instagram, eller pitch-mejl till en tänkt kund. Lägg till "remix-knappar" som tar samma artikel + vinkel och spottar ut alternativa format. *Multiplicera värdet av varje genererat utkast.*

### 5. Publiceringsfönster och tempo
Ett inlägg om dagen kan bli brus. Två starka i veckan kan bli signal. Lägg till en "hold"-funktion där tjänsten parkerar svagare utkast och föreslår dem nästa vecka om inget bättre kommit in – plus att den varnar om du publicerat tre likartade inlägg i rad.

## Tekniska förbättringar

### 1. Ren separation: data, prompt, render
Just nu blandar Python-filen HTML-template, JavaScript-kod, prompt-text och bedömningslogik (det är därför vi precis fick en JavaScript-bug i ett Python-uttryck). Bryt ut prompten till `prompt_template.txt`, JavaScript till `app.js`, HTML-skelett till `template.html`. Python genererar bara data-JSON som JavaScript läser. *Buggen vi just fixade hade aldrig kunnat uppstå med den arkitekturen.*

### 2. Versioning av prompt-iterationer
Du kommer iterera på prompten i `kopiera_prompt` länge. Spara varje version med datum och kort kommentar (`prompts/2026-05-02-vinkel-fokus.txt`). När ett inlägg presterat bra: koppla det till vilken prompt-version som genererade det. *Du ser empiriskt vilka prompt-ändringar som faktiskt hjälpte.*

### 3. A/B-test av rubriker
Generera tre rubrikalternativ per inlägg, inte ett. Du väljer själv vid publicering. Över tid: mönster blir synliga. *Rubriken är det som avgör om inlägget öppnas alls.*

### 4. Faktaverifiering som hård gate, inte bara ett steg
Idag säger CLAUDE.md att STEG 1 är faktaverifiering, men det är upp till modellen att lyda. Bygg in det som ett separat API-anrop: "innan du genererar utkast, returnera en JSON med {påståenden_i_artikeln, verifieringsstatus}". Om något är overifierat: visa varning i UI innan kopiering. *Skydd mot att publicera fel siffror eller felaktiga citat under ditt namn.*

### 5. Mätbar bedömningskvalitet
`bedomning_cache.json` innehåller hög/medel/låg-bedömningar. Spara också varför (kort motivering från modellen) och låt dig markera "håller med" / "håller inte med" i UI:t. När fel ackumuleras: justera bedömningsprompt. *Just nu är cachen en black box.*

### 6. Worker som tunnt skal
Cloudflare Worker:n hanterar nu både Serper-anrop och Anthropic-anrop med tools. Det är OK, men varje schema-ändring kräver dashboard-deploy. Flytta så mycket som möjligt till klientside eller till Python-skriptet, och låt Worker:n bara vara en API-key-skyddande proxy. *Mindre rörliga delar, mindre att deploya.*

### 7. End-to-end-test före publicering
Lägg till `tests/smoke_test.py` som kör hela kedjan med en känd artikel och verifierar att HTML-output är giltig, JavaScript parsar med Node, och att prompten innehåller alla obligatoriska delar enligt CLAUDE.md. Kör det innan varje commit i en pre-commit-hook. *Buggen vi precis fixade hade fångats automatiskt.*

## Prioritering (förslag)

Om bara tre ska startas med:
1. **Smoke-test med Node-validering** – billigast, fångar buggar som den vi precis hade. Liten ändring, stort skydd.
2. **Tråd-medvetenhet** – det är det som faktiskt bygger varumärke. Ett enskilt bra inlägg är värt mindre än fem inlägg som tillsammans säger något.
3. **Engagemangsåterkoppling** – utan den iterar du blint. Med den blir tjänsten bättre för varje vecka.
