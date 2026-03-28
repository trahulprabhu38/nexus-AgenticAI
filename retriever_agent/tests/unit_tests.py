# tests/unit_tests.py
import pytest
from retriever.embeddings import Embedder
from retriever.indexer import load_index
from retriever.semantic import semantic_search

def test_embedder_shape():
    e = Embedder()
    vecs = e.embed(["hello world", "this is a test"])
    assert vecs.shape[0] == 2
    assert vecs.shape[1] == e.dim

def test_index_load():
    idx, meta = load_index()
    assert hasattr(idx, "ntotal")
    assert isinstance(meta, list)

def test_semantic_simple():
    res = semantic_search("algorithms syllabus", top_k=3)
    assert isinstance(res, list)
    # Expect at least one result
    assert len(res) >= 1
