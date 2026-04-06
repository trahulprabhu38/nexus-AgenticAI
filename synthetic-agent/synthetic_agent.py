"""
Synthesis / Orchestrator Agent
Coordinates all agent microservices via HTTP and synthesizes final responses.
"""
import os
import re
import asyncio
import httpx
from openai import AsyncOpenAI
from dotenv import load_dotenv

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

import logging
logger = logging.getLogger("nexus.orchestrator")

# ── Agent service URLs (resolved via Docker Compose service names) ─────
INTENT_AGENT_URL = os.getenv("INTENT_AGENT_URL", "http://intent-agent:8001")
TABLE_AGENT_URL = os.getenv("TABLE_AGENT_URL", "http://table-agent:8002")
COLUMN_PRUNING_URL = os.getenv("COLUMN_PRUNING_URL", "http://column-pruning:8003")
SQL_GENERATOR_URL = os.getenv("SQL_GENERATOR_URL", "http://sql-generator:8004")
SQL_VALIDATOR_URL = os.getenv("SQL_VALIDATOR_URL", "http://sql-validator:8005")
AUDIT_AGENT_URL = os.getenv("AUDIT_AGENT_URL", "http://audit-agent:8006")

DB_URL = os.getenv("AIML_RESULTS_DATABASE_URL")
HOST_EMAIL = os.getenv("HOST_EMAIL", "admin@nexus.ai")


