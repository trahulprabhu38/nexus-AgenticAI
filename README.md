# AIML Nexus - Synthetic Agent Orchestrator

AIML Nexus is a state-of-the-art multi-agent academic platform that natively queries, audits, and presents database metrics using a sleek glassmorphic frontend UI and an incredibly fast backend Orchestrator. 

## 🚀 Quick Start Guide (Nexus v6 Pro)

### 1. Environment Setup (Critical)
The platform is now **strictly environment-driven** for production security. 

1. At the project root, rename `.env.example` to **`.env`**.
2. Fill in your master keys:
   - `NVIDIA_API_KEY`: Your LLaMA-3.1 inference key.
   - `AIML_RESULTS_DATABASE_URL`: Your Postgres connection string.
   - `HOST_EMAIL`: gurunathagoudambiradar@gmail.com

### 2. Start the Backend (Terminal 1)
1. Open PowerShell in `synthetic-agent`.
2. Activate your virtual environment and run the server.

```powershell
cd E:\7th sem\LLM\new\nexus-AgenticAI\synthetic-agent
.\venv\Scripts\Activate.ps1
uvicorn main:app --reload --port 8000
```

### 3. Start the Frontend (Terminal 2)
1. Open a **new** PowerShell tab in `frontend`.
2. Start the React node server.

```powershell
cd E:\7th sem\LLM\new\nexus-AgenticAI\frontend
npm start
```

---

## 🛡️ Production Security Highlights
- **Zero-Code Secrets**: All API keys and database URLs have been wiped from the source code. The platform now pulls 100% of its configuration from the root-level `.env`.
- **Grounded RAG (v5)**: Uses a "First-Look" identity layer to prevent hallucinations by anchoring all results to a verified student in the master database.
- **Glassmorphic Markdown UI**: Auto-generates fully responsive tabular interfaces for academic progression.
- **Master Restoration**: Synced with 13,000+ normalized PostgreSQL records for perfect data integrity.
