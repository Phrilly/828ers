"""
eg_utils.py
Confirmed facts from this debugging session (April 2026):
  - Login page:  https://www.englandgolf.org/igolf-login
  - Field names: ctl73$tbMembershipNumber / ctl73$tbPassword
  - Auth cookies: CWApiToken (24h), CWAuthenticaionToken (1yr)
  - Scores API:  POST https://www.englandgolf.org/api/Score/GetMyScores
  - Score fields: PlayDate (DD/MM/YYYY), AdjustedGross, Marker,
                  Slope, CourseRating, HCDiff, HandicapIndex, Pcc,
                  StablefordPoints, ScoreId
"""

import os, time, pickle, re, json, logging
import requests
from bs4 import BeautifulSoup

import config

log = logging.getLogger(__name__)

BASE          = "https://www.englandgolf.org"
LOGIN_URL     = f"{BASE}/igolf-login"
SCORES_URL    = f"{BASE}/api/Score/GetMyScores"
HI_URL        = f"{BASE}/api/Handicap/GetMemberHandicapIndex"
FRIENDS_URL   = f"{BASE}/my-friends"
SESSION_FILE  = os.path.join(os.path.dirname(__file__), "eg_session.pkl")

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

    # Resolve the real POST target from the form action
    form = soup.find("form", {"method": re.compile("post", re.I)})
    if not form:
        raise EGLoginError("No POST form found on login page — page structure may have changed.")
    action = form.get("action", "")
    if action.startswith("http"):
        post_url = action
    elif action.startswith("/"):
        post_url = BASE + action
    else:
        post_url = LOGIN_URL   # fallback: post back to same page

    # Collect all hidden fields (__VIEWSTATE etc.)
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
        with open(SESSION_FILE, "rb") as f:
            session = pickle.load(f)
        for c in session.cookies:
            if c.name == "CWApiToken":
                if c.expires and c.expires > time.time() + 300:
                    log.info("EG: reusing saved session (CWApiToken valid)")
                    return session
                else:
                    log.info("EG: CWApiToken expired — will re-login")
                    return None
        return None
    except Exception as exc:
        log.warning("EG: could not load saved session: %s", exc)
        try:
            os.remove(SESSION_FILE)
        except OSError:
            pass
        return None

def _save_session(session):
    with open(SESSION_FILE, "wb") as f:
        pickle.dump(session, f)
    log.info("EG: session saved to %s", SESSION_FILE)

def eg_login():
    """Return an authenticated EG session, reusing saved session if valid."""
    session = _load_saved_session()
    if session:
        return session
    session = _do_fresh_login()
    _save_session(session)
    return session

# ── API helpers ─────────────────────────────────────────────────────────────

def eg_fetch_scores(session, passport_id=None, page_size=40):
    """
    Fetch scores for a player.
    passport_id=None  → Phil D (the logged-in account)
    passport_id=int   → another player (requires them to be linked as a friend)
    Returns list of raw score dicts from the EG API.
    """
    payload = {
        "pageNumber":          1,
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
    """Fetch current Handicap Index. Returns float or None."""
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
                    "currentHandicapIndex", "CurrentHandicapIndex", "value"):
            if key in data:
                return float(data[key])
        if isinstance(data, (int, float)):
            return float(data)
    except Exception as exc:
        log.warning("EG HI fetch failed (passport=%s): %s", passport_id, exc)
    return None

def eg_fetch_friends(session):
    """
    Load /my-friends and extract linked friend profile links.
    Returns list of dicts: {name, passportid, code, url}
    """
    r = session.get(FRIENDS_URL, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    friends = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "golf-profile" not in href and "passportid=" not in href.lower():
            continue
        full_url = href if href.startswith("http") else BASE + href
        if full_url in seen:
            continue
        seen.add(full_url)

        # Parse passportid and code from URL
        qs = {}
        if "?" in href:
            for part in href.split("?", 1)[1].split("&"):
                if "=" in part:
                    k, v = part.split("=", 1)
                    qs[k.lower()] = v

        friends.append({
            "name":       " ".join(a.get_text(" ", strip=True).split()) or "Unknown",
            "passportid": qs.get("passportid"),
            "code":       qs.get("code"),
            "url":        full_url,
        })

    return friends

# ── Score field mapping ──────────────────────────────────────────────────────

def parse_play_date(raw):
    """
    EG returns PlayDate as 'DD/MM/YYYY'. Convert to 'YYYY-MM-DD' for MySQL.
    """
    raw_date = raw.get("PlayDate") or raw.get("playDate") or raw.get("DatePlayed") or ""
    if not raw_date:
        return None
    # Handle both DD/MM/YYYY and ISO formats
    if "/" in raw_date:
        parts = raw_date[:10].split("/")
        if len(parts) == 3:
            return f"{parts[2]}-{parts[1]}-{parts[0]}"
    if "T" in raw_date or (len(raw_date) >= 10 and raw_date[4] == "-"):
        return raw_date[:10]
    return None

def parse_gross(raw):
    val = (
        raw.get("AdjustedGross") or raw.get("adjustedGross") or
        raw.get("GrossScore") or raw.get("grossScore") or
        raw.get("Score") or raw.get("score")
    )
    try:
        v = int(val)
        return v if 50 <= v <= 150 else None
    except (TypeError, ValueError):
        return None

def parse_pcc(raw):
    val = raw.get("Pcc") or raw.get("pcc") or raw.get("PCCAdjustment") or 0
    try:
        return int(float(val))
    except (TypeError, ValueError):
        return 0

def parse_hi(raw):
    val = raw.get("HandicapIndex") or raw.get("handicapIndex")
    try:
        return float(val)
    except (TypeError, ValueError):
        return None