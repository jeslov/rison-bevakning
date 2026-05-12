# Wizard – Komplett bevaknings-körning

Detta är instruktionerna för Claude Code att följa när Jesper säger "Kör wizard_bevakning" eller "Uppdatera bevakningen".

Wizarden kör hela kedjan automatiskt utan att stoppa för bekräftelse. Stoppa bara om något kritiskt går fel.

## Steg 1: Sessionsstart
Verifiera arbetskatalogens tillstånd:
- Kör git status och se om bevakning_serper.py har okommitterade ändringar
- Om filen är ren eller bara har förväntad drift (t.ex. wizard_bevakning.md untracked): fortsätt
- Om bevakning_serper.py har okänd modifiering: stoppa och rapportera

## Steg 2: Hämta artiklar
Kör i terminal:
cd ~/rison-bevakning && set -a && source .env && set +a && python3 bevakning_serper.py --hamta

Förväntat utfall: obedoma_artiklar.json, grupper_cache.json, run_state.json skapas/uppdateras. Eventuellt även titlar_for_zeitgeist.json om zeitgeist behöver uppdateras.

Notera antal artiklar i obedoma. Om 0: rapportera och stoppa (inget att bedöma).

## Steg 3: Uppdatera zeitgeist (om filen finns)
Kontrollera om titlar_for_zeitgeist.json finns:
ls -la ~/rison-bevakning/titlar_for_zeitgeist.json

Om filen finns:
1. Läs ~/rison-bevakning/zeitgeist_prompt.md för prompt-format och Risons kontext
2. Läs titlar_for_zeitgeist.json (lista med upp till 150 titlar+snippets)
3. Bygg prompten enligt mallen i zeitgeist_prompt.md
4. Generera 5 teman + 8 sökord enligt prompten
5. Skriv resultatet till zeitgeist_cache.json med format: datum (ISO datetime), teman (lista), sokord (lista)
6. Radera titlar_for_zeitgeist.json (behövs inte längre)

Om filen inte finns: skippa Steg 3.

## Steg 4: Uppdatera dagsaktuella (om behövs)
Läs dagsaktuella_cache.json.

Bestäm om uppdatering behövs:
- Filen saknas → uppdatera
- datum är inte idag (YYYY-MM-DD) → uppdatera
- sokord är tom lista (även om datum=idag) → uppdatera

Om uppdatering behövs:
1. Läs ~/rison-bevakning/dagsaktuella_prompt.md för prompt-format
2. Läs zeitgeist_cache.json för aktuella zeitgeist-sökord (kan vara tom lista)
3. Bestäm säsong utifrån månaden (se tabell i dagsaktuella_prompt.md)
4. Bygg prompten, generera 3 sökord
5. Skriv till dagsaktuella_cache.json med format: datum (YYYY-MM-DD idag), sokord (lista med 3 sträng)

Om uppdatering INTE behövs: skippa Steg 4.

## Steg 5: Bedöm nya artiklar
Läs ~/rison-bevakning/bedom_prompt.md för prompt-format och Risons kontext.

Läs ~/rison-bevakning/obedoma_artiklar.json.

Läs ~/rison-bevakning/bedomning_cache.json (kan vara tom eller saknas).

För varje artikel i obedoma:
- Beräkna artikel_id = md5(url)
- Om aid finns i bedomning_cache: skippa (redan bedömd)
- Annars: lägg till i "att bedöma"-lista

Om att-bedöma-listan är tom: skippa till Steg 6.

Annars: bedöm i batchar om 10 artiklar enligt prompten:

För varje batch:
1. Formatera artiklar enligt mall (titel, källa, text trunkerad till 2000 tecken)
2. Skicka batchen till modellen enligt bedom_prompt.md
3. Parsa JSON-svar
4. För varje resultat:
   - Om relevant=true och relevansniva ∈ Hog, Medel: spara hela bedömningsobjektet i bedomning_cache.json under aid
   - Annars: spara null under aid
5. Skriv bedomning_cache.json efter VARJE batch (persistens vid avbrott)

## Steg 6: Rendera HTML
Kör i terminal:
cd ~/rison-bevakning && set -a && source .env && set +a && python3 bevakning_serper.py --rendera

Detta läser alla caches och bygger index.html med tab-UI (bevakning + proaktiv).

## Steg 7: Rapportera till Jesper
Sammanfattning:
- Antal hämtade artiklar (från obedoma_artiklar.json)
- Antal nya artiklar bedömda (från Steg 5)
- Antal relevanta (höga + medel från --rendera-utskriften)
- Eventuell zeitgeist-uppdatering (skedde / skedde ej)
- Eventuell dagsaktuella-uppdatering (skedde / skedde ej)
- HTML sparad till: ~/rison-bevakning/index.html

Påminn Jesper att öppna index.html i webbläsare:
open ~/rison-bevakning/index.html

## Felhantering
Om något steg går fel:
- Stoppa direkt
- Rapportera vad som hände
- Rapportera vilket steg som var sista lyckade
- Föreslå nästa åtgärd

Inga steg ska "fortsätta trots fel". Bevakningen är inte värd att korrumpera halvvägs.

## Auto-commit
Wizarden gör INGA git-commits. Autopush.sh sköter det när Jesper är redo.
