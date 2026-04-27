"""
repair_holes.py
Targeted hole-score repair — much faster than --backfill.

Two passes:
  Pass 1 (SQL only, no API):
    Scans wp_golf_hole_scores for rows where score_display matches "*(N)"
    but score_status is still 'missing'. Fixes them in-place to
    score_status='adjusted', adjusted_gross_score=N with no API call needed.

  Pass 2 (EG API):
    Finds rounds where hole_count is between 1 and 17 (partially synced).
    Re-fetches the scorecard from EG and re-runs sync_hole_data for those
    rounds only.  Rounds with 0 holes are skipped (too old for EG API).
    Fully complete rounds (18 holes) are skipped.
"""

import sys
import os
import re
import time
import logging

python_version = f"python{sys.version_info.major}.{sys.version_info.minor}"
sys.path.insert(0, os.path.expanduser(f'~/.local/lib/{python_version}/site-packages'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pymysql
import config
from eg_utils import (
    eg_login,
    eg_fetch_scorecard,
    parse_eg_hole_score,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            os.path.join(os.path.dirname(__file__), "repair_holes.log"),
            encoding="utf-8",
        ),
    ],
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# DB connection
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


# ---------------------------------------------------------------------------
# Pass 1 — Fix *(N) rows already in the DB (no API needed)
# ---------------------------------------------------------------------------

def pass1_fix_auto_net_double(conn):
    """
    Find all hole_score rows where score_display looks like *(N) but is
    currently stored as missing/NULL.  Correct them in-place.
    """
    log.info("=== Pass 1: fixing *(N) rows in DB ===")

    with conn.cursor() as cur:
        cur.execute(
            "SELECT hs_id, score_display "
            "FROM {p}golf_hole_scores "
            "WHERE score_status = 'missing' "
            "  AND score_display REGEXP '^\\\\*\\\\([0-9]+\\\\)$'".format(
                p=config.DB_PREFIX
            )
        )
        rows = cur.fetchall()

    if not rows:
        log.info("Pass 1: nothing to fix.")
        return 0

    log.info("Pass 1: found %d rows to fix.", len(rows))
    fixed = 0

    with conn.cursor() as cur:
        for row in rows:
            m = re.match(r"^\*\((\d+)\)$", row["score_display"])
            if not m:
                continue
            adj = int(m.group(1))
            cur.execute(
                "UPDATE {p}golf_hole_scores "
                "SET adjusted_gross_score = %s, "
                "    score_status = 'adjusted' "
                "WHERE hs_id = %s".format(p=config.DB_PREFIX),
                (adj, row["hs_id"]),
            )
            fixed += 1

    conn.commit()
    log.info("Pass 1: fixed %d rows.", fixed)
    return fixed


# ---------------------------------------------------------------------------
# Pass 2 — Re-fetch partial rounds from EG API
# ---------------------------------------------------------------------------

def sync_hole_data(conn, db_score_id, db_tee_id, scorecard):
    """Identical to golf_checker.py sync_hole_data."""
    synced = 0
    incomplete_count = 0

    try:
        raw_inc = scorecard.get("IncompleteCount")
        if raw_inc is not None and str(raw_inc).strip() != "":
            try:
                incomplete_count = int(float(raw_inc))
            except (TypeError, ValueError):
                pass

        with conn.cursor() as cur:
            for i in range(1, 19):
                raw_score = scorecard.get(f"Hole{i}Score")
                raw_class = scorecard.get(f"Hole{i}ScoreClass")
                par       = scorecard.get(f"Hole{i}Par")
                distance  = scorecard.get(f"Hole{i}Distance")

                if raw_score is None:
                    continue

                parsed = parse_eg_hole_score(
                    raw_score=raw_score,
                    raw_class=raw_class,
                    incomplete_count=incomplete_count,
                )

                safe_par = 0
                if par is not None and str(par).strip() != "":
                    try:
                        safe_par = int(float(par))
                    except (TypeError, ValueError):
                        pass

                safe_dist = 0
                if distance is not None and str(distance).strip() != "":
                    try:
                        safe_dist = int(float(distance))
                    except (TypeError, ValueError):
                        pass

                cur.execute(
                    "INSERT INTO {p}golf_holes (tee_id, hole_number, par, length) "
                    "VALUES (%s, %s, %s, %s) "
                    "ON DUPLICATE KEY UPDATE par=VALUES(par), length=VALUES(length)".format(
                        p=config.DB_PREFIX
                    ),
                    (db_tee_id, i, safe_par, safe_dist),
                )

                cur.execute(
                    "SELECT hole_id FROM {p}golf_holes "
                    "WHERE tee_id=%s AND hole_number=%s".format(p=config.DB_PREFIX),
                    (db_tee_id, i),
                )
                hole_row = cur.fetchone()
                if not hole_row:
                    log.warning(
                        "  Could not find/create hole row for tee_id=%s hole=%d — skipping",
                        db_tee_id, i,
                    )
                    continue

                cur.execute(
                    "INSERT INTO {p}golf_hole_scores "
                    "(score_id, hole_id, gross_score, adjusted_gross_score, "
                    " score_status, score_display) "
                    "VALUES (%s, %s, %s, %s, %s, %s) "
                    "ON DUPLICATE KEY UPDATE "
                    "gross_score=VALUES(gross_score), "
                    "adjusted_gross_score=VALUES(adjusted_gross_score), "
                    "score_status=VALUES(score_status), "
                    "score_display=VALUES(score_display)".format(
                        p=config.DB_PREFIX
                    ),
                    (
                        db_score_id,
                        hole_row["hole_id"],
                        parsed["gross_score"],
                        parsed["adjusted_gross_score"],
                        parsed["score_status"],
                        parsed["score_display"],
                    ),
                )
                synced += 1

        conn.commit()
        return synced

    except Exception as exc:
        conn.rollback()
        log.error(
            "sync_hole_data: rollback after %d hole(s) for score_id=%s. Error: %s",
            synced, db_score_id, exc,
        )
        return 0


def pass2_repair_partial_rounds(conn, session):
    """
    Find rounds with 1-17 hole scores and re-sync them from EG API.
    Rounds with 0 holes are too old for EG API and are skipped.
    """
    log.info("=== Pass 2: re-syncing partial rounds from EG API ===")

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
                s.score_id,
                s.tee_id,
                s.eg_score_id,
                s.eg_score_code,
                p.name   AS player_name,
                s.date_played,
                COUNT(hs.hs_id) AS hole_count
            FROM {p}golf_scores s
            JOIN {p}golf_players p ON s.player_id = p.player_id
            LEFT JOIN {p}golf_hole_scores hs ON s.score_id = hs.score_id
            GROUP BY s.score_id, s.tee_id, s.eg_score_id,
                     s.eg_score_code, p.name, s.date_played
            HAVING hole_count BETWEEN 1 AND 17
            ORDER BY s.date_played DESC
            """.format(p=config.DB_PREFIX)
        )
        partial_rounds = cur.fetchall()

    if not partial_rounds:
        log.info("Pass 2: no partial rounds found.")
        return 0

    log.info("Pass 2: found %d partial rounds to repair.", len(partial_rounds))
    repaired = 0

    for row in partial_rounds:
        score_id   = row["score_id"]
        tee_id     = row["tee_id"]
        eg_sid     = row["eg_score_id"]
        eg_code    = row["eg_score_code"]
        name       = row["player_name"]
        date_str   = str(row["date_played"])
        hole_count = row["hole_count"]

        if not eg_sid or not eg_code:
            log.warning(
                "  score_id=%s (%s %s) has %d holes but no EG IDs — skipping.",
                score_id, name, date_str, hole_count,
            )
            continue

        log.info(
            "  Repairing score_id=%s  %s  %s  (currently %d/18 holes)",
            score_id, name, date_str, hole_count,
        )

        try:
            scorecard = eg_fetch_scorecard(session, eg_sid, eg_code)
        except Exception as exc:
            log.error(
                "  EG scorecard fetch failed for score_id=%s: %s", score_id, exc
            )
            time.sleep(1)
            continue

        if not scorecard:
            log.warning(
                "  Empty scorecard from EG for score_id=%s — skipping.", score_id
            )
            time.sleep(0.5)
            continue

        synced = sync_hole_data(conn, score_id, tee_id, scorecard)
        log.info(
            "  score_id=%s: %d hole rows written.", score_id, synced
        )
        if synced > 0:
            repaired += 1

        time.sleep(0.5)

    log.info("Pass 2: repaired %d rounds.", repaired)
    return repaired


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    log.info("=== repair_holes.py starting ===")

    conn = get_conn()

    try:
        # Pass 1 — pure SQL, no API needed
        fixed_rows = pass1_fix_auto_net_double(conn)

        # Pass 2 — EG API for partial rounds
        session = eg_login()
        repaired_rounds = pass2_repair_partial_rounds(conn, session)

        log.info(
            "=== Done. Pass 1 fixed %d hole rows. Pass 2 repaired %d rounds. ===",
            fixed_rows, repaired_rounds,
        )
    finally:
        conn.close()


if __name__ == "__main__":
    main()
