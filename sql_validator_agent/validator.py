import re

import sqlparse
from sqlalchemy import MetaData, create_engine, inspect, text


class SQLValidator:
    def __init__(self, db_uri: str):
        self.engine = create_engine(db_uri, connect_args={"connect_timeout": 5})
        self.metadata = MetaData()
        # Reflect schema — uses a short connect_timeout so a dead DB fails fast
        self.metadata.reflect(bind=self.engine, schema='aiml_academic')
        self.inspector = inspect(self.engine)

    def validate_syntax(self, query: str):
        """Use PostgreSQL to actually parse the query via EXPLAIN."""
        try:
            with self.engine.connect() as conn:
                # Wrap the query securely; this runs AFTER security filters.
                # Start a transaction that we immediately rollback, just in case.
                trans = conn.begin()
                try:
                    conn.execute(text(f"EXPLAIN {query}"))
                finally:
                    trans.rollback()
            return True, "Syntax valid"
        except Exception as e:
            return False, f"Syntax error: {str(e)}"

    def validate_semantics(self, query: str):
        """Check that at least one referenced table exists in the schema, and exactly 1 statement is present."""
        try:
            parsed = sqlparse.parse(query)
            if not parsed:
                return False, "Unable to parse query"
            
            # Prevent Stacked Queries / SQL Injection
            if len(parsed) > 1:
                return False, "Multiple statements are not allowed for security reasons. Provide exactly one query."
            
            stmt = parsed[0]
            if stmt.get_type() != 'SELECT':
                return False, "Only SELECT statements are permitted."
        except Exception as e:
            return False, f"Semantic parse error: {str(e)}"

        tables = set()
        for token in stmt.tokens:
            if isinstance(token, sqlparse.sql.IdentifierList):
                for identifier in token.get_identifiers():
                    if isinstance(identifier, sqlparse.sql.Identifier):
                        name = identifier.get_real_name()
                        if name:
                            tables.add(name)
            elif isinstance(token, sqlparse.sql.Identifier):
                name = token.get_real_name()
                if name:
                    tables.add(name)

        # metadata.tables keys are in the format "schema.tablename" (e.g. "aiml_academic.students")
        valid_table_keys = self.metadata.tables.keys()
        valid_table_names = [k.split('.')[-1] for k in valid_table_keys]
        
        referenced_valid_tables = [t for t in tables if t in valid_table_names or f"aiml_academic.{t}" in valid_table_keys]
        if not referenced_valid_tables:
            return False, "No valid tables referenced from the aiml_academic schema"
        return True, "Semantics valid"

    def validate_data_range(self, query: str):
        """Validate study_year (1-4) and semester_no (1-8) values in WHERE clauses."""
        # Using explicit references to new schema columns
        study_year_pattern = r"(?:study_year\s*=\s*(\d+)|study_year\s+IN\s+\(([^)]+)\))"
        semester_pattern = r"(?:semester_no\s*=\s*(\d+)|semester_no\s+IN\s+\(([^)]+)\))"
        year_match = re.search(study_year_pattern, query, re.IGNORECASE)
        semester_match = re.search(semester_pattern, query, re.IGNORECASE)

        if year_match:
            years = year_match.group(2) or year_match.group(1)
            years = [int(y.strip()) for y in years.split(",") if y.strip()]
            if any(y not in {1, 2, 3, 4} for y in years):
                return False, "Invalid study_year value (must be 1-4)"

        if semester_match:
            semesters = semester_match.group(2) or semester_match.group(1)
            semesters = [int(s.strip()) for s in semesters.split(",") if s.strip()]
            if any(s not in {1, 2, 3, 4, 5, 6, 7, 8} for s in semesters):
                return False, "Invalid semester_no value (must be 1-8)"

        return True, "Data range valid"

    def validate_security(self, query: str):
        """Strict SQL injection / dangerous statement check."""
        # Ban risky keywords entirely from payload
        forbidden_keywords = ["drop", "delete", "insert", "update", "alter", "truncate", "exec", "grant", "revoke", "--", "/*"]
        query_lower = query.lower()
        if any(keyword in query_lower for keyword in forbidden_keywords):
            return False, "Forbidden SQL keyword detected to prevent SQL Injection"
            
        # explicitly block multiple statement trickery
        if ";" in query.strip(" \t\n\r;"):
            return False, "Stacked queries / semicolons are restricted"
            
        return True, "Security valid"

    def validate(self, query: str):
        # Enforce checks in STRICT ORDER so Security & Semantics happen BEFORE the potentially dangerous Syntax (EXPLAIN) check
        checks = [
            ("Semantics", self.validate_semantics(query)),
            ("Security", self.validate_security(query)),
            ("Data Range", self.validate_data_range(query)),
            ("Syntax", self.validate_syntax(query)),
        ]
        results = []
        for name, (valid, message) in checks:
            results.append({"check": name, "valid": valid, "message": message})
            if not valid:
                return False, results
        return True, results
