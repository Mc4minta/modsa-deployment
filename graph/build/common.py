"""Shared local configuration, TLS and audited whitespace-only evidence repair."""
from pathlib import Path
import os
import re
import ssl
import hashlib
import json

ROOT = Path(__file__).resolve().parents[2]
DATA = Path(os.environ.get("MODSA_GRAPH_DATA_DIR", ROOT / "graph/data"))
BASE_URL = "https://token-plan-sgp.xiaomimimo.com/v1"


def canonical(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def fingerprint(value: object) -> str:
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def api_key() -> str:
    key = os.environ.get("MIMO_API_KEY")
    for path in (ROOT / ".env", ROOT / "backend/.env"):
        if key or not path.exists():
            continue
        for line in path.read_text().splitlines():
            name, separator, value = line.strip().removeprefix("export ").partition("=")
            if separator and name.strip() == "MIMO_API_KEY":
                key = value.strip().strip("\"'")
    if not key:
        raise RuntimeError("MIMO_API_KEY missing")
    return key


def ssl_context() -> ssl.SSLContext:
    context = ssl.create_default_context()
    try:
        import certifi
        context.load_verify_locations(certifi.where())
    except ImportError:
        pass
    return context


def restore_source_whitespace(evidence: list, allowed: dict) -> list[dict]:
    """Preserve original offsets and audit; never change words or numbers."""
    repairs = []
    for item in evidence:
        if item.chunk_id not in allowed:
            continue
        source = allowed[item.chunk_id]["content"]
        if item.quote in source:
            continue
        normalized, offsets = [], []
        for token in re.finditer(r"\S+", source):
            if normalized:
                normalized.append(" ")
                offsets.append(token.start())
            for index in range(token.start(), token.end()):
                normalized.append(source[index])
                offsets.append(index)
        wanted = " ".join(item.quote.split())
        start = "".join(normalized).find(wanted) if wanted else -1
        if start >= 0:
            restored = source[offsets[start]:offsets[start + len(wanted) - 1] + 1]
            if " ".join(restored.split()) == wanted:
                repairs.append({"chunk_id": item.chunk_id, "model_quote": item.quote, "source_quote": restored})
                item.quote = restored
    return repairs
