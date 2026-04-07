"""
golf_checker.py
Daily sync: logs in as Phil D, fetches scores for all 4 players,
upserts into wp_golf_scores. The AFTER INSERT trigger fires
sp_process_single_round() which rebuilds wp_golf_handicap_history.

Confirmed April 2026:
  - otherPassportId in GetMyScores = CDH number (NOT passport number)
  - Phil D uses None (he is the logged-in account)
  - Score fields: PlayDate (DD/MM/YYYY), AdjustedGross, Marker,
                  Slope, CourseRating, HCDiff, HandicapIndex, Pcc
"""

import sys
import os
import logging
from datetime import date, timedelta

import pymysql

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config
from eg_utils import (
    eg_login,
    eg_fetch_scores,
    parse_play_date,
    parse_gross,
    parse_pcc,
    parse_hi,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            os.path.join(os.path.dirname(__file__), "golf_checker.log"),
            encoding="utf-8",
        ),
    ],
)
log = logging.getLogger(__name__)

LOOKBACK_DAYS = getattr(config, "LOOKBACK_DAYS", 5)


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_conn():
    return pymysql.connect(
        host=config.DB_HOST,
        port=config.DB_PORT,
        db=config.DB_NAME,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        charset="utf8mb4",
        autocommit=False,
        cursorclass=pymysql.cursors.DictCursor,
    )


def load_players(conn):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT player_id, name, winner_colour "
            "FROM {}golf_players".format(config.DB_PREFIX)
        )
        return {r["name"]: r for r in cur.fetchall()}


def load_tees(conn):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT tee_id, tee_colour, course_rating, slope_rating, par, course_id "
            "FROM {}golf_tees".format(config.DB_PREFIX)
        )
        return {r["tee_colour"].lower(): r for r in cur.fetchall()}


def score_exists(conn, player_id, date_played, gross):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT score_id FROM {}golf_scores "
            "WHERE player_id=%s AND date_played=%s AND gross_score=%s".format(
                config.DB_PREFIX
            ),
            (player_id, date_played, gross),
        )
        return cur.fetchone() is not None


def insert_score(conn, player_id, tee_id, date_played, gross, pcc):
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO {}golf_scores "
            "(player_id, date_played, tee_id, gross_score, pcc_adjustment, "
            "putts, gir, is_excluded) "
            "VALUES (%s, %s, %s, %s, %s, 0, 0, 0)".format(config.DB_PREFIX),
            (player_id, date_played, tee_id, gross, pcc),
        )
    conn.commit()


def read_local_hi(conn, player_name):
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT current_handicap_index "
                "FROM view_handicap_index WHERE player_name=%s",
                (player_name,),
            )
            row = cur.fetchone()
        return float(row["current_handicap_index"]) if row else None
    except Exception as exc:
        log.warning("Could not read local HI for %s: %s", player_name, exc)
        return None


# ---------------------------------------------------------------------------
# Tee resolution
# ---------------------------------------------------------------------------

def resolve_tee(raw, default_tee, tees):
    """
    Match an EG score record to a row in wp_golf_tees.
    EG uses 'Marker' for tee colour (e.g. 'White', 'Yellow', 'Red').
    Falls back to the player's default tee from config.
    """
    marker = (raw.get("Marker") or "").strip().lower()
    if marker and marker in tees:
        return tees[marker]

    # Try course_rating + slope match
    cr = raw.get("CourseRating")
    sl = raw.get("Slope")
    if cr and sl:
        for t in tees.values():
            try:
                if (abs(float(t["course_rating"]) - float(cr)) < 0.2 and
                        int(t["slope_rating"]) == int(sl)):
                    return t
            except (TypeError, ValueError):
                continue

    # Fall back to player default
    return tees.get(default_tee.lower())


# ---------------------------------------------------------------------------
# Main sync
# ---------------------------------------------------------------------------

