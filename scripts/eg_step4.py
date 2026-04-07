"""
eg_step4.py — Test score access for Phil B, Jay, Adder using known CDH+passport values.

URL pattern confirmed from browser:
  /golf-profile?passportid={CDH}&code={PASSPORT}&mode=view

We try both CDH and PASSPORT as the otherPassportId in GetMyScores.
"""
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bs4 import BeautifulSoup
from eg_utils import eg_login, eg_fetch_scores, BASE

SEP = "─" * 60

# Known values from wp_golf_players / player config
# passportid in the URL = CDH, code in the URL = passport
PLAYERS = [
    {"name": "Phil B",  "cdh": 463380,   "passport": 1351504402},
    {"name": "Jay",     "cdh": 1259586,  "passport": 546502055},
    {"name": "Adder",   "cdh": 1259582,  "passport": 1902555258},
]

print()
print("═" * 60)
print("  EG STEP 4 — Other Players Score Access Test")
print("═" * 60)
print()
print("  Note: /my-friends is JS-rendered so the scraper sees 0.")
print("  Using known CDH + passport values directly instead.")
print()

session = eg_login()

for player in PLAYERS:
    name     = player["name"]
    cdh      = player["cdh"]
    passport = player["passport"]
    url      = f"{BASE}/golf-profile?passportid={cdh}&code={passport}&mode=view"

    print(SEP)
    print(f"  Player: {name}")
    print(f"  Profile URL: {url}")

    # 1. Load the golf-profile page
    r = session.get(url, timeout=30, allow_redirects=True)
    print(f"  Profile page status: {r.status_code}  final: {r.url}")
    soup = BeautifulSoup(r.text, "html.parser")
    title = soup.title.get_text(strip=True) if soup.title else "no title"
    print(f"  Page title: {title}")

    # Look for API hints in the raw HTML
    hits = set()
    for pat in [r"/api/[^\s\"'<>]+", r"otherPassportId[^\s\"'<>]*",
                r"passportid=[^\s\"'<>&]+"]:
        for m in re.finditer(pat, r.text, re.I):
            hits.add(m.group(0)[:120])
    if hits:
        print("  API hints in profile HTML:")
        for h in sorted(hits)[:10]:
            print(f"    {h}")

    # 2. Try GetMyScores with passport (original guess — gave 500)
    print(f"\n  [A] GetMyScores otherPassportId={passport} (passport) …")
    try:
        scores = eg_fetch_scores(session, passport_id=passport, page_size=3)
        print(f"      → {len(scores)} record(s)")
        if scores:
            print(f"      → PlayDate={scores[0].get('PlayDate')}  AdjustedGross={scores[0].get('AdjustedGross')}")
    except Exception as e:
        print(f"      → ERROR: {e}")

    # 3. Try GetMyScores with CDH (new hypothesis from URL pattern)
    print(f"  [B] GetMyScores otherPassportId={cdh} (CDH) …")
    try:
        scores = eg_fetch_scores(session, passport_id=cdh, page_size=3)
        print(f"      → {len(scores)} record(s)")
        if scores:
            print(f"      → PlayDate={scores[0].get('PlayDate')}  AdjustedGross={scores[0].get('AdjustedGross')}")
    except Exception as e:
        print(f"      → ERROR: {e}")

print()
print(SEP)
print("  NEXT STEP: paste output — we'll see which ID value works")