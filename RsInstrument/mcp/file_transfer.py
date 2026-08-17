"""Sandboxed stdio MMEM file-transfer policy and Instrument-File tool."""

from __future__ import annotations

import asyncio
import json
import re
import typing
from dataclasses import dataclass
from pathlib import Path

from RsInstrument import RsInstrument
from RsInstrument.mcp._common import safe_tool
from RsInstrument.mcp.scpi_write_policy import ScpiWritePolicy
from RsInstrument.mcp.write_elicitation import _authorize_write

_QUOTED_ENTRY = re.compile(r'"([^"]*)"' + r"|'([^']*)'")


@dataclass(frozen=True)
class CatalogEntry:
    """One entry of an ``MMEM:CATalog?`` response."""

    name: str
    kind: str
    size: int

    @property
    def is_dir(self) -> bool:
        return self.kind.upper() == "DIR"


@dataclass(frozen=True)
class FileTransferPolicy:
    """Local sandbox and instrument-path allow-list for Instrument-File."""

    enabled: bool
    local_root: Path | None
    instrument_allowed_dirs: tuple[str, ...]
    max_transfer_bytes: int = 64 * 1024 * 1024
    max_inline_read_bytes: int = 64 * 1024

    @classmethod
    def disabled(cls) -> FileTransferPolicy:
        return cls(enabled=False, local_root=None, instrument_allowed_dirs=())

    def __post_init__(self) -> None:
        if self.enabled and not self.instrument_allowed_dirs:
            raise ValueError(
                "instrument_allowed_dirs must be non-empty when file transfer is enabled"
            )


def normalize_instrument_path(path: str) -> str:
    """Normalize separators to ``/`` for containment checks (no host resolve)."""
    cleaned = path.replace("\\", "/").strip()
    while "//" in cleaned:
        cleaned = cleaned.replace("//", "/")
    return cleaned


def instrument_path_allowed(path: str, allowed_dirs: tuple[str, ...]) -> bool:
    """Return True when *path* equals or is under an allowed instrument root."""
    target = normalize_instrument_path(path)
    if not target or "\0" in target:
        return False
    segments = [s for s in target.split("/") if s not in ("",)]
    if any(seg in (".", "..") for seg in segments):
        return False
    for root in allowed_dirs:
        allowed = normalize_instrument_path(root).rstrip("/")
        if not allowed:
            continue
        if target == allowed or target.startswith(allowed + "/"):
            return True
    return False


def quote_instrument_path(path: str) -> str:
    """Validate and quote an instrument path for SCPI string literals."""
    if not path or not path.strip():
        raise ValueError("instrument_path is required")
    if "'" in path:
        raise ValueError("instrument_path must not contain single quotes")
    if "\n" in path or "\r" in path or "\0" in path:
        raise ValueError("instrument_path contains illegal characters")
    return f"'{path}'"


def resolve_local_path(local_root: Path, relative: str) -> Path:
    """Resolve a path under *local_root*; reject escapes and absolute inputs."""
    if not relative or not relative.strip():
        raise ValueError("local_path is required")
    candidate = Path(relative)
    if candidate.is_absolute():
        raise ValueError("local_path must be relative to the configured file root")
    root = local_root.resolve()
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("local_path escapes the configured file root") from exc
    return resolved


def parse_catalog(raw: str) -> tuple[int | None, int | None, list[CatalogEntry]]:
    """Parse an ``MMEM:CATalog?`` response."""
    raw = raw.strip()
    entries: list[CatalogEntry] = []
    first_quote_pos: int | None = None
    for match in _QUOTED_ENTRY.finditer(raw):
        if first_quote_pos is None:
            first_quote_pos = match.start()
        quoted = match.group(1) if match.group(1) is not None else match.group(2)
        parts = quoted.rsplit(",", 2)
        if len(parts) == 3 and parts[2].strip().lstrip("-").isdigit():
            name, kind, size_str = parts
            entries.append(
                CatalogEntry(name=name, kind=kind.strip(), size=int(size_str))
            )
        else:
            entries.append(CatalogEntry(name=quoted, kind="", size=0))

    head = raw if first_quote_pos is None else raw[:first_quote_pos]
    numbers = [p.strip() for p in head.split(",") if p.strip().lstrip("-").isdigit()]
    used = int(numbers[0]) if len(numbers) >= 1 else None
    free = int(numbers[1]) if len(numbers) >= 2 else None
    return used, free, entries


