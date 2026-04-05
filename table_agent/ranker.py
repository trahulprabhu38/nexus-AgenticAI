from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any

import sqlite3
import psycopg2
from psycopg2.extras import RealDictCursor


def _database_url() -> str:
    # Use Postgres globally across the nexus platform - Sourced from Master .env
    return os.getenv("AIML_RESULTS_DATABASE_URL")


def _sqlite_db_path() -> str:
    return os.path.join("API_Integrations", "nexus_chat.sqlite")


_SEM_WORDS = {
    1: ("1st", "first", "sem 1", "sem1", "semester 1", "1 sem"),
    2: ("2nd", "second", "sem 2", "sem2", "semester 2", "2 sem"),
    3: ("3rd", "third", "sem 3", "sem3", "semester 3", "3 sem"),
    4: ("4th", "fourth", "sem 4", "sem4", "semester 4", "4 sem"),
    5: ("5th", "fifth", "sem 5", "sem5", "semester 5", "5 sem"),
    6: ("6th", "sixth", "sem 6", "sem6", "semester 6", "6 sem"),
    7: ("7th", "seventh", "sem 7", "sem7", "semester 7", "7 sem"),
    8: ("8th", "eighth", "sem 8", "sem8", "semester 8", "8 sem"),
}


def _infer_semesters(text: str) -> set[int]:
    t = text.lower()
    found: set[int] = set()
    
    # 1. Broad regex for "3rd", "3th", "sem 3", "3 sem", "3 semester"
    patterns = [
        r"(?:sem|semester|levels|s)\s*(\d+)\b",                    # sem 3, semester 3
        r"\b(\d+)\s*(?:st|nd|rd|th)?\s*(?:sem|semester|levels|s)\b", # 3rd sem, 3 th sem
        r"\b([1-8])\s*(?:st|nd|rd|th)\b"                             # 3rd, 4th (without 'sem')
    ]
    
    for p in patterns:
        for m in re.finditer(p, t):
            try:
                val = int(m.group(1))
                if 1 <= val <= 8:
                    found.add(val)
            except ValueError: continue

    # 2. Hardcoded phrase fallback (more strict)
    for n, phrases in _SEM_WORDS.items():
        for p in phrases:
            # Avoid matching "2" as "2 sem" if it's just a digit in a year
            if re.search(rf"\b{re.escape(p)}\b", t):
                found.add(n)
                break
    
    return found


def _infer_years(text: str) -> set[int]:
    # Match any 4-digit academic year from 2010 to 2029
    return {int(x) for x in re.findall(r"\b(20[1-2]\d)\b", text)}


def _row_matches_semester(row: dict[str, Any], sem_q: set[int]) -> bool:
    if not sem_q:
        return True
    sn = row.get("semester_no")
    if sn is None:
        return False
    return int(sn) in sem_q


def _row_matches_year(row: dict[str, Any], years_q: set[int]) -> bool:
    """Match academic-year folders: DB column and/or path like 2022/2022/..."""
    if not years_q:
        return True
    fy = row.get("source_folder_year")
    if fy is not None and int(fy) in years_q:
        return True
    path = "/".join(
        [
            str(row.get("source_relative_path") or "").replace("\\", "/"),
            str(row.get("source_file_name") or ""),
        ]
    )
    for y in years_q:
        ystr = str(y)
        if f"/{ystr}/" in path or path.startswith(f"{ystr}/"):
            return True
    return False


def _narrow_rows_for_query(rows: list[dict[str, Any]], query: str) -> list[dict[str, Any]]:
    sem_q = _infer_semesters(query)
    years_q = _infer_years(query)

    if not sem_q and not years_q:
        return [dict(r) for r in rows]

    narrowed = [
        dict(r)
        for r in rows
        if _row_matches_semester(r, sem_q) and _row_matches_year(r, years_q)
    ]
    if narrowed:
        return narrowed
    return []


def _tokens(text: str) -> set[str]:
    return {w for w in re.split(r"[^a-z0-9]+", text.lower()) if len(w) > 1}


