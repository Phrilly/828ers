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
from datetime import date, timedelta, datetime
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

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
    parse_eg_round_ratings,
    EGRatingError,
    EGRoundRatings,
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


class FeedDataError(ValueError):
    pass


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
            "SELECT s.score_id, s.gross_score, s.tee_id, s.pcc_adjustment, "
            "t.tee_colour, t.course_id, c.course_name "
            "FROM {p}golf_scores s "
            "LEFT JOIN {p}golf_tees t ON s.tee_id = t.tee_id "
            "LEFT JOIN {p}golf_courses c ON t.course_id = c.course_id "
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


def load_recent_manual_dates(
    conn: Any,
    player_id: int,
    check_date: str,
) -> Sequence[str]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT DISTINCT date_played "
            "FROM {p}golf_scores "
            "WHERE player_id=%s "
            "AND rating_source='manual_placeholder' "
            "AND date_played BETWEEN DATE_SUB(%s, INTERVAL 7 DAY) AND %s".format(
                p=config.DB_PREFIX
            ),
            (player_id, check_date, check_date),
        )
        return [str(row["date_played"]) for row in cur.fetchall()]


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


def resolve_tee(
    raw: Mapping[str, Any],
    tees_list: Sequence[Mapping[str, Any]],
) -> Optional[Mapping[str, Any]]:
    marker = (raw.get("Marker") or "").strip().lower()
    eg_facility_id = raw.get("FacilityId") or raw.get("ClubId")
    facility_name = normalize_course_name(
        raw.get("FacilityName") or raw.get("CourseName") or ""
    )

    if eg_facility_id and marker:
        try:
            eg_fac_int = int(eg_facility_id)
            for t in tees_list:
                try:
                    if int(t.get("eg_club_id") or 0) == eg_fac_int and str(t.get("tee_colour") or "").strip().lower() == marker:
                        return t
                except (TypeError, ValueError):
                    continue
        except (TypeError, ValueError):
            pass

    if facility_name and marker:
        for t in tees_list:
            if (
                normalize_course_name(t.get("course_name") or "") == facility_name
                and str(t.get("tee_colour") or "").strip().lower() == marker
            ):
                return t

    return None


def normalize_course_name(value: Any) -> str:
    normalized = re.sub(r"[^a-z0-9]+", " ", str(value or "").strip().lower())
    normalized = re.sub(
        r"\s+(golf\s+club|golf\s+course)$",
        "",
        normalized,
    )
    return " ".join(normalized.split())


def tee_ratings_differ(
    tee_row: Mapping[str, Any],
    ratings: EGRoundRatings,
) -> bool:
    try:
        return (
            round(float(tee_row["course_rating"]), 1) != ratings.course_rating
            or int(tee_row["slope_rating"]) != ratings.slope_rating
            or int(tee_row["par"]) != ratings.par
        )
    except (KeyError, TypeError, ValueError):
        return True


