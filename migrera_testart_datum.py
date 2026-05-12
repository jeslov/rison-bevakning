#!/usr/bin/env python3
"""Engångsmigrering: konvertera relativa datum i testart_artiklar.json till ISO.
Använder filens mtime som referenspunkt så datumen blir historiskt korrekta."""

import json
import re
import os
from pathlib import Path
from datetime import datetime, timedelta

TESTART_FILE = Path(__file__).parent / "testart_artiklar.json"
BACKUP_FILE = Path(__file__).parent / "testart_artiklar.json.pre-datum-migration"

def _parse_relativt_med_referens(s, ref_dt):
    """Som _parse_relativt_datum men med valbar referens-tid."""
    if not s or not isinstance(s, str):
        return ""
    t = s.strip().lower()
    if not t:
        return ""
    if t in ("igår", "yesterday"):
        return (ref_dt - timedelta(days=1)).strftime("%Y-%m-%d")
    if t in ("idag", "today", "just nu", "now"):
        return ref_dt.strftime("%Y-%m-%d")
    if "stund" in t or "moment" in t:
        return ref_dt.strftime("%Y-%m-%d")
    m = re.search(r'(\d+|en|ett)\s*(minut|timm|dag|veck|månad|min|hour|day|week|month)', t)
    if not m:
        return ""
    n_str = m.group(1)
    n = 1 if n_str in ("en", "ett") else int(n_str)
    enhet = m.group(2)
    if enhet.startswith("min"):
        return (ref_dt - timedelta(minutes=n)).strftime("%Y-%m-%d")
    if enhet in ("timm", "hour"):
        return (ref_dt - timedelta(hours=n)).strftime("%Y-%m-%d")
    if enhet in ("dag", "day"):
        return (ref_dt - timedelta(days=n)).strftime("%Y-%m-%d")
    if enhet in ("veck", "week"):
        return (ref_dt - timedelta(weeks=n)).strftime("%Y-%m-%d")
    if enhet in ("månad", "month"):
        return (ref_dt - timedelta(days=n*30)).strftime("%Y-%m-%d")
    return ""

def main():
    if not TESTART_FILE.exists():
        print(f"FEL: {TESTART_FILE} saknas")
        return

    mtime = datetime.fromtimestamp(os.path.getmtime(TESTART_FILE))
    print(f"Använder mtime som referens: {mtime}")

    artiklar = json.loads(TESTART_FILE.read_text())
    print(f"Läste {len(artiklar)} artiklar")

    # Backup
    BACKUP_FILE.write_text(TESTART_FILE.read_text())
    print(f"Backup: {BACKUP_FILE.name}")

    # Migrera
    konverterade = 0
    for a in artiklar:
        gammal = a.get("datum", "")
        if not gammal:
            continue
        # Skippa om redan ISO
        if re.match(r'^\d{4}-\d{2}-\d{2}', gammal):
            continue
        ny = _parse_relativt_med_referens(gammal, mtime)
        if ny:
            a["datum"] = ny
            konverterade += 1
            print(f"  {gammal!r:30} -> {ny}")
        else:
            print(f"  {gammal!r:30} -> KUNDE EJ PARSAS, behåller")

    TESTART_FILE.write_text(json.dumps(artiklar, ensure_ascii=False, indent=2))
    print(f"\nKonverterade {konverterade} av {len(artiklar)} artiklar")
    print(f"Skrev: {TESTART_FILE.name}")

if __name__ == "__main__":
    main()
