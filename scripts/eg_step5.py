#!/usr/bin/env python3
"""
eg_step5.py — Verify Database Connectivity and Player Name Matching

WHAT THIS TESTS:
  - DB connection works
  - wp_golf_players contains rows we expect
  - Player names in config.PLAYERS match wp_golf_players.name exactly
  - wp_golf_tees contains the tee colours we expect
  - view_handicap_index is readable

HOLES FIXED:
  #6  Player name mismatch caught here before it silently breaks the checker
  #5  PCC timing advisory printed
"""

import sys
import pymysql
import config

SEP = "─" * 60
print(f"\n{'═'*60}")
print("  EG STEP 5 — Database Connectivity & Player Name Check")
print(f"{'═'*60}\n")

def get_db():
    return pymysql.connect(
        host=config.DB_HOST, port=config.DB_PORT, db=config.DB_NAME,
        user=config.DB_USER, password=config.DB_PASSWORD,
        charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor,
    )

print("  Connecting to database…")
try:
    conn = get_db()
    print("  ✓ Connected\n")
except Exception as exc:
    print(f"  ✗ Connection FAILED: {exc}")
    sys.exit(1)

p = config.DB_PREFIX

# ── Players ──
print(SEP)
print(f"  {p}golf_players contents:")
print(SEP)
with conn.cursor() as cur:
    cur.execute(f"SELECT player_id, name, winner_colour FROM {p}golf_players ORDER BY player_id")
    db_players = cur.fetchall()

db_names = {r["name"]: r for r in db_players}
for row in db_players:
    print(f"    player_id={row['player_id']}  name='{row['name']}'  colour='{row['winner_colour']}'")

print(f"\n  Checking config.PLAYERS names match DB exactly:")
all_ok = True
for player in config.PLAYERS:
    name = player["name"]
    if name in db_names:
        row = db_names[name]
        print(f"    ✓ '{name}' → player_id={row['player_id']}")
    else:
        print(f"    ✗ '{name}' NOT FOUND in DB")
        # Show close matches
        close = [n for n in db_names if name.lower() in n.lower() or n.lower() in name.lower()]
        if close:
            print(f"      Close matches in DB: {close}")
            print(f"      → Update config.PLAYERS 'name' to match exactly")
        all_ok = False

# ── Tees ──
print(f"\n{SEP}")
print(f"  {p}golf_tees contents:")
print(SEP)
with conn.cursor() as cur:
    cur.execute(f"SELECT tee_id, tee_colour, course_rating, slope_rating FROM {p}golf_tees ORDER BY tee_id")
    db_tees = cur.fetchall()

db_tee_colours = {r["tee_colour"].lower(): r["tee_colour"] for r in db_tees}
for row in db_tees:
    print(f"    tee_id={row['tee_id']}  colour='{row['tee_colour']}'  CR={row['course_rating']}  SR={row['slope_rating']}")

print(f"\n  Checking config.PLAYERS default_tee values match DB exactly:")
for player in config.PLAYERS:
    tee = player["default_tee"]
    if tee.lower() in db_tee_colours:
        actual = db_tee_colours[tee.lower()]
        match = "✓" if tee == actual else f"⚠  case mismatch — DB has '{actual}', config has '{tee}'"
        print(f"    {match}: '{player['name']}' → '{tee}'")
    else:
        print(f"    ✗ '{player['name']}' tee '{tee}' NOT in DB")
        all_ok = False

# ── view_handicap_index ──
print(f"\n{SEP}")
print(f"  view_handicap_index:")
print(SEP)
try:
    with conn.cursor() as cur:
        cur.execute("SELECT player_name, current_handicap_index FROM view_handicap_index ORDER BY player_name")
        hi_rows = cur.fetchall()
    for row in hi_rows:
        print(f"    {row['player_name']}: HI={row['current_handicap_index']}")
    if not hi_rows:
        print("    (no rows returned)")
except Exception as exc:
    print(f"    ✗ Could not query view_handicap_index: {exc}")

conn.close()

print(f"\n{SEP}")
print("  PCC TIMING ADVISORY (#5)")
print(SEP)
print("  EG typically publishes PCC the morning AFTER a round, often after 09:00.")
print("  The recommended cron time is 10:05 AM to ensure PCC is available.")
print("  Current CRON_SETUP.txt suggests 07:05 — consider changing to 10:05.")
print("  Cron line: 5 10 * * * cd /path/to/scripts && python golf_checker.py >> cron.log 2>&1")

print(f"\n{'═'*60}")
if all_ok:
    print("  ✓ All checks passed — proceed to golf_checker.py --dry-run")
else:
    print("  ✗ Fix the issues above before running golf_checker.py")
print(f"{'═'*60}\n")
