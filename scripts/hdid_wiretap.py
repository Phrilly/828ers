import sys
import requests
import re
from datetime import datetime
import json
import logging
import http.client as http_client

# Import your local config
try:
    import config
except ImportError:
    print("CRITICAL: config.py not found.")
    sys.exit(1)

# --- ENABLE HTTP WIRETAP ---
# This forces the requests library to print the raw HTTP traffic
http_client.HTTPConnection.debuglevel = 1
logging.basicConfig(
    filename='http_wiretap.log',
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
requests_log = logging.getLogger("urllib3")
requests_log.setLevel(logging.DEBUG)
requests_log.propagate = True

EMAIL = config.HDID_EMAIL
PASSWORD = config.HDID_PASSWORD
COURSE_ID = config.HDID_COURSE_ID

def run_wiretap():
    print("[*] Starting Wiretap. Raw HTTP traffic is being routed to 'http_wiretap.log'")
    session = requests.Session()
    
    # We use a pristine, modern User-Agent to avoid WAF blocking
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-GB,en;q=0.5",
        "Connection": "keep-alive"
    })

    try:
        # 1. INITIALIZE
        print("[1/4] Accessing Passport...")
        r_init = session.get("https://passport.howdidido.com/Account/Login?returnUrl=https%3a%2f%2fwww.howdidido.com%2fBooking")
        token_match = re.search(r'name="__RequestVerificationToken" type="hidden" value="([^"]+)"', r_init.text)
        token = token_match.group(1) if token_match else ""

        # 2. AUTHENTICATE
        print("[2/4] Submitting Credentials...")
        payload = {
            "__RequestVerificationToken": token,
            "EmailAddress": EMAIL,
            "Password": PASSWORD,
            "RememberMe": "true"
        }
        r_auth = session.post(r_init.url, data=payload, allow_redirects=True)
        
        # 3. HANDOVER
        print("[3/4] Securing Handover Token...")
        r_portal = session.get("https://www.howdidido.com/Booking")
        match = re.search(r'(https://howdidido-whs\.clubv1\.com/[^"]+)', r_portal.text)
        if match:
            handover_url = match.group(1).replace("&amp;", "&")
            r_handover = session.get(handover_url)
            print(f" -> Handover URL hit. Status: {r_handover.status_code}")
        else:
            print(" -> WARNING: Handover token not found in HTML.")

        # 4. THE FATAL CALL (BookingAdd)
        print("[4/4] Triggering the BookingAdd API...")
        # Use a safe date/time for the test
        target_date = datetime.now().strftime("%Y-%m-%d")
        params = {
            "dateTime": f"{target_date}T12:00",
            "courseId": COURSE_ID,
            "startPoint": "1",
            "releasedReservation": "False"
        }
        
        LOCK_URL = "https://howdidido-whs.clubv1.com/HDIDBooking/BookingAdd"
        LIST_URL = f"https://howdidido-whs.clubv1.com/HDIDBooking/BookingList?courseId={COURSE_ID}"
        
        # CRITICAL: We capture exactly what we send
        r_lock = session.get(LOCK_URL, params=params, headers={"Referer": LIST_URL})
        
        print(f"\nResult: HTTP {r_lock.status_code}")
        
        # Dump the exact request headers that caused the 500
        print("\n--- EXACT REQUEST HEADERS SENT ---")
        for k, v in r_lock.request.headers.items():
            print(f"{k}: {v}")
            
        print(f"\n--- EXACT REQUEST URL SENT ---")
        print(r_lock.request.url)

        if r_lock.status_code == 500:
            print("\n[!] 500 ERROR CAPTURED.")
            with open("error_body.html", "w", encoding="utf-8") as f:
                f.write(r_lock.text)
            print(" -> Server response body saved to 'error_body.html'")
            
    except Exception as e:
        print(f"Script crashed: {e}")

if __name__ == "__main__":
    run_wiretap()