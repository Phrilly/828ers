# eg_probe5.py — POST to the real form action URL
import sys
import requests
from bs4 import BeautifulSoup
import config

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept-Language": "en-GB,en;q=0.9",
    "Referer": "https://www.englandgolf.org/igolf-login",
})

r = session.get("https://www.englandgolf.org/igolf-login", timeout=30)
soup = BeautifulSoup(r.text, "html.parser")

# Get the real form action URL
form = soup.find("form", {"method": "post"})
action = form.get("action", "") if form else ""
print(f"Form action: {action}")

# Build absolute POST URL
if action.startswith("http"):
    post_url = action
elif action.startswith("/"):
    post_url = "https://www.englandgolf.org" + action
else:
    post_url = "https://www.englandgolf.org/igolf-login"

print(f"Posting to: {post_url}")

hidden_fields = {}
for inp in soup.find_all("input", {"type": "hidden"}):
    name = inp.get("name")
    if name:
        hidden_fields[name] = inp.get("value", "")

post_data = {
    **hidden_fields,
    "__EVENTTARGET":            "",
    "__EVENTARGUMENT":          "",
    "ctl73$tbMembershipNumber": config.EG_USERNAME,
    "ctl73$tbPassword":         config.EG_PASSWORD,
    "ctl73$cbRememberMe":       "on",
    "ctl73$btnLogin":           "Log in",
}

def trace(r, *args, **kwargs):
    if r.is_redirect:
        print(f"  Redirect {r.status_code} → {r.headers.get('Location','?')}")

r2 = session.post(
    post_url,
    data=post_data,
    timeout=30,
    allow_redirects=True,
    hooks={"response": trace},
    headers={"Referer": "https://www.englandgolf.org/igolf-login"},
)

print(f"Final URL: {r2.url}")
print(f"Status: {r2.status_code}")
print("Cookies:")
for c in session.cookies:
    print(f"  {c.name} @ {c.domain} (expires={c.expires})")

# Check if still on login page
still_login = soup.find("input", {"name": "ctl73$tbPassword"}) is not None
page2_soup = BeautifulSoup(r2.text, "html.parser")
still_login2 = page2_soup.find("input", {"name": "ctl73$tbPassword"}) is not None
print(f"Still on login page: {still_login2}")

cwtoken = session.cookies.get("CWApiToken")
print(f"\nCWApiToken after login: {'YES ✓' if cwtoken else 'NO ✗'}")

if not cwtoken:
    print("\nVisiting /my-scores to trigger CWApiToken...")
    r3 = session.get(
        "https://www.englandgolf.org/my-scores",
        timeout=30,
        allow_redirects=True,
        headers={"Referer": "https://www.englandgolf.org/"},
    )
    print(f"my-scores status: {r3.status_code} — final URL: {r3.url}")
    print("Cookies now:")
    for c in session.cookies:
        print(f"  {c.name} @ {c.domain}")
    cwtoken = session.cookies.get("CWApiToken")
    print(f"\nCWApiToken after /my-scores: {'YES ✓' if cwtoken else 'NO ✗'}")

if cwtoken:
    print("\nTrying API...")
    api = session.post(
        "https://www.englandgolf.org/api/Score/GetMyScores",
        json={"pageNumber":1,"pageSize":5,"otherPassportId":None,
              "includeCasualScores":False,"casualScoresOnly":False,"getDefaultFacility":True},
        headers={"Content-Type":"application/json","Accept":"application/json",
                 "Referer":"https://www.englandgolf.org/my-scores",
                 "X-Requested-With":"XMLHttpRequest"},
        timeout=30,
    )
    print(f"API status: {api.status_code}")
    if api.status_code == 200:
        data = api.json()
        records = data if isinstance(data, list) else data.get("scores", data.get("data", []))
        print(f"✓ SUCCESS — {len(records)} records")
        if records:
            print("\nField names in first record:")
            for k, v in records[0].items():
                print(f"  '{k}': {repr(v)[:60]}")
    else:
        print(f"✗ {api.text[:300]}")