"""Sandbox-safe instrument path normalization and allow-list checks."""

from __future__ import annotations

import posixpath
import re
from collections.abc import Sequence

_DRIVE_PREFIX = re.compile(r"^[A-Za-z]:")
_DRIVE_ABSOLUTE = re.compile(r"^[A-Za-z]:/")


def normalize_instrument_path(path: str) -> str:
    """Normalize separators and drive-letter casing for containment checks."""
    cleaned = path.strip()
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in ("'", '"'):
        cleaned = cleaned[1:-1].strip()
    if not cleaned:
        return ""
    cleaned = cleaned.replace("\\", "/")
    result = posixpath.normpath(cleaned)
    if _DRIVE_PREFIX.match(result):
        result = result.casefold()
    return result


def _raw_segments_contain_dotdot(path: str) -> bool:
    return any(seg == ".." for seg in path.split("/"))


def _is_absolute_instrument_path(path: str) -> bool:
    if path.startswith("/"):
        return True
    return _DRIVE_ABSOLUTE.match(path) is not None


def is_within_allowed(path: str, roots: Sequence[str]) -> bool:
    """Return True when *path* equals or is under an allowed instrument root."""
    if not path or "\0" in path:
        return False
    stripped = path.strip()
    if len(stripped) >= 2 and stripped[0] == stripped[-1] and stripped[0] in ("'", '"'):
        stripped = stripped[1:-1].strip()
    if not stripped:
        return False
    if "\0" in stripped:  # pragma: no cover -- NUL is already rejected on the raw path
        return False
    slash_path = stripped.replace("\\", "/")
    if not _is_absolute_instrument_path(slash_path):
        return False
    if _raw_segments_contain_dotdot(slash_path):
        return False
    normalized = normalize_instrument_path(stripped)
    if not normalized:
        return False
    for root in roots:
        allowed = normalize_instrument_path(root)
        if not allowed:
            continue
        prefix = allowed.rstrip("/") + "/"
        if normalized == allowed or normalized.startswith(prefix):
            return True
    return False


def quote_scpi_path(path: str) -> str:
    """Validate and SCPI-quote *path* for embedding in instrument commands.

    Rejects single quotes, double quotes, semicolons, CR/LF/NUL characters,
    and ``..`` path segments.  Returns the path wrapped in single quotes.
    """
    if not path or not path.strip():
        raise ValueError("path is required")
    if "'" in path:
        raise ValueError("path must not contain single quotes")
    if '"' in path:
        raise ValueError("path must not contain double quotes")
    if ";" in path:
        raise ValueError("path must not contain semicolons")
    if "\n" in path or "\r" in path or "\0" in path:
        raise ValueError("path contains illegal characters (CR/LF/NUL)")
    if any(seg == ".." for seg in path.replace("\\", "/").split("/")):
        raise ValueError("path must not contain '..' segments")
    return f"'{path}'"