class SyntheticAgent:
    def __init__(self):
        self.api_key = os.getenv("NVIDIA_API_KEY") or os.getenv("OPENAI_API_KEY") or ""

        kwargs = {"api_key": self.api_key, "timeout": 30.0}
        if self.api_key.startswith("nvapi-"):
            kwargs["base_url"] = "https://integrate.api.nvidia.com/v1"
            self.model = "meta/llama-3.1-8b-instruct"
        else:
            self.model = "gpt-3.5-turbo"

        self.client = AsyncOpenAI(**kwargs)
        self.http = httpx.AsyncClient(timeout=30.0)
        logger.info("SyntheticAgent initialized — HTTP orchestration mode")

    # ── HTTP helpers to call each agent service ────────────────────────

    async def _call_intent(self, text: str, persona: str) -> dict:
        try:
            r = await self.http.post(f"{INTENT_AGENT_URL}/classify", json={"query": text, "persona": persona})
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.warning("Intent agent call failed: %s", e)
            return {"intent": "default", "confidence": 0.5, "entropy_reduction": 0.0, "delta_h": 0.0, "reasoning": f"Intent agent unavailable: {e}"}

    async def _call_table(self, text: str) -> list:
        try:
            r = await self.http.post(f"{TABLE_AGENT_URL}/rank", json={"query": text, "top_k": 3})
            r.raise_for_status()
            return r.json().get("tables", [])
        except Exception as e:
            logger.warning("Table agent call failed: %s", e)
            return []

    async def _call_column_pruning(self, text: str, table_id: str, columns: list) -> dict:
        try:
            r = await self.http.post(f"{COLUMN_PRUNING_URL}/prune", json={
                "query": text, "table_id": table_id, "columns": columns,
            })
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.warning("Column pruning call failed: %s", e)
            return {"kept": columns, "dropped": [], "mode": "passthrough"}

    async def _call_sql_gen(self, text: str, intent: str = "", tables: list = None, columns: list = None) -> str:
        try:
            r = await self.http.post(f"{SQL_GENERATOR_URL}/generate-sql", json={
                "query": text, "intent": intent,
                "tables": tables or [], "pruned_columns": columns or [],
            })
            r.raise_for_status()
            data = r.json()
            return data.get("sql", "") if data.get("status") == "success" else ""
        except Exception as e:
            logger.warning("SQL generator call failed: %s", e)
            return ""

    async def _call_sql_correction(self, text: str, failed_sql: str, error: str) -> str:
        try:
            r = await self.http.post(f"{SQL_GENERATOR_URL}/correct-sql", json={
                "query": text, "failed_sql": failed_sql, "error_message": error,
            })
            r.raise_for_status()
            data = r.json()
            return data.get("sql", "") if data.get("status") == "success" else ""
        except Exception as e:
            logger.warning("SQL correction call failed: %s", e)
            return ""

    async def _call_validate(self, sql: str) -> tuple[bool, list]:
        try:
            r = await self.http.post(f"{SQL_VALIDATOR_URL}/validate", json={"query": sql})
            r.raise_for_status()
            data = r.json()
            return data.get("valid", False), data.get("results", [])
        except Exception as e:
            logger.warning("SQL validator call failed: %s", e)
            return True, []  # fail-open if validator is down

    async def _call_audit(self, query: str, sql: str, response: str) -> dict:
        try:
            r = await self.http.post(f"{AUDIT_AGENT_URL}/audit", json={
                "query": query, "sql": sql, "response": response,
            })
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.warning("Audit agent call failed: %s", e)
            return {"passed": True, "reasoning": f"Audit unavailable: {e}"}

    async def _record_metrics(self, session_id, duration, outcomes, audit_passed):
        try:
            await self.http.post(f"{AUDIT_AGENT_URL}/record", json={
                "session_id": session_id, "duration": duration,
                "agent_outcomes": outcomes, "audit_passed": audit_passed,
            })
        except Exception:
            pass

    # ── Main orchestration pipeline ────────────────────────────────────

    async def orchestrate(self, text: str, persona: str, history: list) -> dict:
        start_time = asyncio.get_event_loop().time()
        reasoning_parts = []

        # 1. PARALLEL: Intent classification + Table ranking
        logger.info("Pipeline start: query=%s, persona=%s", text[:80], persona)
        intent_result, tables = await asyncio.gather(
            self._call_intent(text, persona),
            self._call_table(text),
        )

        intent = intent_result.get("intent", "default")
        confidence = intent_result.get("confidence", 0.5)
        entropy = intent_result.get("entropy_reduction", 0.0)
        reasoning_parts.append(f"Intent: {intent} ({confidence:.2f})")

        # Fast-path: skip DB for conversational queries
        is_conversational = intent in ["CLARIFICATION_REQUIRED", "NEUTRAL"] or entropy < 0.3

        context_str = ""
        sql_query = ""
        rows = []

        if not is_conversational:
            # Filter tables to aiml_academic schema
            schema_tables = [t for t in tables if t.get("table", "").startswith("aiml_")]
            reasoning_parts.append(f"Tables: {len(schema_tables)} matched")

            # 2. Column Pruning
            if schema_tables:
                top_table = schema_tables[0]
                prune_result = await self._call_column_pruning(
                    text, top_table["table_id"], []
                )
                kept_cols = prune_result.get("kept", [])
                table_name = top_table["table"]
                context_str = f"Target Table: {table_name}. Relevant Columns: {', '.join(kept_cols)}."
                reasoning_parts.append(f"Pruned to {len(kept_cols)} cols")

                # 3. SQL Generation
                table_names = [t["table"] for t in schema_tables[:3]]
                sql_query = await self._call_sql_gen(
                    f"{text}\nContext hint: {context_str}",
                    intent=intent, tables=table_names, columns=kept_cols,
                )
                if sql_query:
                    reasoning_parts.append("SQL generated")
        else:
            reasoning_parts.append("Fast-path: conversational")

        # 4. Grounded RAG — identity lookup
        master_identity = None
        if not is_conversational and DB_URL:
            try:
                from sqlalchemy import create_engine, text as sqla_text
                engine = create_engine(DB_URL)
                with engine.connect() as conn:
                    match = re.search(r"\b1DS\d{2}[A-Z]{2}\d{3}\b", text, re.IGNORECASE)
                    search_term = match.group(0) if match else text.strip()
                    id_query = f"SELECT student_usn, student_name FROM aiml_academic.students WHERE student_usn ILIKE '%{search_term}%' OR student_name ILIKE '%{search_term}%' LIMIT 1"
                    id_res = conn.execute(sqla_text(id_query)).fetchone()
                    if id_res:
                        master_identity = {"usn": id_res[0], "name": id_res[1]}
                        reasoning_parts.append(f"RAG: grounded to {id_res[1]}")
            except Exception:
                pass

        # 5. SQL Validation & Execution
        if sql_query:
            # Re-anchor SQL with identity if found
            if master_identity:
                sql_query = await self._call_sql_gen(
                    f"{text}\nGROUND TRUTH: {master_identity['name']} (USN: {master_identity['usn']}). Context: {context_str}",
                    intent=intent,
                )
                reasoning_parts.append("SQL re-anchored")

            is_valid, _ = await self._call_validate(sql_query)
            if not is_valid:
                reasoning_parts.append("SQL rejected by validator")
                sql_query = ""
            else:
                reasoning_parts.append("SQL validated")

            if sql_query and DB_URL:
                try:
                    from sqlalchemy import create_engine, text as sqla_text
                    engine = create_engine(DB_URL)
                    with engine.connect() as conn:
                        try:
                            result = conn.execute(sqla_text(sql_query))
                        except Exception as first_err:
                            reasoning_parts.append(f"SQL error, self-healing")
                            corrected = await self._call_sql_correction(text, sql_query, str(first_err))
                            if corrected:
                                sql_query = corrected
                                result = conn.execute(sqla_text(sql_query))
                                reasoning_parts.append("SQL self-healed")
                            else:
                                raise first_err

                        rows = [dict(row._mapping) for row in result.fetchmany(20)]
                        context_str += f"\nDatabase Results: {rows}"
                        reasoning_parts.append(f"Fetched {len(rows)} rows")
                except Exception as e:
                    reasoning_parts.append(f"DB execution failed: {str(e)[:40]}")

        # 6. Intelligence: CGPA calculation & ambiguity detection
        final_context = context_str
        try:
            from collections import Counter
            student_counts = Counter([r.get('student_usn') for r in rows if r.get('student_usn')])
            if len(student_counts) > 1:
                ambiguity_list = list(set([
                    f"{r.get('student_usn')} ({r.get('student_name') or r.get('student_name_snapshot')})"
                    for r in rows
                ]))
                final_context += f"\nAMBIGUITY DETECTED: Multiple students found: {ambiguity_list}"
            else:
                sgpas = [float(r.get('sgpa')) for r in rows if r.get('sgpa') is not None]
                if sgpas:
                    cgpa = round(sum(sgpas) / len(sgpas), 2)
                    final_context += f"\nCALCULATED_CGPA: {cgpa} (Avg of {len(sgpas)} semesters: {sgpas})"
        except Exception:
            pass

        # 7. LLM Synthesis
        if len(rows) > 1:
            template = "TREND_ANALYST_PRO"
            instruction = "You are a Trend Analyst. Create a professional trajectory report with growth insights and tables."
        elif len(rows) == 1:
            template = "PERFORMANCE_SNAPSHOT"
            instruction = "You are a Performance Analyst. Create a crisp, high-impact snapshot card."
        else:
            template = "CONVERSATIONAL"
            instruction = "Be friendly and conversational. If data was requested, state 'Record Not Found'."

        prompt = f"""You are the AIML Nexus Senior Academic Analyst (v7 {template}).
{instruction}

User Query: "{text}"
Database Result Summary:
{final_context if final_context.strip() else "(No records found.)"}

REPORTING GUIDELINES:
1. MATH VERIFICATION: If 'CALCULATED_CGPA' is present, use it as ground truth.
2. PROFESSIONALISM: Use clear Markdown formatting.
3. NO HALLUCINATION: Never make up data.
"""

        try:
            completion = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": prompt}],
            )
            final_resp = completion.choices[0].message.content.strip()
        except Exception as e:
            final_resp = f"Failed to generate response: {e}"
            logger.error("LLM synthesis failed: %s", e)

        # 8. Audit
        audit_result = await self._call_audit(text, sql_query, final_resp)
        audit_passed = audit_result.get("passed", True)
        if not audit_passed:
            final_resp = "Response blocked by Audit for safety compliance."
            reasoning_parts.append("Audit: BLOCKED")
        else:
            reasoning_parts.append("Audit: passed")

        duration = round(asyncio.get_event_loop().time() - start_time, 2)
        reasoning = " | ".join(reasoning_parts)

        # 9. Record metrics
        outcomes = {
            "Intent_Agent": intent != "default",
            "Table_Agent": bool(tables),
            "Column_Pruning_Agent": "Pruned" in reasoning,
            "SQL_Generator": bool(sql_query),
            "SQL_Validator": "validated" in reasoning,
            "Audit_Agent": audit_passed,
        }
        await self._record_metrics(None, duration, outcomes, audit_passed)

        logger.info("Pipeline complete: duration=%.2fs, intent=%s, rows=%d", duration, intent, len(rows))

        return {
            "response": final_resp,
            "sender": "synthetic_agent",
            "intent": intent,
            "confidence": confidence,
            "entropy_reduction": entropy,
            "reasoning": reasoning,
            "duration": duration,
        }
