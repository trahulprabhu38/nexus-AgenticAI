"""
Column Pruning Agent
====================
Implements greedy column selection per the architecture spec:
  - Static keyword relevance: map query words to column names
  - Always keep PK/FK columns (ids, usn, codes)
  - LLM greedy pruning: "Which columns do I need to answer X?"
  - Fallback: heuristic keyword scoring when LLM unavailable

Input:  query (str) + table_id (str) + columns (list, optional)
Output: kept (list), dropped (list), mode (str), table (str)
"""
import os
import re
import json
import logging
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger("column-pruning")

# ── Schema registry (mirrors aiml_academic schema) ────────────────────
SCHEMA_REGISTRY: dict[str, list[str]] = {
    "semesters": [
        "semester_no", "study_year", "semester_label"
    ],
    "students": [
        "student_usn", "student_name", "admission_year"
    ],
    "subjects": [
        "subject_code", "subject_label"
    ],
    "result_sessions": [
        "session_id", "source_folder_year", "semester_no",
        "session_label", "study_year", "result_scale"
    ],
    "session_subjects": [
        "session_subject_id", "session_id", "subject_code", "subject_order"
    ],
    "student_semester_results": [
        "semester_result_id", "session_id", "student_usn",
        "student_name_snapshot", "sgpa", "percentage", "grand_total"
    ],
    "student_subject_results": [
        "subject_result_id", "semester_result_id", "session_subject_id",
        "raw_result", "numeric_marks", "grade_text", "result_kind"
    ],
}

# ── PK / FK column patterns (always kept) ─────────────────────────────
_PK_FK_SUFFIXES = ("_id", "_usn", "_no", "_code")


def _is_pk_fk(col: str) -> bool:
    return col.endswith(_PK_FK_SUFFIXES)


def _resolve_columns(table_id: str, provided: list[str]) -> tuple[str, list[str]]:
    """Strip schema prefix and look up columns from registry if not provided."""
    # Handle 'aiml_academic.students' or just 'students'
    table_name = table_id.split(".")[-1].strip()
    columns = provided if provided else SCHEMA_REGISTRY.get(table_name, [])
    return table_name, columns


def _keyword_score(query: str, col: str) -> float:
    """Compute relevance of a column to a query via token overlap."""
    q_tokens = set(re.sub(r"[^\w]", " ", query.lower()).split())
    c_tokens = set(re.sub(r"_", " ", col.lower()).split())
    if not c_tokens:
        return 0.0
    return len(q_tokens & c_tokens) / len(c_tokens)


def _heuristic_prune(query: str, table_name: str, all_cols: list[str]) -> dict:
    """Keyword-based fallback pruning."""
    pk_fk = [c for c in all_cols if _is_pk_fk(c)]
    non_key = [c for c in all_cols if not _is_pk_fk(c)]

    scored = sorted(
        [(c, _keyword_score(query, c)) for c in non_key],
        key=lambda x: x[1],
        reverse=True,
    )
    # Keep top-half relevant columns (minimum 3)
    top_n = max(3, len(non_key) // 2)
    # If scores are all zero (no overlap), keep first top_n
    relevant = [c for c, s in scored[:top_n]]

    kept = list(dict.fromkeys(pk_fk + relevant))  # preserve order, deduplicate
    dropped = [c for c in all_cols if c not in kept]

    return {"kept": kept, "dropped": dropped, "mode": "heuristic", "table": table_name}


def _llm_prune(api_key: str, query: str, table_name: str, all_cols: list[str]) -> list[str] | None:
    """
    Ask LLM: 'Given this query and table schema, which columns do I need?'
    Returns a list of column names, or None on failure.
    """
    try:
        kwargs: dict = {"api_key": api_key, "timeout": 15.0}
        if api_key.startswith("nvapi-"):
            kwargs["base_url"] = "https://integrate.api.nvidia.com/v1"
            model = "meta/llama-3.1-8b-instruct"
        else:
            model = "gpt-3.5-turbo"

        client = OpenAI(**kwargs)
        schema_str = f"{table_name}({', '.join(all_cols)})"
        prompt = (
            f"You are a database column selector.\n"
            f"User query: \"{query}\"\n"
            f"Table schema: {schema_str}\n\n"
            f"Select the minimum columns needed to answer the query.\n"
            f"RULES:\n"
            f"1. Always include columns ending in _id, _usn, _no, _code (keys).\n"
            f"2. Return ONLY a JSON array of column names from the schema, nothing else.\n"
            f"Example: [\"student_usn\", \"student_name\", \"sgpa\"]"
        )

        resp = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
            temperature=0,
        )
        content = resp.choices[0].message.content.strip()
        match = re.search(r"\[.*?\]", content, re.DOTALL)
        if match:
            selected = json.loads(match.group(0))
            # Validate — only keep columns that exist in the schema
            return [c for c in selected if c in all_cols]
    except Exception as e:
        logger.warning("LLM prune failed: %s", e)
    return None


class ColumnPruneAgent:
    def __init__(self):
        self.api_key = os.getenv("NVIDIA_API_KEY") or os.getenv("OPENAI_API_KEY") or ""
        if self.api_key:
            logger.info("ColumnPruneAgent: LLM mode enabled")
        else:
            logger.info("ColumnPruneAgent: heuristic-only mode (no API key)")

    def prune(self, query: str, table_id: str, columns: list[str]) -> dict:
        table_name, all_cols = _resolve_columns(table_id, columns)

        if not all_cols:
            logger.warning("No columns found for table_id=%s", table_id)
            return {"kept": [], "dropped": [], "mode": "passthrough", "table": table_name}

        # Ensure PK/FK columns are always in the final set
        pk_fk = [c for c in all_cols if _is_pk_fk(c)]

        # Try LLM pruning
        if self.api_key:
            llm_result = _llm_prune(self.api_key, query, table_name, all_cols)
            if llm_result:
                kept = list(dict.fromkeys(pk_fk + llm_result))
                dropped = [c for c in all_cols if c not in kept]
                logger.info("LLM prune: table=%s kept=%d dropped=%d", table_name, len(kept), len(dropped))
                return {"kept": kept, "dropped": dropped, "mode": "llm", "table": table_name}

        # Fallback to heuristic
        result = _heuristic_prune(query, table_name, all_cols)
        logger.info("Heuristic prune: table=%s kept=%d dropped=%d", table_name, len(result["kept"]), len(result["dropped"]))
        return result
