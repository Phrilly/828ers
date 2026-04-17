import sys
import argparse
import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

try:
    import config
except ImportError:
    print("CRITICAL: config.py not found. Ensure it is uploaded to the server.")
    sys.exit(1)

EMAIL           = config.HDID_EMAIL
PASSWORD        = config.HDID_PASSWORD
COURSE_ID       = config.HDID_COURSE_ID
DAYS_IN_ADVANCE = 14

CLUB_BASE = "https://howdidido-whs.clubv1.com"
PASSPORT  = "https://passport.howdidido.com"
HDID_BASE = "https://www.howdidido.com"


def _follow_redirects_verbose(session, url, method="GET", data=None, headers=None, max_hops=10):
    """Follow redirects one at a time, printing each hop. Returns final response."""
    extra_headers = headers or {}
    for hop in range(max_hops):
        if method == "POST" and hop == 0:
            r = session.post(url, data=data, allow_redirects=False,
                             headers=extra_headers, timeout=15)
        else:
            r = session.get(url, allow_redirects=False,
                            headers=extra_headers, timeout=15)
        print(f"    [{hop}] {method if hop == 0 else 'GET'} {url}")
        print(f"         -> HTTP {r.status_code}  cookies now: {[c.name for c in session.cookies]}")
        if r.status_code in (301, 302, 303, 307, 308):
            location = r.headers.get("Location", "")
            if location.startswith("/"):
                # Resolve relative redirect against current domain
                from urllib.parse import urlparse
                parsed = urlparse(url)
                location = f"{parsed.scheme}://{parsed.netloc}{location}"
            print(f"         -> Redirect to: {location}")
            url = location
            method = "GET"
        else:
            return r
    return r


