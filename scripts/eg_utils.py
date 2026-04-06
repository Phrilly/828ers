"""
eg_utils.py — shared helpers used by every step script and golf_checker.py
"""

import os
import pickle
import sys
import time
from datetime import date, timedelta

import requests
from bs4 import BeautifulSoup

# ── Path fix — works from any directory ────────────────────────
_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

# ── Config import with helpful error ───────────────────────────
try:
    import config
except ModuleNotFoundError:
    sys.exit(
        "\nERROR: config.py not found.\n"
        "Run:  cp config.example.py config.py\n"
        "Then fill in your real credentials in config.py\n"
    )

SESSION_FILE = os.path.join(_SCRIPTS_DIR, "eg_session.pkl")

LOGIN_URL  = "https://members.whsplatform.englandgolf.org/my-golf-login"
SCORES_URL = "https://www.englandgolf.org/api/Score/GetMyScores"
HI_URL     = "https://www.englandgolf.org/api/Handicap/GetMemberHandicapIndex"


# ══════════════════════════════════════════════════════════════
# CUSTOM EXCEPTIONS
# ══════════════════════════════════════════════════════════════

class EGLoginError(Exception):
    """Raised when EG login fails."""

class EGFieldError(Exception):
    """Raised when expected field names are missing from EG response."""

class EGAPIError(Exception):
    """Raised when EG API returns an unexpected shape or status."""


# ══════════════════════════════════════════════════════════════
# TIMEZONE-SAFE DATE HELPER
# ══════════════════════════════════════════════════════════════

def get_yesterday_bst() -> date:
    """
    Returns yesterday's date in Europe/London time (BST/GMT).
    Prevents off-by-one errors when the server runs on UTC.
    """
    try:
        from zoneinfo import ZoneInfo
        from datetime import datetime as dt
        now_london = dt.now(ZoneInfo("Europe/London"))
        return (now_london - timedelta(days=1)).date()
    except Exception:
        return date.today() - timedelta(days=1)


# ══════════════════════════════════════════════════════════════
# RETRY WRAPPER
# ══════════════════════════════════════════════════════════════

def with_retry(fn, attempts=3, delay=5, label="request"):
    """Retries fn() up to `attempts` times on network errors."""
    last_exc = None
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except (requests.Timeout, requests.ConnectionError) as exc:
            last_exc = exc
            if attempt < attempts:
                print(f"  [{label}] Attempt {attempt} failed ({exc}) — retrying in {delay}s…")
                time.sleep(delay)
    raise EGAPIError(f"{label} failed after {attempts} attempts: {last_exc}")


# ══════════════════════════════════════════════════════════════
# SESSION MANAGEMENT
# ══════════════════════════════════════════════════════════════

def _make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "en-GB,en;q=0.9",
    })
    return s


def _load_saved_session() -> requests.Session | None:
    """
    Loads a pickled session and probes EG to confirm it is still valid.
    Returns None on any failure so caller falls back to fresh login.
    Handles pickle file corruption cleanly.
    """
    if not os.path.exists(SESSION_FILE):
        return None
    try:
        with open(SESSION_FILE, "rb") as f:
            session = pickle.load(f)
        probe = session.get(
            "https://members.whsplatform.englandgolf.org/my-golf",
            timeout=15,
            allow_redirects=False,
        )
        if probe.status_code == 200:
            return session
        return None
    except pickle.UnpicklingError:
        print(f"  WARNING: {SESSION_FILE} is corrupted — deleting and logging in fresh.")
        os.remove(SESSION_FILE)
        return None
    except Exception:
        return None


def _do_fresh_login() -> requests.Session:
    """
    Performs a full EG login using the known ASP.NET form field names.
    ctl74 is the stable ASP.NET control ID for the login form —
    it is tied to the control tree position and only changes if EG
    restructure their page, which would be immediately obvious.
    """
    session = _make_session()

    def get_page():
        return session.get(LOGIN_URL, timeout=30)

    resp = with_retry(get_page, label="GET login page")
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    # ── Extract all hidden ASP.NET fields ──
    hidden_fields = {}
    for inp in soup.find_all("input", {"type": "hidden"}):
        name = inp.get("name")
        if name:
            hidden_fields[name] = inp.get("value", "")

    if "__VIEWSTATE" not in hidden_fields:
        raise EGLoginError(
            "__VIEWSTATE not found on login page — "
            "EG page structure may have changed."
        )

    # ── Build POST with known stable field names ──
    post_data = {
        "__VIEWSTATE":              hidden_fields.get("__VIEWSTATE", ""),
        "__VIEWSTATEGENERATOR":     hidden_fields.get("__VIEWSTATEGENERATOR", ""),
        "__EVENTVALIDATION":        hidden_fields.get("__EVENTVALIDATION", ""),
        "__EVENTTARGET":            "",
        "__EVENTARGUMENT":          "",
        "ctl74$tbMembershipNumber": config.EG_USERNAME,
        "ctl74$tbPassword":         config.EG_PASSWORD,
    }

    # Submit button name is irrelevant to the form — discovered dynamically
    btn = soup.find("input", {"type": "submit"}) or soup.find("button", {"type": "submit"})
    if btn and btn.get("name"):
        post_data[btn["name"]] = btn.get("value", "Log in")

    def do_post():
        return session.post(LOGIN_URL, data=post_data, timeout=30, allow_redirects=True)

    resp2 = with_retry(do_post, label="POST credentials")
    resp2.raise_for_status()

    # ── Detect failure using the known password field name ──
    page_soup = BeautifulSoup(resp2.text, "html.parser")
    still_on_login = page_soup.find("input", {"name": "ctl74$tbPassword"}) is not None

    if still_on_login:
        err_hints = []
        for tag in page_soup.find_all(["span", "div", "p"]):
            t = tag.get_text(strip=True)
            if any(w in t.lower() for w in ("invalid", "incorrect", "error", "failed")):
                err_hints.append(t)
        hint = " | ".join(err_hints[:3]) if err_hints else "no error text found on page"
        raise EGLoginError(
            f"EG login failed — still on login page. EG said: {hint}\n"
            "Check EG_USERNAME and EG_PASSWORD in config.py."
        )

    return session


