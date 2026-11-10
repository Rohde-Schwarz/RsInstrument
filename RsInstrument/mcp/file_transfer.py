"""Sandboxed stdio MMEM file-transfer policy and Instrument-File tool."""

from __future__ import annotations

import asyncio
import re
import threading
import time
import typing
from dataclasses import dataclass
from pathlib import Path

from RsInstrument import RsInstrument
from RsInstrument.Internal.InstrumentErrors import RsInstrException
from RsInstrument.mcp._common import safe_tool
from RsInstrument.mcp.catalog_parser import (
    CatalogEntry,
    catalog_entry_to_json,
    parse_catalog,
)
from RsInstrument.mcp.instrument_paths import (
    is_within_allowed,
    normalize_instrument_path,
    quote_scpi_path,
)
from RsInstrument.mcp.scpi_write_policy import ScpiWritePolicy
from RsInstrument.mcp.write_elicitation import _authorize_write

__all__ = [
    "CatalogEntry",
    "FileTransferPolicy",
    "catalog_entry_to_json",
    "clear_cdir_cache",
    "clear_pinned_roots",
    "invalidate_cdir_cache",
    "make_instrument_file",
    "parse_catalog",
    "query_default_directory",
    "quote_instrument_path",
    "resolve_local_path",
]

try:
    from fastmcp import Context
except ImportError:
    Context = None  # type: ignore[assignment,misc]

_CDIR_QUERY_TIMEOUT_MS = 2000
_CDIR_CACHE_TTL_S = 30.0
_CDIR_FAILED_CACHE_TTL_S = 2.0
_INSTRUMENT_IO_ERRORS = (RsInstrException, OSError, TimeoutError)

_cdir_cache: dict[str, tuple[str | None, float]] = {}
_cdir_cache_lock = threading.Lock()

_pinned_roots: dict[str, str] = {}
_pinned_roots_lock = threading.Lock()


def _resource_key(resource: str) -> str:
    """Canonical cache key for a VISA resource string."""
    return resource.strip().casefold()


@dataclass(frozen=True)
class FileTransferPolicy:
    """Local sandbox and instrument-path allow-list for Instrument-File."""

    enabled: bool
    local_root: Path | None
    instrument_allowed_dirs: tuple[str, ...]
    max_transfer_bytes: int = 64 * 1024 * 1024
    max_inline_read_bytes: int = 64 * 1024
    auto_allow_default_dir: bool = False

    @classmethod
    def disabled(cls) -> FileTransferPolicy:
        return cls(enabled=False, local_root=None, instrument_allowed_dirs=())

    def __post_init__(self) -> None:
        if self.enabled and not self.instrument_allowed_dirs and not self.auto_allow_default_dir:
            raise ValueError(
                "instrument_allowed_dirs must be non-empty when file transfer is enabled "
                "(unless auto_allow_default_dir is True)"
            )


def clear_pinned_roots() -> None:
    """Clear all auto-pinned instrument roots (for tests)."""
    with _pinned_roots_lock:
        _pinned_roots.clear()


def clear_cdir_cache() -> None:
    """Clear the process-local MMEM CDIR cache (for tests)."""
    with _cdir_cache_lock:
        _cdir_cache.clear()
    clear_pinned_roots()


def invalidate_cdir_cache(resource: str) -> None:
    """Drop cached CDIR for *resource* (e.g. after *RST*).

    The auto-pinned root for *resource* is intentionally NOT cleared here;
    the sandbox boundary must survive *RST or later CDIR changes.
    """
    with _cdir_cache_lock:
        _cdir_cache.pop(_resource_key(resource), None)


def query_default_directory(inst: RsInstrument) -> str | None:
    """Query ``MMEM:CDIR?`` with a short timeout; return None on failure."""
    previous_visa = inst.visa_timeout
    previous_opc = inst.opc_timeout
    try:
        inst.visa_timeout = _CDIR_QUERY_TIMEOUT_MS
        inst.opc_timeout = _CDIR_QUERY_TIMEOUT_MS
        try:
            raw = inst.query("MMEM:CDIR?")
        except _INSTRUMENT_IO_ERRORS:
            return None
        path = normalize_instrument_path(raw.strip())
        if not path:
            return None
        try:
            err_raw = inst.query("SYST:ERR?")
        except _INSTRUMENT_IO_ERRORS:
            return None
        code_str = err_raw.split(",", 1)[0].strip()
        if not code_str.lstrip("-").isdigit():
            return None
        if int(code_str) != 0:
            return None
        return path
    finally:
        inst.visa_timeout = previous_visa
        inst.opc_timeout = previous_opc


