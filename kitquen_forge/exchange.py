"""Versioned, filesystem-only exchange shared by Blender and the MCP process."""

import json
import os
import re
from pathlib import Path

PROTOCOL = 1
MAX_REQUEST = 65536
REQUEST_ID = re.compile(r"[0-9a-f]{32}\Z")


def write_json(path: Path, value: dict):
    temporary = path.with_suffix(".tmp")
    try:
        temporary.write_text(
            json.dumps(value, ensure_ascii=True, allow_nan=False), encoding="utf-8"
        )
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def read_json(path: Path, limit: int):
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError("JSON message exceeds size limit")
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("Expected a JSON object")
    return value
