#!/usr/bin/env python3
"""
golf_checker.py — 828ers Daily EG Consistency Check
====================================================
Runs via cron — recommended time: 10:05 AM (after EG publishes PCC).
  5 10 * * * cd /path/to/scripts && python golf_checker.py >> cron.log 2>&1

For each player:
  1. Fetches yesterday's score from EG
  2. Compares gross score, tee colour, date vs wp_golf_scores
  3. Compares EG HI vs view_handicap_index.current_handicap_index
  4. Emails an alert if any mismatch found
  5. If EG reports non-zero PCC and DB has 0, writes PCC to wp_golf_scores
     (AFTER UPDATE trigger then fires sp_repair_from_date automatically)

Schema confirmed from Phrilly/828ers repo audit (April 2026):
  wp_golf_players       — player_id, name, winner_colour
  wp_golf_scores        — score_id, player_id, tee_id, date_played,
                          gross_score, pcc_adjustment, putts, gir, is_excluded
  wp_golf_tees          — tee_id, tee_colour, course_rating, slope_rating, par
  view_handicap_index   — player_name, current_handicap_index

Usage:
  python golf_checker.py                # normal daily run
  python golf_checker.py --dry-run      # check everything, do NOT write PCC to DB
  python golf_checker.py --force-login  # ignore saved session, log in fresh
  python golf_checker.py --debug        # dump raw EG API responses to log

HOLES FIXED vs earlier drafts:
  #1  Dynamic form field discovery
  #3  HI endpoint errors are loud, not silent
  #4  Field name failures raise exceptions, not return None
  #5  Cron scheduled at 10:05 for PCC availability
  #6  Player name match verified (run eg_step5.py first)
  #8  HI mismatch tolerance raised to 0.2 (avoids rounding false positives)
  #10 Timezone-safe BST yesterday date
  #11 Pickle corruption handled cleanly
  #12 Email failures reported separately from content mismatches
  #13 Retry on network timeouts
  #14 sys.path fixed via __file__
  #16 pageSize=40 (not 5)
  #17 Config missing gives clear setup instructions
  #18 Log rotation via RotatingFileHandler
"""

import argparse
import logging
import smtplib
import sys
from datetime import date
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from logging.handlers import RotatingFileHandler

import pymysql

import config
from eg_utils import (
    eg_login, eg_fetch_scores, eg_fetch_hi, parse_yesterday_score,
    get_yesterday_bst,
    EGLoginError, EGAPIError, EGFieldError
)

# ── Logging (#18 — rotation so log never grows forever) ──────────
_log_handler = RotatingFileHandler(
    "golf_checker.log", maxBytes=1_000_000, backupCount=5
)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[_log_handler, logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger(__name__)

DB_PREFIX = config.DB_PREFIX


# ── Database ──────────────────────────────────────────────────────

def get_db():
    return pymysql.connect(
        host=config.DB_HOST, port=config.DB_PORT, db=config.DB_NAME,
        user=config.DB_USER, password=config.DB_PASSWORD,
        charset="utf8mb4", autocommit=False,
        cursorclass=pymysql.cursors.DictCursor,
    )


def db_get_player_id(conn, name: str) -> int | None:
    with conn.cursor() as cur:
        cur.execute(
            f"SELECT player_id FROM {DB_PREFIX}golf_players WHERE name = %s",
            (name,)
        )
        row = cur.fetchone()
    return int(row["player_id"]) if row else None


def db_get_yesterday_score(conn, player_id: int, target_date: date) -> dict | None:
    with conn.cursor() as cur:
        cur.execute(
            f"""SELECT s.score_id, s.gross_score, s.pcc_adjustment,
                       t.tee_colour, s.date_played
                FROM   {DB_PREFIX}golf_scores s
                JOIN   {DB_PREFIX}golf_tees   t ON t.tee_id = s.tee_id
                WHERE  s.player_id  = %s
                  AND  s.date_played = %s
                  AND  s.is_excluded = 0
                LIMIT 1""",
            (player_id, target_date.isoformat()),
        )
        return cur.fetchone()


def db_get_hi(conn, player_name: str) -> float | None:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT current_handicap_index FROM view_handicap_index WHERE player_name = %s",
            (player_name,)
        )
        row = cur.fetchone()
    return float(row["current_handicap_index"]) if row and row["current_handicap_index"] is not None else None


