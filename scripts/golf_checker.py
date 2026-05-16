"""
golf_checker.py
Daily checker & historical backfiller for EG API integration.
"""

import sys
import os
import io
import re
import time
import argparse
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import date, timedelta

# --- CRITICAL FIX FOR HOSTINGER CRON ---
python_version = f"python{sys.version_info.major}.{sys.version_info.minor}"
sys.path.insert(0, os.path.expanduser(f'~/.local/lib/{python_version}/site-packages'))
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
    parse_eg_hole_score,
)

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

HI_IGNORE_PLAYERS = set(["Jay"])


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
            "SELECT t.tee_id, t.tee_colour, t.course_rating, t.slope_rating, "
            "t.par, t.course_id, c.eg_club_id, c.course_name "
            "FROM {p}golf_tees t "
            "JOIN {p}golf_courses c ON t.course_id = c.course_id".format(
                p=config.DB_PREFIX
            )
        )
        return cur.fetchall()


def get_db_score(conn, player_id, date_played):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT s.score_id, s.gross_score, s.tee_id, s.pcc_adjustment, t.tee_colour "
            "FROM {p}golf_scores s "
            "LEFT JOIN {p}golf_tees t ON s.tee_id = t.tee_id "
            "WHERE s.player_id=%s AND s.date_played=%s".format(p=config.DB_PREFIX),
            (player_id, date_played),
        )
        return cur.fetchone()