def _get_cached_cdir(resource: str, inst: RsInstrument) -> str | None:
    key = _resource_key(resource)
    with _cdir_cache_lock:
        entry = _cdir_cache.get(key)
        if entry is not None:
            value, stored_at = entry
            ttl = _CDIR_FAILED_CACHE_TTL_S if value is None else _CDIR_CACHE_TTL_S
            if (time.monotonic() - stored_at) <= ttl:
                return value
    value = query_default_directory(inst)
    with _cdir_cache_lock:
        _cdir_cache[key] = (value, time.monotonic())
    return value


def _get_or_create_pin(resource: str, cdir: str) -> str:
    """Return the existing auto-pinned root for *resource*, or pin *cdir* now."""
    key = _resource_key(resource)
    with _pinned_roots_lock:
        if key not in _pinned_roots:
            _pinned_roots[key] = cdir
        return _pinned_roots[key]


_BARE_DRIVE = re.compile(r"^[a-z]:$")
_UNC_PREFIX = re.compile(r"^//")


def _is_filesystem_root(path: str) -> bool:
    """Return True when *path* normalizes to a filesystem root.

    Roots are ``/``, bare drive letters like ``c:``, empty strings, and UNC
    server or server/share paths (``//server`` or ``//server/share``).
    """
    if not path:
        return True
    n = normalize_instrument_path(path)
    if not n:
        return True
    if n == "/":
        return True
    if _BARE_DRIVE.match(n):
        return True
    if _UNC_PREFIX.match(n):
        # //server and //server/share are UNC roots; deeper paths are not.
        parts = [p for p in n[2:].split("/") if p]
        return len(parts) <= 2
    return False


def _mmem_unsupported_dict(resource: str, message: str | None = None) -> dict[str, str]:
    return {
        "status": "mmem_unsupported",
        "resource": resource,
        "message": message
        or "Instrument does not support MMEM directory queries (MMEM:CDIR?).",
    }


def _unsafe_default_dir_dict(resource: str, cdir: str | None) -> dict[str, typing.Any]:
    return {
        "status": "unsafe_default_directory",
        "default_directory": cdir,
        "message": (
            "Instrument default directory is a filesystem root; "
            "configure explicit --instrument-file-root."
        ),
    }


def _pick_list_directory(
    policy: FileTransferPolicy,
    effective_dirs: tuple[str, ...],
    cdir: str | None,
) -> str:
    if cdir is not None and is_within_allowed(cdir, effective_dirs):
        return cdir
    return effective_dirs[0]


def quote_instrument_path(path: str) -> str:
    """Validate and quote an instrument path for SCPI string literals."""
    if not path or not path.strip():
        raise ValueError("instrument_path is required")
    return quote_scpi_path(path)


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


