# Backlog – tekniska skulder och uppskjutna förbättringar

*Saker som bör fixas men inte är akuta. Skapad 2026-05-04 under proaktiv-implementationen.*

## Encoding-bug i HTML-genereringen
Relevansnivå "Hög" renderas som "Hog" i index.html. proaktiv.py översätter tillbaka i parsningen, men källfelet finns i bevakning_serper.py och bör fixas vid lämpligt tillfälle.

## SyntaxWarning i bevakning_serper.py
Rad 806: `"\)" is an invalid escape sequence`. Liknande typ av problem som backslash-buggen vi fixade på rad 679. Kör inte fel idag men varnar i loggarna.

## Strukturerat datum i bedomning_cache.json
Datum finns i pipelinen (RSS pubDate som ISO, Serper date som naturligt språk) men persisteras bara som visningssträng i index.html. Lägg till "datum" som strukturerat fält i cachen så att proaktiv.py och framtida funktioner inte behöver gå via HTML-parsning.

## Git-författarnamn felkonfigurerat
Commit-meddelanden visar `"Jesper <jesperlovkvist@mac.lan>` (med inledande citattecken och .lan-domän). Bör konfigureras om till korrekt namn och e-post:
git config --global user.name "Jesper Lövkvist"
git config --global user.email "jesper@utopia.se"

## Prompt-refaktorisering till stilprincip
v3 och v4 har lagt till specifika förbud mot exakta formuleringar (t.ex. "tredje part står för investeringen"). Det är effektivt på kort sikt men skapar en växande lista av post-hoc-regler. På sikt: omformulera specifika förbud till en allmän stilprincip som täcker fler liknande fall.
