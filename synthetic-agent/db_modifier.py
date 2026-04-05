import os
import re
import asyncio
from openai import AsyncOpenAI
from sqlalchemy import create_engine, text
from table_agent.ranker import _database_url
from dotenv import load_dotenv

# Load master .env from root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

HOST_EMAIL = os.getenv("HOST_EMAIL", "gurunathagoudambiradar@gmail.com")

class DatabaseModifier:
    def __init__(self):
        api_key = os.getenv("NVIDIA_API_KEY") or os.getenv("OPENAI_API_KEY")
        is_nv = api_key.startswith("nvapi-")
        
        kwargs = {"api_key": api_key, "timeout": 10.0}
        if is_nv:
            kwargs["base_url"] = "https://integrate.api.nvidia.com/v1"
            self.model = "meta/llama-3.1-70b-instruct"
        else:
            self.model = "gpt-3.5-turbo"
            
        self.client = AsyncOpenAI(**kwargs)

    async def process_modification(self, query: str, user_email: str) -> dict:
        """
        Analyzes the query, determines if it is an INSERT or UPDATE,
        checks authorization, generates SQL, and executes it.
        """
        
        # 0. STRICT AUTHORIZATION
        if user_email.lower() != HOST_EMAIL.lower():
            return {
                "status": "denied",
                "message": f"Security Alert: Your account ({user_email}) does not have database write permissions. Only the official host ({HOST_EMAIL}) can perform this action."
            }

        # 1. Determine Intent & Operation Type
        prompt = f"""
Analyze the user request: "{query}"

If the user is providing student details in a format like 'USN: [X], Name: [Y], Year: [Z]', identify it as an INSERT.
Return ONLY a JSON object: {{"operation": "INSERT" | "UPDATE" | "UNKNOWN", "entity": "student" | "result" | "other"}}
"""
        try:
            completion = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": prompt}],
                response_format={ "type": "json_object" }
            )
            import json
            analysis = json.loads(completion.choices[0].message.content)
        except Exception as e:
            return {"status": "error", "message": f"Analysis failed: {str(e)}"}

        operation = analysis.get("operation", "UNKNOWN")
        if operation == "UNKNOWN":
            return {"status": "ignored", "message": "I couldn't identify a valid Add or Edit operation in your message. Please use the format: 'Add student USN: [X], Name: [Y], Year: [Z]'."}

        # 3. SQL Generation for Modification
        sql_prompt = f"""
Generate a raw PostgreSQL query for a {operation} operation based on: "{query}"

Schema: aiml_academic
Tables:
- aiml_academic.students (student_usn, student_name, admission_year)
- aiml_academic.student_semester_results (session_id, student_usn, sgpa, percentage, grand_total)

Rules:
1. ALWAYS use UPPER() for USN values.
2. Output RAW SQL only. No markdown. No comments.
3. If adding a student, use: INSERT INTO aiml_academic.students (student_usn, student_name, admission_year) VALUES (...)
"""

        try:
            sql_completion = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "system", "content": sql_prompt}]
            )
            raw_sql = sql_completion.choices[0].message.content.strip()
            raw_sql = raw_sql.replace("```sql", "").replace("```", "").strip()
        except Exception as e:
            return {"status": "error", "message": f"SQL Generation failed: {str(e)}"}

        # 4. Execution
        try:
            engine = create_engine(_database_url())
            with engine.connect() as conn:
                conn.execute(text(raw_sql))
                conn.commit()
            return {
                "status": "success",
                "message": f"Successfully executed {operation} operation on the database.",
                "sql": raw_sql
            }
        except Exception as e:
            return {"status": "error", "message": f"Database Execution failed: {str(e)}", "sql": raw_sql}

db_modifier = DatabaseModifier()
