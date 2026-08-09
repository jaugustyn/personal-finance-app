"""In-memory sessions and secret verification for the optional app lock."""
from __future__ import annotations

import base64
import hashlib
import secrets
import threading
import time
from collections import deque
from dataclasses import dataclass

APP_LOCK_COOKIE_NAME = "finance_app_lock_session"
ALLOWED_TIMEOUT_MINUTES = frozenset({5, 15, 30, 60})
DEFAULT_TIMEOUT_MINUTES = 15
MIN_CODE_LENGTH = 3
MAX_CODE_LENGTH = 128

_SCRYPT_N = 2**17
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_DKLEN = 32
_SCRYPT_MAXMEM = 256 * 1024 * 1024
_FAILED_ATTEMPT_LIMIT = 5
_FAILED_ATTEMPT_WINDOW_SECONDS = 5 * 60


@dataclass
class _UnlockSession:
    last_activity: float


_sessions: dict[str, _UnlockSession] = {}
_failed_attempts: dict[str, deque[float]] = {}
_state_lock = threading.RLock()


def _now() -> float:
    return time.monotonic()


def validate_code(code: str) -> str:
    if not MIN_CODE_LENGTH <= len(code) <= MAX_CODE_LENGTH:
        raise ValueError(
            f"Code must contain between {MIN_CODE_LENGTH} and {MAX_CODE_LENGTH} characters."
        )
    if not code.strip():
        raise ValueError("Code cannot consist only of whitespace.")
    return code


def validate_timeout(timeout_minutes: int) -> int:
    if timeout_minutes not in ALLOWED_TIMEOUT_MINUTES:
        allowed = ", ".join(str(value) for value in sorted(ALLOWED_TIMEOUT_MINUTES))
        raise ValueError(f"Timeout must be one of: {allowed} minutes.")
    return timeout_minutes


def hash_code(code: str) -> str:
    validated = validate_code(code)
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        validated.encode("utf-8"),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=_SCRYPT_DKLEN,
        maxmem=_SCRYPT_MAXMEM,
    )
    return "$".join(
        (
            "scrypt",
            str(_SCRYPT_N),
            str(_SCRYPT_R),
            str(_SCRYPT_P),
            _encode(salt),
            _encode(digest),
        )
    )


def verify_code(code: str, encoded: str | None) -> bool:
    if not encoded:
        return False
    try:
        algorithm, n_raw, r_raw, p_raw, salt_raw, digest_raw = encoded.split("$")
        if algorithm != "scrypt":
            return False
        expected = _decode(digest_raw)
        actual = hashlib.scrypt(
            code.encode("utf-8"),
            salt=_decode(salt_raw),
            n=int(n_raw),
            r=int(r_raw),
            p=int(p_raw),
            dklen=len(expected),
            maxmem=_SCRYPT_MAXMEM,
        )
    except (ValueError, TypeError):
        return False
    return secrets.compare_digest(actual, expected)


def create_session() -> str:
    token = secrets.token_urlsafe(32)
    with _state_lock:
        _sessions[_token_key(token)] = _UnlockSession(last_activity=_now())
    return token


def session_is_active(
    token: str | None,
    timeout_minutes: int,
    *,
    touch: bool = True,
) -> bool:
    if not token:
        return False
    timeout_seconds = validate_timeout(timeout_minutes) * 60
    now = _now()
    key = _token_key(token)
    with _state_lock:
        current = _sessions.get(key)
        if current is None:
            return False
        if now - current.last_activity >= timeout_seconds:
            _sessions.pop(key, None)
            return False
        if touch:
            current.last_activity = now
        return True


def revoke_session(token: str | None) -> None:
    if not token:
        return
    with _state_lock:
        _sessions.pop(_token_key(token), None)


def revoke_all_sessions() -> None:
    with _state_lock:
        _sessions.clear()


def unlock_retry_after(client_key: str) -> int | None:
    now = _now()
    with _state_lock:
        attempts = _active_attempts(client_key, now)
        if len(attempts) < _FAILED_ATTEMPT_LIMIT:
            return None
        return max(1, int(_FAILED_ATTEMPT_WINDOW_SECONDS - (now - attempts[0])))


def record_failed_unlock(client_key: str) -> int | None:
    now = _now()
    with _state_lock:
        attempts = _active_attempts(client_key, now)
        attempts.append(now)
        if len(attempts) < _FAILED_ATTEMPT_LIMIT:
            return None
        return max(1, int(_FAILED_ATTEMPT_WINDOW_SECONDS - (now - attempts[0])))


def clear_failed_unlocks(client_key: str) -> None:
    with _state_lock:
        _failed_attempts.pop(client_key, None)


def reset_runtime_state() -> None:
    """Clear process-local state. Intended for tests and controlled shutdowns."""
    with _state_lock:
        _sessions.clear()
        _failed_attempts.clear()


def _active_attempts(client_key: str, now: float) -> deque[float]:
    attempts = _failed_attempts.setdefault(client_key, deque())
    cutoff = now - _FAILED_ATTEMPT_WINDOW_SECONDS
    while attempts and attempts[0] <= cutoff:
        attempts.popleft()
    return attempts


def _token_key(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)
