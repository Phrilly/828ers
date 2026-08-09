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
import math
from typing import Any, Mapping, NamedTuple, Optional
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


class EGRatingError(ValueError):
    pass


class EGRoundRatings(NamedTuple):
    course_rating: float
    slope_rating: int
    par: int
    par_source: str


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
        "includeCasualScores": True,
        "casualScoresOnly":    False,
        "getDefaultFacility":  True,
    }

    if passport_id is not None:
        payload["otherPassportId"] = passport_id

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
        for key in ("scores", "Scores", "data", "Data", "results", "Results"):
            if key in data and isinstance(data[key], list):
                return data[key]

        log.warning("EG API returned a dict, but couldn't find scores list. Keys present: %s", list(data.keys()))
        return []

    log.warning("Unexpected scores API shape: %s", type(data))
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


def _parse_finite_number(value: Any, field_name: str) -> float:
    if value is None or str(value).strip() == "":
        raise EGRatingError(f"England Golf field {field_name} is missing")

    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise EGRatingError(
            f"England Golf field {field_name} is not numeric: {value!r}"
        ) from exc

    if not math.isfinite(number):
        raise EGRatingError(
            f"England Golf field {field_name} is not a finite number: {value!r}"
        )

    return number


def _parse_whole_number(value: Any, field_name: str) -> int:
    number = _parse_finite_number(value, field_name)
    if not number.is_integer():
        raise EGRatingError(
            f"England Golf field {field_name} must be a whole number: {value!r}"
        )
    return int(number)


def parse_eg_round_ratings(
    raw: Mapping[str, Any],
    scorecard: Optional[Mapping[str, Any]] = None,
) -> EGRoundRatings:
    course_rating = round(
        _parse_finite_number(raw.get("CourseRating"), "CourseRating"),
        1,
    )
    if not 40.0 <= course_rating <= 100.0:
        raise EGRatingError(
            f"England Golf CourseRating is outside the supported 18-hole range: {course_rating}"
        )

    slope_rating = _parse_whole_number(raw.get("Slope"), "Slope")
    if not 55 <= slope_rating <= 155:
        raise EGRatingError(
            f"England Golf Slope is outside the WHS range: {slope_rating}"
        )

    par_value = None
    par_source = ""
    for field_name in ("Par", "CoursePar"):
        value = raw.get(field_name)
        if value is not None and str(value).strip() != "":
            par_value = value
            par_source = field_name
            break

    if par_value is None and scorecard is not None:
        value = scorecard.get("TotalPar")
        if value is not None and str(value).strip() != "":
            par_value = value
            par_source = "TotalPar"

    par = _parse_whole_number(par_value, par_source or "Par/CoursePar/TotalPar")
    if not 54 <= par <= 90:
        raise EGRatingError(
            f"England Golf par is outside the supported 18-hole range: {par}"
        )

    if scorecard is not None:
        hole_pars = []
        for hole_number in range(1, 19):
            value = scorecard.get(f"Hole{hole_number}Par")
            if value is None or str(value).strip() == "":
                hole_pars = []
                break
            hole_pars.append(
                _parse_whole_number(value, f"Hole{hole_number}Par")
            )

        if hole_pars and sum(hole_pars) != par:
            raise EGRatingError(
                "England Golf round par {} does not match the 18-hole total {}".format(
                    par,
                    sum(hole_pars),
                )
            )

    return EGRoundRatings(
        course_rating=course_rating,
        slope_rating=slope_rating,
        par=par,
        par_source=par_source,
    )


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


# ── Hole score parsing ───────────────────────────────────────────────────────


def parse_eg_hole_score(raw_score, raw_class=None, incomplete_count=0):
    """
    Parse a single EG HoleXScore value into its components.

    EG returns four formats:
      "5"     plain numeric     -- normal complete hole
      "8(7)"  composite         -- player entered 8, EG adjusted to 7 for handicap
      "*(5)"  auto net double   -- hole not completed, EG assigned net double bogey score
      "*"     fully missing     -- hole not entered, no EG auto-score assigned

    Returns a dict:
      gross_score          int or None  -- the player's actual entered strokes
      adjusted_gross_score int or None  -- EG's handicap-adjusted hole value
      score_status         str          -- 'normal' | 'adjusted' | 'missing'
      score_display        str          -- original EG string for traceability
    """
    score_text = "" if raw_score is None else str(raw_score).strip()
    score_class = "" if raw_class is None else str(raw_class).strip().lower()

    # Fully missing / unentered hole with no auto-score  --  "*" bare or "is-na" class
    if score_text == "" or score_text == "*" or score_class == "is-na":
        return {
            "gross_score":          None,
            "adjusted_gross_score": None,
            "score_status":         "missing",
            "score_display":        score_text or "*",
        }

    # EG auto net double bogey  e.g. "*(5)"  --  no raw gross but adjusted value is known
    m = re.match(r"^\*\((\d+)\)$", score_text)
    if m:
        return {
            "gross_score":          None,
            "adjusted_gross_score": int(m.group(1)),
            "score_status":         "adjusted",
            "score_display":        score_text,
        }

    # Composite adjusted score  e.g. "8(7)"  --  player entered 8, EG reduced to 7
    m = re.match(r"^\s*(\d+)\((\d+)\)\s*$", score_text)
    if m:
        return {
            "gross_score":          int(m.group(1)),
            "adjusted_gross_score": int(m.group(2)),
            "score_status":         "adjusted",
            "score_display":        score_text,
        }

    # Plain numeric score  e.g. "5"
    m = re.match(r"^\s*(\d+)\s*$", score_text)
    if m:
        val = int(m.group(1))
        return {
            "gross_score":          val,
            "adjusted_gross_score": val,
            "score_status":         "normal",
            "score_display":        score_text,
        }

    # Unrecognised format -- log and treat as missing
    log.warning(
        "parse_eg_hole_score: unrecognised format %r (class=%r, incomplete=%s)",
        score_text, score_class, incomplete_count,
    )
    return {
        "gross_score":          None,
        "adjusted_gross_score": None,
        "score_status":         "missing",
        "score_display":        score_text,
    }