def eg_login(force: bool = False) -> requests.Session:
    """
    Public login entry point.
    Tries saved session first; falls back to fresh login.
    Saves the new session to disk after a successful fresh login.
    """
    if not force:
        session = _load_saved_session()
        if session:
            return session

    session = _do_fresh_login()
    try:
        with open(SESSION_FILE, "wb") as f:
            pickle.dump(session, f)
    except Exception as exc:
        print(f"  WARNING: Could not save session to disk: {exc}")

    return session


# ══════════════════════════════════════════════════════════════
# EG API CALLS
# ══════════════════════════════════════════════════════════════

# Candidate field name lists — tried in order until one matches.
# If a round IS found but none match, EGFieldError is raised (not silent None).
_DATE_CANDIDATES  = ["DatePlayed", "datePlayed", "Date", "date", "PlayedDate"]
_GROSS_CANDIDATES = ["AdjustedGrossScore", "adjustedGrossScore",
                     "GrossScore", "grossScore", "Score", "score"]
_TEE_CANDIDATES   = ["TeeColour", "teeColour", "Tee", "tee", "TeeName", "teeName"]
_PCC_CANDIDATES   = ["PCCAdjustment", "pccAdjustment", "PCC", "pcc",
                     "PlayingConditionsCalculation", "playingConditionsCalculation"]
_HI_CANDIDATES    = ["handicapIndex", "HandicapIndex", "hi", "HI",
                     "currentHandicapIndex", "CurrentHandicapIndex", "value", "Value"]


def _pick(record: dict, candidates: list, field_label: str):
    """
    Finds the first matching key in candidates that exists in record.
    Returns (key_name, value).
    Raises EGFieldError loudly if none match.
    """
    for key in candidates:
        if key in record:
            return key, record[key]
    raise EGFieldError(
        f"Cannot find '{field_label}' field in EG record.\n"
        f"  Tried: {candidates}\n"
        f"  Record keys present: {list(record.keys())}\n"
        f"  → Run eg_step3.py to see the full raw response and identify the correct field name."
    )


def eg_fetch_scores(session: requests.Session, passport_id, page_size: int = 40) -> list:
    """Fetches recent scores from EG for one player."""
    payload = {
        "pageNumber":          1,
        "pageSize":            page_size,
        "otherPassportId":     passport_id,
        "includeCasualScores": False,
        "casualScoresOnly":    False,
        "getDefaultFacility":  True,
    }

    def call():
        r = session.post(
            SCORES_URL,
            json=payload,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            timeout=30,
        )
        r.raise_for_status()
        return r

    resp = with_retry(call, label=f"GetMyScores passport={passport_id}")
    data = resp.json()

    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("scores", "Scores", "data", "Data", "Results", "results"):
            if key in data and isinstance(data[key], list):
                return data[key]
        raise EGAPIError(
            f"GetMyScores returned a dict but no list found.\n"
            f"Keys present: {list(data.keys())}"
        )
    raise EGAPIError(f"GetMyScores returned unexpected type: {type(data)}")


def eg_fetch_hi(session: requests.Session, passport_id) -> float:
    """
    Fetches Handicap Index from EG.
    Raises EGAPIError or EGFieldError — never returns None silently.
    """
    payload = {"otherPassportId": passport_id}

    def call():
        r = session.post(
            HI_URL,
            json=payload,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            timeout=30,
        )
        r.raise_for_status()
        return r

    resp = with_retry(call, label=f"GetMemberHandicapIndex passport={passport_id}")
    data = resp.json()

    if isinstance(data, (int, float)):
        return float(data)
    if isinstance(data, dict):
        _, value = _pick(data, _HI_CANDIDATES, "HandicapIndex")
        return float(value)
    raise EGAPIError(
        f"HI endpoint returned unexpected type: {type(data)} — {str(data)[:200]}"
    )


def parse_yesterday_score(eg_scores: list, target_date: date) -> dict | None:
    """
    Finds the score for target_date in the EG list.
    Returns a normalised dict, or None if no round that day.
    Raises EGFieldError if a round IS found but expected fields are missing.
    """
    for raw in eg_scores:
        _, raw_date = _pick(raw, _DATE_CANDIDATES, "DatePlayed")
        try:
            score_date = date.fromisoformat(str(raw_date)[:10])
        except (ValueError, TypeError):
            continue
        if score_date != target_date:
            continue

        # Round found — remaining fields must resolve or raise loudly
        _, gross = _pick(raw, _GROSS_CANDIDATES, "GrossScore")
        _, tee   = _pick(raw, _TEE_CANDIDATES,   "TeeColour")

        # PCC is optional — default 0 if absent (legitimately may not exist yet)
        pcc = 0
        for key in _PCC_CANDIDATES:
            if key in raw:
                try:
                    pcc = int(raw[key])
                except (TypeError, ValueError):
                    pcc = 0
                break

        return {
            "date_played":    score_date.isoformat(),
            "gross_score":    int(gross) if gross is not None else None,
            "tee_colour":     str(tee).strip(),
            "pcc_adjustment": pcc,
            "raw":            raw,
        }
    return None