def ensure_course_and_tee(
    conn: Any,
    raw: Mapping[str, Any],
    tees_list: Sequence[Mapping[str, Any]],
    ratings: EGRoundRatings,
    preview: bool = False,
) -> Dict[str, Any]:
    existing = resolve_tee(raw, tees_list)
    if existing:
        changed = tee_ratings_differ(existing, ratings)
        resolved = dict(existing)
        resolved["course_rating"] = ratings.course_rating
        resolved["slope_rating"] = ratings.slope_rating
        resolved["par"] = ratings.par
        resolved["ratings_changed"] = changed

        if changed:
            log.info(
                "  %s tee ratings for course='%s', tee='%s': "
                "CR %s -> %.1f, Slope %s -> %d, Par %s -> %d",
                "WOULD UPDATE" if preview else "UPDATING",
                existing.get("course_name") or existing.get("course_id"),
                existing.get("tee_colour"),
                existing.get("course_rating"),
                ratings.course_rating,
                existing.get("slope_rating"),
                ratings.slope_rating,
                existing.get("par"),
                ratings.par,
            )
            if not preview:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE {p}golf_tees "
                        "SET course_rating=%s, slope_rating=%s, par=%s "
                        "WHERE tee_id=%s".format(p=config.DB_PREFIX),
                        (
                            ratings.course_rating,
                            ratings.slope_rating,
                            ratings.par,
                            existing["tee_id"],
                        ),
                    )

        return resolved

    eg_facility_id = raw.get("FacilityId") or raw.get("ClubId")
    facility_name = (raw.get("FacilityName") or raw.get("CourseName") or "").strip()
    marker = (raw.get("Marker") or "").strip()

    if not marker:
        raise FeedDataError("England Golf record has no tee colour (Marker)")

    if not eg_facility_id and not facility_name:
        raise FeedDataError("England Golf record has no course or facility")

    with conn.cursor() as cur:
        course_id = None
        course_name = facility_name
        stored_eg_club_id = None

        if eg_facility_id:
            try:
                cur.execute(
                    "SELECT course_id, course_name, eg_club_id "
                    "FROM {p}golf_courses WHERE eg_club_id=%s".format(
                        p=config.DB_PREFIX
                    ),
                    (int(eg_facility_id),)
                )
                row = cur.fetchone()
                if row:
                    course_id = row["course_id"]
                    course_name = row["course_name"]
                    stored_eg_club_id = row["eg_club_id"]
            except (TypeError, ValueError):
                pass

        if course_id is None and facility_name:
            cur.execute(
                "SELECT course_id, course_name, eg_club_id "
                "FROM {p}golf_courses WHERE course_name=%s".format(
                    p=config.DB_PREFIX
                ),
                (facility_name,)
            )
            row = cur.fetchone()
            if row:
                course_id = row["course_id"]
                course_name = row["course_name"]
                stored_eg_club_id = row["eg_club_id"]

        if course_id is None and facility_name:
            cur.execute(
                "SELECT course_id, course_name, eg_club_id "
                "FROM {p}golf_courses".format(p=config.DB_PREFIX)
            )
            normalized_name = normalize_course_name(facility_name)
            matching_courses = [
                row
                for row in cur.fetchall()
                if normalize_course_name(row.get("course_name")) == normalized_name
            ]
            if len(matching_courses) > 1:
                raise FeedDataError(
                    f"Multiple database courses match England Golf course {facility_name!r}"
                )
            if matching_courses:
                row = matching_courses[0]
                course_id = row["course_id"]
                course_name = row["course_name"]
                stored_eg_club_id = row["eg_club_id"]

        eg_club_id_value = None
        if eg_facility_id:
            try:
                eg_club_id_value = int(eg_facility_id)
            except (TypeError, ValueError):
                eg_club_id_value = None

        if course_id is None:
            insert_name = facility_name or f"EG Course {eg_facility_id}"
            if preview:
                log.info(
                    "  WOULD CREATE course='%s' (EG facility=%s) and tee='%s'",
                    insert_name,
                    eg_club_id_value,
                    marker,
                )
                return {
                    "tee_id": None,
                    "course_id": None,
                    "tee_colour": marker,
                    "course_rating": ratings.course_rating,
                    "slope_rating": ratings.slope_rating,
                    "par": ratings.par,
                    "course_name": insert_name,
                    "eg_club_id": eg_club_id_value,
                    "ratings_changed": True,
                    "would_create": True,
                }

            cur.execute(
                "INSERT INTO {p}golf_courses (course_name, eg_club_id) "
                "VALUES (%s, %s)".format(p=config.DB_PREFIX),
                (insert_name, eg_club_id_value)
            )
            course_id = cur.lastrowid
            course_name = insert_name
            stored_eg_club_id = eg_club_id_value
            log.info(
                "  AUTO-ADDED course: '%s' (course_id=%s, eg_club_id=%s)",
                insert_name, course_id, eg_club_id_value
            )

        cur.execute(
            "SELECT tee_id, course_id, tee_colour, course_rating, slope_rating, par "
            "FROM {p}golf_tees WHERE course_id=%s AND tee_colour=%s".format(
                p=config.DB_PREFIX
            ),
            (course_id, marker)
        )
        tee_row = cur.fetchone()

        if tee_row:
            tee_row["course_name"] = course_name
            tee_row["eg_club_id"] = stored_eg_club_id
            changed = tee_ratings_differ(tee_row, ratings)
            resolved = dict(tee_row)
            resolved["course_rating"] = ratings.course_rating
            resolved["slope_rating"] = ratings.slope_rating
            resolved["par"] = ratings.par
            resolved["ratings_changed"] = changed

            if changed:
                log.info(
                    "  %s tee ratings for course='%s', tee='%s': "
                    "CR %s -> %.1f, Slope %s -> %d, Par %s -> %d",
                    "WOULD UPDATE" if preview else "UPDATING",
                    course_name,
                    marker,
                    tee_row["course_rating"],
                    ratings.course_rating,
                    tee_row["slope_rating"],
                    ratings.slope_rating,
                    tee_row["par"],
                    ratings.par,
                )
                if not preview:
                    cur.execute(
                        "UPDATE {p}golf_tees "
                        "SET course_rating=%s, slope_rating=%s, par=%s "
                        "WHERE tee_id=%s".format(p=config.DB_PREFIX),
                        (
                            ratings.course_rating,
                            ratings.slope_rating,
                            ratings.par,
                            tee_row["tee_id"],
                        ),
                    )
            return resolved

        if preview:
            log.info(
                "  WOULD CREATE tee='%s' for course='%s' with CR=%.1f, Slope=%d, Par=%d",
                marker,
                course_name,
                ratings.course_rating,
                ratings.slope_rating,
                ratings.par,
            )
            return {
                "tee_id": None,
                "course_id": course_id,
                "tee_colour": marker,
                "course_rating": ratings.course_rating,
                "slope_rating": ratings.slope_rating,
                "par": ratings.par,
                "course_name": course_name,
                "eg_club_id": stored_eg_club_id,
                "ratings_changed": True,
                "would_create": True,
            }

        cur.execute(
            "INSERT INTO {p}golf_tees "
            "(course_id, tee_colour, course_rating, slope_rating, par) "
            "VALUES (%s, %s, %s, %s, %s)".format(p=config.DB_PREFIX),
            (
                course_id,
                marker,
                ratings.course_rating,
                ratings.slope_rating,
                ratings.par,
            )
        )
        tee_id = cur.lastrowid
        log.info(
            "  AUTO-ADDED tee: '%s' for course_id=%s "
            "(tee_id=%s, CR=%.1f, Slope=%d, Par=%d)",
            marker,
            course_id,
            tee_id,
            ratings.course_rating,
            ratings.slope_rating,
            ratings.par,
        )

    return {
        "tee_id": tee_id,
        "course_id": course_id,
        "tee_colour": marker,
        "course_rating": ratings.course_rating,
        "slope_rating": ratings.slope_rating,
        "par": ratings.par,
        "course_name": course_name,
        "eg_club_id": stored_eg_club_id,
        "ratings_changed": True,
        "would_create": False,
    }


