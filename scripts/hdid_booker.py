import sys
import argparse
import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import re

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

    # CRITICAL: Username instead of EmailAddress
    post_data = {
        **hidden_fields,
        "Username":     EMAIL,
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

    hdid_auth = None
    for c in session.cookies:
        if ".ASPXAUTH" in c.name:
            hdid_auth = c.name
            break

    if not hdid_auth:
        raise Exception("Login Failed: .ASPXAUTH cookie was not issued.")
    
    print(f" -> Login Successful! Auth cookie: {hdid_auth}")

    # ── Step 3: Prime www.howdidido.com with the /Booking path ──────────────
    print("\n[*] Hitting www.howdidido.com/Booking to locate the handover link...")
    r_booking = _follow_redirects_verbose(
        session, f"{HDID_BASE}/Booking",
        headers={"Referer": HDID_BASE}
    )

    # ── Step 4: THE MISSING LINK (Extract and activate the Handover Token) ──
    print("\n[*] Extracting ClubV1 Handover Token...")
    # We search the HTML of the Booking page for the link to clubv1
    match = re.search(r'(https://howdidido-whs\.clubv1\.com/[^"]+)', r_booking.text)
    
    if match:
        handover_url = match.group(1).replace("&amp;", "&")
        print(f"    -> FOUND: {handover_url}")
        print("    -> Activating session bridge...")
        # Visiting this URL is what tells ClubV1 who we are
        r_bridge = _follow_redirects_verbose(session, handover_url)
    else:
        print("    -> CRITICAL: No handover link found on the /Booking page.")
        # Diagnostic dump to see WHY it's missing
        with open("booking_page_dump.html", "w", encoding="utf-8") as f:
            f.write(r_booking.text)
        print("    -> HTML of /Booking saved to 'booking_page_dump.html' for analysis.")
        raise Exception("Cannot bridge to ClubV1 without the handover token.")

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
        raise Exception("clubv1.com returned HTTP 500 — The bridge failed to authenticate the session.")

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

    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Attempting to LOCK {target_date} at {target_time}...")
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
        text_lower = r_lock.text.lower()
        if "already been booked" in text_lower:
            print("    Reason: That slot is already taken.")
        elif "locked" in text_lower or "available at 07:00" in text_lower:
            print("    Reason: Timesheet locked / not yet released.")
        elif "login" in text_lower or "sign in" in text_lower:
            print("    Reason: Session expired.")
        else:
            print("    Reason: Unknown server rejection.")
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

    if "Booking Confirmed" in r_confirm.text or "Thank You" in r_confirm.text:
        print(" -> SUCCESS! Tee time officially booked.")
        return True
    else:
        print(" -> FAILED during final confirmation step.")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="828ers HDID Auto Booker")
    parser.add_argument("--tuesday", action="store_true")
    parser.add_argument("--friday",  action="store_true")
    parser.add_argument("--test",    action="store_true")
    args = parser.parse_args()

    if not any([args.tuesday, args.friday, args.test]):
        print("Error: Use --tuesday, --friday, or --test")
        sys.exit(1)

    if args.test:
        target_date_obj = datetime.today() + timedelta(days=14)
        target_date     = target_date_obj.strftime("%Y-%m-%d")
        target_time     = "17:52"
        is_test         = True
    else:
        target_date_obj = datetime.today() + timedelta(days=DAYS_IN_ADVANCE)
        target_date     = target_date_obj.strftime("%Y-%m-%d")
        is_test         = False
        if args.tuesday:
            target_time, expected_weekday = "08:32", 1
        else:
            target_time, expected_weekday = "08:00", 4

        if target_date_obj.weekday() != expected_weekday:
            print(f"CRITICAL: Target date {target_date} is not the correct weekday. Aborting.")
            sys.exit(1)

    print(f"=== 828ers Auto-Booker {'[TEST MODE]' if is_test else ''} ===")
    print(f"Targeting: {target_date} @ {target_time}\n")

    try:
        my_session = hdid_login()
    except Exception as e:
        print(f"CRITICAL: {e}")
        sys.exit(1)

    MAX_ATTEMPTS = 1 if is_test else 60
    for attempt in range(1, MAX_ATTEMPTS + 1):
        if not is_test:
            print(f"--- Attempt {attempt} of {MAX_ATTEMPTS} ---")

        try:
            if book_tee_time(my_session, target_date, target_time):
                sys.exit(0)
        except Exception as e:
            print(f" -> Error during attempt: {e}")

        if attempt < MAX_ATTEMPTS:
            time.sleep(2)

    print("\n[!] Finished all attempts.")