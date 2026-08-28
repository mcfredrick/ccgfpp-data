#!/usr/bin/env python3
"""Pull harvest records from Airtable into the same tidy JSON/CSV format the
site reads.

Airtable (not the Google Sheet) is the source of truth going forward -- see
data/crop_mapping.json's note and scripts/parse_sheet.py's docstring for how
the original 2022-2025 data was migrated in. This script is what regenerates
data/tidy/ after new records are added in Airtable.

Requires AIRTABLE_TOKEN and AIRTABLE_BASE_ID in a .env file at the project
root (gitignored -- never commit these). Uses only the standard library so
running this doesn't require installing anything.
"""
import csv
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).parent.parent
TIDY_DIR = ROOT / "data" / "tidy"
TABLE_NAME = "Harvests"


def load_env():
    env = dict(os.environ)
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env.setdefault(k, v)
    return env


def fetch_all_records(token, base_id):
    records = []
    offset = None
    while True:
        params = {"pageSize": 100}
        if offset:
            params["offset"] = offset
        url = f"https://api.airtable.com/v0/{base_id}/{urllib.parse.quote(TABLE_NAME)}?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
        with urllib.request.urlopen(req) as resp:
            page = json.loads(resp.read().decode())
        records.extend(page["records"])
        offset = page.get("offset")
        if not offset:
            break
    return records


def to_tidy(records):
    tidy = []
    skipped = 0
    for r in records:
        f = r["fields"]
        if not all(k in f for k in ("Date", "Crop", "Unit", "Quantity", "Year")):
            skipped += 1  # an in-progress row someone hasn't finished filling in
            continue
        tidy.append({
            "year": f["Year"],
            "crop": f["Crop"],
            "unit": f["Unit"],
            "date": f["Date"],
            "quantity": f["Quantity"],
            "donated": f.get("Donated", False),
        })
    tidy.sort(key=lambda r: (r["year"], r["crop"], r["date"]))
    return tidy, skipped


def main():
    env = load_env()
    token = env.get("AIRTABLE_TOKEN")
    base_id = env.get("AIRTABLE_BASE_ID")
    if not token or not base_id or "your_" in (token or "") + (base_id or ""):
        raise SystemExit("AIRTABLE_TOKEN and AIRTABLE_BASE_ID must be set in .env (see .env for placeholders)")

    records = fetch_all_records(token, base_id)
    tidy, skipped = to_tidy(records)

    TIDY_DIR.mkdir(parents=True, exist_ok=True)
    (TIDY_DIR / "harvests.json").write_text(json.dumps(tidy, indent=2))
    with (TIDY_DIR / "harvests.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["year", "crop", "unit", "date", "quantity", "donated"])
        writer.writeheader()
        writer.writerows(tidy)

    years = sorted(set(r["year"] for r in tidy))
    print(f"Pulled {len(tidy)} records from Airtable across years: {years}")
    print(f"Distinct crops: {len(set(r['crop'] for r in tidy))}")
    if skipped:
        print(f"Skipped {skipped} incomplete row(s) (missing Date/Crop/Unit/Quantity)")


if __name__ == "__main__":
    main()