def insert_score(
    conn: Any,
    player_id: int,
    date_played: str,
    tee_row: Mapping[str, Any],
    gross_score: int,
    pcc: int,
    ratings: EGRoundRatings,
    preview: bool = False,
) -> Tuple[Optional[int], bool]:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT s.score_id, s.tee_id, s.gross_score, s.pcc_adjustment, "
            "t.course_id, t.tee_colour "
            "FROM {p}golf_scores s "
            "LEFT JOIN {p}golf_tees t ON t.tee_id=s.tee_id "
            "WHERE s.player_id=%s AND s.date_played=%s "
            "ORDER BY s.score_id".format(p=config.DB_PREFIX),
            (player_id, date_played),
        )
        existing_rows = cur.fetchall()

        if len(existing_rows) > 1:
            raise FeedDataError(
                f"Multiple database rounds exist for player_id={player_id} on {date_played}"
            )

        existing = existing_rows[0] if existing_rows else None
        if existing:
            same_course = (
                tee_row.get("course_id") is not None
                and existing.get("course_id") is not None
                and int(tee_row["course_id"]) == int(existing["course_id"])
            )
            same_tee_colour = (
                str(tee_row.get("tee_colour") or "").strip().lower()
                == str(existing.get("tee_colour") or "").strip().lower()
            )
            if not same_course or not same_tee_colour:
                raise FeedDataError(
                    "Existing round does not match England Golf course and tee: "
                    "DB course_id={}, tee={!r}; EG course_id={}, tee={!r}".format(
                        existing.get("course_id"),
                        existing.get("tee_colour"),
                        tee_row.get("course_id"),
                        tee_row.get("tee_colour"),
                    )
                )

            log.info(
                "  %s existing score_id=%s with gross=%s, PCC=%s, "
                "CR=%.1f, Slope=%d, Par=%d",
                "WOULD OVERWRITE" if preview else "OVERWRITING",
                existing["score_id"],
                gross_score,
                pcc,
                ratings.course_rating,
                ratings.slope_rating,
                ratings.par,
            )
            if not preview:
                cur.execute(
                    "UPDATE {p}golf_scores SET "
                    "tee_id=%s, gross_score=%s, pcc_adjustment=%s, "
                    "round_course_rating=%s, round_slope_rating=%s, round_par=%s, "
                    "rating_source=%s, rating_updated_at=%s "
                    "WHERE score_id=%s".format(p=config.DB_PREFIX),
                    (
                        tee_row["tee_id"],
                        gross_score,
                        pcc,
                        ratings.course_rating,
                        ratings.slope_rating,
                        ratings.par,
                        "eg_import",
                        datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                        existing["score_id"],
                    ),
                )
            return existing["score_id"], False

        log.info(
            "  %s new score with gross=%s, PCC=%s, CR=%.1f, Slope=%d, Par=%d",
            "WOULD INSERT" if preview else "INSERTING",
            gross_score,
            pcc,
            ratings.course_rating,
            ratings.slope_rating,
            ratings.par,
        )
        if preview:
            return None, True

        if tee_row.get("tee_id") is None:
            raise FeedDataError("Cannot insert a score without a database tee")

        cur.execute(
            "INSERT INTO {p}golf_scores "
            "(player_id, date_played, tee_id, gross_score, pcc_adjustment, "
            "round_course_rating, round_slope_rating, round_par, "
            "rating_source, rating_updated_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)".format(
                p=config.DB_PREFIX
            ),
            (
                player_id,
                date_played,
                tee_row["tee_id"],
                gross_score,
                pcc,
                ratings.course_rating,
                ratings.slope_rating,
                ratings.par,
                "eg_import",
                datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            )
        )
        return cur.lastrowid, True


