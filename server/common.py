"""Shared helpers: ids, time, hashing, redaction, API envelope, errors."""
import hashlib
import json
import re
import secrets
import time
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import HTTPException

SENSITIVE_KEY = re.compile(r"(password|passwd|secret|token|api[_-]?key|authorization|ssn|card|email|phone|address|verification[_-]?code|verify[_-]?code|otp|pin)", re.I)
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(5)}"


def state_hash(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()[:16]


def redact(value: Any) -> Any:
    """Mask secret-looking keys and email addresses in nested dicts/lists. Keeps structure for review."""
    if isinstance(value, dict):
        return {k: ("[REDACTED]" if SENSITIVE_KEY.search(str(k)) else redact(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    if isinstance(value, str):
        return EMAIL_RE.sub("[email]", value)
    return value


class ApiError(HTTPException):
    """HTTP error that still carries the standard envelope."""

    def __init__(self, status_code: int, code: str, message: str, data: Optional[dict] = None):
        super().__init__(status_code=status_code, detail={"code": code, "message": message, "data": data or {}})


def envelope(status: str, code: str, message: str, correlation_id: str, data: Any = None) -> dict:
    return {"status": status, "code": code, "message": message, "correlation_id": correlation_id, "data": data}


def tokenize(text: str) -> list:
    return [t for t in re.findall(r"[a-z]+-\d+|[a-z0-9]+", (text or "").lower()) if len(t) > 1]
