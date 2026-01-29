import sqlite3
import os

db_path = "edurank.db"
if not os.path.exists(db_path):
    print(f"Error: {db_path} not found")
else:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print("Tables:", tables)
        
        cursor.execute("SELECT id, title FROM courses;")
        courses = cursor.fetchall()
        print("Courses:", courses)
    except Exception as e:
        print("Error:", e)
    finally:
        conn.close()
