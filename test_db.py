import psycopg2
try:
    conn = psycopg2.connect("postgresql://localhost:5433/edurank_dev")
    print("Connection successful with default user!")
    conn.close()
except Exception as e:
    print(f"Error: {e}")
