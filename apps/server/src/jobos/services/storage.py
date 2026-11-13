"""Local file storage (documents, screenshots). Interface kept tiny so S3/R2 can replace it."""

from __future__ import annotations

import base64
import hashlib
from pathlib import Path

from jobos.config import get_settings


def _root() -> Path:
    root = get_settings().data_dir.resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def put_bytes(rel_path: str, data: bytes) -> str:
    path = (_root() / rel_path).resolve()
    if not str(path).startswith(str(_root())):
        raise ValueError("invalid storage path")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return rel_path


def get_bytes(rel_path: str) -> bytes:
    path = (_root() / rel_path).resolve()
    if not str(path).startswith(str(_root())):
        raise ValueError("invalid storage path")
    return path.read_bytes()


def put_b64(rel_path: str, data_b64: str) -> str:
    return put_bytes(rel_path, base64.b64decode(data_b64))


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
