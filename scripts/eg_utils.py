"""
eg_utils.py
Confirmed facts from this debugging session (April 2026):
  - Login page:  https://www.englandgolf.org/igolf-login
  - Field names: ctl73$tbMembershipNumber / ctl73$tbPassword
  - Auth cookies: CWApiToken (24h), CWAuthenticaionToken (1yr)
  - Scores API:  POST https://www.englandgolf.org/api/Score/GetMyScores
  - Score fields: PlayDate (DD/MM/YYYY), AdjustedGross, Marker,
                  Slope, CourseRating, HCDiff, HandicapIndex, Pcc,
                  StablefordPoints, ScoreId, ScoreCode
  - HI API:      POST https://www.englandgolf.org/api/Score/GetMemberHandicapIndex
  - Scorecard:   POST https://www.englandgolf.org/api/Score/GetMyScoreDetails
                  Payload: { ScoreId, ScoreCode }  -- NOTE: ScoreCode != ScoreId
"""

import os
import time
import json
import re
import logging
from urllib.parse import urlparse, parse_qs

import requests
from bs4 import BeautifulSoup

import config

log = logging.getLogger(__name__)

BASE              = "https://www.englandgolf.org"
LOGIN_URL         = f"{BASE}/igolf-login"
SCORES_URL        = f"{BASE}/api/Score/GetMyScores"
HI_URL            = f"{BASE}/api/Score/GetMemberHandicapIndex"
SCORE_DETAILS_URL = f"{BASE}/api/Score/GetMyScoreDetails"
SESSION_FILE      = os.path.join(os.path.dirname(__file__), "eg_session.json")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-GB,en;q=0.9",
}


class EGLoginError(Exception):
    pass


# ── Session management ──────────────────────────────────────────────────────

def _make_session():
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


def _do_fresh_login():
    session = _make_session()

    log.info("EG: GET %s", LOGIN_URL)
    r = session.get(LOGIN_URL, timeout=30)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")

    form = soup.find("form", {"method": re.compile("post", re.I)})
    if not form:
        raise EGLoginError("No POST form found on login page — page structure may have changed.")
    action = form.get("action", "")
    if action.startswith("http"):
        post_url = action
    elif action.startswith("/"):
        post_url = BASE + action
    else:
        post_url = LOGIN_URL

    hidden = {
        inp["name"]: inp.get("value", "")
        for inp in soup.find_all("input", {"type": "hidden"})
        if inp.get("name")
    }
    if "__VIEWSTATE" not in hidden:
        raise EGLoginError("__VIEWSTATE missing — EG page structure changed.")

    post_data = {
        **hidden,
        "__EVENTTARGET":            "",
        "__EVENTARGUMENT":          "",
        "ctl73$tbMembershipNumber": config.EG_USERNAME,
        "ctl73$tbPassword":         config.EG_PASSWORD,
        "ctl73$cbRememberMe":       "on",
        "ctl73$btnLogin":           "Log in",
    }

    log.info("EG: POST credentials to %s", post_url)
    r2 = session.post(
        post_url, data=post_data, timeout=30, allow_redirects=True,
        headers={"Referer": LOGIN_URL},
    )
    r2.raise_for_status()

    if not session.cookies.get("CWApiToken"):
        soup2 = BeautifulSoup(r2.text, "html.parser")
        errors = [
            t.get_text(strip=True)
            for t in soup2.find_all(["span", "div", "p"])
            if any(w in t.get_text().lower()
                   for w in ("invalid", "incorrect", "error", "wrong"))
        ]
        raise EGLoginError(
            "Login failed — CWApiToken not set.\n"
            f"EG message: {' | '.join(errors[:3]) or 'none found'}\n"
            "Check EG_USERNAME and EG_PASSWORD in config.py."
        )

    log.info("EG: Login OK — cookies: %s", list(session.cookies.keys()))
    return session


def _load_saved_session():
    if not os.path.exists(SESSION_FILE):
        return None
    try:
        with open(SESSION_FILE, "r") as f:
            data = json.load(f)
        
        # EG CWApiToken is typically valid for 24 hours. We expire local cache after ~22h (80000s)
        if time.time() - data.get("timestamp", 0) > 80000:
            log.info("EG: Saved session expired — will re-login")
            return None
            
        session = _make_session()
        requests.utils.cookiejar_from_dict(data.get("cookies", {}), cookiejar=session.cookies)
        log.info("EG: reusing saved session (JSON)")
        return session
    except Exception as exc:
        log.warning("EG: could not load saved session: %s", exc)
        try:
            os.remove(SESSION_FILE)
        except OSError:
            pass
        return None


