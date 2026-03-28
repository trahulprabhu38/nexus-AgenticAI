# build_sample_data.py
import os, pickle, sqlite3, datetime
from config import SAMPLE_DATA_DIR, FAISS_INDEX_PATH, META_PATH, SAMPLE_DB_PATH, EMBED_MODEL, EMBED_DIM
from sentence_transformers import SentenceTransformer
import numpy as np
import faiss

os.makedirs(SAMPLE_DATA_DIR, exist_ok=True)

# 1) sample documents (3 docs: syllabus, timetable, rules)
SAMPLE_DOCS = [
    {
        "id": "syllabus_cs_s7",
        "semester": "S7",
        "subject": "Algorithms",
        "source": "syllabus_cs_s7.txt",
        "text": """Algorithms S7 syllabus:
Week1: Graph algorithms, BFS/DFS. Week2: Shortest paths Dijkstra, Bellman-Ford. Week3: Minimum Spanning Trees Kruskal, Prim.
Week4: Dynamic Programming fundamentals. Week5: Greedy algorithms and practice problems.
Assessment: Assignments + End semester exam."""
    },
    {
        "id": "timetable_cs_s7",
        "semester": "S7",
        "subject": "Timetable",
        "source": "timetable_cs_s7.txt",
        "text": """Timetable S7: Monday - Algorithms 9:00-10:30, Data Mining 11:00-12:30.
Tuesday - Systems Programming 9:00-10:30, AI Lab 14:00-17:00.
Semester start: 01-Aug-2025. End semester: 31-Dec-2025."""
    },
    {
        "id": "rules_academic",
        "semester": "All",
        "subject": "Rules",
        "source": "rules_academic.txt",
        "text": """Academic Rules: Attendance minimum 75%. Exams: Re-evaluation allowed within 7 days of result publication.
Grade policy: Pass>=40%. Re-assessment: Fill reval form and pay the fee. Plagiarism rules: Zero tolerance."""
    }
]

# chunking
def chunk_text(text, chunk_size_words=120, overlap=20):
    tokens = text.split()
    chunks=[]
    i=0
    while i < len(tokens):
        chunk = " ".join(tokens[i:i+chunk_size_words])
        chunks.append(chunk)
        i += chunk_size_words - overlap
    return chunks

# embed
print("Loading embedder model...")
model = SentenceTransformer(EMBED_MODEL)

all_chunks = []
meta = []
for d in SAMPLE_DOCS:
    chs = chunk_text(d["text"])
    for idx, c in enumerate(chs):
        meta.append({
            "doc_id": d["id"],
            "chunk_id": idx,
            "semester": d.get("semester"),
            "subject": d.get("subject"),
            "source": d.get("source"),
            "created_at": datetime.datetime.utcnow().isoformat(),
            "text_preview": c[:200]
        })
        all_chunks.append(c)

print(f"Embedding {len(all_chunks)} chunks...")
embs = model.encode(all_chunks, convert_to_numpy=True, show_progress_bar=True)
# normalize
faiss.normalize_L2(embs)

# build FAISS index (IndexFlatIP)
index = faiss.IndexFlatIP(EMBED_DIM)
index.add(embs)
faiss.write_index(index, FAISS_INDEX_PATH)
with open(META_PATH, "wb") as f:
    pickle.dump(meta, f)

print(f"FAISS index saved to {FAISS_INDEX_PATH}, meta saved to {META_PATH}")

# create sample SQLite DB with simple student_result and placement tables
conn = sqlite3.connect(SAMPLE_DB_PATH)
c = conn.cursor()
c.execute("""
CREATE TABLE IF NOT EXISTS student_result (
    student_id INTEGER,
    course_id TEXT,
    semester INTEGER,
    marks INTEGER,
    grade TEXT,
    reval_status TEXT
)
""")
c.execute("DELETE FROM student_result")
sample_rows = [
    (101, "CS701", 7, 78, "B", "None"),
    (102, "CS701", 7, 55, "C", "Pending"),
    (103, "CS702", 7, 88, "A", "None"),
]
c.executemany("INSERT INTO student_result VALUES (?,?,?,?,?,?)", sample_rows)

c.execute("""
CREATE TABLE IF NOT EXISTS placement_stats (
    year INTEGER,
    branch TEXT,
    total_placed INTEGER,
    highest_package REAL
)
""")
c.execute("DELETE FROM placement_stats")
c.executemany("INSERT INTO placement_stats VALUES (?,?,?,?)", [
    (2023, "CSE", 120, 24.5),
    (2024, "CSE", 140, 27.0),
])

conn.commit()
conn.close()
print(f"Sample DB created at {SAMPLE_DB_PATH}")
