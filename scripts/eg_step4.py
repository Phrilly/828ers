#!/usr/bin/env python3
"""
eg_step4.py — Test otherPassportId for Phil B, Jay, Adder

WHAT THIS TESTS:
  - CRITICAL: confirms Phil D's session can actually fetch OTHER players' scores
    via otherPassportId — this has NEVER been confirmed with a live call
  - Detects if EG ignores otherPassportId and always returns Phil D's scores
    (the "silently wrong" failure mode)
  - Dumps field names for each player so we can confirm consistency

HOLES FIXED:
  #2  Explicit detection of passthrough failure (EG ignoring otherPassportId)

RUN: python eg_step4.py
"""

import json
import sys
from datetime import date
from eg_utils import (
    eg_login, eg_fetch_scores, get_yesterday_bst,
    EGLoginError, EGAPIError
)
import config

SEP = "─" * 60
print(f"\n{'═'*60}")
print("  EG STEP 4 — otherPassportId Test (Phil B, Jay, Adder)")
print(f"{'═'*60}\n")

print("  ⚠  CRITICAL TEST: if passports don't work, we only ever check Phil D")
print("  Success = different scores returned for different passport IDs\n")

print("  Getting session…")
try:
    session = eg_login()
except EGLoginError as exc:
    print(f"  ✗ Login failed: {exc}")
    sys.exit(1)

# Fetch Phil D first as reference baseline
print(f"  Fetching Phil D (passport=None) as baseline…")
try:
    pd_records = eg_fetch_scores(session, passport_id=None, page_size=5)
    pd_ref_date = None
    for date_key in ["DatePlayed","datePlayed","Date","date"]:
        if pd_records and date_key in pd_records[0]:
            pd_ref_date = pd_records[0][date_key]
            break
    print(f"  Phil D most recent date: {pd_ref_date}")
    print(f"  Phil D record count:     {len(pd_records)}")
except Exception as exc:
    print(f"  ✗ Phil D fetch failed: {exc}")
    pd_records = []
    pd_ref_date = None

players_to_test = [p for p in config.PLAYERS if p["eg_passport_id"] is not None]

for player in players_to_test:
    print(f"\n{SEP}")
    print(f"  Testing: {player['name']} (passport={player['eg_passport_id']})")
    print(SEP)

    try:
        records = eg_fetch_scores(session, passport_id=player["eg_passport_id"], page_size=5)
    except EGAPIError as exc:
        print(f"  ✗ API ERROR: {exc}")
        continue

    print(f"  Records returned: {len(records)}")

    if not records:
        print("  — No records returned")
        print("  This could mean: no scores on EG, wrong passport ID, or not linked to Phil D's account")
        continue

    # Check if it looks like Phil D's data was returned instead (#2)
    other_ref_date = None
    for date_key in ["DatePlayed","datePlayed","Date","date"]:
        if date_key in records[0]:
            other_ref_date = records[0][date_key]
            break

    print(f"  Most recent date: {other_ref_date}")

    if pd_ref_date and other_ref_date and str(pd_ref_date)[:10] == str(other_ref_date)[:10]:
        # Dates match — check gross score to see if it's genuinely the same
        pd_gross = pd_records[0] if pd_records else {}
        for gross_key in ["AdjustedGrossScore","adjustedGrossScore","GrossScore","grossScore","Score","score"]:
            if gross_key in records[0] and gross_key in pd_gross:
                if records[0][gross_key] == pd_gross[gross_key]:
                    print(f"  ⚠  WARNING: same date AND same gross score as Phil D")
                    print(f"     EG may be ignoring otherPassportId and returning Phil D's data")
                    print(f"     → Manually verify: Phil D gross={pd_gross[gross_key]}, {player['name']} gross={records[0][gross_key]}")
                else:
                    print(f"  ✓ Different gross score to Phil D — passport ID appears to be working")
                break
    else:
        print(f"  ✓ Different data returned to Phil D — passport ID confirmed working")

    print(f"\n  Field names in {player['name']}'s most recent record:")
    for k, v in records[0].items():
        print(f"    '{k}': {repr(v)[:80]}")

print(f"\n{'═'*60}")
print("  STEP 4 COMPLETE")
print("  → If all 4 players returned different data: proceed to eg_step5.py")
print("  → If any player returned Phil D's data: report back before continuing")
print(f"{'═'*60}\n")
