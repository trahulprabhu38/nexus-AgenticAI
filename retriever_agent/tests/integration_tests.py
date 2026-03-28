# tests/integration_tests.py
import requests
import time

BASE = "http://127.0.0.1:8000"

def test_retrieve_api_running():
    resp = requests.get(f"{BASE}/health", timeout=3)
    assert resp.status_code == 200
    assert "status" in resp.json()

def test_retrieve_query():
    payload = {"query":"Syllabus of Algorithms S7", "top_k_total":5}
    resp = requests.post(f"{BASE}/retrieve", json=payload, timeout=5)
    assert resp.status_code == 200
    data = resp.json()
    assert "evidence" in data
