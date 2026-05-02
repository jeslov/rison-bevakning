# Arbetsregler – Rison Bevakning

## Hårda regler (bryts aldrig)
- Gör alltid minimala kirurgiska ändringar – aldrig omskrivning av hela block
- Kör syntaxkontroll EFTER varje ändring innan commit
- Verifiera att inget befintligt innehåll försvunnit efter varje ändring
- Aldrig generera HTML utan att syntaxkontroll passerat
- Vid fel i arbetssättet: lägg till regel i denna fil omedelbart

## Sessionsstart
Kör automatiskt vid varje ny session:
\`\`\`bash
md5 ~/rison-bevakning/bevakning_serper.py
git -C ~/rison-bevakning log --oneline -1
\`\`\`
Verifiera att MD5 matchar checksumman i senaste commit-meddelandet. Om inte – stoppa och rapportera till Jesper innan något ändras.

## Arbetsflöde vid ändring
1. Läs hela det berörda blocket med \`sed -n\` eller \`grep\` innan ändring föreslås
2. Gör minimal kirurgisk ändring
3. Kör syntaxkontroll:
   \`\`\`bash
   python3 -c "import py_compile; py_compile.compile('/Users/jesperlovkvist/rison-bevakning/bevakning_serper.py', doraise=True); print('Syntax OK')"
   \`\`\`
4. Verifiera att inget innehåll försvunnit
5. **Auto-commit efter syntax OK** med beskrivande commit-meddelande som inkluderar ny MD5
6. Påminn om cache-rensning enligt tabell nedan

## Feldiagnostik
- Kör \`sed -n\` och \`grep\` för att hitta exakt innehåll i filen innan fix föreslås
- Aldrig be Jesper debugga – det är Claudes ansvar
- Om syntaxkontroll misslyckas: rulla tillbaka ändringen och rapportera felet, gör inte commit

## Prompt-innehåll i \`kopiera_prompt\`
Måste alltid finnas:
- Rubrik max 8 ord
- Källreferenser och organisationshänvisningar naturligt i brödtexten
- STEG 1: Faktaverifiering mot oberoende källor innan utkast
- STEG 2: Utkast i klartext utan @-slugs
- STEG 3: Slug-sökning efter att utkastet är klart
- Max 3000 tecken
- Hashtags och URL på sista raden

## Cache-rensning
Påminn alltid när ändring påverkar bedömningar eller sökord:

| Ändring | Rensa |
|---------|-------|
| Prompt-ändringar | \`bedomning_cache.json\` |
| Zeitgeist-prompt | \`zeitgeist_cache.json\` |
| Dagsaktuella-prompt | \`dagsaktuella_cache.json\` |

## Auto-tillåtna kommandon
Följande kommandon kräver inte godkännande:
- Läsoperationer: md5, sed -n, grep, head, tail, cat, ls, wc, git status, git log, git diff, git show
- Syntaxkontroll: python3 -c "import py_compile..."
- Skriptkörning: python3 bevakning_serper.py
- Git-operationer (auto-commit redan godkänd): git add, git commit, git push

Kommandon som ALLTID kräver explicit godkännande:
- Destruktiva git-operationer: git reset --hard, git push --force, git rebase
- Filborttagning: rm (även cache-filer)
- Operationer utanför ~/rison-bevakning/

## Cloudflare Worker
Senaste fungerande Worker-kod finns i Cloudflare dashboard:
\`risonbevakning.jesper-75b.workers.dev\`

Backup hanteras där, inte i denna fil eller repo.
# Test 1: kod-ändring
