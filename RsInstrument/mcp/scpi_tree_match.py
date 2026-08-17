"""Pure SCPI help-header matching helpers for Instrument-SCPI-Exists."""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

MatchType = Literal["exact", "prefix", "fragment", "none"]

_MAX_FRAGMENT_MATCHES = 30


def normalize_tree_line_for_match(line: str) -> str:
    """Normalize a ``SYST:HELP:HEAD?`` entry for matching."""
    normalized = line.split("/", maxsplit=1)[0].strip()
    normalized = re.sub(r"<[^>]+>", "", normalized)
    normalized = re.sub(r"\{[^}]+\}", "", normalized)
    normalized = re.sub(r"\[([^\]]*)\]", r"\1", normalized)
    normalized = re.sub(r":+", ":", normalized).strip(": ").upper().rstrip("?")
    return normalized.strip()


def normalize_user_scpi_fragment(fragment: str) -> str:
    """Normalize a user SCPI fragment; strip trailing 1–2 digit repcaps on long nodes."""
    normalized = fragment.strip().rstrip("?").upper()
    parts: list[str] = []
    for part in normalized.split(":"):
        part = part.strip()
        if not part:
            continue
        match = re.fullmatch(r"([A-Z#]{4,})(\d{1,2})", part)
        if match:
            part = match.group(1)
        parts.append(part)
    return ":".join(parts)


def _is_ordered_subsequence(needle_nodes: list[str], haystack_nodes: list[str]) -> bool:
    """Return True when every needle node appears in order in haystack (non-contiguous)."""
    if not needle_nodes:
        return False
    i = 0
    for node in haystack_nodes:
        if node == needle_nodes[i]:
            i += 1
            if i == len(needle_nodes):
                return True
    return False


def find_fragment_matches(
    fragment: str,
    tree: Sequence[str],
    *,
    max_matches: int = _MAX_FRAGMENT_MATCHES,
) -> tuple[list[str], bool]:
    """Return original tree lines matching as ordered node subsequence; truncated flag."""
    needle = normalize_user_scpi_fragment(fragment)
    if not needle:
        return [], False
    needle_nodes = [n for n in needle.split(":") if n]
    matches: list[str] = []
    truncated = False
    for original in tree:
        hay = normalize_tree_line_for_match(original)
        hay_nodes = [n for n in hay.split(":") if n]
        if _is_ordered_subsequence(needle_nodes, hay_nodes):
            if len(matches) >= max_matches:
                truncated = True
                break
            matches.append(original)
    return matches, truncated


def find_longest_prefix_match(
    command_normalized: str,
    tree: Sequence[str],
) -> str | None:
    """Return the longest normalized tree header that is a path prefix of *command*."""
    best: str | None = None
    best_len = 0
    for original in tree:
        header = normalize_tree_line_for_match(original)
        if not header:
            continue
        if command_normalized == header:
            return original
        if (
            command_normalized.startswith(header)
            and len(command_normalized) > len(header)
            and command_normalized[len(header)] in (":", ";")
            and len(header) > best_len
        ):
            best = original
            best_len = len(header)
    return best


@dataclass(frozen=True)
class ScpiMatchResult:
    """Structured match result for Instrument-SCPI-Exists."""

    exists: bool
    matched_header: str | None
    matches: list[str]
    match_type: MatchType
    truncated: bool
    supported: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "exists": self.exists,
            "matched_header": self.matched_header,
            "matches": self.matches,
            "match_type": self.match_type,
            "truncated": self.truncated,
            "supported": self.supported,
        }


def match_scpi_command(
    command: str,
    tree: Sequence[str],
    *,
    max_fragment_matches: int = _MAX_FRAGMENT_MATCHES,
) -> ScpiMatchResult:
    """Exact → longest-prefix → ordered-subsequence fragment matching."""
    needle = normalize_user_scpi_fragment(command)
    if not needle:
        return ScpiMatchResult(
            exists=False,
            matched_header=None,
            matches=[],
            match_type="none",
            truncated=False,
            supported=True,
        )

    exact_hits = [
        original
        for original in tree
        if normalize_tree_line_for_match(original) == needle
    ]
    if exact_hits:
        return ScpiMatchResult(
            exists=True,
            matched_header=exact_hits[0],
            matches=exact_hits,
            match_type="exact",
            truncated=False,
            supported=True,
        )

    prefix = find_longest_prefix_match(needle, tree)
    if prefix is not None:
        return ScpiMatchResult(
            exists=True,
            matched_header=prefix,
            matches=[prefix],
            match_type="prefix",
            truncated=False,
            supported=True,
        )

    fragments, truncated = find_fragment_matches(
        needle,
        tree,
        max_matches=max_fragment_matches,
    )
    if fragments:
        return ScpiMatchResult(
            exists=True,
            matched_header=fragments[0],
            matches=fragments,
            match_type="fragment",
            truncated=truncated,
            supported=True,
        )

    return ScpiMatchResult(
        exists=False,
        matched_header=None,
        matches=[],
        match_type="none",
        truncated=False,
        supported=True,
    )


def normalize_scpi_header_lines(raw: str) -> list[str]:
    """Split and lightly normalize raw ``SYST:HELP:HEAD?`` text into lines."""
    lines: list[str] = []
    for line in raw.replace("\r\n", "\n").split("\n"):
        stripped = line.strip()
        if stripped:
            lines.append(stripped)
    return lines
