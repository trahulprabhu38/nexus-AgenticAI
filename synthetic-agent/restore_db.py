import psycopg2
import os

DB_URL = "postgresql://admin01:aiml1203@185.197.251.236:5432/nexus"
SQL_FILE = r"e:\7th sem\LLM\new\nexus-AgenticAI\db\results_aiml_normalized_postgres.sql"

def restore():
    print(f"Reading master SQL file: {SQL_FILE}")
    with open(SQL_FILE, 'r', encoding='utf-8') as f:
        sql_content = f.read()
    
    print("Connecting to database...")
    conn = psycopg2.connect(DB_URL)
    conn.autocommit = True
    cur = conn.cursor()
    
    print("Executing restoration script. This may take 30-60 seconds...")
    try:
        # The SQL file has BEGIN/COMMIT, but for some drivers it's better to execute raw
        cur.execute(sql_content)
        print("Restoration successful! Database synchronized with master.")
    except Exception as e:
        print(f"Restoration failed: {e}")
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    restore()
