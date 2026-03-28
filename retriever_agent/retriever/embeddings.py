# retriever/embeddings.py
from sentence_transformers import SentenceTransformer
import numpy as np
import faiss
from config import EMBED_MODEL, EMBED_DIM

class Embedder:
    def __init__(self, model_name=EMBED_MODEL):
        self.model = SentenceTransformer(model_name)
        self.dim = EMBED_DIM

    def embed(self, texts):
        # texts: list[str]
        vecs = self.model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
        # normalize L2 for cosine search with IndexFlatIP
        faiss.normalize_L2(vecs)
        return vecs
