#!/usr/bin/env python3
"""
eg_step2.py — Test Session Persistence

WHAT THIS TESTS:
  - eg_session.pkl can be reloaded after step 1
  - The saved cookie is still accepted by EG
  - Confirms cron night-2+ won't need a fresh login

HOLES FIXED:
  #11 Pickle corruption detected and reported cleanly

RUN: python eg_step2.py
  (run WITHOUT --fresh to test the saved cookie, not a new login)
"""

import os
import sys
import pickle
from eg_utils import SESSION_FILE, EGLoginError

SEP = "─" * 60
print(f"\n{'═'*60}")
print("  EG STEP 2 — Session Persistence Test")
print(f"{'═'*60}\n")

if not os.path.exists(SESSION_FILE):
    print(f"  ✗ {SESSION_FILE} not found")
    print("  → Run eg_step1.py first to create the saved session")
    sys.exit(1)

print(f"  Loading {SESSION_FILE} from disk…")
try:
    with open(SESSION_FILE, "rb") as f:
        session = pickle.load(f)
    print(f"  ✓ File loaded. Cookies present: {list(session.cookies.keys())}")
except pickle.UnpicklingError:
    print(f"  ✗ File is corrupted — run: python eg_step1.py --fresh")
    sys.exit(1)
except Exception as exc:
    print(f"  ✗ Load error: {exc}")
    sys.exit(1)

print("\n  Probing EG with saved session (GET /my-golf)…")
import requests
try:
    probe = session.get(
        "https://members.whsplatform.englandgolf.org/my-golf",
        timeout=15,
        allow_redirects=False,
    )
    print(f"  Status: {probe.status_code}")
    if probe.status_code == 200:
        print("  ✓ SESSION IS VALID — persistent login confirmed")
        print("  The cron job will not need to re-login every night")
    elif probe.status_code in (301, 302, 303):
        loc = probe.headers.get("Location", "?")
        print(f"  ✗ REDIRECTED to: {loc}")
        print("  Session has expired — run: python eg_step1.py --fresh")
        sys.exit(1)
    else:
        print(f"  ? Unexpected status {probe.status_code} — manual check needed")
except Exception as exc:
    print(f"  ✗ Probe failed: {exc}")
    sys.exit(1)

print(f"\n  NEXT STEP: run python eg_step3.py to see what EG sends back for Phil D's scores")