def process_eg_round(
    conn: Any,
    raw: Mapping[str, Any],
    scorecard: Optional[Mapping[str, Any]],
    tees_list: List[Mapping[str, Any]],
    player_id: int,
    date_played: str,
    gross_score: int,
    pcc: int,
    preview: bool = False,
) -> Tuple[Optional[int], bool, Dict[str, Any], EGRoundRatings]:
    ratings = parse_eg_round_ratings(raw, scorecard=scorecard)

    try:
        tee_row = ensure_course_and_tee(
            conn,
            raw,
            tees_list,
            ratings,
            preview=preview,
        )
        score_id, inserted = insert_score(
            conn,
            player_id=player_id,
            date_played=date_played,
            tee_row=tee_row,
            gross_score=gross_score,
            pcc=pcc,
            ratings=ratings,
            preview=preview,
        )
        if preview:
            conn.rollback()
        else:
            conn.commit()
            tees_list.clear()
            tees_list.extend(load_tees(conn))
        return score_id, inserted, tee_row, ratings
    except Exception:
        if not preview:
            conn.rollback()
        raise


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

            scorecard = None

            if eg_score_id and eg_score_code:
                try:
                    scorecard = eg_fetch_scorecard(session, eg_score_id, score_code=eg_score_code)
                except Exception as exc:
                    log.error("  BACKFILL scorecard fetch error for %s on %s: %s", name, play_date_str, exc)

            if eg_gross is None:
                continue

            try:
                score_id, inserted, tee_row, ratings = process_eg_round(
                    conn,
                    raw=raw,
                    scorecard=scorecard,
                    tees_list=tees_list,
                    player_id=player_id,
                    date_played=play_date_str,
                    gross_score=eg_gross,
                    pcc=eg_pcc,
                )
            except (EGRatingError, FeedDataError) as exc:
                log.warning(
                    "  BACKFILL skipped %s on %s: %s",
                    name,
                    play_date_str,
                    exc,
                )
                continue
            except Exception as exc:
                log.error(
                    "  BACKFILL failed %s on %s: %s",
                    name,
                    play_date_str,
                    exc,
                )
                continue

            db_score = None
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


def build_target_date_set(
    from_date_str: Optional[str] = None,
    to_date_str: Optional[str] = None,
    default_date_str: Optional[str] = None,
) -> set[str]:
    if from_date_str or to_date_str:
        if not from_date_str or not to_date_str:
            raise ValueError("Both --from and --to must be provided for a custom date range.")
        start_date = date.fromisoformat(from_date_str)
        end_date = date.fromisoformat(to_date_str)
        if end_date < start_date:
            raise ValueError("The --to date must be on or after the --from date.")
        return {
            (start_date + timedelta(days=offset)).isoformat()
            for offset in range((end_date - start_date).days + 1)
        }

    return {default_date_str} if default_date_str else set()


