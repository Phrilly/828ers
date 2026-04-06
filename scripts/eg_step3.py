#!/usr/bin/env python3
"""
eg_step3.py — Inspect EG Scores API for Phil D

WHAT THIS TESTS:
  - Scores API responds correctly for the logged-in user (passport=None)
  - Dumps ALL field names so we can confirm exact names
  - Looks for yesterday's round and prints it in full

HOLES FIXED:
  #4  Explicit field name discovery — output tells you exactly what to use
  #10 Uses BST-aware yesterday date

RUN:
  python eg_step3.py
  python eg_step3.py --debug    # full raw dump of every record

IMPORTANT OUTPUT TO SHARE:
  "All field names" section — paste this back so we can lock
  in the exact names for golf_checker.py
"""

import argparse
import json
import sys
from datetime import date
from eg_utils import eg_login, eg_fetch_scores, get_yesterday_bst, EGLoginError, EGAPIError

parser = argparse.ArgumentParser()
parser.add_argument("--debug", action="store_true", help="Dump all raw records")
args = parser.parse_args()

SEP = "─" * 60
print(f"\n{'═'*60}")
print("  EG STEP 3 — Scores API Field Inspection (Phil D)")
print(f"{'═'*60}\n")

yesterday = get_yesterday_bst()
print(f"  Looking for yesterday: {yesterday}\n")

print("  Getting session…")
try:
    session = eg_login()
except EGLoginError as exc:
    print(f"  ✗ Login failed: {exc}")
    sys.exit(1)

print(f"  Fetching scores for Phil D (passport=None)…")
try:
    records = eg_fetch_scores(session, passport_id=None, page_size=40)
except EGAPIError as exc:
    print(f"  ✗ Scores API failed: {exc}")
    sys.exit(1)

print(f"  ✓ Got {len(records)} records\n")

if not records:
    print("  No records returned — Phil D may have no scores on this account?")
    sys.exit(0)

# ── Field name map ──
print(SEP)
print("  ALL FIELD NAMES IN MOST RECENT RECORD (copy these to confirm):")
print(SEP)
for k, v in records[0].items():
    print(f"    '{k}': {repr(v)[:80]}")

# ── Yesterday's round ──
print(f"\n{SEP}")
print(f"  SEARCHING FOR YESTERDAY'S ROUND ({yesterday})")
print(SEP)
found = None
for rec in records:
    for date_key in ["DatePlayed","datePlayed","Date","date","PlayedDate"]:
        if date_key in rec:
            raw = rec[date_key]
            try:
                if date.fromisoformat(str(raw)[:10]) == yesterday:
                    found = rec
                    break
            except Exception:
                pass
    if found:
        break

if found:
    print(f"  ✓ Found a round for {yesterday}!")
    print(json.dumps(found, indent=4, default=str))
else:
    print(f"  — No round found for {yesterday}")
    print("  (Either Phil D didn't play yesterday, or the date field name is different)")
    print("\n  Most recent record shown for reference:")
    print(json.dumps(records[0], indent=4, default=str))

if args.debug:
    print(f"\n{SEP}")
    print("  ALL RECORDS (--debug mode):")
    print(SEP)
    for i, rec in enumerate(records):
        print(f"\n  Record {i+1}:")
        print(json.dumps(rec, indent=4, default=str))

print(f"\n  NEXT STEP: run python eg_step4.py to test the other 3 players' passport IDs")
