import sys
import os
import re
import json
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, parse_qs

try:
    import config
except ImportError:
    print("CRITICAL: config.py not found.")
    sys.exit(1)

EMAIL = config.HDID_EMAIL
PASSWORD = config.HDID_PASSWORD
COURSE_ID = str(config.HDID_COURSE_ID)

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
OUTDIR = "output/hdid_probe"
os.makedirs(OUTDIR, exist_ok=True)


def dump_text(name, text):
    path = os.path.join(OUTDIR, name)
    with open(path, "w", encoding="utf-8", errors="ignore") as f:
        f.write(text)
    return path


def dump_json(name, obj):
    path = os.path.join(OUTDIR, name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
    return path


def cookies_snapshot(session):
    rows = []
    for c in session.cookies:
        rows.append({
            "domain": c.domain,
            "name": c.name,
            "value_prefix": str(c.value)[:80],
            "path": c.path,
            "secure": c.secure,
            "expires": c.expires,
        })
    return rows


def response_meta(label, r, session):
    return {
        "label": label,
        "url": r.url,
        "status_code": r.status_code,
        "is_redirect": r.is_redirect,
        "location": r.headers.get("Location"),
        "content_type": r.headers.get("Content-Type"),
        "set_cookie": r.headers.get("Set-Cookie"),
        "cookies_now": cookies_snapshot(session),
    }


def print_cookies(session, heading):
    print(f"\n=== {heading} ===")
    if not session.cookies:
        print("(no cookies)")
        return
    for c in session.cookies:
        print(f"{c.domain:30} {c.name:30} {str(c.value)[:60]}")


def absolute(base, href):
    return urljoin(base, href)


def scan_html(label, base_url, html):
    findings = {
        "title": None,
        "forms": [],
        "links_with_keywords": [],
        "scripts_with_keywords": [],
        "tokenish_strings": [],
        "clubv1_urls": [],
        "passport_urls": [],
        "booking_urls": [],
    }

    soup = BeautifulSoup(html, "html.parser")
    findings["title"] = soup.title.string.strip() if soup.title and soup.title.string else None

    for i, form in enumerate(soup.find_all("form"), start=1):
        inputs = []
        for inp in form.find_all("input"):
            inputs.append({
                "name": inp.get("name"),
                "type": inp.get("type"),
                "value_prefix": (inp.get("value") or "")[:120],
            })
        findings["forms"].append({
            "index": i,
            "action": absolute(base_url, form.get("action", "")),
            "method": form.get("method", "GET").upper(),
            "inputs": inputs,
        })

    keywords = ["clubv1", "token", "booking", "passport", "returnurl", "signin", "login", "hdid"]

    for a in soup.find_all("a", href=True):
        href = absolute(base_url, a["href"])
        low = href.lower()
        if any(k in low for k in keywords):
            findings["links_with_keywords"].append(href)
        if "clubv1.com" in low:
            findings["clubv1_urls"].append(href)
        if "passport.howdidido.com" in low:
            findings["passport_urls"].append(href)
        if "booking" in low:
            findings["booking_urls"].append(href)

    for s in soup.find_all("script"):
        txt = s.string or s.get_text(" ", strip=False) or ""
        low = txt.lower()
        if any(k in low for k in keywords):
            findings["scripts_with_keywords"].append(txt[:1000])

    regexes = [
        r"https://howdidido-whs\.clubv1\.com/[^\"'\s<]+",
        r"https://passport\.howdidido\.com/[^\"'\s<]+",
        r"https://www\.howdidido\.com/[^\"'\s<]+",
        r"token=[A-Za-z0-9\-_%\.]+",
        r"returnUrl=[^\"'\s<]+",
        r"__RequestVerificationToken",
        r"\.ASPXAUTH",
    ]
    for rx in regexes:
        for m in re.findall(rx, html, flags=re.I):
            findings["tokenish_strings"].append(m)

    for key in ("links_with_keywords", "clubv1_urls", "passport_urls", "booking_urls", "tokenish_strings"):
        findings[key] = sorted(set(findings[key]))

    return findings


def main():
    session = requests.Session()
    session.headers.update({
        "User-Agent": UA,
        "Accept-Language": "en-GB,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    })

    report = {"steps": []}

    print("[*] Step 1: GET Passport login page")
    login_url = "https://passport.howdidido.com/Account/Login?returnUrl=%2fBooking"
    r1 = session.get(login_url, timeout=20)
    report["steps"].append(response_meta("passport_login_get", r1, session))
    dump_text("01_passport_login.html", r1.text)
    dump_json("01_passport_login_scan.json", scan_html("passport_login_get", r1.url, r1.text))
    print(f"    {r1.status_code} -> {r1.url}")
    print_cookies(session, "Cookies after GET login")

    soup1 = BeautifulSoup(r1.text, "html.parser")
    hidden = {
        inp.get("name"): inp.get("value", "")
        for inp in soup1.find_all("input", {"type": "hidden"})
        if inp.get("name")
    }
    dump_json("02_passport_hidden_fields.json", hidden)
    print(f"    Hidden fields found: {list(hidden.keys())}")

    print("\n[*] Step 2: POST Passport credentials")
    post_data = {
        **hidden,
        "EmailAddress": EMAIL,
        "Password": PASSWORD,
        "RememberMe": "true",
    }
    r2 = session.post(r1.url, data=post_data, headers={"Referer": r1.url}, allow_redirects=True, timeout=20)
    report["steps"].append(response_meta("passport_login_post", r2, session))
    dump_text("03_passport_post_final.html", r2.text)
    dump_json("03_passport_post_scan.json", scan_html("passport_login_post", r2.url, r2.text))
    print(f"    {r2.status_code} -> {r2.url}")
    print_cookies(session, "Cookies after POST login")

    print("\n[*] Step 3: GET www.howdidido.com/Booking")
    r3 = session.get("https://www.howdidido.com/Booking", headers={"Referer": "https://www.howdidido.com/"}, allow_redirects=True, timeout=20)
    report["steps"].append(response_meta("hdid_booking_get", r3, session))
    dump_text("04_hdid_booking.html", r3.text)
    booking_scan = scan_html("hdid_booking_get", r3.url, r3.text)
    dump_json("04_hdid_booking_scan.json", booking_scan)
    print(f"    {r3.status_code} -> {r3.url}")
    print_cookies(session, "Cookies after GET /Booking")
    print(f"    Title: {booking_scan['title']}")
    print(f"    clubv1 URLs found: {len(booking_scan['clubv1_urls'])}")
    print(f"    token-ish strings: {len(booking_scan['tokenish_strings'])}")

    handover_candidates = []
    handover_candidates.extend(booking_scan["clubv1_urls"])
    for item in booking_scan["tokenish_strings"]:
        if "clubv1.com" in item.lower() or "token=" in item.lower():
            handover_candidates.append(item)
    handover_candidates = sorted(set(handover_candidates))
    dump_json("05_handover_candidates.json", handover_candidates)

    if handover_candidates:
        print("\n[*] Step 4: Probe handover candidates")
        probe_results = []
        for idx, candidate in enumerate(handover_candidates[:10], start=1):
            url = candidate
            if url.startswith("token="):
                continue
            try:
                print(f"    [{idx}] {url}")
                rr = session.get(url, headers={"Referer": r3.url}, allow_redirects=True, timeout=20)
                probe_results.append(response_meta(f"handover_{idx}", rr, session))
                dump_text(f"handover_{idx}.html", rr.text)
                dump_json(f"handover_{idx}_scan.json", scan_html(f"handover_{idx}", rr.url, rr.text))
                print(f"        -> {rr.status_code} {rr.url}")
            except Exception as e:
                probe_results.append({"label": f"handover_{idx}", "url": url, "error": str(e)})
                print(f"        -> ERROR: {e}")
        report["handover_probes"] = probe_results
    else:
        print("\n[*] No handover candidates found in /Booking HTML")

    print("\n[*] Step 5: Probe clubv1 BookingList directly")
    r5 = session.get(
        "https://howdidido-whs.clubv1.com/HDIDBooking/BookingList",
        params={"courseId": COURSE_ID},
        headers={"Referer": "https://www.howdidido.com/Booking"},
        allow_redirects=True,
        timeout=20,
    )
    report["steps"].append(response_meta("clubv1_bookinglist", r5, session))
    dump_text("06_clubv1_bookinglist.html", r5.text)
    dump_json("06_clubv1_bookinglist_scan.json", scan_html("clubv1_bookinglist", r5.url, r5.text))
    print(f"    {r5.status_code} -> {r5.url}")
    print_cookies(session, "Cookies after clubv1 BookingList")

    print("\n[*] Step 6: Probe BookingAdd directly")
    r6 = session.get(
        "https://howdidido-whs.clubv1.com/HDIDBooking/BookingAdd",
        params={
            "dateTime": "2026-05-01T17:52",
            "courseId": COURSE_ID,
            "startPoint": "1",
            "crossOverStartPoint": "0",
            "crossOverMinutes": "0",
            "releasedReservation": "False",
        },
        headers={"Referer": f"https://howdidido-whs.clubv1.com/HDIDBooking/BookingList?courseId={COURSE_ID}"},
        allow_redirects=True,
        timeout=20,
    )
    report["steps"].append(response_meta("clubv1_bookingadd", r6, session))
    dump_text("07_clubv1_bookingadd.html", r6.text)
    dump_json("07_clubv1_bookingadd_scan.json", scan_html("clubv1_bookingadd", r6.url, r6.text))
    print(f"    {r6.status_code} -> {r6.url}")

    report["final_cookies"] = cookies_snapshot(session)
    dump_json("00_report.json", report)

    print("\nDone. Files written to:", OUTDIR)
    print("Most useful files:")
    print(" - output/hdid_probe/00_report.json")
    print(" - output/hdid_probe/04_hdid_booking.html")
    print(" - output/hdid_probe/04_hdid_booking_scan.json")
    print(" - output/hdid_probe/05_handover_candidates.json")
    print(" - output/hdid_probe/06_clubv1_bookinglist.html")
    print(" - output/hdid_probe/07_clubv1_bookingadd.html")


if __name__ == "__main__":
    main()
