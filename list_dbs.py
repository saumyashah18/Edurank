import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

url = os.getenv("DATABASE_URL")
if not url:
    print("No DATABASE_URL found")
    exit(1)

try:
    conn = psycopg2.connect(url)
    cursor = conn.cursor()
    cursor.execute("SELECT datname FROM pg_database WHERE datistemplate = false;")
    dbs = cursor.fetchall()
    print("Databases found:")
    for db in dbs:
        print(f"- {db[0]}")
    conn.close()
except Exception as e:
    print(f"Error connecting: {e}")