def db_update_pcc(conn, score_id: int, pcc: int, dry_run: bool = False) -> None:
    """
    Writes PCC to wp_golf_scores.
    AFTER UPDATE trigger fires sp_repair_from_date() automatically.
    Note: repo has two update triggers (trg_scores_after_update + trg_scores_update)
    which both fire — this is a known repo characteristic, not a bug in this script.
    """
    if dry_run:
        log.info("  DRY-RUN: would SET pcc_adjustment=%d for score_id=%d", pcc, score_id)
        return
    with conn.cursor() as cur:
        cur.execute(
            f"UPDATE {DB_PREFIX}golf_scores SET pcc_adjustment = %s WHERE score_id = %s",
            (pcc, score_id),
        )
    conn.commit()
    log.info("  ✓ PCC written: score_id=%d → pcc_adjustment=%d (SP chain triggered)", score_id, pcc)


# ── Email (#12 — separated so email failure != mismatch failure) ──

def send_email(subject: str, body: str) -> bool:
    """Returns True if sent successfully, False if send failed."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = config.EMAIL_FROM
    msg["To"]      = config.EMAIL_TO
    msg.attach(MIMEText(body, "plain"))
    try:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=30) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(config.SMTP_USER, config.SMTP_PASSWORD)
            smtp.sendmail(config.EMAIL_FROM, [config.EMAIL_TO], msg.as_string())
        log.info("EMAIL sent: %s", subject)
        return True
    except Exception as exc:
        log.error("EMAIL SEND FAILED: %s", exc)
        log.error("The mismatches above were detected but the alert email was NOT delivered.")
        return False


# ── Main ──────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="828ers daily EG checker")
    parser.add_argument("--dry-run",     action="store_true")
    parser.add_argument("--force-login", action="store_true")
    parser.add_argument("--debug",       action="store_true")
    args = parser.parse_args()

    yesterday = get_yesterday_bst()    # #10: BST-aware
    log.info("═══ 828ers Daily Check — %s ═══", yesterday.isoformat())
    if args.dry_run:
        log.info("DRY-RUN mode: PCC will NOT be written to DB")

    # ── Login ──
    try:
        session = eg_login(force=args.force_login)
    except EGLoginError as exc:
        log.error("EG login failed: %s", exc)
        send_email(
            f"828ers ✗ Login failed — {yesterday}",
            f"The daily checker could not log in to England Golf.\n\nError: {exc}"
        )
        sys.exit(1)

    # ── DB ──
    try:
        conn = get_db()
    except Exception as exc:
        log.error("DB connection failed: %s", exc)
        sys.exit(1)

    mismatches  = []
    pcc_updates = []
    eg_errors   = []

    for player in config.PLAYERS:
        name     = player["name"]
        code     = player["code"]
        passport = player["eg_passport_id"]

        log.info("─── %s (%s) ───", name, code)

        # Player ID from DB (#6)
        player_id = db_get_player_id(conn, name)
        if not player_id:
            msg = (
                f"'{name}' not found in wp_golf_players. "
                f"Check config.PLAYERS 'name' matches DB exactly (run eg_step5.py)."
            )
            log.error("  ✗ %s", msg)
            eg_errors.append(f"CONFIG ERROR — {name}: {msg}")
            continue

        # EG scores
        try:
            eg_records = eg_fetch_scores(session, passport, page_size=40)
        except (EGAPIError, Exception) as exc:
            log.error("  EG scores fetch failed: %s", exc)
            eg_errors.append(f"EG FETCH ERROR — {name}: {exc}")
            continue

        if args.debug:
            log.debug("  EG raw records: %s", str(eg_records)[:500])

        # Find yesterday's EG round (#4 — loud failure if fields missing in found record)
        try:
            eg_score = parse_yesterday_score(eg_records, yesterday)
        except EGFieldError as exc:
            log.error("  ✗ EG field name error: %s", exc)
            eg_errors.append(f"FIELD NAME ERROR — {name}: {exc}")
            continue

        # EG HI (#3 — errors are loud)
        try:
            eg_hi = eg_fetch_hi(session, passport)
        except (EGAPIError, EGFieldError) as exc:
            log.warning("  EG HI fetch failed: %s", exc)
            eg_hi = None
            eg_errors.append(f"HI FETCH WARNING — {name}: {exc}")

        # DB score and HI
        db_score = db_get_yesterday_score(conn, player_id, yesterday)
        db_hi    = db_get_hi(conn, name)

        # ── Comparisons ──
        player_issues = []

        if eg_score and db_score:
            # Gross score
            eg_gross = eg_score["gross_score"]
            db_gross = int(db_score["gross_score"])
            if eg_gross is not None and eg_gross != db_gross:
                player_issues.append(f"Gross mismatch: EG={eg_gross} vs DB={db_gross}")
            else:
                log.info("  Gross ✓ %s", db_gross)

            # Tee colour
            eg_tee = eg_score["tee_colour"].lower()
            db_tee = db_score["tee_colour"].lower()
            if eg_tee and eg_tee != db_tee:
                player_issues.append(f"Tee mismatch: EG='{eg_tee}' vs DB='{db_tee}'")
            else:
                log.info("  Tee   ✓ %s", db_score["tee_colour"])

            # PCC
            eg_pcc = eg_score["pcc_adjustment"]
            db_pcc = int(db_score["pcc_adjustment"])
            if eg_pcc != 0 and db_pcc == 0:
                log.info("  PCC   → EG=%d, DB=0 — writing PCC", eg_pcc)
                db_update_pcc(conn, int(db_score["score_id"]), eg_pcc, dry_run=args.dry_run)
                pcc_updates.append(f"{name} ({yesterday}): PCC set to {eg_pcc:+d}")
            elif eg_pcc != db_pcc:
                player_issues.append(f"PCC mismatch: EG={eg_pcc:+d} vs DB={db_pcc:+d}")
            else:
                log.info("  PCC   ✓ %d", db_pcc)

        elif eg_score and not db_score:
            player_issues.append(
                f"EG has a round (gross={eg_score['gross_score']}, tee={eg_score['tee_colour']}) "
                f"but DB has no entry for {yesterday}"
            )
        elif not eg_score and db_score:
            log.info("  DB has round but EG doesn't yet — OK (may be submitted later)")
        else:
            log.info("  No round on EG or DB for %s — OK", yesterday)

        # HI — both EG and DB publish to 1dp, so compare exactly at 1dp.
        # round() to 1dp handles any floating point noise (e.g. 14.0999 vs 14.1).
        # A difference of 0.1 is a genuine mismatch and will be caught.
        if eg_hi is not None and db_hi is not None:
            eg_hi_1dp = round(eg_hi, 1)
            db_hi_1dp = round(db_hi, 1)
            if eg_hi_1dp != db_hi_1dp:
                player_issues.append(
                    f"HI mismatch: EG={eg_hi_1dp:.1f} vs DB={db_hi_1dp:.1f}"
                )
            else:
                log.info("  HI    ✓ %.1f", db_hi_1dp)

        if player_issues:
            for issue in player_issues:
                log.warning("  ✗ %s: %s", name, issue)
                mismatches.append(f"❌ {name}: {issue}")
        else:
            log.info("  ✓ All checks passed")

    conn.close()

    # ── Report ────────────────────────────────────────────────────
    email_sent = True
    if mismatches or pcc_updates or eg_errors:
        lines = [f"828ers Daily Check — {yesterday.isoformat()}", "=" * 50]
        if mismatches:
            lines += ["", "MISMATCHES:"] + mismatches
        if pcc_updates:
            lines += ["", "PCC UPDATES APPLIED:"] + pcc_updates
        if eg_errors:
            lines += ["", "ERRORS/WARNINGS:"] + eg_errors
        if args.dry_run:
            lines += ["", "(DRY-RUN: PCC updates were NOT written to DB)"]

        n = len(mismatches)
        subject = f"828ers ⚠ {n} mismatch{'es' if n != 1 else ''} — {yesterday}"
        email_sent = send_email(subject, "\n".join(lines))    # #12

        log.warning("═══ DONE — %d mismatch(es), %d PCC update(s), %d error(s) ═══",
                    len(mismatches), len(pcc_updates), len(eg_errors))
        sys.exit(1)
    else:
        log.info("═══ DONE — all checks passed, no email sent ═══")
        sys.exit(0)


if __name__ == "__main__":
    main()
