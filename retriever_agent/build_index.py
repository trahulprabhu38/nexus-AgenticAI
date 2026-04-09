"""
Builds FAISS index from PostgreSQL academic data at container startup.
Runs once; skips if index already exists.
"""
import os
import pickle
import faiss
import numpy as np
from sqlalchemy import create_engine, text
from sentence_transformers import SentenceTransformer
from config import FAISS_INDEX_PATH, META_PATH, SAMPLE_DATA_DIR, EMBED_MODEL, EMBED_DIM

DB_URL = os.getenv("AIML_RESULTS_DATABASE_URL", "")


def build():
    if os.path.exists(FAISS_INDEX_PATH) and os.path.exists(META_PATH):
        print("[build_index] Index already exists, skipping build.")
        return

    if not DB_URL:
        print("[build_index] No AIML_RESULTS_DATABASE_URL set, skipping build.")
        return

    print("[build_index] Building FAISS index from PostgreSQL...")
    try:
        engine = create_engine(DB_URL)
        with engine.connect() as conn:
            rows = conn.execute(text("""
                SELECT s.student_usn, s.student_name, r.sgpa, r.percentage,
                       rs.session_label
                FROM aiml_academic.students s
                JOIN aiml_academic.student_semester_results r ON s.student_usn = r.student_usn
                JOIN aiml_academic.result_sessions rs ON r.session_id = rs.session_id
                ORDER BY s.student_usn, rs.session_label
            """)).fetchall()
    except Exception as e:
        print(f"[build_index] DB query failed: {e}. Skipping index build.")
        return

    if not rows:
        print("[build_index] No rows found in DB, skipping index build.")
        return

    texts = []
    metas = []
    for row in rows:
        usn, name, sgpa, pct, sem = row
        text_chunk = f"{name} ({usn}) scored SGPA {sgpa} ({pct}%) in {sem}."
        texts.append(text_chunk)
        metas.append({
            "student_usn": usn,
            "student_name": name,
            "sgpa": float(sgpa) if sgpa else None,
            "percentage": float(pct) if pct else None,
            "semester": sem,
            "text_preview": text_chunk,
        })

    print(f"[build_index] Embedding {len(texts)} records...")
    model = SentenceTransformer(EMBED_MODEL)
    vecs = model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
    faiss.normalize_L2(vecs)

    index = faiss.IndexFlatIP(EMBED_DIM)
    index.add(vecs.astype(np.float32))

    os.makedirs(SAMPLE_DATA_DIR, exist_ok=True)
    faiss.write_index(index, FAISS_INDEX_PATH)
    with open(META_PATH, "wb") as f:
        pickle.dump(metas, f)

    print(f"[build_index] Done. Indexed {index.ntotal} records.")


if __name__ == "__main__":
    build()