def make_instrument_file(
    file_transfer: FileTransferPolicy | None = None,
    write_policy: ScpiWritePolicy | None = None,
) -> typing.Callable[..., typing.Any]:
    """Build sandboxed ``Instrument-File`` (registered even when disabled)."""
    policy = file_transfer or FileTransferPolicy.disabled()
    write = write_policy or ScpiWritePolicy.defaults()

    @safe_tool
    async def instrument_file(
        ctx: Context,
        action: typing.Literal[
            "list", "exists", "download", "upload", "read", "delete", "info"
        ],
        resource: str,
        instrument_path: str = "",
        local_path: str = "",
        opc_timeout: int = 10000,
    ) -> typing.Any:
        """MMEM file operations under FileTransferPolicy sandbox."""
        if not policy.enabled or policy.local_root is None:
            return {
                "status": "file_transfer_disabled",
                "message": (
                    "Instrument-File requires stdio transport and "
                    "--file-root / --instrument-file-root (or BuiltinToolSettings)."
                ),
            }

        if action in ("download", "upload") and not local_path.strip():
            raise ValueError("local_path is required for download/upload")

        if action != "info" and action != "list" and not instrument_path.strip():
            raise ValueError("instrument_path is required")

        # For explicit allow-list: validate path BEFORE _authorize_write.
        if (
            instrument_path.strip()
            and policy.instrument_allowed_dirs
            and not is_within_allowed(instrument_path, policy.instrument_allowed_dirs)
        ):
            raise ValueError(
                "instrument_path is outside the configured instrument-file-root allow-list"
            )

        # For auto mode upload/delete: resolve CDIR/pin BEFORE authorization so
        # the allow-list check happens before the user is ever prompted.
        if (
            action in ("upload", "delete")
            and policy.auto_allow_default_dir
            and not policy.instrument_allowed_dirs
            and instrument_path.strip()
        ):
            def _fetch_cdir_for_auth() -> str | None:
                with RsInstrument(resource) as inst:
                    return _get_cached_cdir(resource, inst)

            pre_cdir = await asyncio.to_thread(_fetch_cdir_for_auth)
            if pre_cdir is None:
                return _mmem_unsupported_dict(resource)
            if _is_filesystem_root(pre_cdir):
                return _unsafe_default_dir_dict(resource, pre_cdir)
            pre_pin = _get_or_create_pin(resource, pre_cdir)
            if not is_within_allowed(instrument_path, (pre_pin,)):
                raise ValueError(
                    "instrument_path is outside the configured "
                    "instrument-file-root allow-list"
                )

        if action in ("upload", "delete"):
            auth_cmd = (
                f"MMEMory:DATA {quote_instrument_path(instrument_path)},#0"
                if action == "upload"
                else f"MMEMory:DELete {quote_instrument_path(instrument_path)}"
            )
            decision = await _authorize_write(
                ctx,
                command=auth_cmd,
                resource=resource,
                policy=write,
            )
            if decision is not None:
                return decision

        def _run() -> dict[str, typing.Any]:
            local: Path | None = None
            if action in ("download", "upload"):
                local = resolve_local_path(policy.local_root, local_path)  # type: ignore[arg-type]

            try:
                with RsInstrument(resource) as inst:
                    inst.opc_timeout = opc_timeout
                    needs_cdir = (
                        action == "info"
                        or (action == "list" and not instrument_path.strip())
                        or (
                            policy.auto_allow_default_dir
                            and not policy.instrument_allowed_dirs
                        )
                    )
                    cdir: str | None = None
                    if needs_cdir:
                        cdir = _get_cached_cdir(resource, inst)

                    # Build effective allowed directories with auto-pinning.
                    effective: tuple[str, ...]
                    if policy.instrument_allowed_dirs:
                        effective = policy.instrument_allowed_dirs
                    elif policy.auto_allow_default_dir:
                        if cdir is None:
                            return _mmem_unsupported_dict(resource)
                        if _is_filesystem_root(cdir):
                            return _unsafe_default_dir_dict(resource, cdir)
                        pinned = _get_or_create_pin(resource, cdir)
                        effective = (pinned,)
                    else:  # pragma: no cover -- enabled policy always has dirs or auto_allow
                        return _mmem_unsupported_dict(resource)

                    resolved_path = instrument_path
                    if action == "list" and not resolved_path.strip():
                        resolved_path = _pick_list_directory(policy, effective, cdir)

                    if action == "info":
                        return {
                            "mmem_supported": cdir is not None,
                            "default_directory": cdir,
                            "allowed_dirs": list(effective),
                        }

                    if not resolved_path.strip():  # pragma: no cover -- gated before _run
                        raise ValueError("instrument_path is required")
                    if not is_within_allowed(resolved_path, effective):
                        raise ValueError(
                            "instrument_path is outside the configured "
                            "instrument-file-root allow-list"
                        )

                    quoted = quote_instrument_path(resolved_path)

                    if action == "list":
                        try:
                            query = f"MMEMory:CATalog? {quoted}"
                            raw = inst.query(query)
                            catalog = parse_catalog(raw)
                        except _INSTRUMENT_IO_ERRORS:
                            return _mmem_unsupported_dict(resource)
                        _dot_entries = [e for e in catalog.entries if e.name in (".", "..")]
                        _visible_entries = [e for e in catalog.entries if e.name not in (".", "..")]
                        return {
                            "directory": resolved_path,
                            "used_bytes": catalog.used_bytes,
                            "free_bytes": catalog.free_bytes,
                            "format": catalog.format,
                            "warnings": list(catalog.warnings),
                            "skipped_entries": len(_dot_entries),
                            "entries": [catalog_entry_to_json(e) for e in _visible_entries],
                        }
                    if action == "exists":
                        exists = inst.file_exists(resolved_path)
                        return {
                            "instrument_path": resolved_path,
                            "exists": bool(exists),
                        }
                    if action == "download":
                        assert local is not None
                        size = inst.get_file_size(resolved_path)
                        if size is not None and size > policy.max_transfer_bytes:
                            raise ValueError(
                                f"File size {size} exceeds max_transfer_bytes "
                                f"{policy.max_transfer_bytes}"
                            )
                        local.parent.mkdir(parents=True, exist_ok=True)
                        inst.read_file_from_instrument_to_pc(resolved_path, str(local))
                        return {
                            "status": "downloaded",
                            "instrument_path": resolved_path,
                            "local_path": str(local),
                        }
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
                        inst.send_file_from_pc_to_instrument(str(local), resolved_path)
                        return {
                            "status": "uploaded",
                            "instrument_path": resolved_path,
                            "local_path": str(local),
                        }
                    if action == "read":
                        size = inst.get_file_size(resolved_path)
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
                        return {
                            "instrument_path": resolved_path,
                            "text": text,
                            "bytes": len(data),
                        }
                    if action == "delete":
                        inst.write(f"MMEMory:DELete {quoted}")
                        return {"status": "deleted", "instrument_path": resolved_path}
                    raise ValueError(f"Unsupported action: {action!r}")
            except ValueError:
                raise
            except _INSTRUMENT_IO_ERRORS:
                invalidate_cdir_cache(resource)
                raise

        return await asyncio.to_thread(_run)

    return instrument_file
