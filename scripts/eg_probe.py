# save as eg_probe.py in your scripts folder and run it
# python eg_probe.py

import sys
from eg_utils import eg_login, with_retry, EGLoginError, EGAPIError

print("Logging in...")
try:
    session = eg_login(force=True)
except EGLoginError as exc:
    print(f"Login failed: {exc}")
    sys.exit(1)

print(f"Cookies: {list(session.cookies.keys())}")
print(f"Cookie domains: {[c.domain for c in session.cookies]}\n")

PAYLOAD = {
    "pageNumber": 1, "pageSize": 5,
    "otherPassportId": None,
    "includeCasualScores": False,
    "casualScoresOnly": False,
    "getDefaultFacility": True,
}
HEADERS = {"Content-Type": "application/json", "Accept": "application/json"}

# Try every plausible URL
CANDIDATE_URLS = [
    "https://members.whsplatform.englandgolf.org/api/Score/GetMyScores",
    "https://members.whsplatform.englandgolf.org/api/score/getmyscores",
    "https://members.whsplatform.englandgolf.org/Score/GetMyScores",
    "https://www.englandgolf.org/api/Score/GetMyScores",
    "https://whsplatform.englandgolf.org/api/Score/GetMyScores",
]

for url in CANDIDATE_URLS:
    try:
        r = session.post(url, json=PAYLOAD, headers=HEADERS, timeout=15)
        print(f"  {r.status_code}  {url}")
        if r.status_code == 200:
            print(f"         ✓ GOT DATA: {r.text[:200]}")
        elif r.status_code not in (401, 403, 404):
            print(f"         Response: {r.text[:200]}")
    except Exception as exc:
        print(f"  ERR  {url} — {exc}")