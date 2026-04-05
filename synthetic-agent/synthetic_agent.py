import os
import sys
import asyncio
from openai import AsyncOpenAI
from dotenv import load_dotenv

# Load master .env from root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

# Add parent path to allow cross-folder imports of sibling agents
sys.path.append(PROJECT_ROOT)

# Add parent path to allow cross-folder imports of sibling agents
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from Intent_Agent3.intent_agent import HierarchicalIntentAgent
except ImportError:
    HierarchicalIntentAgent = None

try:
    from Audit_agent.audit_agent import AuditAgent
except ImportError:
    AuditAgent = None

# Connect sibling agents
try:
    from table_agent.agent import TableAgent
except ImportError:
    TableAgent = None

try:
    from column_pruning_agent.agent import ColumnPruningAgent
except ImportError:
    ColumnPruningAgent = None

try:
    from SQL_QUERY_GENERATOR.sql_agent import generate_sql_with_agent, generate_sql_with_correction
except ImportError:
    generate_sql_with_agent = None
    generate_sql_with_correction = None

try:
    from sql_validator_agent.validator import SQLValidator
except ImportError:
    SQLValidator = None

try:
    from table_agent.ranker import _database_url
except ImportError:
    _database_url = lambda: os.getenv("AIML_RESULTS_DATABASE_URL")

# Global DB URL - Strictly from Environment in Production
DB_URL = os.getenv("AIML_RESULTS_DATABASE_URL")
HOST_EMAIL = os.getenv("HOST_EMAIL", "gurunathagoudambiradar@gmail.com")

class Message:
    def __init__(self, text, metadata=None, sender="user"):
        self.text = text
        self.metadata = metadata or {}
        self.sender = sender

