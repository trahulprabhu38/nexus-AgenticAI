import json
import os
from datetime import datetime

DATA_FILE = os.path.join(os.path.dirname(__file__), "audit_store.json")


def _load_store():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "total_requests": 0,
        "completed_requests": 0,
        "audit_passes": 0,
        "latency_samples": [],
        "agent_success": {
            "Intent_Agent": 0,
            "Table_Agent": 0,
            "Column_Pruning_Agent": 0,
            "SQL_Generator": 0,
            "SQL_Validator": 0,
            "Audit_Agent": 0,
        },
        "agent_attempts": {
            "Intent_Agent": 0,
            "Table_Agent": 0,
            "Column_Pruning_Agent": 0,
            "SQL_Generator": 0,
            "SQL_Validator": 0,
            "Audit_Agent": 0,
        },
        "events": [],
        "feedbacks": [],
    }


def _save_store(data):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


class AuditAgent:
    def __init__(self):
        self.api_key = os.getenv("NVIDIA_API_KEY") or os.getenv("OPENAI_API_KEY")
        self.base_url = "https://integrate.api.nvidia.com/v1" if self.api_key and self.api_key.startswith("nvapi-") else None

        kwargs = {"api_key": self.api_key, "timeout": 10.0}
        if self.base_url:
            kwargs["base_url"] = self.base_url

        try:
            from openai import OpenAI
            self.client = OpenAI(**kwargs)
        except Exception:
            self.client = None

        self.model = "meta/llama-3.1-8b-instruct" if self.base_url else "gpt-3.5-turbo"
        self.store = _load_store()

    def _persist(self):
        _save_store(self.store)

    def audit(self, query: str, sql: str, response: str) -> dict:
        suspicious_keywords = ["drop table", "truncate", "delete", "update", "insert", "grant", "revoke"]
        if sql:
            for kw in suspicious_keywords:
                if kw in sql.lower() and "select" not in sql.lower()[:10]:
                    return {"passed": False, "reasoning": "Audit failed: Potentially destructive SQL detected."}

        if not sql.strip():
            return {"passed": True, "reasoning": "Audit passed: conversational query or no SQL generated."}

        if not self.client:
            return {"passed": True, "reasoning": "Audit fallback: no OpenAI client available."}

        prompt = f"""You are the Audit and Feedback Agent.
Review the following user query, corresponding SQL (if any), and the drafted response.
Ensure the response uses proper tone and does not expose sensitive database connection details.

Query: {query}
SQL: {sql}
Draft Response: {response}

Reply with 'PASS' if safe, or 'FAIL: [reason]' if unsafe."""

        try:
            res = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=100,
                temperature=0.0,
            )
            val = res.choices[0].message.content.strip()
            if val.upper().startswith("PASS"):
                return {"passed": True, "reasoning": "Audit passed safely."}
            return {"passed": False, "reasoning": val}
        except Exception as e:
            return {"passed": True, "reasoning": f"Audit fallback due to error: {e}"}

    def record_request(self, session_id: str, duration: float, agent_outcomes: dict, audit_passed: bool):
        self.store["total_requests"] += 1
        if audit_passed:
            self.store["audit_passes"] += 1
        self.store["latency_samples"].append(round(duration, 2))

        for agent_name, attempted in agent_outcomes.items():
            if agent_name not in self.store["agent_attempts"]:
                self.store["agent_attempts"][agent_name] = 0
                self.store["agent_success"][agent_name] = 0
            self.store["agent_attempts"][agent_name] += 1
            if attempted:
                self.store["agent_success"][agent_name] += 1

        event = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "session_id": session_id,
            "duration": round(duration, 2),
            "agents": agent_outcomes,
            "audit_passed": audit_passed,
        }
        self.store["events"].insert(0, event)
        self.store["events"] = self.store["events"][0:200]
        self._persist()

    def submit_feedback(self, session_id: str, feedback_text: str, email: str = "guest@nexus.ai") -> dict:
        entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "session_id": session_id,
            "email": email,
            "feedback": feedback_text,
        }
        self.store["feedbacks"].insert(0, entry)
        self.store["feedbacks"] = self.store["feedbacks"][0:200]
        self._persist()
        return entry

    def get_metrics(self) -> dict:
        total = self.store.get("total_requests", 0)
        avg_latency = round(sum(self.store["latency_samples"]) / len(self.store["latency_samples"]), 2) if self.store["latency_samples"] else 0.0
        audit_rate = round((self.store.get("audit_passes", 0) / total) * 100, 2) if total else 0.0

        agent_success_rate = {}
        for agent, attempts in self.store["agent_attempts"].items():
            agent_success_rate[agent] = round((self.store["agent_success"].get(agent, 0) / attempts) * 100, 2) if attempts else 0.0

        return {
            "total_requests": total,
            "average_latency": avg_latency,
            "audit_pass_rate": audit_rate,
            "agent_success_rate": agent_success_rate,
            "recent_events": self.store["events"][0:20],
            "feedbacks": self.store["feedbacks"][0:20],
        }
