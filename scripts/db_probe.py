import sys, os
python_version = f"python{sys.version_info.major}.{sys.version_info.minor}"
sys.path.insert(0, os.path.expanduser(f'~/.local/lib/{python_version}/site-packages'))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import socket
import pymysql
import config

print("DB_HOST =", repr(config.DB_HOST))
print("DB_PORT =", repr(config.DB_PORT))
print("DB_NAME =", repr(config.DB_NAME))
print("DB_USER =", repr(config.DB_USER))
print("DB_PASSWORD_LEN =", len(config.DB_PASSWORD))
print("RESOLUTION =", socket.getaddrinfo(config.DB_HOST, config.DB_PORT, type=socket.SOCK_STREAM))

try:
    conn = pymysql.connect(
        host=config.DB_HOST,
        port=config.DB_PORT,
        db=config.DB_NAME,
        user=config.DB_USER,
        password=config.DB_PASSWORD,
        charset="utf8mb4",
        autocommit=False,
        cursorclass=pymysql.cursors.DictCursor,
    )
    with conn.cursor() as cur:
        cur.execute("SELECT DATABASE() AS db, CURRENT_USER() AS current_user, @@hostname AS host")
        print("CONNECTED =", cur.fetchone())
    conn.close()
except Exception as exc:
    print("CONNECT_ERROR =", repr(exc))