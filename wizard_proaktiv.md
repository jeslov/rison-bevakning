# Wizard – Generera proaktivt LinkedIn-inlägg

Detta är instruktionerna för Claude Code att följa när Jesper säger "kör wizard_proaktiv" eller "generera proaktivt förslag".

## Steg 1: Sessionsstart
Verifiera enligt CLAUDE.md att MD5 av bevakning_serper.py matchar senaste commit. Om mismatch – stoppa och rapportera.

## Steg 2: Generera prompten
Kör python3 proaktiv.py för att se den aktuella prompten med teser och bevakningsbild inläst.

## Steg 3: Välj tes
Läs prompten och välj den tes (1, 2 eller 3) som har starkast aktuellt stöd i bevakningsbilden. Motivera valet kort.

Försök variera tesen mellan körningar om bevakningsbilden tillåter – titta i proaktiv_cache.json vilka teser som drivit de senaste tre förslagen och välj annan om möjligt.

## Steg 4: Sök kompletterande källor
Sök på webben efter 1-3 oberoende, institutionella källor:
- Myndigheter: Boverket, Energimyndigheten, Naturvårdsverket, Riksdagen
- Internationella institutioner: IEA, ADB, IPCC, OECD, IMF, EU-kommissionen
- Akademiska studier
- Kvalificerade branschpublikationer

Inte bara nyhetsartiklar. Inte bara samma källor som tidigare förslag i cachen om möjligt.

## Steg 5: Skriv inlägget
Följ alla regler i prompten – särskilt:
- 500-3000 tecken
- Obligatorisk konkret liknelse eller skarp omramning
- Ingen finansjargong utan att förklaras vardagligt
- Inga mekaniska beskrivningar av Risons modell eller EaaS
- Hashtags och eventuell artikel-URL på sista raden

## Steg 6: Spara
Anropa proaktiv.spara_forslag(tes=..., rubrik=..., text=..., kallor=[...], refererar_till_artikel=...) direkt i sessionen. Spara även en dump till tempfil för läsning.

## Steg 6.5: Uppdatera HTML
Anropa proaktiv.uppdatera_html_med_forslag() i samma session så att index.html visar det nyligen sparade förslaget.

## Steg 7: Mätningar
Kör de tre programmatiska mätningarna för mekanik, rapportstil och jargong. Förväntat: alla tre 0.

## Steg 8: Rapportera
Kort sammanfattning till Jesper:
- Vald tes och kort motivering
- Använda källor (3-4 URL:er)
- Liknelse/omramning som användes
- Tre mätningar (mekanik / rapportstil / jargong)
- Antal tecken
- Eventuellt refererad artikel

Inget auto-commit förrän Jesper har sett och godkänt förslaget. Om Jesper säger "godkänd" eller "OK" – då räknas det som att autopush får committa.

Om något i prompten är oklart eller bevakningsbilden är tom – fråga, gissa inte.