def hdid_login():
    session = requests.Session()
    session.headers.update({
        "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                           "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept-Language": "en-GB,en;q=0.9",
        "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    })

    # ── Step 1: GET passport login page ─────────────────────────────────────
    LOGIN_URL = f"{PASSPORT}/Account/Login"
    print("[*] Fetching login page for anti-forgery token...")
    r = session.get(LOGIN_URL, timeout=15)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")
    hidden_fields = {
        inp.get("name"): inp.get("value", "")
        for inp in soup.find_all("input", {"type": "hidden"})
        if inp.get("name")
    }

    post_data = {
        **hidden_fields,
        "EmailAddress": EMAIL,
        "Password":     PASSWORD,
        "RememberMe":   "true"
    }

    # ── Step 2: POST credentials, following every redirect manually ──────────
    print("[*] Submitting credentials — tracing full redirect chain:")
    r2 = _follow_redirects_verbose(
        session, LOGIN_URL, method="POST", data=post_data,
        headers={"Referer": LOGIN_URL}
    )

    print(f"\n    Final landing page: {r2.url}")
    print(f"    All cookies after login:")
    for c in session.cookies:
        print(f"        {c.domain}: {c.name}={str(c.value)[:50]}")

    # Check for authenticated cookie on www.howdidido.com
    # Typical auth cookies: .AspNet.ApplicationCookie, .HDID_Auth, __hdid_auth, etc.
    hdid_auth = None
    for c in session.cookies:
        if "howdidido.com" in c.domain and c.name not in (
            ".ASPXANONYMOUS", "ASP.NET_SessionId", "__RequestVerificationToken"
        ):
            hdid_auth = c.name
            break

    if not hdid_auth:
        # Check the final page text for sign-out link
        if "Sign Out" in r2.text or "sign-out" in r2.text.lower():
            print(" -> Login Successful (confirmed via page text)!")
        else:
            # Not logged into www.howdidido.com yet — need to check if
            # passport issued a redirect_uri back to howdidido.com
            print("    [!] No auth cookie on howdidido.com yet.")
            print("    Page title:", BeautifulSoup(r2.text, "html.parser").title)
            # Look for a return URL or OpenID connect callback in the response
            soup2 = BeautifulSoup(r2.text, "html.parser")
            for a in soup2.find_all("a", href=True):
                if "howdidido.com" in a["href"]:
                    print(f"    Found link to howdidido.com: {a['href']}")
    else:
        print(f" -> Login Successful! Auth cookie: {hdid_auth}")

    # ── Step 3: Ensure www.howdidido.com has an authenticated session ────────
    # If we landed on passport.howdidido.com (not www), follow the return URL
    if "passport.howdidido.com" in r2.url or "Account/Login" in r2.url:
        print("\n[*] Still on passport — looking for return URL...")
        soup_p = BeautifulSoup(r2.text, "html.parser")

        # Look for hidden ReturnUrl or a form action pointing back to howdidido.com
        return_url = None
        for inp in soup_p.find_all("input"):
            if inp.get("name", "").lower() in ("returnurl", "return_url", "redirecturl"):
                return_url = inp.get("value", "")
                break

        # Check URL params
        if not return_url and "returnUrl" in r2.url:
            from urllib.parse import urlparse, parse_qs, unquote
            qs = parse_qs(urlparse(r2.url).query)
            return_url = unquote(qs.get("returnUrl", [""])[0])

        if return_url:
            if return_url.startswith("/"):
                return_url = f"{PASSPORT}{return_url}"
            print(f"    Following return URL: {return_url}")
            r3 = _follow_redirects_verbose(session, return_url)
            print(f"\n    Post-return cookies:")
            for c in session.cookies:
                print(f"        {c.domain}: {c.name}={str(c.value)[:50]}")

    # ── Step 4: Prime www.howdidido.com with the /Booking path ──────────────
    print("\n[*] Hitting www.howdidido.com/Booking (tracing redirects):")
    r_booking = _follow_redirects_verbose(
        session, f"{HDID_BASE}/Booking",
        headers={"Referer": HDID_BASE}
    )
    print(f"\n    Final URL: {r_booking.url}")
    print(f"    Cookies after /Booking:")
    for c in session.cookies:
        print(f"        {c.domain}: {c.name}={str(c.value)[:50]}")

    # ── Step 5: Verify clubv1.com session ────────────────────────────────────
    print("\n[*] Verifying clubv1.com session...")
    r5 = session.get(
        f"{CLUB_BASE}/HDIDBooking/BookingList",
        params={"courseId": COURSE_ID},
        headers={"Referer": f"{HDID_BASE}/Booking"},
        timeout=15,
        allow_redirects=True
    )
    print(f"    BookingList: HTTP {r5.status_code} -> {r5.url}")

    if r5.status_code == 500:
        soup5 = BeautifulSoup(r5.text, "html.parser")
        print(f"    Page title: {soup5.title.string.strip() if soup5.title else '(none)'}")
        raise Exception("clubv1.com returned HTTP 500 — see redirect trace above for diagnosis.")

    print(" -> clubv1.com session confirmed!")
    time.sleep(0.5)
    return session


def book_tee_time(session, target_date, target_time):
    datetime_str = f"{target_date}T{target_time}"
    LOCK_URL     = f"{CLUB_BASE}/HDIDBooking/BookingAdd"
    LIST_URL     = f"{CLUB_BASE}/HDIDBooking/BookingList?courseId={COURSE_ID}"

    params = {
        "dateTime":            datetime_str,
        "courseId":            COURSE_ID,
        "startPoint":          "1",
        "crossOverStartPoint": "0",
        "crossOverMinutes":    "0",
        "releasedReservation": "False"
    }

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Attempting to LOCK {target_date} at {target_time}...")
    r_lock = session.get(
        LOCK_URL,
        params=params,
        headers={"Referer": LIST_URL},
        timeout=10
    )

    soup = BeautifulSoup(r_lock.text, "html.parser")
    form = soup.find("form")

    if not form:
        print(" -> FAILED: Could not find confirmation form.")
        print(f"    HTTP Status : {r_lock.status_code}")
        print(f"    Page title  : {soup.title.string.strip() if soup.title else '(no title)'}")
        print(f"    Final URL   : {r_lock.url}")
        print(f"    Body snippet:\n{r_lock.text[:600]}")
        text_lower = r_lock.text.lower()
        if "already been booked" in text_lower:
            print("    Reason: That slot is already taken.")
        elif "locked" in text_lower or "available at 07:00" in text_lower:
            print("    Reason: Timesheet locked / not yet released.")
        elif "login" in text_lower or "sign in" in text_lower:
            print("    Reason: Session expired.")
        else:
            print("    Reason: Unknown — check body snippet above.")
        return False

    payload = {
        inp.get("name"): inp.get("value", "")
        for inp in form.find_all("input")
        if inp.get("name")
    }
    print(f" -> Time LOCKED. BookingLockId: {payload.get('BookingLockId')}")

    print(" -> Injecting Phil Bentham and Jason Corkill...")
    payload["Players[0].PersonID"]         = "2512799"
    payload["Players[0].Forename"]         = "Phil"
    payload["Players[0].Surname"]          = "Bentham"
    payload["Players[0].TeeSheetPosition"] = "2"
    payload["Players[0].Amount"]           = "0"
    payload["Players[0].GreenFeeRateID"]   = "0"

    payload["Players[1].PersonID"]         = "1446025"
    payload["Players[1].Forename"]         = "Jason"
    payload["Players[1].Surname"]          = "Corkill"
    payload["Players[1].TeeSheetPosition"] = "3"
    payload["Players[1].Amount"]           = "0"
    payload["Players[1].GreenFeeRateID"]   = "0"

    time.sleep(1.5)

    action_path = form.get("action", "HDIDBooking/bookingConfirmAndPay")
    if action_path.startswith("/"):
        action_path = action_path[1:]
    CONFIRM_URL = f"{CLUB_BASE}/{action_path}"

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Confirming booking at {CONFIRM_URL}...")
    r_confirm = session.post(
        CONFIRM_URL,
        data=payload,
        headers={"Referer": r_lock.url},
        timeout=10
    )

    if "Booking Confirmed" in r_confirm.t
