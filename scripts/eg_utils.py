"""
eg_utils.py
Confirmed facts from this debugging session (April 2026):
  - Login page:  https://www.englandgolf.org/igolf-login
  - Field names: ctl73$tbMembershipNumber / ctl73$tbPassword
  - Auth cookies: CWApiToken (24h), CWAuthenticaionToken (1yr)
  - Scores API:  POST https://www.englandgolf.org/api/Score/GetMyScores
  - HI API:      POST https://www.englandgolf.org/api/Score/GetMemberHandicapIndex
  - Scorecard:   POST https://www.englandgolf.org/api/Score/GetMyScoreDetails
"""

import os
import time
import json
import re
import logging
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
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "en-GB,en;q=0.9",
    "Referer": LOGIN_URL,
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
        raise EGLoginError("No POST form found on login page.")
        
    action = form.get("action", "")
    if action.startswith("http"):
        post_url = action
    elif action.startswith("/"):
        post_url = BASE + action
    else:
        post_url = LOGIN_URL

    hidden_fields = {
        inp.get("name"): inp.get("value", "")
        for inp in soup.find_all("input", {"type": "hidden"})
        if inp.get("name")
    }

    post_data = {
        **hidden_fields,
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

    cwtoken = session.cookies.get("CWApiToken")
    if not cwtoken:
        # Sometimes EG requires a hop to /my-scores to set the token
        r3 = session.get(f"{BASE}/my-scores", timeout=30, allow_redirects=True, headers={"Referer": BASE})
        r3.raise_for_status()
        cwtoken = session.cookies.get("CWApiToken")

    if not cwtoken:
        raise EGLoginError("Login failed — CWApiToken not set. Check credentials.")

    log.info("EG: Login OK — cookies: %s", list(session.cookies.keys()))
    return session

def _load_saved_session():
    if not os.path.exists(SESSION_FILE):
        return None
    try:
        with open(SESSION_FILE, "r") as f:
            data = json.load(f)
        
        # EG CWApiToken is typically valid for 24 hours. Cache invalidates after ~22h (80000s)
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

def eg_fetch_scores(session, passport_id, page_size=40, page_number=1):
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
        headers={
            "Content-Type": "application/json", 
            "Accept": "application/json",
            "Referer": f"{BASE}/my-scores",
            "X-Requested-With": "XMLHttpRequest"
        },
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()

    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("scores", data.get("data", []))
    return []

def eg_fetch_scorecard(session, score_id, score_code):
    payload = {"scoreId": score_id, "scoreCode": score_code}
    r = session.post(
        SCORE_DETAILS_URL,
        json=payload,
        headers={
            "Content-Type": "application/json", 
            "Accept": "application/json",
            "Referer": f"{BASE}/my-scores",
            "X-Requested-With": "XMLHttpRequest"
        },
        timeout=30,
    )
    r.raise_for_status()
    return r.json()

def eg_fetch_hi(session, passport_id):
    r = session.post(
        HI_URL,
        json={"otherPassportId": passport_id},
        headers={
            "Content-Type": "application/json", 
            "Accept": "application/json",
            "Referer": f"{BASE}/my-overview",
            "X-Requested-With": "XMLHttpRequest"
        },
        timeout=30,
    )
    r.raise_for_status()
    data = r.json()
    
    if isinstance(data, dict):
        for key in ("HandicapIndex", "handicapIndex", "ExactHandicap", "exactHandicap", "value"):
            if key in data and data[key] is not None:
                return float(data[key])
    elif data is not None:
        return float(data)
    return None

# ── Score field mapping ──────────────────────────────────────────────────────

def parse_play_date(raw):
    v = raw.get("PlayDate")
    if not v:
        return None
    v = str(v).strip()
    
    m = re.match(r"^(\d{2})/(\d{2})/(\d{4})$", v)
    if m:
        dd, mm, yyyy = m.groups()
        return f"{yyyy}-{mm}-{dd}"

    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", v)
    if m:
        yyyy, mm, dd = m.groups()
        return f"{yyyy}-{mm}-{dd}"
    return None

def parse_gross(raw):
    candidates = [
        raw.get("AdjustedGross"),
        raw.get("GrossScore"),
        raw.get("Score"),
        raw.get("TotalScore"),
    ]
    
    total_score_text = raw.get("TotalScoreText")
    if total_score_text and isinstance(total_score_text, str):
        m = re.match(r"^\s*(\d+)", total_score_text)
        if m:
            candidates.append(m.group(1))

    for val in candidates:
        if val is None or str(val).strip() == "":
            continue
        try:
            v = int(float(val))
            if 40 <= v <= 180:
                return v
        except (TypeError, ValueError):
            continue
    return None

def parse_pcc(raw):
    candidates = [
        raw.get("Pcc"),
        raw.get("PCC"),
        raw.get("pcc"),
        raw.get("Adjustments"),
    ]
    for val in candidates:
        if val is None or str(val).strip() == "":
            continue
        try:
            return int(round(float(val)))
        except (TypeError, ValueError):
            continue
    return 0

def parse_hi(raw):
    candidates = [
        raw.get("HandicapIndex"),
        raw.get("HI"),
        raw.get("ExactHandicap"),
    ]
    for val in candidates:
        if val is None or str(val).strip() == "":
            continue
        try:
            return float(val)
        except (TypeError, ValueError):
            continue
    return None