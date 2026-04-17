import sys
import argparse
import time
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta

# Import your existing local config file
try:
    import config
except ImportError:
    print("CRITICAL: config.py not found. Ensure it is uploaded to the server.")
    sys.exit(1)

# --- CONFIGURATION ---
EMAIL             = config.HDID_EMAIL
PASSWORD          = config.HDID_PASSWORD
COURSE_ID         = config.HDID_COURSE_ID
DAYS_IN_ADVANCE   = 14


# --- SETUP SESSION ---
def hdid_login():
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    })

    LOGIN_URL = "https://passport.howdidido.com/Account/Login"

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

    if "Sign Out" in r2.text or "HowDidiDo" in r2.text:
        print(" -> Login Successful!")

        # --- THE FIX ---
        # passport.howdidido.com authenticates you, but howdidido-whs.clubv1.com is a
        # SEPARATE server with its own session. It only issues a session token once you
        # visit a page on THAT subdomain while authenticated. Without this prime the
        # BookingAdd endpoint doesn't recognise you and returns a login/error page
        # instead of the booking form.
        print("[*] Priming WHS booking session on clubv1.com...")
        PRIME_URL = f"https://howdidido-whs.clubv1.com/HDIDBooking/BookingList?courseId={COURSE_ID}"
        r_prime = session.get(PRIME_URL, timeout=15, allow_redirects=True)
        print(f"    Prime response: HTTP {r_prime.status_code}")
        time.sleep(1)
        return session
    else:
        raise Exception("Login Failed. Check credentials in config.py.")


# --- BOOKING LOGIC ---
def book_tee_time(session, target_date, target_time):
    datetime_str    = f"{target_date}T{target_time}"
    LOCK_URL        = "https://howdidido-whs.clubv1.com/HDIDBooking/BookingAdd"
    BOOKING_LIST    = f"https://howdidido-whs.clubv1.com/HDIDBooking/BookingList?courseId={COURSE_ID}"

    params = {
        "dateTime":               datetime_str,
        "courseId":               COURSE_ID,
        "startPoint":             "1",
        "crossOverStartPoint":    "0",
        "crossOverMinutes":       "0",
        "releasedReservation":    "False"
    }

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Attempting to LOCK {target_date} at {target_time}...")

    # Referer makes the request look like natural browser navigation
    r_lock = session.get(
        LOCK_URL,
        params=params,
        headers={"Referer": BOOKING_LIST},
        timeout=10
    )

    soup = BeautifulSoup(r_lock.text, "html.parser")
    form = soup.find("form")

    if not form:
        print(" -> FAILED: Could not find confirmation form.")
        # Diagnostic output to help identify exactly why it failed
        print(f"    HTTP Status : {r_lock.status_code}")
        print(f"    Page title  : {soup.title.string.strip() if soup.title else '(no title)'}")
        print(f"    Final URL   : {r_lock.url}")
        print(f"    Body snippet:\n{r_lock.text[:500]}")
        text_lower = r_lock.text.lower()
        if "already been booked" in text_lower:
            print("    Reason: That slot is already taken.")
        elif "locked" in text_lower or "available at 07:00" in text_lower:
            print("    Reason: The timesheet is locked / not yet released.")
        elif "login" in text_lower or "sign in" in text_lower:
            print("    Reason: Session expired — server returned a login page.")
        else:
            print("    Reason: Unknown — check body snippet above.")
        return False

    payload = {
        inp.get("name"): inp.get("value", "")
        for inp in form.find_all("input")
        if inp.get("name")
    }

    print(f" -> Time LOCKED. BookingLockId: {payload.get('BookingLockId')}")

    # --- PLAYER INJECTION ---
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

    CONFIRM_URL = f"https://howdidido-whs.clubv1.com/{action_path}"

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


# --- ENTRY POINT ---
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

    MAX_ATTEMPTS = 1 if is_test else 30
    for attempt in range(1, MAX_ATTEMPTS + 1):
        if not is_test:
            print(f"--- Attempt {attempt} of {MAX_ATTEMPTS} ---")

        try:
            if book_tee_time(my_session, target_date, target_time):
                sys.exit(0)
        except Exception as e:
            print(f" -> Error during attempt: {e}")

        if attempt < MAX_ATTEMPTS:
            time.sleep(10)

    print("\n[!] Finished all attempts.")