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
RETRIEVER_AGENT_URL = os.getenv("RETRIEVER_AGENT_URL", "http://retriever-agent:8007")

DB_URL = os.getenv("AIML_RESULTS_DATABASE_URL")
HOST_EMAIL = os.getenv("HOST_EMAIL", "admin@nexus.ai")


class SyntheticAgent:
    def __init__(self):
        self.api_key = os.getenv("NVIDIA_API_KEY") or os.getenv("OPENAI_API_KEY") or ""

        # LLM inference (especially NVIDIA llama) can take 60-120s under load.
        kwargs = {"api_key": self.api_key, "timeout": 120.0}
        if self.api_key.startswith("nvapi-"):
            kwargs["base_url"] = "https://integrate.api.nvidia.com/v1"
            self.model = "meta/llama-3.1-8b-instruct"
        else:
            self.model = "gpt-3.5-turbo"

        self.client = AsyncOpenAI(**kwargs, max_retries=1)
        # Agent microservice calls — 90s allows for slow startup / cold pods.
        self.http = httpx.AsyncClient(timeout=90.0)
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

    async def _call_retriever(self, query: str, persona: str, sql: str = None, table_candidates: list = None, column_whitelist: list = None) -> dict:
        try:
            r = await self.http.post(f"{RETRIEVER_AGENT_URL}/retrieve", json={
                "query": query,
                "persona": persona,
                "sql": sql,
                "table_candidates": table_candidates or [],
                "column_whitelist": column_whitelist or [],
                "top_k_semantic": 5,
                "top_k_total": 10,
            })
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.warning("Retriever agent call failed: %s", e)
            return {"results": [], "error": str(e)}

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
        pipeline_steps = []  # Track which agents ran for frontend display

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
        pipeline_steps.append({"agent": "Intent Agent", "status": "done", "detail": f"{intent} ({confidence:.0%})"})
        pipeline_steps.append({"agent": "Table Agent", "status": "done" if tables else "skipped", "detail": f"{len(tables)} tables ranked"})

        # Fast-path: skip DB for conversational queries
        # Only treat as conversational if intent says so AND the query has no academic keywords
        academic_keywords = re.search(r'\b(result|cgpa|sgpa|usn|semester|marks|grade|percentage|score|performance|placed|placement|student|faculty|timetable|syllabus|subject)\b', text, re.IGNORECASE)
        is_conversational = (intent in ["CLARIFICATION_REQUIRED", "NEUTRAL"] or entropy < 0.3) and not academic_keywords

        context_str = ""
        sql_query = ""
        rows = []
        kept_cols = []
        is_aggregate_query = bool(re.search(r'\b(all|list|every|top|highest|lowest|average|avg|count|how many|students with|batch|year|admission)\b', text, re.IGNORECASE))

        if not is_conversational:
            # Filter tables to aiml_academic schema (table_id carries the aiml_ prefix)
            schema_tables = [t for t in tables if t.get("table_id", "").startswith("aiml_")]
            if not schema_tables:
                # Fallback: use all tables if none matched the prefix filter
                schema_tables = tables
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
                pipeline_steps.append({"agent": "Column Pruning", "status": "done", "detail": f"{len(kept_cols)} columns kept"})

                # 3. SQL Generation
                # For aggregate/batch queries, build SQL directly from inferred filters
                # instead of delegating to the LLM which doesn't know the schema.
                batch_year_match = re.search(r'\b(20\d{2})\b', text)
                sem_match_agg = re.search(r'\b(?:sem(?:ester)?\s*(\d)|(\d)\s*(?:st|nd|rd|th)?\s*sem(?:ester)?)\b', text, re.IGNORECASE)
                inferred_sem = int(sem_match_agg.group(1) or sem_match_agg.group(2)) if sem_match_agg else None
                inferred_year = int(batch_year_match.group(1)) if batch_year_match else None

                if is_aggregate_query and (inferred_year or inferred_sem):
                    filters = []
                    if inferred_year:
                        filters.append(f"s.admission_year = {inferred_year}")
                    if inferred_sem:
                        filters.append(f"rs.semester_no = {inferred_sem}")
                    where_clause = " AND ".join(filters)
                    wants_top = bool(re.search(r'\b(highest|top|best|topper|rank|max|maximum)\b', text, re.IGNORECASE))
                    order_limit = "ORDER BY r.sgpa DESC NULLS LAST" + (" LIMIT 10" if wants_top else "")
                    sql_query = (
                        f"SELECT s.student_usn, s.student_name, s.admission_year, "
                        f"rs.semester_no, r.sgpa, r.percentage "
                        f"FROM aiml_academic.students s "
                        f"JOIN aiml_academic.student_semester_results r ON s.student_usn = r.student_usn "
                        f"JOIN aiml_academic.result_sessions rs ON r.session_id = rs.session_id "
                        f"WHERE {where_clause} "
                        f"{order_limit}"
                    )
                    reasoning_parts.append(f"SQL built directly (batch y={inferred_year} s={inferred_sem})")
                    pipeline_steps.append({"agent": "SQL Generator", "status": "done", "detail": "direct batch SQL"})
                else:
                    db_tables = ["aiml_academic.students", "aiml_academic.student_semester_results", "aiml_academic.student_subject_results", "aiml_academic.semesters", "aiml_academic.subjects", "aiml_academic.session_subjects", "aiml_academic.result_sessions"]
                    sql_query = await self._call_sql_gen(
                        f"{text}\nContext hint: {context_str}",
                        intent=intent, tables=db_tables, columns=kept_cols,
                    )
                    if sql_query:
                        reasoning_parts.append("SQL generated")
                        pipeline_steps.append({"agent": "SQL Generator", "status": "done", "detail": "query generated"})
                    else:
                        pipeline_steps.append({"agent": "SQL Generator", "status": "failed", "detail": "no SQL produced"})
        else:
            reasoning_parts.append("Fast-path: conversational")
            pipeline_steps.append({"agent": "Column Pruning", "status": "skipped"})
            pipeline_steps.append({"agent": "SQL Generator", "status": "skipped"})

        # 4. Grounded RAG — identity lookup
        master_identity = None
        if not is_conversational and DB_URL:
            try:
                from sqlalchemy import create_engine, text as sqla_text
                engine = create_engine(DB_URL, connect_args={"connect_timeout": 5, "options": "-csearch_path=aiml_academic"})
                with engine.connect() as conn:
                    usn_match = re.search(r"\b1DS\d{2}[A-Z]{2}\d{3}\b", text, re.IGNORECASE)
                    # Extract proper name: strip common query words to isolate the student name
                    name_text = re.sub(r'\b(what|who|is|the|of|for|get|show|find|me|my|cgpa|sgpa|usn|result|results|marks|grade|gpa|semester|sem|student|name|tell|about|details|give|please|wise|all|list|how|much|many|can|you|has|have|their|percentage|total|score|performance|academic|record|records|average|avg|highest|lowest|maximum|minimum|max|min|count|top|bottom|rank|ranking|ranked|above|below|between|across|and|or|in|with|by|on|at|a|an)\b', '', text, flags=re.IGNORECASE).strip()
                    name_text = re.sub(r'\s+', ' ', name_text).strip()
                    if usn_match:
                        search_term = usn_match.group(0)
                        id_query = f"SELECT student_usn, student_name FROM aiml_academic.students WHERE student_usn ILIKE '%{search_term}%' LIMIT 1"
                    elif len(name_text) >= 3:
                        search_term = name_text
                        id_query = f"SELECT student_usn, student_name FROM aiml_academic.students WHERE student_name ILIKE '%{search_term}%' LIMIT 1"
                    else:
                        id_query = None
                    if id_query:
                        id_res = conn.execute(sqla_text(id_query)).fetchone()
                        if id_res:
                            master_identity = {"usn": id_res[0], "name": id_res[1]}
                            reasoning_parts.append(f"RAG: grounded to {id_res[1]}")
            except Exception:
                pass

        # If identity is confirmed but SQL generation failed/timed out, build SQL directly
        if not is_conversational and master_identity and not sql_query:
            usn = master_identity["usn"]
            sql_query = (
                f"SELECT s.student_usn, s.student_name, s.admission_year, "
                f"rs.semester_no, r.sgpa, r.percentage "
                f"FROM aiml_academic.students s "
                f"LEFT JOIN aiml_academic.student_semester_results r "
                f"ON s.student_usn = r.student_usn "
                f"LEFT JOIN aiml_academic.result_sessions rs "
                f"ON r.session_id = rs.session_id "
                f"WHERE s.student_usn = '{usn}' "
                f"ORDER BY rs.semester_no"
            )
            reasoning_parts.append("SQL grounded directly (identity fallback)")
            pipeline_steps.append({"agent": "SQL Generator", "status": "done", "detail": "identity-grounded (no LLM)"})

        # 4b. Retriever — enrich context with semantically retrieved chunks
        retriever_context = ""
        if not is_conversational:
            retriever_result = await self._call_retriever(
                query=text,
                persona=persona,
                sql=sql_query or None,
                table_candidates=[t.get("table_id") for t in schema_tables],
                column_whitelist=kept_cols,
            )
            retrieved = retriever_result.get("evidence", retriever_result.get("results", []))
            if retrieved:
                snippets = [r.get("text") or r.get("content") or str(r) for r in retrieved[:5]]
                retriever_context = "\nRetrieved Context:\n" + "\n".join(f"- {s}" for s in snippets)
                reasoning_parts.append(f"Retriever: {len(retrieved)} chunks")
                pipeline_steps.append({"agent": "Retriever Agent", "status": "done", "detail": f"{len(retrieved)} chunks"})
            else:
                pipeline_steps.append({"agent": "Retriever Agent", "status": "skipped", "detail": "no results"})
        else:
            pipeline_steps.append({"agent": "Retriever Agent", "status": "skipped"})

        # 5. SQL Validation & Execution
        if sql_query:
            # Re-anchor SQL with identity if found.
            # Build the query directly using the confirmed USN — do NOT delegate
            # this back to the LLM since small models ignore the USN and use the
            # name with a case-sensitive = which returns 0 rows.
            if master_identity:
                usn = master_identity["usn"]
                sql_query = (
                    f"SELECT s.student_usn, s.student_name, s.admission_year, "
                    f"rs.semester_no, r.sgpa, r.percentage "
                    f"FROM aiml_academic.students s "
                    f"LEFT JOIN aiml_academic.student_semester_results r "
                    f"ON s.student_usn = r.student_usn "
                    f"LEFT JOIN aiml_academic.result_sessions rs "
                    f"ON r.session_id = rs.session_id "
                    f"WHERE s.student_usn = '{usn}' "
                    f"ORDER BY rs.semester_no"
                )
                reasoning_parts.append("SQL grounded by USN")

            is_valid, val_results = await self._call_validate(sql_query)
            if not is_valid:
                # Self-healing: try to correct the SQL using validation feedback
                feedback_msg = "; ".join(
                    f"{c.get('check')}: {c.get('message')}" for c in val_results if not c.get("valid")
                ) if val_results else "Validation failed"
                reasoning_parts.append(f"SQL rejected ({feedback_msg[:60]}), attempting correction")
                corrected = await self._call_sql_correction(text, sql_query, feedback_msg)
                if corrected:
                    is_valid2, _ = await self._call_validate(corrected)
                    if is_valid2:
                        sql_query = corrected
                        reasoning_parts.append("SQL self-healed after validation")
                        pipeline_steps.append({"agent": "SQL Validator", "status": "done", "detail": "passed (after correction)"})
                    else:
                        reasoning_parts.append("SQL correction also rejected")
                        pipeline_steps.append({"agent": "SQL Validator", "status": "failed", "detail": "rejected"})
                        sql_query = ""
                else:
                    reasoning_parts.append("SQL correction failed")
                    pipeline_steps.append({"agent": "SQL Validator", "status": "failed", "detail": "rejected"})
                    sql_query = ""
            else:
                reasoning_parts.append("SQL validated")
                pipeline_steps.append({"agent": "SQL Validator", "status": "done", "detail": "passed"})

            if sql_query and DB_URL:
                try:
                    from sqlalchemy import create_engine, text as sqla_text
                    engine = create_engine(DB_URL, connect_args={"connect_timeout": 5, "options": "-csearch_path=aiml_academic"})
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

                        fetch_limit = 500 if is_aggregate_query else 50
                        rows = [dict(row._mapping) for row in result.fetchmany(fetch_limit)]
                        context_str += f"\nDatabase Results: {rows}"
                        reasoning_parts.append(f"Fetched {len(rows)} rows")
                except Exception as e:
                    reasoning_parts.append(f"DB execution failed: {str(e)[:40]}")

        # 6. Intelligence: CGPA calculation & ambiguity detection
        final_context = context_str
        try:
            from collections import Counter, defaultdict
            student_counts = Counter([r.get('student_usn') for r in rows if r.get('student_usn')])
            if is_aggregate_query and len(student_counts) > 1:
                # Batch/aggregate query: compute per-student CGPA then overall average
                student_sgpas = defaultdict(list)
                student_names = {}
                for r in rows:
                    usn = r.get('student_usn')
                    sgpa = r.get('sgpa')
                    if usn and sgpa is not None:
                        student_sgpas[usn].append(float(sgpa))
                        student_names[usn] = r.get('student_name') or r.get('student_name_snapshot') or usn
                if student_sgpas:
                    per_student_cgpa = {
                        usn: round(sum(sgpas) / len(sgpas), 2)
                        for usn, sgpas in student_sgpas.items()
                    }
                    all_cgpas = list(per_student_cgpa.values())
                    batch_avg = round(sum(all_cgpas) / len(all_cgpas), 2)
                    # Build compact summary for LLM (top 30 to keep prompt size manageable)
                    sorted_students = sorted(per_student_cgpa.items(), key=lambda x: x[1], reverse=True)
                    summary_rows = [
                        {"usn": usn, "name": student_names.get(usn, usn), "cgpa": cgpa}
                        for usn, cgpa in sorted_students[:60]
                    ]
                    final_context = (
                        f"Target Table: students + student_semester_results. "
                        f"BATCH_AVERAGE_CGPA: {batch_avg} across {len(per_student_cgpa)} students.\n"
                        f"PER_STUDENT_CGPA (sorted by CGPA desc):\n"
                        + "\n".join(f"  {r['name']} ({r['usn']}): {r['cgpa']}" for r in summary_rows)
                    )
                    reasoning_parts.append(f"Batch CGPA: avg={batch_avg}, n={len(per_student_cgpa)}")
            elif len(student_counts) == 1:
                # Single student: compute CGPA
                sgpas = [float(r.get('sgpa')) for r in rows if r.get('sgpa') is not None]
                if sgpas:
                    cgpa = round(sum(sgpas) / len(sgpas), 2)
                    final_context += f"\nCALCULATED_CGPA: {cgpa} (Avg of {len(sgpas)} semesters: {sgpas})"
            elif len(student_counts) > 1 and not is_aggregate_query:
                # Ambiguous single-student query returned multiple students
                ambiguity_list = list(set([
                    f"{r.get('student_usn')} ({r.get('student_name') or r.get('student_name_snapshot')})"
                    for r in rows
                ]))
                final_context += f"\nAMBIGUITY DETECTED: Multiple students found: {ambiguity_list}"
        except Exception:
            pass

        # 7. LLM Synthesis
        if is_conversational:
            prompt = f"""You are the AIML Nexus assistant — a friendly, intelligent academic chatbot for the AIML department at Dayananda Sagar College of Engineering.

User said: "{text}"

Respond naturally and warmly, like a helpful college assistant would. If they greet you, greet them back and briefly mention what you can help with (results, CGPA, semester performance, student lookups, etc.). Keep it short and friendly — 2-3 sentences max. Don't be robotic."""

        else:
            prompt = f"""You are the AIML Nexus academic assistant — a helpful, knowledgeable assistant for the AIML department. You have access to real student academic data.

User Query: "{text}"
Database Results:
{final_context if final_context.strip() else "(No matching records found in the database.)"}
{retriever_context}

RESPONSE STYLE:
- Be warm and helpful, like a knowledgeable academic advisor. Not robotic, not overly formal.
- Start with the direct answer, then add brief context if useful.
- For single-value questions (USN, CGPA, name): state the answer clearly in 1-2 sentences, then optionally add a small note.
- For multi-row data (semester-wise results): use a clean Markdown table, with a brief sentence before/after summarizing the trend.
- If 'CALCULATED_CGPA' is present, highlight it naturally: e.g. "Abdur Rahman's CGPA is **8.5**, averaged across 6 semesters."
- If 'BATCH_AVERAGE_CGPA' is present, lead with the batch average (e.g. "The average CGPA of batch 2020 is **7.52**"), then show a table of student name + CGPA sorted by CGPA descending. Keep the table concise.
- Keep it under 300 words for batch queries, 150 words for single-student queries.
- Never make up data. If no records match, say so helpfully and suggest what they could search instead.
- Do NOT repeat the same data in multiple formats."""

        try:
            completion = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": prompt}],
            )
            final_resp = completion.choices[0].message.content.strip()
        except Exception as e:
            logger.error("LLM synthesis failed: %s", e)
            # Fallback: format data directly without LLM when synthesis times out
            if master_identity and not rows:
                final_resp = f"**{master_identity['name']}** — USN: `{master_identity['usn']}`"
            elif master_identity and rows:
                sgpas = [float(r['sgpa']) for r in rows if r.get('sgpa') is not None]
                cgpa = round(sum(sgpas) / len(sgpas), 2) if sgpas else None
                sem_lines = "\n".join(
                    f"| {r.get('semester_no')} | {r.get('sgpa')} | {r.get('percentage')}% |"
                    for r in rows if r.get('semester_no')
                )
                cgpa_line = f"\n**CGPA: {cgpa}**" if cgpa else ""
                final_resp = (
                    f"**{master_identity['name']}** (USN: `{master_identity['usn']}`){cgpa_line}\n\n"
                    f"| Semester | SGPA | Percentage |\n|---|---|---|\n{sem_lines}"
                    if sem_lines else f"**{master_identity['name']}** — USN: `{master_identity['usn']}`"
                )
            else:
                final_resp = "I found some data but couldn't generate a summary. Please try again."

        # Anti-hallucination guard: if no DB rows returned, block invented data for ALL query types
        if not is_conversational and not rows:
            no_data_phrases = ["not found", "no record", "couldn't find", "could not find", "no data", "no results", "no matching", "unable to find"]
            lresp = final_resp.lower()
            already_honest = any(p in lresp for p in no_data_phrases)
            # Block if LLM invented numbers or student names when we have zero rows
            has_hallucinated = (
                bool(re.search(r'\b\d+\.\d+\b', final_resp)) or
                bool(re.search(r'\|\s*\w', final_resp))  # markdown table with data
            ) and not already_honest
            if has_hallucinated:
                search_name = re.sub(r'\b(what|who|is|the|of|for|get|show|find|me|cgpa|sgpa|usn|result|results|semester|wise|tell|about|performance|academic|average|avg|marks|batch|highest|top|best)\b', '', text, flags=re.IGNORECASE).strip()
                search_name = re.sub(r'\s+', ' ', search_name).strip() or "the requested query"
                final_resp = f"I couldn't find any matching records for **{search_name}** in our database. Please double-check the details and try again."
                logger.warning("Hallucination blocked for query: %s", text[:60])

        pipeline_steps.append({"agent": "Synthesis", "status": "done", "detail": "conversational" if is_conversational else f"{len(rows)} rows"})

        # 8. Audit
        audit_result = await self._call_audit(text, sql_query, final_resp)
        audit_passed = audit_result.get("passed", True)
        if not audit_passed:
            final_resp = "Response blocked by Audit for safety compliance."
            reasoning_parts.append("Audit: BLOCKED")
            pipeline_steps.append({"agent": "Audit Agent", "status": "blocked"})
        else:
            reasoning_parts.append("Audit: passed")
            pipeline_steps.append({"agent": "Audit Agent", "status": "done", "detail": "passed"})

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
            "Retriever_Agent": "Retriever" in reasoning,
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
            "pipeline": pipeline_steps,
        }
