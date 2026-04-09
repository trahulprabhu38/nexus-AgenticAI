"""
Shared utilities for all Nexus agent microservices.
Provides: structured JSON logging (Loki-compatible), request middleware,
health endpoint factory, and Prometheus-compatible metrics.
"""
import os
import sys
import time
import json
import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# ── Structured JSON Formatter (Loki / Grafana compatible) ──────────────

class JSONFormatter(logging.Formatter):
    """Outputs one JSON object per log line — ready for Loki/Promtail."""
    def __init__(self, service_name: str):
        super().__init__()
        self.service_name = service_name

    def format(self, record):
        entry = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "service": self.service_name,
        }
        if record.exc_info and record.exc_info[0]:
            entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(entry)


def setup_logging(service_name: str) -> logging.Logger:
    """Configure root logger with JSON output and return a named logger."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter(service_name))
    logging.root.handlers = [handler]
    logging.root.setLevel(os.getenv("LOG_LEVEL", "INFO").upper())
    return logging.getLogger(service_name)


# ── Service Factory ────────────────────────────────────────────────────

def create_service(title: str, service_name: str) -> tuple[FastAPI, logging.Logger]:
    """
    Create a FastAPI app pre-configured with CORS, request logging
    middleware, and a /health endpoint. Returns (app, logger).
    """
    logger = setup_logging(service_name)

    app = FastAPI(title=title)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        start = time.time()
        response = await call_next(request)
        duration = round(time.time() - start, 3)
        logger.info(
            "%s %s -> %s (%ss)",
            request.method, request.url.path, response.status_code, duration,
        )
        return response

    logger.info("Service '%s' initializing", service_name)
    return app, logger
