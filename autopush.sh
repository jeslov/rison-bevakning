#!/bin/bash
cd ~/rison-bevakning
echo "Bevakar ändringar i ~/rison-bevakning..."
fswatch -o -r . --exclude='.git' --exclude='__pycache__' --exclude='.DS_Store' . | while read; do
    sleep 2
    git add -A
    if git diff --staged --quiet; then
        echo "$(date '+%H:%M') no changes, skipping"
    else
        CHECKSUM=$(md5 -q bevakning_serper.py)
        CHANGED=$(git diff --cached --name-only)
        if echo "$CHANGED" | grep -qE '\.(py|md)$|_cache\.json$|autopush\.sh$|\.gitignore$'; then
            PREFIX="[code]"
        else
            PREFIX="[report]"
        fi
        git commit -m "${PREFIX} Auto-commit $(date '+%Y-%m-%d %H:%M') [md5:${CHECKSUM}]" && git push && echo "Pushad $(date '+%H:%M') ${PREFIX}"
    fi
done
