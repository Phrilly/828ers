import pymysql
import sys

# Hardcoded config for isolated testing - Switched to localhost
DB_HOST = 'localhost'
DB_PORT = 3306
DB_NAME = 'u271511030_9syka'
DB_USER = 'u271511030_AFpgR'
DB_PASSWORD = 'YOUR_PASSWORD_HERE' # Replace with actual password before running

def test_connection():
    print(f"Attempting to connect to {DB_NAME} at {DB_HOST} (Internal Localhost) as {DB_USER}...")
    try:
        connection = pymysql.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME,
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=10
        )
        print("SUCCESS: Database connection established via localhost.")
        connection.close()
    except pymysql.MySQLError as e:
        print(f"FAILED: MySQL Error: {e}")
    except Exception as e:
        print(f"FAILED: General Error: {e}")

if __name__ == "__main__":
    if DB_PASSWORD == 'YOUR_PASSWORD_HERE':
        print("ERROR: Please insert the actual database password into db_probe.py before running.")
        sys.exit(1)
    test_connection()