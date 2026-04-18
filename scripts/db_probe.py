import pymysql
import sys

DB_HOST = '127.0.0.1'
DB_PORT = 3306
DB_NAME = 'u271511030_9syka'
DB_USER = 'u271511030_AFpgR'
DB_PASSWORD = 'p9bXvxr3xN'

def test_connection():
    print(f"Attempting to connect to {DB_NAME} at {DB_HOST} (Forced IPv4 Localhost) as {DB_USER}...")
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
        print("SUCCESS: Database connection established via 127.0.0.1.")
        connection.close()
    except pymysql.MySQLError as e:
        print(f"FAILED: MySQL Error: {e}")
    except Exception as e:
        print(f"FAILED: General Error: {e}")

if __name__ == "__main__":
    test_connection()