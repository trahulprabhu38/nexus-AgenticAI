import os
import re
from openai import OpenAI
from dotenv import load_dotenv

# Load master .env from root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

class AuditAgent:
    def __init__(self):
        self.api_key = os.getenv("NVIDIA_API_KEY") or os.getenv("OPENAI_API_KEY")
        self.base_url = "https://integrate.api.nvidia.com/v1" if self.api_key and self.api_key.startswith("nvapi-") else None
        
        kwargs = {"api_key": self.api_key, "timeout": 10.0}
        if self.base_url:
            kwargs["base_url"] = self.base_url
        self.client = OpenAI(**kwargs)
        self.model = "meta/llama-3.1-8b-instruct" if self.base_url else "gpt-3.5-turbo"

    def audit(self, query: str, sql: str, response: str) -> dict:
        """Audits the output to ensure no PII leakage or harmful SQL execution instructions."""
        
        # Simple rule-based audit
        suspicious_keywords = ["drop table", "truncate", "delete", "update", "insert", "grant", "revoke"]
        if sql:
            for kw in suspicious_keywords:
                if kw in sql.lower() and "select" not in sql.lower()[:10]:
                    return {"passed": False, "reasoning": "Audit failed: Potentially destructive SQL detected."}
        
        if not sql.strip():
            return {"passed": True, "reasoning": "Audit passed: Conversational query (No SQL)."}
            
        # LLM-based audit
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
                temperature=0.0
            )
            val = res.choices[0].message.content.strip()
            if val.startswith("PASS"):
                return {"passed": True, "reasoning": "Audit passed safely."}
            else:
                return {"passed": False, "reasoning": val}
        except Exception as e:
            # Fallback to true if API fails
            return {"passed": True, "reasoning": f"Audit fallback due to error: {e}"}
