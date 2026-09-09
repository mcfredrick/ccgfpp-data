#!/usr/bin/env python3
"""One-time parser for the 2026 collated harvest list (2026_collated.txt) into
Airtable-ready records. Not a general email parser -- this file has its own
particular format (date header, then bare "N cropname" lines). The real
weekly-email parser (freeform prose) is a separate, harder problem.

Unit convention (per user decision, 2026-09-08):
- Explicit "bag(s)" wording, or no unit given for a normally bunch-tracked
  crop -> unit "bags/bunches" (a deliberate consolidation label, not a claim
  that a bag == a bunch in the historical "bunch" data -- see design-notes).
- Qualitative amounts ("a handful") -> quantity 1, unit "bags/bunches", noted
  as approximate.
- Explicit numeric units (pt/pint, lb/pound, head, half pint) -> used as given.
- No unit given for a normally count-tracked crop (peppers, squash, zucchini,
  cucumbers, tomatoes) -> unit "#", matching that crop's historical convention.
- A two-date block ("8/19 & 8/20") splits its totals evenly across both real
  dates, noted as a combined-report split, per user decision.
"""
import json
import re
from pathlib import Path

RAW_PATH = Path(__file__).parent.parent / "data" / "raw" / "2026_collated.txt"
OUT_PATH = Path(__file__).parent.parent / "data" / "staged" / "2026_collated_parsed.json"
FLAGGED_OUT_PATH = Path(__file__).parent.parent / "data" / "staged" / "2026_collated_flagged.json"

BUNCH_TYPE_CROPS = {
    "Kale", "Swiss Chard", "Lettuce", "Radishes", "Beets", "Carrots", "Turnips",
    "Green beans", "Garlic scapes", "Bok choy", "Mesclun Mix", "Collards", "Cilantro",
}

# (regex fragment matched case-insensitively against the line, canonical crop, note-if-matched)
CROP_ALIASES = [
    (r"baby kale", "Kale", "baby"),
    (r"\bkale\b", "Kale", None),
    (r"scapes", "Garlic scapes", None),
    (r"mesclun", "Mesclun Mix", None),
    (r"collards?", "Collards", None),
    (r"cilantro", "Cilantro", None),
    (r"radish", "Radishes", None),
    (r"lettuce|head of lettuce", "Lettuce", None),
    (r"turnips?", "Turnips", None),
    (r"\bpeas?\b|snap peas?", "Peas", lambda m: "snap peas" if "snap" in m else None),
    (r"zucchini\s*/\s*squash", "Zucchini", None),  # user call: count all as zucchini this week
    (r"^summer squash(es)?$|^yellow squash$|^crookneck", "Summer Squash",
        lambda m: "crookneck" if "crookneck" in m else ("yellow squash" if "yellow squash" in m else None)),
    (r"^squash(es)?$", "Summer Squash", None),
    (r"zuke|zucchini", "Zucchini", None),
    (r"yellow cucumbers?", "Cucumbers", "yellow cucumbers"),
    (r"cukes?|cucumbers?", "Cucumbers", None),
    (r"green beans?|\bbeans\b", "Green beans", None),
    (r"beets?", "Beets", None),
    (r"carrots?", "Carrots", None),
    (r"swiss chard|\bchard\b", "Swiss Chard", None),
    (r"cherry tomato|pint cherry|cherry\b", "Tomatoes, cherry", None),
    (r"slicing/campari|campari", "Tomatoes, slicer", "campari"),
    (r"\btomato(es)?\b", "Tomatoes, slicer", None),
    (r"bell pepper|sweet pepper", "Peppers", None),
    (r"hot pepper|jalape", "Hot Peppers", None),
    (r"juliet", "Tomatoes, cherry", "Juliet variety"),  # user call: Juliets count as cherry tomatoes
]

