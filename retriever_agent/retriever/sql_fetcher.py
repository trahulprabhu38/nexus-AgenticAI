# retriever/sql_fetcher.py
import re
from sqlalchemy import create_engine, text
from config import SAMPLE_DB_PATH
from typing import List, Dict

# SQLite connection string for SQLAlchemy
CONN_STR = f"sqlite:///{SAMPLE_DB_PATH}"

# Dangerous tokens to block
BLACKLIST = [
    ";", "drop ", "insert ", "update ", "delete ", "alter ", "create ",
    "attach ", "detach ", "pragma ", "exec ", "system", "copy ", "vacuum ",
    "transaction", "shutdown"
]

class SQLFetcher:
    def __init__(self, conn_str=CONN_STR):
        self.engine = create_engine(conn_str, future=True)

    def _is_safe(self, sql: str) -> bool:
        s = sql.lower()
        if "select" not in s:
            return False
        for token in BLACKLIST:
            if token in s:
                return False
        return True

    def _check_whitelist(self, sql: str, whitelist: List[str] = None) -> bool:
        if not whitelist:
            return True
        # basic check: ensure selected columns are subset of whitelist
        # naive parse: find between SELECT and FROM
        m = re.search(r"select(.*?)from", sql, flags=re.IGNORECASE | re.DOTALL)
        if not m:
            return False
        cols_part = m.group(1)
        cols = [c.strip() for c in cols_part.split(",")]
        # if '*' present allow if whitelist includes all columns? We'll disallow '*' for safety
        if any(c == "*" or "*" in c for c in cols):
            return False
        # simple column names (no table prefixes) check
        cols_simple = [re.sub(r'.*\.', '', c).strip().lower() for c in cols]
        whitelist_lower = [w.lower() for w in whitelist]
        for c in cols_simple:
            # allow expressions like COUNT(...) by skipping non-alphanumeric starts
            if re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', c):
                if c not in whitelist_lower:
                    return False
        return True

    def safe_select(self, sql: str, params: Dict = None, column_whitelist: List[str] = None, limit: int = 100):
        if not self._is_safe(sql):
            raise ValueError("Unsafe SQL detected or non-SELECT statement.")
        if not self._check_whitelist(sql, column_whitelist):
            raise ValueError("SQL selects columns outside whitelist or uses '*'.")
        # ensure LIMIT
        if re.search(r"\blimit\b", sql, flags=re.IGNORECASE) is None:
            sql = f"{sql} LIMIT {limit}"
        with self.engine.connect() as conn:
            stmt = text(sql)
            res = conn.execute(stmt, params or {})
            rows = [dict(r) for r in res]
        return rows