class SyntheticAgent:
    def __init__(self):
        # Smartly detect API key type to prevent 401 Unauthorized errors
        self.api_key = os.getenv("NVIDIA_API_KEY") or os.getenv("OPENAI_API_KEY") or ""
        
        kwargs = {"api_key": self.api_key, "timeout": 10.0}
        if self.api_key.startswith("nvapi-"):
            kwargs["base_url"] = "https://integrate.api.nvidia.com/v1"
            self.model = "meta/llama-3.1-8b-instruct"
        else:
            # Fallback to standard OpenAI or groq if it starts with sk-
            self.model = "gpt-3.5-turbo" 
            
        self.client = AsyncOpenAI(**kwargs)
        
        self.intent_agent = HierarchicalIntentAgent() if HierarchicalIntentAgent else None
        self.table_agent = TableAgent() if TableAgent else None
        self.col_pruning_agent = ColumnPruningAgent() if ColumnPruningAgent else None
        self.audit_agent = AuditAgent() if AuditAgent else None
        
        # Instantiate SQLValidator if DB URL is available
        self.validator = None
        if SQLValidator and _database_url:
            url = _database_url()
            if url: self.validator = SQLValidator(url)

    async def orchestrate(self, text: str, persona: str, history: list) -> dict:
        start_time = asyncio.get_event_loop().time()
        intent, confidence, entropy, reasoning = "default", 0.8, 0.5, "Parallelizing pipeline."
        
        # 1. PARALLEL INTENT & TABLE SELECTION
        # Use asyncio.gather to fire off multiple agents simultaneously
        intent_task = self.intent_agent.handle_message(Message(text, metadata={"persona": persona})) if self.intent_agent else None
        table_task = self.table_agent.handle_message(Message(text)) if self.table_agent else None
        
        # Wait for both to finish (concurrently)
        intent_res, table_res = await asyncio.gather(
            intent_task or asyncio.sleep(0), 
            table_task or asyncio.sleep(0)
        )
        
        if intent_res and hasattr(intent_res, 'metadata'):
            intent = intent_res.metadata.get("intent", intent)
            confidence = intent_res.metadata.get("confidence", confidence)
            entropy = intent_res.metadata.get("entropy_reduction", entropy)
            reasoning = intent_res.metadata.get("reasoning", "")

        # SPEED OPTIMIZATION: FAST-PATH BYPASS
        # If it's clearly a conversational greeting or needs clarification, skip the heavy DB overhead
        is_conversational = intent in ["CLARIFICATION_REQUIRED", "NEUTRAL"] or entropy < 0.3
        
        context_str = ""
        sql_query = ""
        rows = []
        
        if not is_conversational:
            # 2. Table & Column Pruning Phase (Parallelized where possible)
            try:
                raw_tables = table_res.metadata.get("ranked_tables", []) if table_res else []
                # SCHEMA LOCKDOWN: Only allow tables from the aiml_academic schema
                tables = [t for t in raw_tables if t.get("table", "").startswith("aiml_academic.")]
                
                if tables and self.col_pruning_agent:
                    col_res = await self.col_pruning_agent.handle_message(Message(text))
                    kept_cols = col_res.metadata.get("kept", [])
                    table_name = col_res.metadata.get("table", tables[0]["table"])
                    context_str = f"Target Table: {table_name}. Relevant Columns: {', '.join(kept_cols)}."
                    reasoning += f" | Table Context: Pulled {table_name} schema (Post-Filter)."
            except Exception as e:
                pass
                
            # 3. SQL Gen Phase (Uses 70B for high-precision SELECTs)
            if generate_sql_with_agent:
                try:
                    sql_input = f"{text}\nContext hint: {context_str}"
                    sql_query = await asyncio.to_thread(generate_sql_with_agent, sql_input)
                    reasoning += " | SQL Gen: Drafted."
                except Exception as e:
                    pass
        else:
            reasoning += " | Fast-Path: Bypassed DB overhead for conversational flow."

        # 4. Grounded RAG Phase (Identity First-Look)
        master_identity = None
        if not is_conversational and text:
            # Quick greedy search for a USN or Name in the master students table
            try:
                from sqlalchemy import create_engine, text as sqla_text
                engine = create_engine(DB_URL)
                with engine.connect() as conn:
                    # Search for something that looks like a USN or Name
                    match = re.search(r"\b1DS\d{2}[A-Z]{2}\d{3}\b", text, re.IGNORECASE)
                    search_term = match.group(0) if match else text.strip()
                    
                    id_query = f"SELECT student_usn, student_name FROM aiml_academic.students WHERE student_usn ILIKE '%{search_term}%' OR student_name ILIKE '%{search_term}%' LIMIT 1"
                    id_res = conn.execute(sqla_text(id_query)).fetchone()
                    if id_res:
                        master_identity = {"usn": id_res[0], "name": id_res[1]}
                        reasoning += f" | RAG: Grounded to {id_res[1]} ({id_res[0]})."
            except Exception:
                pass

        # 5. Filter / Validate SQL & Execute
        if sql_query:
            should_execute = True
            # Inject Ground Truth into the SQL prompt if found
            if master_identity:
                sql_input = f"{text}\nGROUND TRUTH IDENTITY: Student is {master_identity['name']} (USN: {master_identity['usn']}). Context: {context_str}"
                # Re-generate or refine SQL with the anchor
                try:
                    sql_query = await asyncio.to_thread(generate_sql_with_agent, sql_input)
                    reasoning += " | SQL: Re-anchored to Master Identity."
                except Exception: pass
            
            if self.validator:
                is_valid, v_res = await asyncio.to_thread(self.validator.validate, sql_query)
                if not is_valid:
                    should_execute = False
                    reasoning += " | SQL Validation: Rejected (blocked for security)."
                else:
                    reasoning += " | SQL Validation: Passed Check."
            
            if should_execute:
                # 5. Execute SQL (with Self-Healing Loop)
                try:
                    from sqlalchemy import create_engine, text as sqla_text
                    engine = create_engine(DB_URL)
                    with engine.connect() as conn:
                        try:
                            result = conn.execute(sqla_text(sql_query))
                        except Exception as first_err:
                            # SELF-HEALING LOOP: Retry with correction
                            reasoning += f" | SQL Error: {str(first_err)[:50]}... Healing..."
                            if generate_sql_with_correction:
                                sql_query = await asyncio.to_thread(generate_sql_with_correction, text, sql_query, str(first_err))
                                result = conn.execute(sqla_text(sql_query))
                                reasoning += " | SQL: Self-Healed."
                            else: raise first_err

                        # Fetch rows for analysis
                        rows = [dict(row._mapping) for row in result.fetchmany(20)]
                        context_str += f"\nDatabase Execution Results: {rows}"
                        reasoning += f" | DB Execution: Fetched {len(rows)} rows."
                except Exception as final_err:
                    reasoning += f" | DB Execution: Permanent Failure ({final_err})"

        # 5. Intelligence Phase: Math & Ambiguity Handling
        final_context = context_str
        ambiguity_list = []
        try:
            # Check for multiple students if a name was searched
            from collections import Counter
            student_counts = Counter([r.get('student_usn') for r in rows if r.get('student_usn')])
            if len(student_counts) > 1:
                # Ambiguity detected! Format as a list.
                ambiguity_list = list(set([f"{r.get('student_usn')} ({r.get('student_name') or r.get('student_name_snapshot')})" for r in rows]))
                final_context += f"\nAMBIGUITY DETECTED: Found multiple students matching query. Display this list: {ambiguity_list}"
            else:
                # Single student or no rows. Check for multiple semesters to calculate CGPA.
                sgpas = [float(r.get('sgpa')) for r in rows if r.get('sgpa') is not None]
                if sgpas:
                    calculated_cgpa = round(sum(sgpas) / len(sgpas), 2)
                    final_context += f"\nCALCULATED_CGPA: {calculated_cgpa} (Avg of {len(sgpas)} semesters: {sgpas})"
        except Exception:
            pass

        # 6. Dynamic Template Selection (Pro Synthesis v7)
        # Select Report Template based on data volume
        if len(rows) > 1:
            template_name = "TREND_ANALYST_PRO"
            dynamic_instruction = "You are a Trend Analyst. Create a professional trajectory report with growth insights and tables."
        elif len(rows) == 1:
            template_name = "PERFORMANCE_SNAPSHOT"
            dynamic_instruction = "You are a Performance Analyst. Create a crisp, high-impact snapshot card for this specific record."
        else:
            template_name = "CONVERSATIONAL"
            dynamic_instruction = "Be friendly and conversational if the user is chatting. If they are asking for data, professionally state 'Record Not Found'."

        prompt = f"""You are the AIML Nexus Senior Academic Analyst (v7 {template_name}).
{dynamic_instruction}

User Query: "{text}"
Database Result Summary: 
{final_context if final_context.strip() else "(No records found.)"}

REPORTING GUIDELINES:
1. MATH VERIFICATION: If 'CALCULATED_CGPA' is present, use it as the ground truth.
2. PROFESSIONALISM: Use clear Markdown formatting.
3. ADAPTIVE: {dynamic_instruction}
4. NO HALLUCINATION: Never make up data.
"""

        try:
            completion = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": prompt}]
            )
            final_resp = completion.choices[0].message.content.strip()
        except Exception as e:
            final_resp = f"I failed to generate a response via LLM gracefully. Error: {e}"

        # 6. Audit Pipeline Phase
        audit_passed = True
        if self.audit_agent:
            try:
                a_res = await asyncio.to_thread(self.audit_agent.audit, text, sql_query, final_resp)
                audit_passed = a_res.get("passed", True)
                if not audit_passed:
                    final_resp = "Response blocked by Audit for safety compliance."
            except Exception:
                audit_passed = True

        duration = round(asyncio.get_event_loop().time() - start_time, 2)

        # 7. Metrics capture for dashboard and review
        if self.audit_agent:
            try:
                outcomes = {
                    "Intent_Agent": bool(intent_res),
                    "Table_Agent": bool(table_res and getattr(table_res, 'metadata', {}).get('ranked_tables')),
                    "Column_Pruning_Agent": bool('col_res' in locals() and getattr(col_res, 'metadata', {}).get('kept')),
                    "SQL_Generator": bool(sql_query),
                    "SQL_Validator": bool(self.validator is None or 'is_valid' in locals() and is_valid),
                    "Audit_Agent": audit_passed,
                }
                self.audit_agent.record_request(
                    session_id=None,
                    duration=duration,
                    agent_outcomes=outcomes,
                    audit_passed=audit_passed,
                )
            except Exception:
                pass
                
        return {
            "response": final_resp,
            "sender": "synthetic_agent",
            "intent": intent,
            "confidence": confidence,
            "entropy_reduction": entropy,
            "reasoning": reasoning,
            "duration": duration
        }
