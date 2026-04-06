# config.example.py — SAFE TO COMMIT — contains no real credentials
# ─────────────────────────────────────────────────────────────────
# SETUP: copy this file to config.py and fill in your real values.
#        config.py is gitignored and must NEVER be committed.
#
#   cp config.example.py config.py
#   nano config.py
# ─────────────────────────────────────────────────────────────────

# England Golf — Phil D is the login account holder
EG_USERNAME = "1017311170"           # membership number — safe to commit
EG_PASSWORD = "YOUR_EG_PASSWORD"     # ← fill in config.py only

# WordPress MySQL
DB_HOST     = "localhost"
DB_PORT     = 3306
DB_NAME     = "your_wordpress_db"
DB_USER     = "your_db_user"
DB_PASSWORD = "YOUR_DB_PASSWORD"     # ← fill in config.py only
DB_PREFIX   = "wp_"

# Email alerts (Gmail: use an App Password from myaccount.google.com)
SMTP_HOST     = "smtp.gmail.com"
SMTP_PORT     = 587
SMTP_USER     = "you@gmail.com"
SMTP_PASSWORD = "YOUR_APP_PASSWORD"  # ← fill in config.py only
EMAIL_FROM    = "you@gmail.com"
EMAIL_TO      = "you@gmail.com"

# Players — passport IDs confirmed from reverse-engineering session.
# tee_colour MUST match wp_golf_tees.tee_colour exactly (check casing).
# Run: SELECT tee_id, tee_colour FROM wp_golf_tees;
PLAYERS = [
    {
        "code":           "PD",
        "name":           "Phil D",    # must match wp_golf_players.name exactly
        "eg_passport_id": None,         # None = the logged-in account itself
        "default_tee":    "Green",      # verify against your DB
    },
    {
        "code":           "PB",
        "name":           "Phil B",
        "eg_passport_id": 1351504402,
        "default_tee":    "Blue",
    },
    {
        "code":           "JC",
        "name":           "Jay",
        "eg_passport_id": 546502055,
        "default_tee":    "Red",
    },
    {
        "code":           "AC",
        "name":           "Adder",
        "eg_passport_id": 1902555258,
        "default_tee":    "Purple",
    },
]
