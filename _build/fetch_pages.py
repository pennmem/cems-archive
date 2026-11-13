"""Download raw (toolbar-free) Wayback snapshots of the old CEMS wiki pages.

Usage: python fetch_pages.py RAW_DIR
Writes RAW_DIR/<PageName>.html plus RAW_DIR/pages.json (page -> snapshot timestamp).
"""
import json
import sys
import time
from pathlib import Path

import requests

PAGES = ["CEMS"] + [f"CEMS_{y}" for y in range(2009, 2025) if y != 2016] + [
    "CEMS_2026", "CEMS_2015_registration", "MBC2023"]
SITE = "https://memory.psych.upenn.edu/"
UA = {"User-Agent": "cems-archive-restore/1.0"}


def snapshot(page):
    r = requests.get("https://archive.org/wayback/available",
                     params={"url": "memory.psych.upenn.edu/" + page}, headers=UA, timeout=60)
    snap = r.json().get("archived_snapshots", {}).get("closest")
    return snap["timestamp"] if snap and snap.get("status") == "200" else None


def main(raw_dir):
    raw = Path(raw_dir)
    raw.mkdir(parents=True, exist_ok=True)
    meta = {}
    for page in PAGES:
        out = raw / f"{page}.html"
        ts = snapshot(page)
        if not ts:
            print(f"{page}: no snapshot")
            continue
        meta[page] = ts
        if out.exists():
            continue
        url = f"https://web.archive.org/web/{ts}id_/{SITE}{page}"
        for attempt in range(4):
            try:
                r = requests.get(url, headers=UA, timeout=90)
                r.raise_for_status()
                out.write_bytes(r.content)
                print(f"{page}: {ts} {len(r.content)} bytes")
                break
            except Exception as e:  # Wayback is flaky; back off and retry
                print(f"{page}: attempt {attempt + 1} failed ({e})")
                time.sleep(5 * (attempt + 1))
        time.sleep(1)
    (raw / "pages.json").write_text(json.dumps(meta, indent=1))


if __name__ == "__main__":
    main(sys.argv[1])
