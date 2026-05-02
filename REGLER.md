# Arbetsregler för Claude – Rison Bevakning

## Vid sessionsstart
- Kör `md5 ~/rison-bevakning/bevakning_serper.py` och jämför med senaste checksumma i git-loggen
- Läs denna fil och bekräfta att reglerna är förstådda

## Kvalitetskontroll vid varje ändring
- Läs igenom hela det berörda blocket INNAN du föreslår en ändring
- Gör alltid minimala kirurgiska ändringar – skriv aldrig om hela block
- Kör alltid syntaxkontroll efter varje ändring: `python3 -c "import py_compile; py_compile.compile('/Users/jesperlovkvist/rison-bevakning/bevakning_serper.py', doraise=True); print('Syntax OK')"`
- Verifiera att inget befintligt innehåll har försvunnit efter varje ändring

## Prompt-innehåll som alltid måste finnas i kopiera_prompt
- Rubrik på max 8 ord
- Källreferenser och organisationshänvisningar naturligt i brödtexten
- STEG 1: Faktaverifiering mot oberoende källor innan utkastet skrivs
- STEG 2: Utkast i klartext utan @-slugs
- STEG 3: Slug-sökning först efter att utkastet är klart
- Max 3000 tecken
- Hashtags och URL på sista raden

## Generella arbetsregler
- Aldrig skriva om hela block – gör minimala ändringar
- Syntaxkontroll körs alltid av Claude INNAN kod föreslås och EFTER att ändring bekräftats – aldrig av Jesper
- Aldrig generera HTML utan att syntaxkontroll passerat
- Aldrig föreslå nedladdning av filer – gör ändringar direkt i terminalen
- Om Jesper påtalar fel i arbetssättet – addera ny regel i denna fil omedelbart
