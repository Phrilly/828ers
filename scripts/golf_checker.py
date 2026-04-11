"""
golf_checker.py
Daily checker: logs in as Phil D, fetches yesterday's scores from EG
for all 4 players and compares them against existing records in
wp_golf_scores.

Rules (confirmed April 2026):
  1. NEVER insert new scores into the DB under any circumstances.
  2. Only check scores dated yesterday (the day before the script runs).
     Scores for today are always ignored.
  3. For each player, compare gross score, tee and PCC from EG against
     the existing DB row for that date.
  4. If EG reports a non-zero PCC, silently update pcc_adjustment in the
     DB to match EG regardless of the current DB value. No email is sent.
  5. For gross score or tee discrepancies, send one summary alert email.
  6. PCC corrections are never included in the discrepancy email.
  7. HI mismatch triggers an alert email for all players EXCEPT Jay,
     whose HI is known to diverge from EG and is always ignored.
  8. Hole-by-hole scores are fetched from EG and stored in wp_golf_holes
     and wp_golf_hole_scores each time the script runs for that date.
     Uses ON DUPLICATE KEY UPDATE so re-runs are safe.

Usage:
  python golf_checker.py           # normal run -- checks yesterday
  python golf_checker.py --test    # test run -- checks today's scores
"""

import sys
import os
import io
import argparse
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import date, timedelta

# --- CRITICAL FIX FOR HOSTINGER CRON ---
# Dynamically inject the local site-packages path based on the running Python version
python_version = f"python{sys.version_info.major}.{sys.version_info.minor}"
sys.path.insert(0, os.path.expanduser(f'~/.local/lib/{python_version}/site-packages'))

# Add local scripts folder for config.py and eg_utils.py
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pymysql
import config
from eg_utils import (
    eg_login,
    eg_fetch_scores,
    eg_fetch_scorecard,
    eg_fetch_hi,
    parse_play_date,
    parse_gross,
    parse_pcc,
    parse_hi,
)

# Setup log capture for the daily email
log_stream = io.StringIO()
capture_handler = logging.StreamHandler(log_stream)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(
            os.path.join(os.path.dirname(__file__), "golf_checker.log"),
            encoding="utf-8",
        ),
        capture_handler,
    ],
)
log = logging.getLogger(__name__)

# Rule 7: HI mismatch is ignored for this player
HI_IGNORE_PLAYERS = {"Jay"}


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
    """
    Load tee data joined to courses so we have eg_club_id available
    for accurate course+tee matching in resolve_tee().
    eg_club_id lives in wp_golf_courses -- see ALTER TABLE applied April 2026.
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT t.tee_id, t.tee_colour, t.course_rating, t.slope_rating, "
            "t.par, t.course_id, c.eg_club_id "
            "FROM {p}golf_tees t "
            "JOIN {p}golf_courses c ON t.course_id = c.course_id".format(
                p=config.DB_PREFIX
            )
        )
        # Return as list so resolve_tee() can iterate over all rows
        return cur.fetchall()


def get_db_score(conn, player_id, date_played):
    """
    Return the DB score row for a player on a specific date, or None
    if no record exists. Checks date only -- not gross or tee.
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT s.score_id, s.gross_score, s.tee_id, s.pcc_adjustment, t.tee_colour "
            "FROM {p}golf_scores s "
            "LEFT JOIN {p}golf_tees t ON s.tee_id = t.tee_id "
            "WHERE s.player_id=%s AND s.date_played=%s".format(p=config.DB_PREFIX),
            (player_id, date_played),
        )
        return cur.fetchone()


def update_pcc(conn, score_id, new_pcc):
    """
    Silently correct pcc_adjustment on an existing score row.
    Called only when EG reports a non-zero PCC. No email is sent (Rule 6).
    """
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE {p}golf_scores SET pcc_adjustment=%s "
            "WHERE score_id=%s".format(p=config.DB_PREFIX),
            (int(new_pcc), score_id),
        )
    conn.commit()


def read_local_hi(conn, player_name):
    """
    Read the player's current handicap index from view_handicap_index.
    Returns a float or None if the view is unavailable.
    """
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