def run_daily_check(
    session,
    conn,
    db_players,
    tees_list,
    check_date_str,
    test_mode,
    preview_mode=False,
    from_date_str=None,
    to_date_str=None,
):
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

        target_dates = build_target_date_set(
            from_date_str=from_date_str,
            to_date_str=to_date_str,
            default_date_str=check_date_str,
        )

        if not from_date_str and not to_date_str:
            try:
                recent_manual_dates = load_recent_manual_dates(
                    conn,
                    player_id,
                    check_date_str,
                )
                target_dates.update(recent_manual_dates)
                if recent_manual_dates:
                    log.info(
                        "  Rechecking unresolved manual dates: %s",
                        ", ".join(sorted(recent_manual_dates)),
                    )
            except Exception as exc:
                log.error("  Could not load recent manual dates for %s: %s", name, exc)
                player_issues.add(
                    "  Could not identify recent manual rounds awaiting England Golf"
                )

        target_records = [
            (parse_play_date(r), r)
            for r in raw_scores
            if parse_play_date(r) in target_dates
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

                try:
                    score_id, inserted, tee_row, ratings = process_eg_round(
                        conn,
                        raw=raw,
                        scorecard=scorecard,
                        tees_list=tees_list,
                        player_id=player_id,
                        date_played=play_date_str,
                        gross_score=eg_gross,
                        pcc=eg_pcc,
                        preview=preview_mode,
                    )
                except (EGRatingError, FeedDataError) as exc:
                    issue = (
                        "  England Golf round not processed for {} on {}: {} "
                        "(course={}, tee={})"
                    ).format(
                        name,
                        play_date_str,
                        exc,
                        raw.get("FacilityName") or raw.get("CourseName") or eg_facility,
                        (raw.get("Marker") or "").strip(),
                    )
                    player_issues.add(issue)
                    log.warning(
                        "  England Golf round not processed for %s on %s: %s",
                        name,
                        play_date_str,
                        exc,
                    )
                    status_msgs.add("EG DATA INVALID — NOT PROCESSED")
                    continue
                except Exception as exc:
                    issue = "  Database update failed for {} on {}: {}".format(
                        name,
                        play_date_str,
                        exc,
                    )
                    player_issues.add(issue)
                    log.error(
                        "  Database update failed for %s on %s: %s",
                        name,
                        play_date_str,
                        exc,
                    )
                    status_msgs.add("DB UPDATE FAILED")
                    continue

                log.info(
                    "  EG ratings: CR=%.1f, Slope=%d, Par=%d (source=%s)",
                    ratings.course_rating,
                    ratings.slope_rating,
                    ratings.par,
                    ratings.par_source,
                )

                if preview_mode:
                    status_msgs.add(
                        "PREVIEW — WOULD INSERT" if inserted else "PREVIEW — WOULD OVERWRITE"
                    )
                    continue

                if inserted:
                    log.info(
                        "  AUTO-INSERTED score for %s on %s: gross=%s, "
                        "tee='%s' (id=%s), pcc=%s, score_id=%s",
                        name,
                        play_date_str,
                        eg_gross,
                        tee_row["tee_colour"],
                        tee_row["tee_id"],
                        eg_pcc,
                        score_id,
                    )
                    status_msgs.add("AUTO-INSERTED")
                else:
                    log.info(
                        "  OVERWROTE existing score for %s on %s from EG feed: score_id=%s",
                        name,
                        play_date_str,
                        score_id,
                    )
                    status_msgs.add("OVERWROTE MANUAL/EXISTING")

                if not verify_trigger_effect(conn, score_id):
                    player_issues.add(
                        "  Handicap history missing after score write for {} on {} — trigger may not have run".format(
                            name,
                            play_date_str,
                        )
                    )

                db_score = get_db_score(conn, player_id, play_date_str)
                if db_score is None:
                    log.error(
                        "  Could not reload db_score after score write for %s on %s — skipping checks",
                        name,
                        play_date_str,
                    )
                    continue

                score_id = db_score["score_id"]
                db_gross = db_score["gross_score"]
                db_tee_id = db_score["tee_id"]
                db_pcc = db_score["pcc_adjustment"]
                db_tee_col = db_score["tee_colour"] or "UNKNOWN"

                eg_tee_id = tee_row["tee_id"]
                eg_tee_col = tee_row["tee_colour"]

                log.info("  DB:  gross=%s  tee=%s (id=%s)  pcc=%s", db_gross, db_tee_col, db_tee_id, db_pcc)
                log.info(
                    "  EG → DB tee match:  EG tee=%s (id=%s)  DB tee=%s (id=%s)",
                    eg_tee_col, eg_tee_id, db_tee_col, db_tee_id,
                )

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


def check(test_mode=False, backfill_mode=False, preview_mode=False, from_date=None, to_date=None):
    if backfill_mode:
        check_date_str = "BACKFILL_MODE"
        log.info("=== 828ers EG Check - BACKFILL MODE ===")
        log.info("Fetching all historical records to sync missing scores and hole-by-hole data.")
        log.info("Emails and general mismatch checks are suppressed during backfill.")
    elif from_date and to_date:
        check_date_str = f"{from_date} to {to_date}"
        log.info("=== 828ers EG Daily Check - custom range %s to %s ===", from_date, to_date)
        log.info("Checking EG scores for custom date range: %s to %s", from_date, to_date)
    elif test_mode:
        check_date = date.today()
        check_date_str = check_date.isoformat()
        log.info("=== 828ers EG Daily Check - %s [TEST MODE] ===", date.today())
        log.info("TEST MODE: checking today's scores (%s) instead of yesterday", check_date_str)
    else:
        check_date = date.today() - timedelta(days=1)
        check_date_str = check_date.isoformat()
        log.info(
            "=== 828ers EG Daily Check - %s%s ===",
            date.today(),
            " [PREVIEW]" if preview_mode else "",
        )
        log.info("Checking EG scores for yesterday: %s", check_date_str)

    if preview_mode:
        log.info("PREVIEW MODE: England Golf and database data will be read, but no changes will be saved.")

    try:
        session = eg_login()
    except Exception as exc:
        log.error("EG login failed: %s", exc)
        if not preview_mode:
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

        config_player_names = {p["name"] for p in config.PLAYERS}
        for db_name in db_players.keys():
            if db_name not in config_player_names:
                log.warning("Player '%s' is in the DB but missing from config.PLAYERS.", db_name)

        if backfill_mode:
            results, discrepancy_lines = run_backfill(session, conn, db_players, tees_list)
        else:
            results, discrepancy_lines = run_daily_check(
                session,
                conn,
                db_players,
                tees_list,
                check_date_str,
                test_mode,
                preview_mode=preview_mode,
                from_date_str=from_date,
                to_date_str=to_date,
            )

    except Exception as exc:
        log.error("DB connection or main loop failed: %s", exc)
        if not preview_mode:
            send_email(
                "828ers EG Score Check - RUN FAILED",
                f"An unexpected error occurred during execution.\n\n=== RUN LOG ===\n{log_stream.getvalue()}"
            )
        sys.exit(1)
    finally:
        if conn:
            conn.close()

    mode_label = (
        " [PREVIEW MODE]"
        if preview_mode
        else (" [TEST MODE]" if test_mode else (" [BACKFILL MODE]" if backfill_mode else ""))
    )
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

    if preview_mode:
        log.info("Preview complete. No database changes or email alerts were generated.")
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
    parser.add_argument(
        "--preview", action="store_true",
        help="Read EG and database data and report proposed changes without writing to the database",
    )
    parser.add_argument(
        "--from", "--from-date",
        dest="from_date",
        help="Custom EG check start date (YYYY-MM-DD). Requires --to.",
    )
    parser.add_argument(
        "--to", "--to-date",
        dest="to_date",
        help="Custom EG check end date (YYYY-MM-DD). Requires --from.",
    )
    args = parser.parse_args()
    if args.preview and args.backfill:
        parser.error("--preview cannot be combined with --backfill")
    if (args.from_date or args.to_date) and not (args.from_date and args.to_date):
        parser.error("--from and --to must be supplied together for a custom date range")
    if args.backfill and (args.from_date or args.to_date):
        parser.error("--backfill cannot be combined with a custom date range")
    check(
        test_mode=args.test,
        backfill_mode=args.backfill,
        preview_mode=args.preview,
        from_date=args.from_date,
        to_date=args.to_date,
    )
