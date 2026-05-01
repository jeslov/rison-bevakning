#!/bin/bash
cd ~/rison-bevakning
echo "Bevakar ändringar i ~/rison-bevakning..."
fswatch -o -r . --exclude='.git' --exclude='__pycache__' --exclude='.DS_Store' . | while read; do
    sleep 2
    md5 -q bevakning_serper.py > .checksum
    git add -A
    CHECKSUM=$(cat .checksum)
    if ! git diff --staged --quiet; then
        git commit -m "Auto-commit $(date '+%Y-%m-%d %H:%M') [md5:${CHECKSUM}]" && git push && echo "Pushad $(date '+%H:%M')"
    fi
done
