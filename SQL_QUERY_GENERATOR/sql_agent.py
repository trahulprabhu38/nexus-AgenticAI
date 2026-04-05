import os
import re
from openai import OpenAI
from dotenv import load_dotenv

# Load master .env from root
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

# --------------------------------------------------
# Main agent function
# --------------------------------------------------
def generate_sql_with_agent(user_query: str) -> str:
    return _call_llm_for_sql(user_query)

def generate_sql_with_correction(user_query: str, last_sql: str, error_msg: str) -> str:
    """
    Self-Healing Loop: Takes a failed SQL and its error message to generate a fixed version.
    """
    repair_prompt = f"""
### SELF-HEALING MISSION: REPAIR FAILED SQL
The previous SQL query failed. You must fix it.

User Query: {user_query}
Failed SQL: {last_sql}
Error Message: {error_msg}

STRICT REPAIR RULES:
1. THE ERROR indicates you used an aggregate (AVG, SUM, etc.) or a wrong table.
2. YOU MUST REMOVE all AVG(), SUM(), MAX(), and GROUP BY clauses.
3. Fetch RAW rows only.
4. Correct any 'missing FROM-clause' or 'UndefinedTable' errors.

CORRECT PATTERN:
SELECT s.student_usn, s.student_name, r.sgpa, r.percentage, r.grand_total 
FROM aiml_academic.students s 
JOIN aiml_academic.student_semester_results r ON s.student_usn = r.student_usn 
WHERE s.student_usn = '[EXACT USN]'
"""
    return _call_llm_for_sql(repair_prompt)


def _call_llm_for_sql(prompt_text: str) -> str:
    api_key = os.getenv("NVIDIA_API_KEY") or os.getenv("OPENAI_API_KEY")
    is_nv = api_key.startswith("nvapi-") if api_key else False
    
    kwargs = {"api_key": api_key, "timeout": 10.0}
    if is_nv:
        kwargs["base_url"] = "https://integrate.api.nvidia.com/v1"
        model = "meta/llama-3.1-8b-instruct"
    else:
        model = "gpt-3.5-turbo"
        
    client = OpenAI(**kwargs)

    prompt = prompt_text
    if "MISSION" not in prompt_text:
        prompt = f"""
### MISSION: GENERATE RAW DATA SELECT QUERIES ONLY.

STRICT RULES (FAILURE TO FOLLOW = CRASH):
1. FORBIDDEN: NEVER use AVG(), SUM(), MAX(), or COUNT().
2. FORBIDDEN: NEVER use GROUP BY or HAVING.
3. FORBIDDEN: DO NOT calculate CGPA in SQL. The Python orchestrator handles all math.
4. SCHEMA LOCKDOWN: ONLY use 'aiml_academic.' tables.
5. IDENTITY ANCHOR: If 'GROUND TRUTH IDENTITY' is provided, use that EXACT USN.
6. RESILIENT JOIN: Always JOIN students s ON r.student_usn = s.student_usn. 
7. TABLE MAPPING: 'sgpa' is in 'student_semester_results'. 'numeric_marks' is in 'student_subject_results'.
8. Output RAW SQL only. No markdown. No comments.

REQUIRED PATTERN:
SELECT s.student_usn, s.student_name, r.sgpa, r.percentage, r.grand_total 
FROM aiml_academic.students s 
JOIN aiml_academic.student_semester_results r ON s.student_usn = r.student_usn 
WHERE s.student_usn = '[USN]'

User query & Context:
{prompt_text}
"""

    completion = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": prompt}]
    )
    
    sql_query = completion.choices[0].message.content.strip()
    sql_query = sql_query.replace("```sql", "").replace("```", "").strip()
    match = re.search(r"(SELECT[\s\S]+?)(?:;|\Z)", sql_query, re.IGNORECASE)
    if match:
        sql_query = match.group(1).strip()
    
    return sql_query


