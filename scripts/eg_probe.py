# save as eg_probe2.py
import sys
import json
from eg_utils import eg_login, EGLoginError

print("Step 1: Login to members.whsplatform.englandgolf.org...")
try:
    session = eg_login(force=True)
except EGLoginError as exc:
    print(f"Login failed: {exc}")
    sys.exit(1)

print(f"Cookies after login: {list(session.cookies.keys())}")

print("\nStep 2: Visit www.englandgolf.org/my-scores to collect CWApiToken...")
page = session.get(
    "https://www.englandgolf.org/my-scores",
    timeout=30,
    allow_redirects=True
)
print(f"Status: {page.status_code}")
print(f"Cookies now: {list(session.cookies.keys())}")

cwtoken = session.cookies.get("CWApiToken")
print(f"CWApiToken present: {'YES ✓' if cwtoken else 'NO ✗'}")
if cwtoken:
    print(f"CWApiToken (first 50 chars): {cwtoken[:50]}...")

print("\nStep 3: Now try the API with CWApiToken in place...")
PAYLOAD = {
    "pageNumber": 1, "pageSize": 5,
    "otherPassportId": None,
    "includeCasualScores": False,
    "casualScoresOnly": False,
    "getDefaultFacility": True,
}
HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Referer": "https://www.englandgolf.org/my-scores",
    "X-Requested-With": "XMLHttpRequest",
}

r = session.post(
    "https://www.englandgolf.org/api/Score/GetMyScores",
    json=PAYLOAD,
    headers=HEADERS,
    timeout=30,
)
print(f"API status: {r.status_code}")
if r.status_code == 200:
    data = r.json()
    print(f"✓ GOT DATA!")
    print(f"Response type: {type(data)}")
    if isinstance(data, list) and data:
        print(f"Records returned: {len(data)}")
        print(f"\nFirst record field names:")
        for k, v in data[0].items():
            print(f"  '{k}': {repr(v)[:60]}")
    elif isinstance(data, dict):
        print(f"Keys: {list(data.keys())}")
        print(json.dumps(data, indent=2, default=str)[:1000])
else:
    print(f"✗ Failed: {r.text[:300]}")