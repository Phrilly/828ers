#!/usr/bin/env python3
"""
eg_step1.py — Test EG Login

WHAT THIS TESTS:
  - VIEWSTATE extraction works
  - Login POST succeeds with your credentials
  - Session cookie is received and saved to eg_session.pkl

HOLES FIXED:
  #1  Form fields discovered dynamically (no hardcoded ctl74)
  #11 Pickle save errors reported clearly
  #14 Works from any directory

RUN:
  python eg_step1.py
  python eg_step1.py --fresh   # ignore saved session, force new login
"""

import argparse
import sys
from eg_utils import eg_login, SESSION_FILE, EGLoginError

parser = argparse.ArgumentParser()
parser.add_argument("--fresh", action="store_true", help="Ignore saved session")
args = parser.parse_args()

SEP = "─" * 60
print(f"\n{'═'*60}")
print("  EG STEP 1 — Login Test")
print(f"{'═'*60}")

try:
    session = eg_login(force=args.fresh)
except EGLoginError as exc:
    print(f"\n  ✗ LOGIN FAILED\n  {exc}")
    sys.exit(1)
except Exception as exc:
    print(f"\n  ✗ UNEXPECTED ERROR: {exc}")
    sys.exit(1)

print(f"\n  ✓ Login succeeded")
print(f"  Session file: {SESSION_FILE}")
print(f"  Cookies:      {list(session.cookies.keys())}")
for c in session.cookies:
    expiry = c.expires if hasattr(c, "expires") else "unknown"
    print(f"    {c.name}: domain={c.domain}, expires={expiry}")

print(f"\n  NEXT STEP: run python eg_step2.py to confirm session persistence")
