"""
SQL Validator Agent — Standalone Microservice
Port: 8005
Validates SQL queries for syntax, semantics, security, and data range.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from pydantic import BaseModel
from service_utils import create_service

app, logger = create_service("Nexus SQL Validator", "sql-validator")

DB_URL = os.getenv("AIML_RESULTS_DATABASE_URL", "")

validator = None
if DB_URL:
    try:
        from validator import SQLValidator
        validator = SQLValidator(DB_URL)
        logger.info("SQLValidator connected to database")
    except Exception as e:
        logger.error("Failed to initialize SQLValidator: %s", e)
else:
    logger.warning("No AIML_RESULTS_DATABASE_URL set — validator will be unavailable")


class ValidateRequest(BaseModel):
    query: str


class CheckResult(BaseModel):
    check: str
    valid: bool
    message: str


class ValidateResponse(BaseModel):
    valid: bool
    results: list[CheckResult]


@app.get("/health")
def health():
    return {
        "status": "healthy" if validator else "degraded",
        "service": "sql-validator",
        "database_connected": validator is not None,
    }


@app.post("/validate", response_model=ValidateResponse)
def validate_query(req: ValidateRequest):
    if not validator:
        # DB unavailable — fail-open so the pipeline isn't blocked by a dead validator
        logger.warning("Validator DB unavailable, passing SQL through (fail-open)")
        return ValidateResponse(valid=True, results=[
            CheckResult(check="Connection", valid=True, message="Validator skipped: DB unreachable")
        ])

    logger.info("Validating SQL: %s", req.query[:100])
    is_valid, results = validator.validate(req.query)
    logger.info("Validation result: valid=%s, checks=%d", is_valid, len(results))
    return ValidateResponse(valid=is_valid, results=[CheckResult(**r) for r in results])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8005)
