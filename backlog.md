# Backlog – tekniska skulder och uppskjutna förbättringar

*Saker som bör fixas men inte är akuta. Skapad 2026-05-04 under proaktiv-implementationen.*

## Encoding-bug i HTML-genereringen
Relevansnivå "Hög" renderas som "Hog" i index.html. proaktiv.py översätter tillbaka i parsningen, men källfelet finns i bevakning_serper.py och bör fixas vid lämpligt tillfälle.

## SyntaxWarning i bevakning_serper.py
Rad 806: `"\)" is an invalid escape sequence`. Liknande typ av problem som backslash-buggen vi fixade på rad 679. Kör inte fel idag men varnar i loggarna.

## Strukturerat datum i bedomning_cache.json
Datum finns i pipelinen (RSS pubDate som ISO, Serper date som naturligt språk) men persisteras bara som visningssträng i index.html. Lägg till "datum" som strukturerat fält i cachen så att proaktiv.py och framtida funktioner inte behöver gå via HTML-parsning.