def make_instrument_file(
    file_transfer: FileTransferPolicy | None = None,
    write_policy: ScpiWritePolicy | None = None,
) -> typing.Callable[..., typing.Any]:
    """Build sandboxed ``Instrument-File`` (registered even when disabled)."""
    policy = file_transfer or FileTransferPolicy.disabled()
    write = write_policy or ScpiWritePolicy.defaults()

    @safe_tool
    async def instrument_file(
        ctx: typing.Any,
        action: typing.Literal[
            "list", "exists", "download", "upload", "read", "delete"
        ],
        resource: str,
        instrument_path: str = "",
        local_path: str = "",
        confirm: bool = False,
        opc_timeout: int = 10000,
    ) -> typing.Any:
        """MMEM file operations under FileTransferPolicy sandbox."""
        if not policy.enabled or policy.local_root is None:
            return json.dumps(
                {
                    "status": "file_transfer_disabled",
                    "message": (
                        "Instrument-File requires stdio transport and "
                        "--file-root / --instrument-file-root (or BuiltinToolSettings)."
                    ),
                }
            )

        if action == "list" and not instrument_path.strip():
            instrument_path = policy.instrument_allowed_dirs[0]
        if not instrument_path.strip():
            raise ValueError("instrument_path is required")
        if action in ("download", "upload") and not local_path.strip():
            raise ValueError("local_path is required for download/upload")

        if not instrument_path_allowed(instrument_path, policy.instrument_allowed_dirs):
            raise ValueError(
                "instrument_path is outside the configured instrument-file-root allow-list"
            )

        quoted = quote_instrument_path(instrument_path)

        if action in ("upload", "delete"):
            auth_cmd = (
                f"MMEMory:DATA {quoted},#0"
                if action == "upload"
                else f"MMEMory:DELete {quoted}"
            )
            decision = await _authorize_write(
                ctx,
                command=auth_cmd,
                resource=resource,
                confirm=confirm,
                policy=write,
            )
            if decision is not None:
                return decision

        def _run() -> str:
            local: Path | None = None
            if action in ("download", "upload"):
                local = resolve_local_path(policy.local_root, local_path)  # type: ignore[arg-type]

            with RsInstrument(resource) as inst:
                inst.opc_timeout = opc_timeout
                if action == "list":
                    query = f"MMEMory:CATalog? {quoted}"
                    raw = inst.query(query)
                    used, free, entries = parse_catalog(raw)
                    return json.dumps(
                        {
                            "directory": instrument_path,
                            "used_bytes": used,
                            "free_bytes": free,
                            "entries": [
                                {
                                    "name": e.name,
                                    "kind": e.kind,
                                    "size": e.size,
                                    "is_dir": e.is_dir,
                                }
                                for e in entries
                                if e.name not in (".", "..")
                            ],
                        }
                    )
                if action == "exists":
                    exists = inst.file_exists(instrument_path)
                    return json.dumps(
                        {"instrument_path": instrument_path, "exists": bool(exists)}
                    )
                if action == "download":
                    assert local is not None
                    size = inst.get_file_size(instrument_path)
                    if size is not None and size > policy.max_transfer_bytes:
                        raise ValueError(
                            f"File size {size} exceeds max_transfer_bytes "
                            f"{policy.max_transfer_bytes}"
                        )
                    local.parent.mkdir(parents=True, exist_ok=True)
                    inst.read_file_from_instrument_to_pc(instrument_path, str(local))
                    return json.dumps(
                        {
                            "status": "downloaded",
                            "instrument_path": instrument_path,
                            "local_path": str(local),
                        }
                    )
                if action == "upload":
                    assert local is not None
                    if not local.is_file():
                        raise FileNotFoundError(f"Local file not found: {local}")
                    size = local.stat().st_size
                    if size > policy.max_transfer_bytes:
                        raise ValueError(
                            f"Local file size {size} exceeds max_transfer_bytes "
                            f"{policy.max_transfer_bytes}"
                        )
                    inst.send_file_from_pc_to_instrument(str(local), instrument_path)
                    return json.dumps(
                        {
                            "status": "uploaded",
                            "instrument_path": instrument_path,
                            "local_path": str(local),
                        }
                    )
                if action == "read":
                    size = inst.get_file_size(instrument_path)
                    if size is not None and size > policy.max_inline_read_bytes:
                        raise ValueError(
                            f"File size {size} exceeds max_inline_read_bytes "
                            f"{policy.max_inline_read_bytes}; use download"
                        )
                    data = inst.query_bin_block(f"MMEMory:DATA? {quoted}")
                    if len(data) > policy.max_inline_read_bytes:
                        raise ValueError(
                            f"Read payload exceeds max_inline_read_bytes "
                            f"{policy.max_inline_read_bytes}"
                        )
                    text = data.decode("utf-8", errors="replace")
                    return json.dumps(
                        {
                            "instrument_path": instrument_path,
                            "text": text,
                            "bytes": len(data),
                        }
                    )
                if action == "delete":
                    inst.write(f"MMEMory:DELete {quoted}")
                    return json.dumps(
                        {"status": "deleted", "instrument_path": instrument_path}
                    )
                raise ValueError(f"Unsupported action: {action!r}")

        return await asyncio.to_thread(_run)

    return instrument_file