def _short_table_label(row: dict[str, Any]) -> str:
    label = (row.get("session_label") or "").strip()
    if label:
        part = label.split()[0] if label.split() else label
        if len(part) > 24:
            return part[:21] + "..."
        return part
    path = row.get("source_relative_path") or row.get("source_file_name") or ""
    base = os.path.basename(path.replace("\\", "/"))
    return (base[:24] + ("..." if len(base) > 24 else "")) if base else ""


def _table_id_slug(row: dict[str, Any]) -> str:
    rel = (row.get("source_relative_path") or row.get("source_file_name") or "").strip()
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", rel.replace("\\", "/")).strip("_").lower()
    sid = row.get("session_id")
    if slug:
        return "aiml_" + slug
    return f"aiml_session_{sid}"


def _source_file_display(row: dict[str, Any]) -> str:
    return (row.get("source_relative_path") or row.get("source_file_name") or "").strip()


@dataclass
class RankedTable:
    table: str
    score: float
    table_id: str
    source_file: str
    db_type: str = "postgres"  # "postgres" or "sqlite"

    def as_dict(self) -> dict[str, Any]:
        return {
            "table": self.table,
            "score": round(self.score, 4),
            "table_id": self.table_id,
            "source_file": self.source_file,
            "db_type": self.db_type
        }