def _save_session(session):
    try:
        data = {
            "cookies": requests.utils.dict_from_cookiejar(session.cookies),
            "timestamp": time.time()
        }
        with open(SESSION_FILE, "w") as f:
            json.dump(data, f)
        log.info("EG: session saved to %s", SESSION_FILE)
    except Exception as exc:
        log.warning("EG: Failed to save session to JSON: %s", exc)


def eg_login():
    """Return an authenticated EG session, reusing saved session if valid."""
    session = _load_saved_session()
    if session:
        return session
    session = _do_fresh_login()
    _save_session(session)
    return session


# ── API helpers ─────────────────────────────────────────────────────────────

def eg_fetch_scores(session, passport_id=None, page_size=40, page_number=1):
    """
    Fetch scores for a player with pagination support.
    """
    payload = {
        "pageNumber":          page_number,
        "pageSize":            page_size,
        "otherPassportId":     passport_id,
        "includeCasualScores": False,
        "casualScoresOnly":    False,
        "getDefaultFacility":  True,
    }
    r = session.post(
        SCORES_URL,
        json=payload,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()

    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("scores", "Scores", "data", "Data", "results", "Results"):
            if key in data and isinstance(data[key], list):
                return data[key]
    log.warning("Unexpected scores API shape: %s", str(data)[:200])
    return []


def eg_fetch_hi(session, passport_id=None):
    """
    Fetch current Handicap Index from the live EG API.
    Returns float or None.
    """
    try:
        r = session.post(
            HI_URL,
            json={"otherPassportId": passport_id},
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            timeout=30,
        )
        r.raise_for_status()
        data = r.json()
        for key in ("handicapIndex", "HandicapIndex", "hi", "HI",
                    "currentHandicapIndex", "CurrentHandicapIndex", "value", "HandicapIndexText"):
            if key in data:
                try:
                    return float(str(data[key]).replace('c', '').strip())
                except ValueError:
                    pass
        log.warning(
            "EG HI fetch (passport=%s): no recognised key in response. "
            "Keys present: %s  |  Raw: %s",
            passport_id,
            list(data.keys()) if isinstance(data, dict) else type(data).__name__,
            str(data)[:200],
        )
        if isinstance(data, (int, float)):
            return float(data)
    except Exception as exc:
        log.warning("EG HI fetch failed (passport=%s): %s", passport_id, exc)
    return None


def eg_fetch_scorecard(session, score_id, score_code=None):
    """
    Fetch hole-by-hole scorecard for a specific round.
    """
    if score_code is None:
        log.warning(
            "eg_fetch_scorecard called without ScoreCode for ScoreId=%s. "
            "The EG API requires both fields. Scorecard fetch may fail.",
            score_id,
        )
    payload = {"ScoreId": score_id, "ScoreCode": score_code}
    try:
        r = session.post(
            SCORE_DETAILS_URL,
            json=payload,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            timeout=30,
        )
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        log.warning("Failed to fetch scorecard (ScoreId=%s, ScoreCode=%s): %s", score_id, score_code, exc)
        return None


# ── Score field mapping ──────────────────────────────────────────────────────

def parse_play_date(raw):
    """
    EG returns PlayDate as 'DD/MM/YYYY'. Convert to 'YYYY-MM-DD' for MySQL.
    """
    raw_date = raw.get("PlayDate") or raw.get("playDate") or raw.get("DatePlayed") or ""
    if not raw_date:
        return None
    if "/" in raw_date:
        parts = raw_date[:10].split("/")
        if len(parts) == 3:
            return f"{parts[2]}-{parts[1]}-{parts[0]}"
    if "T" in raw_date or (len(raw_date) >= 10 and raw_date[4] == "-"):
        return raw_date[:10]
    return None


def parse_gross(raw):
    """
    Extract gross score from a raw EG score dict. Logs a warning if outside expected range.
    """
    val = (
        raw.get("AdjustedGross") or raw.get("adjustedGross") or
        raw.get("GrossScore")    or raw.get("grossScore") or
        raw.get("Score")         or raw.get("score")
    )
    try:
        v = int(float(val))
        if not (50 <= v <= 150):
            log.warning("parse_gross: value %s is unusually high or low. Continuing anyway.", v)
        return v
    except (TypeError, ValueError):
        return None


def parse_pcc(raw):
    """
    Extract PCC adjustment. Explicitly checks for None to allow valid integer 0.
    """
    for key in ("Pcc", "pcc", "PCCAdjustment"):
        if key in raw and raw[key] is not None:
            try:
                return int(float(raw[key]))
            except (TypeError, ValueError):
                pass
    return 0


def parse_hi(raw):
    val = raw.get("HandicapIndex") or raw.get("handicapIndex")
    try:
        return float(val)
    except (TypeError, ValueError):
        return None