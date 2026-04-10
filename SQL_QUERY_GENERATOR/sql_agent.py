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
    
    kwargs = {"api_key": api_key, "timeout": 60.0}
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

DATABASE SCHEMA (aiml_academic):
  students(student_usn PK, student_name, admission_year)
  student_semester_results(semester_result_id PK, session_id FK, student_usn FK, student_name_snapshot, serial_no, sgpa, percentage, grand_total, source_excel_row)
  result_sessions(session_id PK, session_label)  -- session_label = 'Semester 1', 'Semester 2', etc.
  semesters(semester_no, study_year, semester_label)
  student_subject_results(subject_result_id PK, semester_result_id FK, session_subject_id FK, raw_result, numeric_marks, grade_text, result_kind)
  subjects(subject_id PK, subject_code, subject_name)
  session_subjects(session_subject_id PK, session_id FK, subject_id FK)

KEY JOINS:
  students.student_usn = student_semester_results.student_usn
  student_semester_results.session_id = result_sessions.session_id
  student_semester_results.semester_result_id = student_subject_results.semester_result_id

STRICT RULES:
1. FORBIDDEN: NEVER use AVG(), SUM(), MAX(), COUNT(), GROUP BY, HAVING. The Python orchestrator handles all math.
2. SCHEMA LOCKDOWN: ONLY use 'aiml_academic.' prefix for all tables.
3. IDENTITY ANCHOR: If 'GROUND TRUTH' is provided, use that EXACT USN in WHERE.
4. Always SELECT s.student_usn, s.student_name, r.sgpa, r.percentage, r.grand_total, rs.session_label for semester queries.
5. Always JOIN result_sessions rs ON r.session_id = rs.session_id to get semester labels.
6. For subject-level queries, JOIN student_subject_results and session_subjects and subjects.
7. Output RAW SQL only. No markdown. No comments. No explanations.
8. ORDER BY rs.session_label for semester-wise results.

EXAMPLE (semester results for a student):
SELECT s.student_usn, s.student_name, r.sgpa, r.percentage, r.grand_total, rs.session_label
FROM aiml_academic.students s
JOIN aiml_academic.student_semester_results r ON s.student_usn = r.student_usn
JOIN aiml_academic.result_sessions rs ON r.session_id = rs.session_id
WHERE s.student_usn = '1DS20AI001'
ORDER BY rs.session_label

EXAMPLE (students with SGPA > 9 in a specific semester):
SELECT s.student_usn, s.student_name, r.sgpa, rs.session_label
FROM aiml_academic.students s
JOIN aiml_academic.student_semester_results r ON s.student_usn = r.student_usn
JOIN aiml_academic.result_sessions rs ON r.session_id = rs.session_id
WHERE r.sgpa > 9 AND rs.session_label = 'Semester 6'
ORDER BY r.sgpa DESC

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