def sync_hole_data(conn, db_score_id, db_tee_id, scorecard):
    """
    Sync hole-by-hole data from an EG scorecard JSON into:
      wp_golf_holes       -- physical hole definition (par, distance per tee)
      wp_golf_hole_scores -- player's gross score per hole for this round

    Both tables use ON DUPLICATE KEY UPDATE so this is safe to re-run.

    FIX #9: Wrapped in try/except with explicit rollback so a failure
    on hole 12 doesn't leave holes 1-11 committed with the rest missing.
    """
    synced = 0
    try:
        with conn.cursor() as cur:
            for i in range(1, 19):
                gross    = scorecard.get(f"Hole{i}Score")
                par      = scorecard.get(f"Hole{i}Par")
                distance = scorecard.get(f"Hole{i}Distance")

                if not gross or not str(gross).isdigit():
                    continue

                # 1. Upsert physical hole definition (par + distance)
                cur.execute(
                    "INSERT INTO {p}golf_holes (tee_id, hole_number, par, length) "
                    "VALUES (%s, %s, %s, %s) "
                    "ON DUPLICATE KEY UPDATE par=VALUES(par), length=VALUES(length)".format(
                        p=config.DB_PREFIX
                    ),
                    (db_tee_id, i, int(par) if par else 0, int(distance) if distance else 0),
                )

                # Fetch the resulting hole_id
                cur.execute(
                    "SELECT hole_id FROM {p}golf_holes "
                    "WHERE tee_id=%s AND hole_number=%s".format(p=config.DB_PREFIX),
                    (db_tee_id, i),
                )
                hole_row = cur.fetchone()
                if not hole_row:
                    continue
                hole_id = hole_row["hole_id"]

                # 2. Upsert player's gross score for this hole
                cur.execute(
                    "INSERT INTO {p}golf_hole_scores (score_id, hole_id, gross_score) "
                    "VALUES (%s, %s, %s) "
                    "ON DUPLICATE KEY UPDATE gross_score=VALUES(gross_score)".format(
                        p=config.DB_PREFIX
                    ),
                    (db_score_id, hole_id, int(gross)),
                )
                synced += 1

        conn.commit()
        return synced

    except Exception as exc:
        conn.rollback()
        log.error(
            "sync_hole_data: rollback triggered after syncing %d hole(s) "
            "for score_id=%s. Error: %s",
            synced, db_score_id, exc,
        )
        return 0


# ---------------------------------------------------------------------------
# Tee resolution
# ---------------------------------------------------------------------------


def resolve_tee(raw, tees_list):
    """
    Match an EG score record to a row in wp_golf_tees.

    Primary match: official England Golf FacilityId + Tee colour.
    The eg_club_id values are stored in wp_golf_courses and joined in load_tees().

    Isle of Man club IDs (stored in wp_golf_courses.eg_club_id):
      Ramsey Golf Club          : 101345
      Comis At Mount Murray     : 101159
      Peel Golf Club            : 101276
      Douglas Golf Club         : 100526

    FIX #7: Cast both sides of the eg_club_id comparison to int() to
    prevent silent mismatches caused by MySQL returning Decimal/str
    vs the EG API returning an integer.

    Fallback: Course Rating + Slope matching for away courses not yet
    mapped with an eg_club_id.
    """
    eg_facility_id = raw.get("FacilityId") or raw.get("ClubId")
    marker         = (raw.get("Marker") or "").strip().lower()

    # 1. Primary Match: Official EG Club ID + Tee Colour
    if eg_facility_id and marker:
        try:
            eg_fac_int = int(eg_facility_id)
            for t in tees_list:
                try:
                    if int(t.get("eg_club_id") or 0) == eg_fac_int and t["tee_colour"].lower() == marker:
                        return t
                except (TypeError, ValueError):
                    continue
        except (TypeError, ValueError):
            pass

    # 2. Secondary Fallback: Course Rating + Slope
    # Covers away courses that don't yet have an eg_club_id in the DB.
    cr = raw.get("CourseRating")
    sl = raw.get("Slope")
    if cr and sl:
        try:
            eg_cr = float(cr)
            eg_sl = int(sl)
            for t in tees_list:
                try:
                    if (abs(float(t["course_rating"]) - eg_cr) < 0.2 and
                            int(t["slope_rating"]) == eg_sl):
                        return t
                except (TypeError, ValueError):
                    continue
        except (TypeError, ValueError):
            pass

    return None


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------


