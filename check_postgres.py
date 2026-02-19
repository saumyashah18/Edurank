import os
import psycopg2
from dotenv import load_dotenv
import time

load_dotenv()

DB_URL = os.getenv("DATABASE_URL")
print(f"Checking connection to: {DB_URL}")

try:
    conn = psycopg2.connect(DB_URL)
    print("SUCCESS: Connected to PostgreSQL!")
    cur = conn.cursor()
    cur.execute("SELECT version();")
    db_version = cur.fetchone()
    print(f"Database Version: {db_version}")
    cur.close()
    conn.close()
except Exception as e:
    print(f"CONNECTION FAILED: {e}")

