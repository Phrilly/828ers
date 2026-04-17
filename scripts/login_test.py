import requests
from bs4 import BeautifulSoup
import config

print(f"[*] Testing login for: {config.HDID_EMAIL}")

s = requests.Session()
s.headers.update({"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"})

# 1. Get the form
r1 = s.get("https://passport.howdidido.com/Account/Login")
soup1 = BeautifulSoup(r1.text, "html.parser")

# 2. Build the exact payload
payload = {inp.get("name"): inp.get("value", "") for inp in soup1.find_all("input", type="hidden") if inp.get("name")}
payload["EmailAddress"] = config.HDID_EMAIL
payload["Password"] = config.HDID_PASSWORD
payload["RememberMe"] = "true"

# 3. Submit
r2 = s.post(r1.url, data=payload)
soup2 = BeautifulSoup(r2.text, "html.parser")

# 4. Scrape the error messages
summary = soup2.find("div", class_="validation-summary-errors")
field_errors = soup2.find_all("span", class_="field-validation-error")

print("\n--- SERVER RESPONSE ---")
if summary and summary.text.strip():
    print(f"Form Error: {summary.text.strip()}")
    
if field_errors:
    for e in field_errors:
        if e.text.strip():
            print(f"Field Error: {e.text.strip()}")

if ".ASPXAUTH" in [c.name for c in s.cookies]:
    print("\nSUCCESS! Auth cookie found. The login worked.")
elif not summary and not field_errors:
    print("\nUNKNOWN FAILURE. No text errors found on the page, but no auth cookie issued.")