import requests
from bs4 import BeautifulSoup

r = requests.get("https://passport.howdidido.com/Account/Login")
soup = BeautifulSoup(r.text, "html.parser")

print("--- LOGIN FORM INPUTS ---")
for inp in soup.find_all("input"):
    print(f"Name: {inp.get('name')} | Type: {inp.get('type')}")