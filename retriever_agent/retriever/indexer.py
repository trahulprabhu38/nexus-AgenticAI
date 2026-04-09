# retriever/indexer.py
import faiss, pickle
from config import FAISS_INDEX_PATH, META_PATH
import os

def load_index(index_path=FAISS_INDEX_PATH, meta_path=META_PATH):
    if not os.path.exists(index_path) or not os.path.exists(meta_path):
        raise FileNotFoundError("FAISS index or meta not found. Run build_sample_data.py first.")
    index = faiss.read_index(index_path)
    with open(meta_path, "rb") as f:
        meta = pickle.load(f)
    return index, meta
