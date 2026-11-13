"""Symmetric encryption for stored secrets (mailbox app passwords, generated ATS passwords).

Key derived from JOBOS_SECRET_KEY. Envelope encryption with a cloud KMS replaces this at Phase 3.
"""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet

from jobos.config import get_settings


def _fernet() -> Fernet:
    key = hashlib.sha256(get_settings().secret_key.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def encrypt(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt(token: str) -> str:
    return _fernet().decrypt(token.encode()).decode()