def has_hole_scores(conn, score_id):
    """
    Returns True only when all 18 hole rows exist for this round.
    A round with fewer than 18 rows (e.g. 17 because a missing/asterisk hole
    was previously silently dropped) will return False so the caller re-runs
    sync_hole_data, which is safe because it uses ON DUPLICATE KEY UPDATE.
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) as c FROM {p}golf_hole_scores "
            "WHERE score_id=%s".format(p=config.DB_PREFIX),
            (score_id,)
        )
        return cur.fetchone()["c"] >= 18


def update_pcc(conn, score_id, new_pcc):
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE {p}golf_scores SET pcc_adjustment=%s "
            "WHERE score_id=%s".format(p=config.DB_PREFIX),
            (int(new_pcc), score_id),
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


def verify_trigger_effect(conn, score_id):
    with conn.cursor() as cur:
        cur.execute(
            "SELECT score_id FROM {p}golf_handicap_history WHERE score_id=%s".format(
                p=config.DB_PREFIX
            ),
            (score_id,),
        )
        return cur.fetchone() is not None


def sync_hole_data(conn, db_score_id, db_tee_id, scorecard):
    """
    Write hole-by-hole scores for a round, correctly handling all three
    EG score formats:

      "5"    plain numeric  — normal complete hole
      "8(7)"  composite      — player entered 8, EG adjusted to 7 for handicap
      "*"    missing        — hole not entered; round submitted incomplete

    All holes present in the scorecard payload are written.  Missing holes
    receive NULL gross values and score_status='missing' rather than being
    silently dropped.

    Uses ON DUPLICATE KEY UPDATE throughout so it is safe to re-run on
    rounds that were previously partially imported.
    """
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

                log.debug(
                    "  score_id=%s hole=%d raw=%r class=%r → status=%s gross=%s adj=%s",
                    db_score_id, i, raw_score, raw_class,
                    parsed["score_status"], parsed["gross_score"],
                    parsed["adjusted_gross_score"],
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
                    "INSERT INTO {p}golf_hole_scores "
                    "(score_id, hole_number, gross_score, adjusted_gross_score, "
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
                        i,
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


# ---------------------------------------------------------------------------
# Dynamic Insertion Helpers
# ---------------------------------------------------------------------------


def resolve_tee(raw, tees_list):
    eg_facility_id = raw.get("FacilityId") or raw.get("ClubId")
    marker = (raw.get("Marker") or "").strip().lower()

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

    cr = raw.get("CourseRating")
    sl = raw.get("Slope")
    if cr and sl:
        try:
            eg_cr = float(cr)
            eg_sl = int(sl)
            for t in tees_list:
                try:
                    if abs(float(t["course_rating"]) - eg_cr) < 0.2 and int(t["slope_rating"]) == eg_sl:
                        return t
                except (TypeError, ValueError):
                    continue
        except (TypeError, ValueError):
            pass

    return None


def get_par_from_sources(raw, scorecard=None):
    for val in (raw.get("Par"), raw.get("CoursePar")):
        if val is not None and str(val).strip() != "":
            try:
                return int(float(val)), False
            except (TypeError, ValueError):
                pass

    if scorecard:
        for val in (scorecard.get("TotalPar"),):
            if val is not None and str(val).strip() != "":
                try:
                    return int(float(val)), False
                except (TypeError, ValueError):
                    pass

    return 72, True


def ensure_course_and_tee(conn, raw, tees_list, player_issues=None, scorecard=None):
    existing = resolve_tee(raw, tees_list)
    if existing:
        return existing

    eg_facility_id = raw.get("FacilityId") or raw.get("ClubId")
    facility_name = (raw.get("FacilityName") or raw.get("CourseName") or "").strip()
    marker = (raw.get("Marker") or "").strip()
    cr = raw.get("CourseRating")
    sl = raw.get("Slope")

    if not marker:
        log.warning("  ensure_course_and_tee: no Marker in EG record — cannot insert tee")
        return None

    if not cr or not sl:
        log.warning("  ensure_course_and_tee: missing CourseRating/Slope in EG record — cannot insert tee")
        return None

    try:
        cr_float = float(cr)
        sl_int = int(sl)
    except (TypeError, ValueError) as exc:
        log.warning("  ensure_course_and_tee: could not parse numeric fields: %s", exc)
        return None

    par_int, guessed_par = get_par_from_sources(raw, scorecard=scorecard)

    try:
        with conn.cursor() as cur:
            course_id = None

            if eg_facility_id:
                try:
                    cur.execute(
                        "SELECT course_id FROM {p}golf_courses WHERE eg_club_id=%s".format(p=config.DB_PREFIX),
                        (int(eg_facility_id),)
                    )
                    row = cur.fetchone()
                    if row:
                        course_id = row["course_id"]
                except (TypeError, ValueError):
                    pass

            if course_id is None and facility_name:
                cur.execute(
                    "SELECT course_id FROM {p}golf_courses WHERE course_name=%s".format(p=config.DB_PREFIX),
                    (facility_name,)
                )
                row = cur.fetchone()
                if row:
                    course_id = row["course_id"]

            if course_id is None:
                insert_name = facility_name or f"EG Course {eg_facility_id or 'Unknown'}"
                eg_club_id_value = None
                if eg_facility_id:
                    try:
                        eg_club_id_value = int(eg_facility_id)
                    except (TypeError, ValueError):
                        eg_club_id_value = None

                cur.execute(
                    "INSERT INTO {p}golf_courses (course_name, eg_club_id) VALUES (%s, %s)".format(p=config.DB_PREFIX),
                    (insert_name, eg_club_id_value)
                )
                course_id = cur.lastrowid
                log.info(
                    "  AUTO-ADDED course: '%s' (course_id=%s, eg_club_id=%s)",
                    insert_name, course_id, eg_club_id_value
                )

            cur.execute(
                "SELECT tee_id FROM {p}golf_tees WHERE course_id=%s AND tee_colour=%s".format(
                    p=config.DB_PREFIX
                ),
                (course_id, marker)
            )
            tee_row = cur.fetchone()

            if tee_row:
                tee_id = tee_row["tee_id"]
                log.info("  Tee '%s' already exists for course_id=%s (tee_id=%s)", marker, course_id, tee_id)
            else:
                cur.execute(
                    "INSERT INTO {p}golf_tees (course_id, tee_colour, course_rating, slope_rating, par) "
                    "VALUES (%s, %s, %s, %s, %s)".format(p=config.DB_PREFIX),
                    (course_id, marker, cr_float, sl_int, par_int)
                )
                tee_id = cur.lastrowid
                log.info(
                    "  AUTO-ADDED tee: '%s' for course_id=%s (tee_id=%s, CR=%.1f, Slope=%d, Par=%d)",
                    marker, course_id, tee_id, cr_float, sl_int, par_int
                )

        conn.commit()

        tees_list.clear()
        tees_list.extend(load_tees(conn))

        if guessed_par and player_issues is not None:
            player_issues.add(
                "  Auto-added course/tee used guessed par 72 for '{}' / '{}' — please verify manually".format(
                    facility_name or "Unknown course", marker
                )
            )

        new_tee = resolve_tee(raw, tees_list)
        if not new_tee:
            new_tee = next((t for t in tees_list if t["tee_id"] == tee_id), None)

        return new_tee

    except Exception as exc:
        conn.rollback()
        log.error("  ensure_course_and_tee: DB error — rollback. %s", exc)
        return None


def insert_score(conn, player_id, date_played, tee_id, gross_score, pcc):
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT score_id FROM {p}golf_scores WHERE player_id=%s AND date_played=%s".format(
                    p=config.DB_PREFIX
                ),
                (player_id, date_played),
            )
            existing = cur.fetchone()
            if existing:
                return existing["score_id"], False

            cur.execute(
                "INSERT INTO {p}golf_scores "
                "(player_id, date_played, tee_id, gross_score, pcc_adjustment) "
                "VALUES (%s, %s, %s, %s, %s)".format(p=config.DB_PREFIX),
                (player_id, date_played, tee_id, gross_score, pcc)
            )
            new_id = cur.lastrowid

        conn.commit()
        return new_id, True

    except Exception as exc:
        conn.rollback()
        log.error("  insert_score: DB error — rollback. %s", exc)
        return None, False


# ---------------------------------------------------------------------------
# Email
# ---------------------------------------------------------------------------


def send_email(subject, body):
    try:
        msg = MIMEMultipart()
        msg["From"] = config.EMAIL_FROM
        msg["To"] = config.EMAIL_TO
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))

        recipients = [addr.strip() for addr in config.EMAIL_TO.split(",")]

        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=15) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(config.SMTP_USER, config.SMTP_PASSWORD)
            smtp.sendmail(config.EMAIL_FROM, recipients, msg.as_string())

        log.info("Email sent: %s", subject)

    except Exception as exc:
        log.error("Failed to send email '%s': %s", subject, exc)


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


def run_backfill(session, conn, db_players, tees_list):
    results = []

    for player_cfg in config.PLAYERS:
        name = player_cfg["name"]
        eg_id = player_cfg["eg_passport_id"]
        log.info("--- BACKFILL: %s (eg_id=%s) ---", name, eg_id)

        db_row = db_players.get(name)
        if not db_row:
            log.warning("'%s' not found in wp_golf_players -- skipping", name)
            results.append({
                "name": name, "status": "NOT IN DB", "issues": 0, "eg_hi": "n/a", "local_hi": "n/a"
            })
            continue

        player_id = db_row["player_id"]
        action_count = 0
        all_records = []
        page = 1

        try:
            while True:
                records = eg_fetch_scores(session, passport_id=eg_id, page_size=100, page_number=page)
                if not records:
                    break
                all_records.extend(records)
                page += 1
            log.info("  Fetched %d historical records across %d pages", len(all_records), page - 1)
        except Exception as exc:
            log.error("  EG fetch failed for %s: %s", name, exc)
            results.append({
                "name": name, "status": "EG ERROR", "issues": 0, "eg_hi": "n/a", "local_hi": "n/a"
            })
            continue

        for raw in all_records:
            play_date_str = parse_play_date(raw)
            if not play_date_str:
                continue

            eg_gross = parse_gross(raw)
            eg_pcc = parse_pcc(raw)
            eg_score_id = raw.get("ScoreId")
            eg_score_code = raw.get("ScoreCode")

            db_score = get_db_score(conn, player_id, play_date_str)
            scorecard = None

            if eg_score_id and eg_score_code:
                try:
                    scorecard = eg_fetch_scorecard(session, eg_score_id, score_code=eg_score_code)
                except Exception as exc:
                    log.error("  BACKFILL scorecard fetch error for %s on %s: %s", name, play_date_str, exc)

            if not db_score:
                if eg_gross is None:
                    continue

                tee_row = ensure_course_and_tee(conn, raw, tees_list, player_issues=None, scorecard=scorecard)
                if tee_row is None:
                    continue

                score_id, inserted = insert_score(
                    conn,
                    player_id=player_id,
                    date_played=play_date_str,
                    tee_id=tee_row["tee_id"],
                    gross_score=eg_gross,
                    pcc=eg_pcc,
                )

                if score_id:
                    db_score = get_db_score(conn, player_id, play_date_str)
                    action_count += 1

            if not db_score:
                continue

            score_id = db_score["score_id"]
            db_tee_id = db_score["tee_id"]

            if scorecard and not has_hole_scores(conn, score_id):
                synced = sync_hole_data(conn, score_id, db_tee_id, scorecard)
                if synced > 0:
                    log.info("  BACKFILL hole sync OK: %d holes for score_id=%s (%s)", synced, score_id, play_date_str)
                    action_count += 1

            time.sleep(0.3)

        log.info("  BACKFILL complete for %s: %d actions", name, action_count)
        results.append({
            "name": name, "status": f"BACKFILLED {action_count}", "issues": 0, "eg_hi": "n/a", "local_hi": "n/a"
        })
        time.sleep(0.5)

    return results, []


def run_daily_check(session, conn, db_players, tees_list, check_date_str, test_mode):
    results = []
    discrepancy_lines = []

    for player_cfg in config.PLAYERS:
        name = player_cfg["name"]
        eg_id = player_cfg["eg_passport_id"]
        log.info("--- %s (eg_id=%s) ---", name, eg_id)

        eg_hi_str = "n/a"
        local_hi_str = "n/a"
        eg_hi = None
        player_issues = set()

        db_row = db_players.get(name)
        if not db_row:
            log.warning("'%s' not found in wp_golf_players -- skipping", name)
            results.append({
                "name": name, "status": "NOT IN DB", "issues": 0, "eg_hi": "n/a", "local_hi": "n/a"
            })
            continue

        player_id = db_row["player_id"]

        try:
            eg_hi = eg_fetch_hi(session, passport_id=eg_id)
            if eg_hi is not None:
                eg_hi_str = "{:.1f}".format(float(eg_hi))
            log.info("  EG HI=%s  Local HI=<pending score check>", eg_hi_str)
        except Exception as e:
            log.error("  Error fetching EG HI: %s", e)

        try:
            raw_scores = eg_fetch_scores(session, passport_id=eg_id, page_size=40)
            log.info("  EG returned %d records", len(raw_scores))
        except Exception as exc:
            log.error("  EG fetch failed: %s", exc)
            results.append({
                "name": name, "status": "EG ERROR", "issues": len(player_issues),
                "eg_hi": eg_hi_str, "local_hi": local_hi_str,
            })
            continue

        target_records = [
            (parse_play_date(r), r)
            for r in raw_scores
            if parse_play_date(r) == check_date_str
        ]

        if not target_records:
            log.info("  No target EG scores found for %s -- nothing to check", name)
            status_msgs = {"NO TARGET EG SCORES"}

        else:
            status_msgs = set()
            processed_dates = set()

            for play_date_str, raw in target_records:
                if play_date_str in processed_dates:
                    log.warning(
                        "  Duplicate EG record found for %s on %s - skipping to prevent hole corruption",
                        name, play_date_str
                    )
                    continue
                processed_dates.add(play_date_str)

                eg_gross = parse_gross(raw)
                eg_pcc = parse_pcc(raw)
                eg_score_id = raw.get("ScoreId")
                eg_score_code = raw.get("ScoreCode")
                eg_facility = raw.get("FacilityId") or raw.get("ClubId")
                scorecard = None

                log.info(
                    "  EG: gross=%s  facility=%s  marker=%s  pcc=%s  ScoreId=%s  ScoreCode=%s",
                    eg_gross, eg_facility, (raw.get("Marker") or "").strip(), eg_pcc,
                    eg_score_id, eg_score_code,
                )

                if eg_gross is None:
                    player_issues.add(
                        "  EG returned an impossible or unreadable gross score for {} on {} — not processed".format(
                            name, play_date_str
                        )
                    )
                    status_msgs.add("BAD EG GROSS")
                    continue

                if eg_score_id and eg_score_code:
                    try:
                        scorecard = eg_fetch_scorecard(session, eg_score_id, score_code=eg_score_code)
                    except Exception as e:
                        log.error("  Error fetching scorecard before insert/check: %s", e)

                db_score = get_db_score(conn, player_id, play_date_str)

                if db_score is None:
                    log.info(
                        "  No DB record for %s on %s — attempting auto-insert from EG data",
                        name, play_date_str
                    )

                    tee_row = ensure_course_and_tee(
                        conn, raw, tees_list, player_issues=player_issues, scorecard=scorecard
                    )

                    if tee_row is None:
                        log.warning(
                            "  Cannot insert score for %s on %s: tee could not be resolved or created.",
                            name, play_date_str
                        )
                        player_issues.add(
                            "  Missing round NOT inserted: tee unresolvable for {} on {} "
                            "(EG marker={}, facility={})".format(
                                name, play_date_str,
                                (raw.get("Marker") or "").strip(), eg_facility
                            )
                        )
                        status_msgs.add("TEE UNRESOLVABLE — NOT INSERTED")
                        continue

                    score_id, inserted = insert_score(
                        conn,
                        player_id=player_id,
                        date_played=play_date_str,
                        tee_id=tee_row["tee_id"],
                        gross_score=eg_gross,
                        pcc=eg_pcc,
                    )

                    if score_id:
                        if inserted:
                            log.info(
                                "  AUTO-INSERTED score for %s on %s: gross=%s, tee='%s' (id=%s), pcc=%s → score_id=%s",
                                name, play_date_str, eg_gross,
                                tee_row["tee_colour"], tee_row["tee_id"], eg_pcc, score_id
                            )
                            status_msgs.add("AUTO-INSERTED")
                        else:
                            log.warning(
                                "  Duplicate guard prevented second insert for %s on %s — using existing score_id=%s",
                                name, play_date_str, score_id
                            )
                            status_msgs.add("ALREADY EXISTS")

                        if not verify_trigger_effect(conn, score_id):
                            player_issues.add(
                                "  Handicap history missing after insert for {} on {} — trigger may not have run".format(
                                    name, play_date_str
                                )
                            )

                        if scorecard:
                            synced_count = sync_hole_data(conn, score_id, tee_row["tee_id"], scorecard)
                            if synced_count > 0:
                                log.info("  Hole sync OK: %d hole scores written for score_id=%s", synced_count, score_id)
                            else:
                                log.warning("  Hole sync returned 0 rows for score_id=%s", score_id)

                        db_score = get_db_score(conn, player_id, play_date_str)
                        if db_score is None:
                            log.error(
                                "  Could not reload db_score after insert for %s on %s — skipping checks",
                                name, play_date_str
                            )
                            continue
                else:
                    status_msgs.add("CHECKED")

                score_id = db_score["score_id"]
                db_gross = db_score["gross_score"]
                db_tee_id = db_score["tee_id"]
                db_pcc = db_score["pcc_adjustment"]
                db_tee_col = db_score["tee_colour"] or "UNKNOWN"

                eg_tee_row = resolve_tee(raw, tees_list)
                eg_tee_id = eg_tee_row["tee_id"] if eg_tee_row else None
                eg_tee_col = eg_tee_row["tee_colour"] if eg_tee_row else "UNKNOWN"

                log.info("  DB:  gross=%s  tee=%s (id=%s)  pcc=%s", db_gross, db_tee_col, db_tee_id, db_pcc)
                log.info(
                    "  EG → DB tee match:  EG tee=%s (id=%s)  DB tee=%s (id=%s)",
                    eg_tee_col, eg_tee_id, db_tee_col, db_tee_id,
                )

                if eg_pcc != 0:
                    if int(eg_pcc) != int(db_pcc):
                        log.info(
                            "  PCC UPDATED %s %s: DB had %s --> EG says %s (no email per Rule 6)",
                            name, play_date_str, db_pcc, eg_pcc,
                        )
                        try:
                            update_pcc(conn, score_id, eg_pcc)
                        except Exception as exc:
                            log.error("  PCC update failed for %s on %s: %s", name, play_date_str, exc)
                    else:
                        log.info("  PCC already matches EG: %s -- no update needed", eg_pcc)
                else:
                    log.info("  PCC is 0 on EG -- no PCC update required")

                if eg_gross is not None and db_gross is not None:
                    if int(eg_gross) != int(db_gross):
                        player_issues.add(
                            "  Gross score mismatch:  EG={}  DB={}".format(eg_gross, db_gross)
                        )

                if eg_tee_id is not None and db_tee_id is not None:
                    if int(eg_tee_id) != int(db_tee_id):
                        player_issues.add(
                            "  Tee/Course mismatch:  EG mapped to tee_id={} ({})  DB is tee_id={} ({})".format(
                                eg_tee_id, eg_tee_col, db_tee_id, db_tee_col
                            )
                        )

                if scorecard and db_tee_id:
                    synced_count = sync_hole_data(conn, score_id, db_tee_id, scorecard)
                    if synced_count > 0:
                        log.info("  Hole sync OK: %d hole scores written for score_id=%s", synced_count, score_id)
                    else:
                        log.warning("  Hole sync returned 0 rows for score_id=%s", score_id)
                elif eg_score_id and not eg_score_code:
                    log.warning(
                        "  ScoreCode missing from EG record for ScoreId=%s -- hole sync skipped.",
                        eg_score_id,
                    )

        try:
            local_hi = read_local_hi(conn, name)
            if local_hi is not None:
                local_hi_str = "{:.1f}".format(float(local_hi))
            log.info("  EG HI=%s  Local HI=%s", eg_hi_str, local_hi_str)

            if name not in HI_IGNORE_PLAYERS:
                if eg_hi is not None and local_hi is not None:
                    if abs(float(eg_hi) - float(local_hi)) > 0.05:
                        player_issues.add(
                            "  HI mismatch:  EG={}  Local={}".format(eg_hi_str, local_hi_str)
                        )
        except Exception as e:
            log.error("  Error reading local HI for %s: %s", name, e)

        final_status = " | ".join(sorted(status_msgs)) if status_msgs else "UNKNOWN"

        if player_issues:
            block = "Player: {}  |  Date: {}{}{}".format(
                name, check_date_str,
                " [TEST MODE]" if test_mode else "",
                "\n" + "\n".join(sorted(list(player_issues))),
            )
            discrepancy_lines.append(block)
            log.warning("  Discrepancies found for %s:", name)
            for issue in player_issues:
                log.warning(issue)
        else:
            log.info("  All data matches for %s (no alertable discrepancies)", name)

        results.append({
            "name": name,
            "status": final_status,
            "issues": len(player_issues),
            "eg_hi": eg_hi_str,
            "local_hi": local_hi_str,
        })

        time.sleep(0.5)

    return results, discrepancy_lines


# ---------------------------------------------------------------------------
# Main checker
# ---------------------------------------------------------------------------


def check(test_mode=False, backfill_mode=False):
    if backfill_mode:
        check_date_str = "BACKFILL_MODE"
        log.info("=== 828ers EG Check - BACKFILL MODE ===")
        log.info("Fetching all historical records to sync missing scores and hole-by-hole data.")
        log.info("Emails and general mismatch checks are suppressed during backfill.")
    elif test_mode:
        check_date = date.today()
        check_date_str = check_date.isoformat()
        log.info("=== 828ers EG Daily Check - %s [TEST MODE] ===", date.today())
        log.info("TEST MODE: checking today's scores (%s) instead of yesterday", check_date_str)
    else:
        check_date = date.today() - timedelta(days=1)
        check_date_str = check_date.isoformat()
        log.info("=== 828ers EG Daily Check - %s ===", date.today())
        log.info("Checking EG scores for yesterday: %s", check_date_str)

    try:
        session = eg_login()
    except Exception as exc:
        log.error("EG login failed: %s", exc)
        send_email(
            "828ers EG Score Check - LOGIN FAILED",
            f"Could not log into EG API.\n\n=== RUN LOG ===\n{log_stream.getvalue()}"
        )
        sys.exit(1)

    conn = None
    try:
        conn = get_conn()

        db_players = load_players(conn)
        tees_list = list(load_tees(conn))

        if not db_players or not tees_list:
            log.error("Missing players or tees in DB config.")
            sys.exit(1)

        log.info("DB players : %s", list(db_players.keys()))

        if not backfill_mode and not test_mode:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM {p}golf_scores s "
                    "LEFT JOIN {p}golf_hole_scores hs ON hs.score_id = s.score_id "
                    "WHERE s.date_played=%s AND s.is_excluded=0 "
                    "GROUP BY s.score_id HAVING COUNT(hs.hole_number) >= 18 LIMIT 1".format(
                        p=config.DB_PREFIX
                    ),
                    (check_date_str,),
                )
                if cur.fetchone():
                    log.info("Hole-by-hole data already exists for %s -- skipping run.", check_date_str)
                    return

        config_player_names = {p["name"] for p in config.PLAYERS}
        for db_name in db_players.keys():
            if db_name not in config_player_names:
                log.warning("Player '%s' is in the DB but missing from config.PLAYERS.", db_name)

        if backfill_mode:
            results, discrepancy_lines = run_backfill(session, conn, db_players, tees_list)
        else:
            results, discrepancy_lines = run_daily_check(session, conn, db_players, tees_list, check_date_str, test_mode)

    except Exception as exc:
        log.error("DB connection or main loop failed: %s", exc)
        send_email(
            "828ers EG Score Check - RUN FAILED",
            f"An unexpected error occurred during execution.\n\n=== RUN LOG ===\n{log_stream.getvalue()}"
        )
        sys.exit(1)
    finally:
        if conn:
            conn.close()

    mode_label = " [TEST MODE]" if test_mode else (" [BACKFILL MODE]" if backfill_mode else "")
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

    if backfill_mode:
        log.info("Backfill complete. No email alerts are generated in backfill mode.")
        return

    if not discrepancy_lines:
        log.info("No alertable discrepancies found; summary email suppressed.")
        return

    log.info("Preparing discrepancy email...")
    capture_handler.flush()
    full_log_contents = log_stream.getvalue()

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
        "Missing rounds may have been auto-inserted into the DB.\n\n"
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
    parser.add_argument(
        "--backfill", action="store_true",
        help="Backfill mode: fetch all historical scorecards that are missing from the local DB",
    )
    args = parser.parse_args()
    check(test_mode=args.test, backfill_mode=args.backfill)
