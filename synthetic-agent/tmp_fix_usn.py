import psycopg2
try:
    conn = psycopg2.connect("postgresql://admin01:aiml1203@185.197.251.236:5432/nexus")
    cur = conn.cursor()
    # Fix the typo in the master students table for Manasa M
    cur.execute("UPDATE aiml_academic.students SET student_usn = '1DS23AI036' WHERE student_usn = '1DS23AI06'")
    conn.commit()
    print("✅ Successfully patched USN typo: 1DS23AI06 -> 1DS23AI036")
    cur.close()
    conn.close()
except Exception as e:
    print(f"❌ DB Patch Failed: {e}")
