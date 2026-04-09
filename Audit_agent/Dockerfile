FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    "fastapi>=0.115.0" \
    "uvicorn[standard]>=0.30.0" \
    "python-dotenv>=1.0.1" \
    "openai>=1.50.0" \
    "pydantic>=2.0.0"

COPY . .

EXPOSE 8006

CMD ["uvicorn", "serve:app", "--host", "0.0.0.0", "--port", "8006"]
