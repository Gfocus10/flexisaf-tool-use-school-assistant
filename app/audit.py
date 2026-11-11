import json
import os
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()

AUDIT_FILE = os.getenv("AUDIT_LOG_PATH", "audit.log")
SENSITIVE_KEYS = {"guardian_phone", "api_key"}


def redact(value):
    if isinstance(value, dict):
        return {k: "[REDACTED]" if k in SENSITIVE_KEYS else redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value


def write_audit(event: str, tool: str, args: dict, outcome: str, actor: str = "assistant") -> None:
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event": event,
        "actor": actor,
        "tool": tool,
        "args": redact(args),
        "outcome": outcome,
    }
    with open(AUDIT_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
