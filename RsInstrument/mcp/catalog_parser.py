"""Tolerant parser for MMEMory:CATalog? and related catalog response shapes."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

_QUOTED_ENTRY = re.compile(r'"([^"]*)"' + r"|'([^']*)'")
_SIZE_RE = re.compile(r"^-?\d+$")
_DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}|\d{2}[./]\d{2}[./]\d{4})$")
_TIME_RE = re.compile(r"^\d{1,2}:\d{2}(:\d{2})?$")
_DATETIME_RE = re.compile(
    r"^(\d{4}-\d{2}-\d{2}|\d{2}[./]\d{2}[./]\d{4})\s+(\d{1,2}:\d{2}(:\d{2})?)$"
)
_ATTR_RE = re.compile(r"^[rwxdahs-]{1,6}$", re.IGNORECASE)


@dataclass(frozen=True)
class CatalogEntry:
    name: str
    is_dir: bool | None  # None = unknown (plain-name format without path separator)
    size: int | None
    kind: str = ""
    modified: str | None = None
    attributes: str | None = None
    parse_status: Literal["ok", "unparsed"] = "ok"
    raw: str = ""


@dataclass(frozen=True)
class CatalogResult:
    used_bytes: int | None
    free_bytes: int | None
    entries: tuple[CatalogEntry, ...]
    format: Literal["empty", "quoted_fields", "plain_names", "unparsed"]
    warnings: tuple[str, ...]


def _is_type_token(token: str) -> bool:
    stripped = token.strip()
    if not stripped:
        return True
    if len(stripped) > 8:
        return False
    inner = stripped.strip("<>")
    return inner.isalnum()


def _type_indicates_dir(kind: str) -> bool:
    normalized = kind.strip().strip("<>").upper()
    return normalized == "DIR"


def _attributes_indicate_dir(attributes: str | None) -> bool:
    if not attributes:
        return False
    if attributes[0] in ("d", "D"):
        return True
    return "D" in attributes


def _resolve_is_dir(kind: str, size: int | None, attributes: str | None) -> bool:
    if _type_indicates_dir(kind):
        return True
    if _attributes_indicate_dir(attributes):
        return True
    if not kind.strip() and size is not None:
        return False
    return False


def _parse_head_integers(raw: str, first_quote_pos: int | None) -> tuple[int | None, int | None, str]:
    head = raw if first_quote_pos is None else raw[:first_quote_pos]
    head = head.strip().rstrip(",")
    if not head:
        return None, None, head
    tokens = [p.strip() for p in head.split(",") if p.strip()]
    numbers: list[int] = []
    rest_start = 0
    for idx, token in enumerate(tokens):
        if token.lstrip("-").isdigit():
            numbers.append(int(token))
            rest_start = idx + 1
        else:
            break
    used = numbers[0] if len(numbers) >= 1 else None
    free = numbers[1] if len(numbers) >= 2 else None
    rest = ",".join(tokens[rest_start:]) if rest_start < len(tokens) else ""
    return used, free, rest


def _looks_like_attributes(token: str) -> bool:
    return "-" in token and bool(_ATTR_RE.match(token))


def _parse_quoted_content(content: str) -> tuple[CatalogEntry, tuple[str, ...]]:
    warnings: list[str] = []
    raw = content
    parts = content.split(",")
    size: int | None = None
    kind = ""
    modified: str | None = None
    attributes: str | None = None
    saw_trailing_meta = False

    while len(parts) > 1:
        tail = parts[-1]
        tail_stripped = tail.strip()

        if _looks_like_attributes(tail_stripped) and (
            saw_trailing_meta
            or (
                len(parts) >= 2
                and (
                    _TIME_RE.match(parts[-2].strip())
                    or _DATE_RE.match(parts[-2].strip())
                    or _DATETIME_RE.match(parts[-2].strip())
                )
            )
        ):
            attributes = tail_stripped
            parts.pop()
            saw_trailing_meta = True
            continue

        if _DATETIME_RE.match(tail_stripped):
            modified = tail_stripped
            parts.pop()
            saw_trailing_meta = True
            continue

        if (
            len(parts) >= 2
            and _TIME_RE.match(parts[-1].strip())
            and _DATE_RE.match(parts[-2].strip())
        ):
            modified = f"{parts[-2].strip()} {parts[-1].strip()}"
            parts.pop()
            parts.pop()
            saw_trailing_meta = True
            continue

        if _TIME_RE.match(tail_stripped) and (
            saw_trailing_meta
            or (
                len(parts) >= 2
                and _SIZE_RE.match(parts[-2].strip())
            )
        ):
            if modified and _DATE_RE.match(modified):
                modified = f"{modified} {tail_stripped}"
            else:
                modified = tail_stripped
            parts.pop()
            saw_trailing_meta = True
            continue

        if _DATE_RE.match(tail_stripped):
            if modified and _TIME_RE.match(modified):
                modified = f"{tail_stripped} {modified}"
            else:
                modified = tail_stripped
            parts.pop()
            saw_trailing_meta = True
            continue

        if _SIZE_RE.match(tail_stripped):
            size = int(tail_stripped)
            parts.pop()
            saw_trailing_meta = True
            continue

        if (
            tail_stripped
            and not _SIZE_RE.match(tail_stripped)
            and len(parts) == 3
            and _is_type_token(parts[-2].strip())
        ):
            warnings.append(
                f"non-numeric size field '{tail_stripped}' treated as absent"
            )
            parts.pop()
            saw_trailing_meta = True
            continue

        if (tail_stripped == "" or _is_type_token(tail)) and (
            saw_trailing_meta or len(parts) == 2
        ):
            kind = tail_stripped
            parts.pop()
            saw_trailing_meta = True
            continue

        if tail_stripped == "" and not saw_trailing_meta and len(parts) >= 2:
            parts.pop()
            size = None
            saw_trailing_meta = True
            continue

        break

    name = ",".join(parts).strip()
    if not name and content:
        return (
            CatalogEntry(
                name="",
                is_dir=False,
                size=size,
                kind=kind,
                modified=modified,
                attributes=attributes,
                parse_status="unparsed",
                raw=raw,
            ),
            tuple(warnings) + ("could not determine entry name",),
        )

    if not name and not content:
        return (
            CatalogEntry(
                name="",
                is_dir=False,
                size=None,
                parse_status="unparsed",
                raw=raw,
            ),
            ("empty quoted catalog entry",),
        )

    is_dir = _resolve_is_dir(kind, size, attributes)

    return (
        CatalogEntry(
            name=name,
            is_dir=is_dir,
            size=size,
            kind=kind,
            modified=modified,
            attributes=attributes,
            parse_status="ok",
            raw=raw,
        ),
        tuple(warnings),
    )


def parse_catalog(raw: str) -> CatalogResult:
    """Parse an instrument catalog response into structured entries."""
    text = raw.strip()
    warnings: list[str] = []

    if not text:
        return CatalogResult(None, None, (), "empty", ())

    if text.startswith("#"):
        return CatalogResult(
            None,
            None,
            (),
            "unparsed",
            ("catalog response looks like SCPI block data, not a field list",),
        )

    quoted_matches: list[str] = []
    first_quote_pos: int | None = None
    for match in _QUOTED_ENTRY.finditer(text):
        if first_quote_pos is None:
            first_quote_pos = match.start()
        quoted = match.group(1) if match.group(1) is not None else match.group(2)
        quoted_matches.append(quoted)

    used, free, head_rest = _parse_head_integers(text, first_quote_pos)

    if quoted_matches:
        entries: list[CatalogEntry] = []
        for quoted in quoted_matches:
            entry, entry_warnings = _parse_quoted_content(quoted)
            entries.append(entry)
            warnings.extend(entry_warnings)
        return CatalogResult(
            used,
            free,
            tuple(entries),
            "quoted_fields",
            tuple(warnings),
        )

    if head_rest.strip():
        plain_tokens = [t.strip() for t in head_rest.split(",") if t.strip()]
        if plain_tokens:
            warnings.append(
                "plain file names without quoted metadata; type and size are unavailable; "
                "is_dir is unknown unless the name ends with a path separator"
            )
            plain_entries = tuple(
                CatalogEntry(
                    name=token,
                    is_dir=True if token.endswith(("/", "\\")) else None,
                    size=None,
                    kind="",
                    parse_status="ok",
                    raw=token,
                )
                for token in plain_tokens
            )
            return CatalogResult(
                used,
                free,
                plain_entries,
                "plain_names",
                tuple(warnings),
            )
        # head_rest was non-empty (e.g. commas/spaces only) but yielded no tokens:
        # the response had unrecognized content that could not be parsed into entries.
        warnings.append(
            "catalog response contained unrecognized non-entry content after the header"
        )
        return CatalogResult(used, free, (), "unparsed", tuple(warnings))

    return CatalogResult(used, free, (), "empty", tuple(warnings))


def catalog_entry_to_json(entry: CatalogEntry) -> dict[str, object]:
    """Serialize a catalog entry for Instrument-File list responses."""
    payload: dict[str, object] = {
        "name": entry.name,
        "is_dir": entry.is_dir,
        "size": entry.size,
        "kind": entry.kind,
        "modified": entry.modified,
        "attributes": entry.attributes,
        "parse_status": entry.parse_status,
    }
    if entry.parse_status == "unparsed":
        payload["raw"] = entry.raw
    return payload