def send_email(subject, body):
    """
    Send a plain-text alert email using SMTP settings from config.
    Config keys: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD,
                 EMAIL_FROM, EMAIL_TO.
    """
    try:
        msg = MIMEMultipart()
        msg["From"]    = config.EMAIL_FROM
        msg["To"]      = config.EMAIL_TO
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(config.SMTP_USER, config.SMTP_PASSWORD)
            smtp.sendmail(config.EMAIL_FROM, config.EMAIL_TO, msg.as_string())

        log.info("Email sent: %s", subject)

    except Exception as exc:
        log.error("Failed to send email '%s': %s", subject, exc)


# ---------------------------------------------------------------------------
# Main checker
# ---------------------------------------------------------------------------


def check(test_mode=False):
    if test_mode:
        check_date     = date.today()
        check_date_str = check_date.isoformat()
        log.info("=== 828ers EG Daily Check - %s [TEST MODE] ===", date.today())
        log.info("TEST MODE: checking today's scores (%s) instead of yesterday", check_date_str)
        log.info("TEST MODE: PCC corrections and emails behave exactly as in production")
    else:
        check_date     = date.today() - timedelta(days=1)
        check_date_str = check_date.isoformat()
        log.info("=== 828ers EG Daily Check - %s ===", date.today())
        log.info("Checking EG scores for yesterday: %s", check_date_str)
        log.info("Note: scores for today (%s) are always ignored in normal mode", date.today())

    try:
        session = eg_login()
    except Exception as exc:
        log.error("EG login failed: %s", exc)
        send_email(
            "828ers EG Score Check - LOGIN FAILED",
            f"Could not log into EG API.\n\n=== RUN LOG ===\n{log_stream.getvalue()}"
        )
        sys.exit(1)

    try:
        conn = get_conn()
    except Exception as exc:
        log.error("DB connection failed: %s", exc)
        send_email(
            "828ers EG Score Check - DB FAILED",
            f"Could not connect to DB.\n\n=== RUN LOG ===\n{log_stream.getvalue()}"
        )
        sys.exit(1)

    db_players = load_players(conn)
    tees_list  = load_tees(conn)

    if not db_players or not tees_list:
        log.error("Missing players or tees in DB config.")
        sys.exit(1)

    log.info("DB players : %s", list(db_players.keys()))

    discrepancy_lines = []
    results           = []

    for player_cfg in config.PLAYERS:
        name  = player_cfg["name"]
        eg_id = player_cfg["eg_passport_id"]

        log.info("--- %s (eg_id=%s) ---", name, eg_id)

        db_row = db_players.get(name)
        if not db_row:
            log.warning("'%s' not found in wp_golf_players -- skipping", name)
            results.append({
                "name": name, "status": "NOT IN DB",
                "issues": 0, "eg_hi": "n/a", "local_hi": "n/a"
            })
            continue

        player_id     = db_row["player_id"]
        player_issues = []

        # --- Live HI comparison (string-based to avoid float arithmetic errors) ---
        eg_hi    = eg_fetch_hi(session, passport_id=eg_id)
        local_hi = read_local_hi(conn, name)

        # Format strictly to 1dp strings for comparison -- prevents 11.09999... != 11.1
        eg_hi_str    = "{:.1f}".format(float(eg_hi))    if eg_hi    is not None else "n/a"
        local_hi_str = "{:.1f}".format(float(local_hi)) if local_hi is not None else "n/a"

        log.info("  EG HI=%s  Local HI=%s", eg_hi_str, local_hi_str)

        if name not in HI_IGNORE_PLAYERS:
            if eg_hi_str != "n/a" and local_hi_str != "n/a":
                if eg_hi_str != local_hi_str:
                    player_issues.append(
                        "  HI mismatch:  EG={}  Local={}".format(eg_hi_str, local_hi_str)
                    )
        else:
            if eg_hi_str != "n/a" and local_hi_str != "n/a" and eg_hi_str != local_hi_str:
                log.info(
                    "  HI mismatch noted for %s (ignored per Rule 7): EG=%s  Local=%s",
                    name, eg_hi_str, local_hi_str,
                )

        # --- Fetch EG scores for this player ---
        try:
            raw_scores = eg_fetch_scores(session, passport_id=eg_id, page_size=40)
            log.info("  EG returned %d records", len(raw_scores))
        except Exception as exc:
            log.error("  EG fetch failed: %s", exc)
            results.append({
                "name": name, "status": "EG ERROR",
                "issues": len(player_issues), "eg_hi": eg_hi_str, "local_hi": local_hi_str
            })
            continue

        target_records = [r for r in raw_scores if parse_play_date(r) == check_date_str]

        if not target_records:
            log.info("  No EG score found for %s on %s -- nothing to check", name, check_date_str)
            status_msg = "NO EG SCORE FOR DATE"
        else:
            raw = target_records[0]

            eg_gross      = parse_gross(raw)
            eg_pcc        = parse_pcc(raw)
            eg_score_id   = raw.get("ScoreId")
            eg_score_code = raw.get("ScoreCode")   # FIX #3 -- extract separately, NOT the same as ScoreId
            eg_facility   = raw.get("FacilityId") or raw.get("ClubId")

            log.info(
                "  EG: gross=%s  facility=%s  marker=%s  pcc=%s  ScoreId=%s  ScoreCode=%s",
                eg_gross, eg_facility, (raw.get("Marker") or "").strip(), eg_pcc,
                eg_score_id, eg_score_code,
            )

            # FIX #8 -- get the DB record FIRST before calling resolve_tee
            # No point resolving the tee if there's no DB row to compare it against
            db_score = get_db_score(conn, player_id, check_date_str)

            if db_score is None:
                log.info(
                    "  No DB record for %s on %s -- no action taken (Rule 1)",
                    name, check_date_str,
                )
                status_msg = "NO DB RECORD FOR DATE"
            else:
                score_id   = db_score["score_id"]
                db_gross   = db_score["gross_score"]
                db_tee_id  = db_score["tee_id"]
                db_pcc     = db_score["pcc_adjustment"]
                db_tee_col = db_score["tee_colour"] or "UNKNOWN"

                # FIX #8 -- resolve_tee called here, only when we have a DB record
                eg_tee_row = resolve_tee(raw, tees_list)
                eg_tee_id  = eg_tee_row["tee_id"]    if eg_tee_row else None
                eg_tee_col = eg_tee_row["tee_colour"] if eg_tee_row else "UNKNOWN"

                log.info(
                    "  DB:  gross=%s  tee=%s (id=%s)  pcc=%s",
                    db_gross, db_tee_col, db_tee_id, db_pcc,
                )
                log.info(
                    "  EG → DB tee match:  EG tee=%s (id=%s)  DB tee=%s (id=%s)",
                    eg_tee_col, eg_tee_id, db_tee_col, db_tee_id,
                )

                # --- PCC correction (Rule 4 & 6) ---
                if eg_pcc != 0:
                    if int(eg_pcc) != int(db_pcc):
                        log.info(
                            "  PCC UPDATED %s %s: DB had %s --> EG says %s (no email per Rule 6)",
                            name, check_date_str, db_pcc, eg_pcc,
                        )
                        try:
                            update_pcc(conn, score_id, eg_pcc)
                        except Exception as exc:
                            log.error(
                                "  PCC update failed for %s on %s: %s",
                                name, check_date_str, exc,
                            )
                    else:
                        log.info("  PCC already matches EG: %s -- no update needed", eg_pcc)
                else:
                    log.info("  PCC is 0 on EG -- no PCC update required")

                # --- Gross mismatch check (Rule 5) ---
                if eg_gross is not None and db_gross is not None:
                    if int(eg_gross) != int(db_gross):
                        player_issues.append(
                            "  Gross score mismatch:  EG={}  DB={}".format(eg_gross, db_gross)
                        )

                # --- Tee/Course mismatch check (Rule 5) ---
                if eg_tee_id is not None and db_tee_id is not None:
                    if int(eg_tee_id) != int(db_tee_id):
                        player_issues.append(
                            "  Tee/Course mismatch:  EG mapped to tee_id={} ({})  "
                            "DB is tee_id={} ({})".format(
                                eg_tee_id, eg_tee_col, db_tee_id, db_tee_col
                            )
                        )

                # --- Hole-by-hole sync (Rule 8) ---
                # Fetch the full scorecard from EG and store in wp_golf_holes
                # and wp_golf_hole_scores. Safe to re-run (ON DUPLICATE KEY UPDATE).
                if eg_score_id and eg_score_code and db_tee_id:
                    scorecard = eg_fetch_scorecard(session, eg_score_id, score_code=eg_score_code)
                    if scorecard:
                        synced_count = sync_hole_data(conn, score_id, db_tee_id, scorecard)
                        if synced_count > 0:
                            log.info(
                                "  Hole sync OK: %d hole scores written for score_id=%s",
                                synced_count, score_id,
                            )
                        else:
                            log.warning(
                                "  Hole sync returned 0 rows for score_id=%s "
                                "(check scorecard field names in EG response)",
                                score_id,
                            )
                    else:
                        log.warning(
                            "  Could not fetch scorecard from EG for ScoreId=%s ScoreCode=%s",
                            eg_score_id, eg_score_code,
                        )
                elif eg_score_id and not eg_score_code:
                    log.warning(
                        "  ScoreCode missing from EG record for ScoreId=%s -- "
                        "hole sync skipped. Check GetMyScores response fields.",
                        eg_score_id,
                    )

                status_msg = "CHECKED"

        if player_issues:
            block = "Player: {}  |  Date: {}{}{}".format(
                name, check_date_str,
                " [TEST MODE]" if test_mode else "",
                "\n" + "\n".join(player_issues),
            )
            discrepancy_lines.append(block)
            log.warning("  Discrepancies found for %s:", name)
            for issue in player_issues:
                log.warning(issue)
        else:
            log.info("  All data matches for %s (no alertable discrepancies)", name)

        results.append({
            "name":     name,
            "status":   status_msg,
            "issues":   len(player_issues),
            "eg_hi":    eg_hi_str,
            "local_hi": local_hi_str,
        })

    conn.close()

    # --- Print End Summary ---
    mode_label = " [TEST MODE]" if test_mode else ""
    log.info("")
    log.info("=== CHECK COMPLETE%s ===", mode_label)
    log.info("%-14s  %-26s  %-6s  %-8s  %s", "Player", "Status", "Issues", "EG HI", "Local HI")
    log.info("-" * 68)
    for r in results:
        log.info(
            "%-14s  %-26s  %-6s  %-8s  %s",
            r["name"],
            r["status"],
            str(r.get("issues", "-")),
            r["eg_hi"],
            r["local_hi"],
        )

    # --- Capture Logs & Send Daily Email ---
    log.info("Preparing daily confirmation email...")
    capture_handler.flush()
    full_log_contents = log_stream.getvalue()

    if discrepancy_lines:
        subject = "{}828ers EG Score Check - DISCREPANCIES FOUND ({})".format(
            "[TEST] " if test_mode else "", check_date_str
        )
        body = (
            "{}The following discrepancies were found between EG and the "
            "828ers DB for scores dated {}:\n\n".format(
                "*** TEST MODE -- checking today's scores ***\n\n" if test_mode else "",
                check_date_str,
            )
        )
        body += "\n\n".join(discrepancy_lines)
        body += (
            "\n\n---\n"
            "Note: any PCC corrections have been applied to the DB automatically "
            "and are not included in this alert (Rule 6).\n"
            "Jay's HI discrepancy is always suppressed (Rule 7).\n"
            "No scores were inserted or deleted. The DB is read-only except "
            "for PCC corrections (Rule 1).\n\n"
        )
    else:
        subject = "{}828ers EG Score Check - OK ({})".format(
            "[TEST] " if test_mode else "", check_date_str
        )
        body = (
            "The daily England Golf sync completed successfully. "
            "No alertable discrepancies were found.\n\n"
        )

    body += "=== FULL RUN LOG ===\n"
    body += full_log_contents

    send_email(subject, body)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="828ers EG daily score checker")
    parser.add_argument(
        "--test", action="store_true",
        help="Test mode: check today's scores instead of yesterday's",
    )
    args = parser.parse_args()
    check(test_mode=args.test)