def fetch_sessions(
    conn,
    semester_nos: list[int] | None = None,
    years: list[int] | None = None,
) -> list[dict[str, Any]]:
    """
    Load sessions. When semester_nos and/or years are set, apply SQL filters so
    only rows tied to that semester / calendar folder year enter ranking.
    """
    where_parts: list[str] = []
    params: list[Any] = []

    if semester_nos:
        where_parts.append("semester_no IN %s")
        params.append(tuple(int(x) for x in semester_nos))

    if years:
        yt = tuple(int(x) for x in years)
        year_clauses = ["source_folder_year IN %s"]
        params.append(yt)
        for y in yt:
            year_clauses.append(
                "(source_relative_path LIKE %s OR source_relative_path LIKE %s "
                "OR source_file_name LIKE %s OR source_file_name LIKE %s)"
            )
            params.extend(
                (
                    f"%/{y}/%",
                    f"{y}/%",
                    f"%/{y}/%",
                    f"{y}/%",
                )
            )
        where_parts.append("(" + " OR ".join(year_clauses) + ")")

    where_sql = " AND ".join(where_parts) if where_parts else "TRUE"
    sql = f"""
        SELECT session_id, session_label, source_file_name, source_relative_path,
               semester_no, source_folder_year, study_year, result_scale
        FROM aiml_academic.result_sessions
        WHERE {where_sql}
        ORDER BY session_id
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql, params)
        return list(cur.fetchall())


def score_row(query: str, row: dict[str, Any]) -> float:
    q_tok = _tokens(query)
    doc_parts = [
        str(row.get("session_label") or ""),
        str(row.get("source_file_name") or ""),
        str(row.get("source_relative_path") or ""),
        f"semester {row.get('semester_no')}",
        f"year {row.get('source_folder_year')}",
        f"study {row.get('study_year')}",
        str(row.get("result_scale") or ""),
    ]
    doc = " ".join(doc_parts).lower()
    d_tok = _tokens(doc)

    overlap = sum(1.0 for t in q_tok if t in d_tok)
    score = overlap * 1.2

    sem_q = _infer_semesters(query)
    years_q = _infer_years(query)

    sem_match = False
    if sem_q and row.get("semester_no") is not None and int(row["semester_no"]) in sem_q:
        score += 8.0  # Increased boost
        sem_match = True

    year_match = False
    fy = row.get("source_folder_year")
    if years_q and fy is not None and int(fy) in years_q:
        score += 6.0  # Increased boost
        year_match = True

    # Bonus for BOTH semester and year matching
    if sem_match and year_match:
        score += 10.0

    if "batch" in query.lower() and years_q and row.get("study_year") is not None:
        if int(row["study_year"]) in years_q:
            score += 2.0

    if row.get("session_id") is not None and str(row["session_id"]) in query:
        score += 2.0

    return score


def rank_tables(query: str, top_k: int = 5) -> tuple[list[dict[str, Any]], str | None]:
    if top_k < 1: top_k = 1
    if top_k > 50: top_k = 50

    # 1. Try Postgres (AIML_RESULTS_DATABASE_URL)
    pg_url = _database_url()
    if pg_url:
        try:
            conn = psycopg2.connect(pg_url)
            try:
                sem_q = _infer_semesters(query)
                years_q = _infer_years(query)
                rows = fetch_sessions(conn, semester_nos=list(sem_q), years=list(years_q))
                if rows:
                    return _process_pg_results(query, rows, top_k)
            finally:
                conn.close()
        except Exception as e:
            # Only log if it's not a missing URL error
            print(f"[table_agent] Postgres check failed: {e}")

    # 2. Fallback to SQLite (nexus_chat.sqlite)
    # If the user mentioned "result" or "semester" but Postgres failed, we must be careful.
    if ("result" in query.lower() or "sem" in query.lower()) and not pg_url:
        print("[table_agent] Query mentions results but no PostgreSQL URL found. Falling back to local data.")

    return _rank_sqlite_tables(query, top_k)


def _process_pg_results(query: str, rows: list[dict[str, Any]], top_k: int) -> tuple[list[dict[str, Any]], str | None]:
    candidates = _narrow_rows_for_query(rows, query)
    if not candidates:
        # If we have rows but none match the specific filters, just use all rows
        candidates = rows

    scored: list[tuple[float, dict[str, Any]]] = []
    for row in candidates:
        s = score_row(query, row)
        scored.append((s, row))

    scored.sort(key=lambda x: x[0], reverse=True)
    if not scored:
        return [], "No matching results found in Postgres."
        
    max_s = scored[0][0]
    
    out = []
    for s, r in scored[:top_k]:
        norm = min(1.0, s / max_s) if max_s else 1.0
        sid = r.get("session_id")
        out.append(RankedTable(
            table=_short_table_label(r) or f"session_{sid}",
            score=norm,
            table_id=_table_id_slug(r),
            source_file=_source_file_display(r),
            db_type="postgres"
        ))
    return [x.as_dict() for x in out], None


def _rank_sqlite_tables(query: str, top_k: int) -> tuple[list[dict[str, Any]], str | None]:
    db_path = _sqlite_db_path()
    if not os.path.exists(db_path):
        return [], f"Database connection failed and local SQLite file not found at {db_path}"

    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        db_tables = [row[0] for row in cur.fetchall()]
        conn.close()

        if not db_tables:
            return [], "No active sessions or tables found in the database."

        table_keywords = {
            "Student": ["student", "roll", "name", "id", "sem"],
            "Marks": ["mark", "result", "score", "grade", "performance", "exam"],
            "Semester": ["sem", "semester", "academic", "level"],
            "Subjects": ["subject", "course", "branch", "syllabus"],
            "Timetable": ["time", "schedule", "class", "day", "room", "lecture"]
        }

        q_tokens = _tokens(query)
        scored_tables = []
        for tname in db_tables:
            score = 0.0
            if tname.lower() in query.lower(): score += 5.0
            for k in table_keywords.get(tname, []):
                if k in q_tokens: score += 2.0
            if score > 0: scored_tables.append((score, tname))

        scored_tables.sort(key=lambda x: x[0], reverse=True)
        
        # Avoid returning hardcoded 'Marks' if it doesn't actually exist in SQLite
        if not scored_tables:
            # Only fallback to generic if the tables actually exist
            available = set(db_tables)
            if "Marks" in available or "Student" in available:
                if "result" in query.lower() or "sem" in query.lower():
                    scored_tables = [(5.0, t) for t in ["Marks", "Student", "Semester"] if t in available]

        if not scored_tables:
            return [], "No relevant tables found for your query in the current data source."

        out = []
        for s, tname in scored_tables[:top_k]:
            out.append(RankedTable(
                table=tname,
                score=1.0, 
                table_id=tname,
                source_file=f"sqlite://{tname}",
                db_type="sqlite"
            ))
        return [x.as_dict() for x in out], None

    except Exception as e:
        return [], f"Local database error: {e}"