def sync():
    log.info("=== 828ers EG Daily Sync - %s ===", date.today())
    cutoff = date.today() - timedelta(days=LOOKBACK_DAYS)
    log.info("Checking scores back to %s", cutoff)

    # Login
    try:
        session = eg_login()
    except Exception as exc:
        log.error("EG login failed: %s", exc)
        sys.exit(1)

    # DB connection
    try:
        conn = get_conn()
    except Exception as exc:
        log.error("DB connection failed: %s", exc)
        sys.exit(1)

    db_players = load_players(conn)
    tees = load_tees(conn)

    if not db_players:
        log.error("No players in %sgolf_players. Check DB config.", config.DB_PREFIX)
        sys.exit(1)
    if not tees:
        log.error("No tees in %sgolf_tees. Check DB config.", config.DB_PREFIX)
        sys.exit(1)

    log.info("DB players : %s", list(db_players.keys()))
    log.info("DB tees    : %s", list(tees.keys()))

    results = []

    for player_cfg in config.PLAYERS:
        name    = player_cfg["name"]
        eg_id   = player_cfg["eg_passport_id"]   # CDH, or None for Phil D
        def_tee = player_cfg["default_tee"]

        log.info("--- %s (eg_id=%s) ---", name, eg_id)

        db_row = db_players.get(name)
        if not db_row:
            log.warning("'%s' not found in wp_golf_players -- skipping", name)
            results.append({"name": name, "status": "NOT IN DB", "inserted": 0})
            continue

        player_id = db_row["player_id"]

        # Fetch EG scores
        try:
            raw_scores = eg_fetch_scores(session, passport_id=eg_id, page_size=40)
            log.info("  EG returned %d records", len(raw_scores))
        except Exception as exc:
            log.error("  EG fetch failed: %s", exc)
            results.append({"name": name, "status": "EG ERROR", "inserted": 0})
            continue

        inserted = 0
        for raw in raw_scores:
            date_played = parse_play_date(raw)
            if not date_played:
                continue
            if date_played < cutoff.isoformat():
                continue

            gross = parse_gross(raw)
            if not gross:
                continue

            pcc = parse_pcc(raw)

            tee_row = resolve_tee(raw, def_tee, tees)
            if not tee_row:
                log.warning(
                    "  Cannot resolve tee for %s on %s (Marker=%s) -- skipping",
                    name, date_played, raw.get("Marker"),
                )
                continue

            if score_exists(conn, player_id, date_played, gross):
                log.info(
                    "  SKIP duplicate: %s %s gross=%s", name, date_played, gross
                )
                continue

            try:
                insert_score(
                    conn, player_id, tee_row["tee_id"], date_played, gross, pcc
                )
                log.info(
                    "  INSERTED %s  %s  gross=%s  tee=%s",
                    name, date_played, gross, tee_row["tee_colour"],
                )
                inserted += 1
            except Exception as exc:
                log.error("  INSERT failed for %s on %s: %s", name, date_played, exc)
                conn.rollback()

        # Read back local HI (after trigger has fired for any new inserts)
        local_hi = read_local_hi(conn, name)
        eg_hi = parse_hi(raw_scores[0]) if raw_scores else None

        if eg_hi and local_hi and abs(eg_hi - local_hi) > 0.5:
            log.warning(
                "  HI mismatch: EG=%.1f  Local=%.1f  diff=%.1f",
                eg_hi, local_hi, abs(eg_hi - local_hi),
            )

        log.info(
            "  Inserted=%d  EG HI=%s  Local HI=%s",
            inserted,
            "{:.1f}".format(eg_hi) if eg_hi is not None else "n/a",
            "{:.1f}".format(local_hi) if local_hi is not None else "n/a",
        )

        results.append({
            "name":     name,
            "status":   "OK",
            "inserted": inserted,
            "eg_hi":    eg_hi,
            "local_hi": local_hi,
        })

    conn.close()

    log.info("")
    log.info("=== SYNC COMPLETE ===")
    log.info("%-10s  %-10s  %-8s  %-8s  %s",
             "Player", "Status", "Inserted", "EG HI", "Local HI")
    log.info("-" * 52)
    for r in results:
        log.info(
            "%-10s  %-10s  %-8d  %-8s  %s",
            r["name"],
            r["status"],
            r.get("inserted", 0),
            "{:.1f}".format(r["eg_hi"])    if r.get("eg_hi")    is not None else "n/a",
            "{:.1f}".format(r["local_hi"]) if r.get("local_hi") is not None else "n/a",
        )


if __name__ == "__main__":
    sync()