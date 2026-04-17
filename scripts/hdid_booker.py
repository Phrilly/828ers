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

CLUB_BASE   = "https://howdidido-whs.clubv1.com"
PASSPORT    = "https://passport.howdidido.com"
HDID_BASE   = "https://www.howdidido.com"


def hdid_login():
    session = requests.Session()
    session.headers.update({
        "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                           "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept-Language": "en-GB,en;q=0.9",
        "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    })

    # ── Step 1: Passport login ───────────────────────────────────────────────
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

    print("[*] Submitting login credentials...")
    r2 = session.post(LOGIN_URL, data=post_data, allow_redirects=True, timeout=15)
    r2.raise_for_status()

    if "Sign Out" not in r2.text and "HowDidiDo" not in r2.text:
        raise Exception("Login Failed. Check credentials in config.py.")
    print(" -> Login Successful!")

    # ── Step 2: Get the SSO token from howdidido.com ─────────────────────────
    # After passport login, howdidido.com holds an SSO token it can pass to
    # clubv1.com. We must visit the howdidido booking page FIRST so it generates
    # the token, then follow the redirect chain to clubv1.com.
    print("[*] Fetching SSO token from howdidido.com...")
    r3 = session.get(f"{HDID_BASE}/Booking", timeout=15, allow_redirects=True)
    print(f"    howdidido /Booking: HTTP {r3.status_code} -> {r3.url}")

    # ── Step 3: Follow the club-specific SSO handoff ─────────────────────────
    # howdidido.com redirects to a club-specific URL like:
    #   https://howdidido-whs.clubv1.com/HDIDBooking/HDIDLogin?token=XXXX&...
    # We must follow that redirect so clubv1.com can validate the token and
    # set its own session cookie. Without this, clubv1.com returns HTTP 500.
    if "clubv1.com" in r3.url:
        # We're already there — the redirect was followed automatically
        print(f"    SSO redirect followed automatically -> {r3.url}")
    else:
        # Look for a redirect link in the page (some setups use a meta refresh
        # or a JS redirect instead of a 302)
        soup3 = BeautifulSoup(r3.text, "html.parser")
        redirect_url = None

        # Check for meta refresh
        meta = soup3.find("meta", attrs={"http-equiv": lambda v: v and v.lower() == "refresh"})
        if meta:
            content = meta.get("content", "")
            if "url=" in content.lower():
                redirect_url = content.split("url=", 1)[-1].strip().strip("'"")

        # Check for a link to clubv1.com in the page body
        if not redirect_url:
            for a in soup3.find_all("a", href=True):
                if "clubv1.com" in a["href"]:
                    redirect_url = a["href"]
                    break

        if redirect_url:
            print(f"    Following manual SSO redirect: {redirect_url}")
            r4 = session.get(redirect_url, timeout=15, allow_redirects=True)
            print(f"    clubv1.com SSO: HTTP {r4.status_code} -> {r4.url}")
        else:
            # Fallback: try to hit the club booking endpoint directly via the
            # HDID partner booking URL, which includes an auto-SSO token in
            # the redirect chain
            PARTNER_URL = f"{HDID_BASE}/Booking/Club/{COURSE_ID}"
            print(f"    No redirect found. Trying partner URL: {PARTNER_URL}")
            r4 = session.get(PARTNER_URL, timeout=15, allow_redirects=True)
            print(f"    Partner URL: HTTP {r4.status_code} -> {r4.url}")

    # ── Step 4: Verify clubv1.com session is active ──────────────────────────
    # Hit the BookingList directly to confirm the session works
    print("[*] Verifying clubv1.com session...")
    r5 = session.get(
        f"{CLUB_BASE}/HDIDBooking/BookingList",
        params={"courseId": COURSE_ID},
        headers={"Referer": f"{HDID_BASE}/Booking"},
        timeout=15,
        allow_redirects=True
    )
    print(f"    BookingList: HTTP {r5.status_code} -> {r5.url}")

    if r5.status_code == 500:
        # Dump cookies so we can diagnose
        print("    [!] HTTP 500 — dumping cookies for diagnosis:")
        for c in session.cookies:
            print(f"        {c.domain}: {c.name}={c.value[:30]}...")
        raise Exception(
            "clubv1.com returned HTTP 500 on BookingList. "
            "The SSO token exchange likely failed. "
            "Try logging in manually in a browser and checking the Network tab "
            "for the exact redirect chain from howdidido.com to clubv1.com."
        )

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

    if "Booking Confirmed" in r_confirm.text or "Thank You" in r_confirm.text:
        print(" -> SUCCESS! Tee time officially booked.")
        return True
    else:
        print(" -> FAILED during final confirmation step.")
        conf_soup = BeautifulSoup(r_confirm.text, "html.parser")
        print(f"    HTTP Status : {r_confirm.status_code}")
        print(f"    Page title  : {conf_soup.title.string.strip() if conf_soup.title else '(no title)'}")
        print(f"    Body snippet:\n{r_confirm.text[:500]}")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="828ers HDID Auto Booker")
    parser.add_argument("--tuesday", action="store_true", help="Book the Tuesday 08:32 slot")
    parser.add_argument("--friday",  action="store_true", help="Book the Friday 08:00 slot")
    parser.add_argument("--test",    action="store_true", help="Test mode: target 17:52 in 14 days")
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
            target_time, expected_weekday =