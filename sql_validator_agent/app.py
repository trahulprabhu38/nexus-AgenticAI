from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from validator import SQLValidator


DB_URI = "postgresql://admin01:aiml1203@185.197.251.236:5432/nexus"  # TODO: update with real credentials

app = FastAPI()
validator = SQLValidator(DB_URI)


class QueryRequest(BaseModel):
    query: str


@app.post("/validate")
def validate_query(request: QueryRequest):
    is_valid, results = validator.validate(request.query)
    if is_valid:
        return {"valid": True, "message": "Query is valid", "results": results}
    raise HTTPException(
        status_code=400,
        detail={"valid": False, "results": results},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