DONATED_RE = re.compile(r"\((?:by\s+)?(anonymous\s+don\w*|donated)\)", re.IGNORECASE)
DATE_HEADER_RE = re.compile(r"^(\d{1,2}/\d{1,2}(?:/\d{2})?)(?:\s*&\s*(\d{1,2}/\d{1,2}(?:/\d{2})?))?\s*$")
QTY_RE = re.compile(r"^(a\s+handful|\d+(?:\.\d+)?(?:/\d+)?)\s+(.*)$", re.IGNORECASE)


def to_iso(date_str, year=2026):
    date_str = date_str.split("/")
    month, day = int(date_str[0]), int(date_str[1])
    return f"{year:04d}-{month:02d}-{day:02d}"


def parse_quantity(qty_text, rest):
    qty_text = qty_text.strip().lower()
    unit_override = None
    if qty_text == "a handful":
        return 1.0, "bags/bunches", "handful (approximate)"
    if "/" in qty_text:  # e.g. "1/2"
        num, den = qty_text.split("/")
        return float(num) / float(den), None, None
    # "3 half pints jalapeno" -- quantity already captured as 3, but "half pint" halves the pint value
    if rest.lower().startswith("half pint"):
        return float(qty_text) * 0.5, "pint", None
    return float(qty_text), None, None


def match_crop(text):
    low = text.lower()
    for pattern, crop, note in CROP_ALIASES:
        if re.search(pattern, low):
            resolved_note = note(low) if callable(note) else note
            return crop, resolved_note
    return None, f"UNRECOGNIZED: {text!r}"


def infer_unit(rest, crop):
    low = rest.lower()
    if "bag" in low:
        return "bags/bunches"
    if re.search(r"\bpt\b|\bpint", low):
        return "pint"
    if re.search(r"\blb\b|pound", low):
        return "lb"
    if re.search(r"\bhead\b", low):
        return "head"
    if crop in BUNCH_TYPE_CROPS:
        return "bags/bunches"
    return "#"


def main():
    lines = RAW_PATH.read_text().splitlines()
    records = []
    flagged = []
    current_dates = None

    for raw_line in lines:
        line = raw_line.strip()
        if not line or set(line) == {"-"}:
            continue
        header_match = DATE_HEADER_RE.match(line)
        if header_match:
            d1 = to_iso(header_match.group(1))
            d2 = to_iso(header_match.group(2)) if header_match.group(2) else None
            current_dates = [d1] if d2 is None or d2 == d1 else [d1, d2]
            continue
        if line == "2026":
            continue

        donated = bool(DONATED_RE.search(line))
        line_wo_donation = DONATED_RE.sub("", line).strip()

        m = QTY_RE.match(line_wo_donation)
        if not m:
            flagged.append({"line": raw_line, "reason": "no quantity found"})
            continue
        qty_text, rest = m.groups()
        rest = rest.replace("\xa0", " ").strip()
        quantity, unit_override, note = parse_quantity(qty_text, rest)
        crop, crop_note = match_crop(rest)

        if crop is None:
            flagged.append({"line": raw_line, "dates": current_dates, "reason": crop_note})
            continue

        unit = unit_override or infer_unit(rest, crop)
        final_note = note or crop_note

        per_date_qty = quantity / len(current_dates)
        for d in current_dates:
            rec = {
                "date": d,
                "crop": crop,
                "unit": unit,
                "quantity": round(per_date_qty, 2),
                "donated": donated,
                "notes": final_note or "",
                "source_line": raw_line.strip(),
            }
            if len(current_dates) > 1:
                rec["notes"] = (rec["notes"] + f"; split evenly from combined {current_dates[0]}+{current_dates[1]} report (total {quantity:g})").strip("; ")
            records.append(rec)

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(records, indent=2))
    FLAGGED_OUT_PATH.write_text(json.dumps(flagged, indent=2))

    print(f"Parsed {len(records)} records from {RAW_PATH.name}")
    print(f"Flagged {len(flagged)} lines needing manual review:")
    for f in flagged:
        print(f"  - {f}")


if __name__ == "__main__":
    main()
