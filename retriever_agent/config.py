import os
BASE_DIR = os.path.dirname(__file__)
SAMPLE_DATA_DIR = os.path.join(BASE_DIR, "sample_data")
FAISS_INDEX_PATH = os.path.join(SAMPLE_DATA_DIR, "faiss.index")
META_PATH = os.path.join(SAMPLE_DATA_DIR, "meta.pkl")
SAMPLE_DB_PATH = os.path.join(SAMPLE_DATA_DIR, "sample.db")

# Embedding model
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBED_DIM = 384  # for model above
