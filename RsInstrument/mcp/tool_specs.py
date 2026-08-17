"""ToolSpec model, BuiltinToolSettings, and builtin tool registration."""

from __future__ import annotations

import typing
from collections.abc import Collection
from dataclasses import dataclass, field

from pydantic import BaseModel, ConfigDict

if typing.TYPE_CHECKING:
    from fastmcp import FastMCP
else:
    try:
        from fastmcp import FastMCP
    except ImportError:
        FastMCP = None  # type: ignore[misc, assignment]

from RsInstrument.mcp._common import (
    ANN_DESTRUCTIVE_IDEMPOTENT,
    ANN_READONLY,
    ANN_STATE_CHANGE,
    ANN_WRITE,
)
from RsInstrument.mcp.basic_tools import (
    instrument_discovery,
    instrument_fetch_errors,
    instrument_query_scpi,
    instrument_scpi_exists,
    make_instrument_reset,
    make_instrument_write_scpi,
)
from RsInstrument.mcp.batch import ScpiBatchPolicy, make_instrument_batch_scpi
from RsInstrument.mcp.device_io import (
    DeviceIoProfileRegistry,
    instrument_go_to_local,
    make_instrument_enable_user_interaction,
    make_instrument_get_screenshot,
)
from RsInstrument.mcp.file_transfer import FileTransferPolicy, make_instrument_file
from RsInstrument.mcp.scpi_write_policy import ScpiWritePolicy
from RsInstrument.mcp.state_storage import make_instrument_save_recall


class ToolSpec(BaseModel):
    """Specification for registering an MCP tool (built-in or custom)."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    name: str
    description: str
    fn: typing.Callable[..., typing.Any]
    annotations: dict[str, typing.Any] | None = None


ToolInput = tuple[str, str, typing.Callable[..., typing.Any]] | ToolSpec


@dataclass(frozen=True)
class BuiltinToolSettings:
    """Immutable aggregate for builtin MCP tool configuration."""

    write_policy: ScpiWritePolicy = field(default_factory=ScpiWritePolicy.defaults)
    batch_policy: ScpiBatchPolicy = field(default_factory=ScpiBatchPolicy.defaults)
    device_profiles: DeviceIoProfileRegistry = field(
        default_factory=DeviceIoProfileRegistry.defaults
    )
    file_transfer: FileTransferPolicy = field(
        default_factory=FileTransferPolicy.disabled
    )
    excluded_tools: frozenset[str] = frozenset()

    @classmethod
    def create(
        cls,
        *,
        write_policy: ScpiWritePolicy | None = None,
        batch_policy: ScpiBatchPolicy | None = None,
        device_profiles: DeviceIoProfileRegistry | None = None,
        file_transfer: FileTransferPolicy | None = None,
        excluded_tools: Collection[str] = (),
        excluded_write_rule_ids: Collection[str] = (),
    ) -> BuiltinToolSettings:
        """Resolve defaults; apply rule exclusion only to builtin default policy."""
        if write_policy is None:
            resolved_write = ScpiWritePolicy.defaults(
                exclude_rule_ids=excluded_write_rule_ids,
            )
        else:
            resolved_write = write_policy
        return cls(
            write_policy=resolved_write,
            batch_policy=batch_policy or ScpiBatchPolicy.defaults(),
            device_profiles=device_profiles or DeviceIoProfileRegistry.defaults(),
            file_transfer=file_transfer or FileTransferPolicy.disabled(),
            excluded_tools=frozenset(excluded_tools),
        )


def _normalize_tool(item: ToolInput) -> ToolSpec:
    """Convert legacy tuple tools to :class:`ToolSpec`."""
    if isinstance(item, ToolSpec):
        return item
    name, description, fn = item
    return ToolSpec(name=name, description=description, fn=fn)


def merge_tool_specs(
    *groups: typing.Sequence[ToolInput] | None,
) -> list[ToolSpec]:
    """Concatenate tool groups into one list.

    Later entries with the same ``name`` replace earlier ones (last wins),
    preserving first-seen order for unique names.
    """
    by_name: dict[str, ToolSpec] = {}
    order: list[str] = []
    for group in groups:
        if not group:
            continue
        for item in group:
            spec = _normalize_tool(item)
            if spec.name not in by_name:
                order.append(spec.name)
            by_name[spec.name] = spec
    return [by_name[name] for name in order]


def create_builtin_tool_specs(
    settings: BuiltinToolSettings | None = None,
) -> list[ToolSpec]:
    """Create ToolSpecs for built-in RsInstrument MCP tools.

    Each call returns **new** callables closed over ``settings`` (write / batch /
    device / file policies). Prefer this — or ``add_builtin_tools`` / ``run``,
    which call it — over importing module-level aliases such as
    ``basic_tools.instrument_write_scpi``, which always use default write rules.
    """
    cfg = settings or BuiltinToolSettings.create()
    policy = cfg.write_policy
    specs = [
        ToolSpec(
            name="Instrument-Query-SCPI",
            description="Query a command from an instrument via RsInstrument.",
            fn=instrument_query_scpi,
            annotations=ANN_READONLY,
        ),
        ToolSpec(
            name="Instrument-Write-SCPI",
            description=(
                "Write a command to an instrument via RsInstrument. "
                "Dangerous writes may require user confirmation (elicitation) "
                "or confirm=true."
            ),
            fn=make_instrument_write_scpi(policy),
            annotations=ANN_WRITE,
        ),
        ToolSpec(
            name="Instrument-Fetch-Errors",
            description="Fetch errors from an instrument via RsInstrument.",
            fn=instrument_fetch_errors,
            annotations=ANN_WRITE,
        ),
        ToolSpec(
            name="Instrument-Reset",
            description=("Reset the instrument. Requires confirmation (*RST policy)."),
            fn=make_instrument_reset(policy),
            annotations=ANN_DESTRUCTIVE_IDEMPOTENT,
        ),
        ToolSpec(
            name="Instrument-Go-To-Local",
            description="Restore local front-panel control (GTL).",
            fn=instrument_go_to_local,
            annotations=ANN_STATE_CHANGE,
        ),
        ToolSpec(
            name="Instrument-Enable-User-Interaction",
            description=(
                "Enable front-panel/display interaction for the instrument family "
                "while keeping the remote SCPI session usable."
            ),
            fn=make_instrument_enable_user_interaction(cfg.device_profiles),
            annotations=ANN_STATE_CHANGE,
        ),
        ToolSpec(
            name="Instrument-Get-Screenshot",
            description="Capture a PNG screenshot from the instrument display.",
            fn=make_instrument_get_screenshot(cfg.device_profiles),
            annotations=ANN_STATE_CHANGE,
        ),
        ToolSpec(
            name="Instrument-Batch-SCPI",
            description=(
                "Run multiple SCPI commands (query if '?' present). "
                "Matching writes use write_with_opc; trailing error queue is drained. "
                "Writes may require confirmation; confirm=true skips elicitation."
            ),
            fn=make_instrument_batch_scpi(policy, cfg.batch_policy),
            annotations=ANN_WRITE,
        ),
        ToolSpec(
            name="Instrument-Save-Recall",
            description=(
                "Save or recall instrument state via *SAV/*RCL (slots 0..9). "
                "Recall uses write_with_opc and requires confirmation."
            ),
            fn=make_instrument_save_recall(policy),
            annotations=ANN_WRITE,
        ),
        ToolSpec(
            name="Instrument-File",
            description=(
                "MMEM file transfer (list/exists/download/upload/read/delete). "
                "Disabled unless FileTransferPolicy is enabled (stdio sandbox)."
            ),
            fn=make_instrument_file(cfg.file_transfer, policy),
            annotations=ANN_WRITE,
        ),
        ToolSpec(
            name="Instrument-SCPI-Exists",
            description=(
                "Check SCPI command against SYST:HELP:HEAD? tree when supported."
            ),
            fn=instrument_scpi_exists,
            annotations=ANN_READONLY,
        ),
        ToolSpec(
            name="Instrument-Discovery",
            description=(
                "Discover VISA-visible instruments. Default call returns a cached "
                "snapshot (TTL ~30s, zero VISA traffic on hit). "
                "Set identify=true for *IDN? queries, refresh=true for a fresh live "
                "scan, or model/manufacturer to filter (requires identify=true)."
            ),
            fn=instrument_discovery,
            annotations=ANN_READONLY,
        ),
    ]
    if not cfg.excluded_tools:
        return specs
    return [spec for spec in specs if spec.name not in cfg.excluded_tools]


def register_one_tool(
    fastmcp: FastMCP,
    spec: ToolSpec,
) -> None:
    """Register a single tool, forwarding annotations when supported."""
    tool_kwargs: dict[str, typing.Any] = {
        "name": spec.name,
        "description": spec.description,
    }
    if spec.annotations:
        tool_kwargs["annotations"] = spec.annotations
    try:
        decorator = fastmcp.tool(**tool_kwargs)
        decorator(spec.fn)
    except TypeError:
        fastmcp.tool(name=spec.name, description=spec.description)(spec.fn)


def add_builtin_tools(
    fastmcp: FastMCP,
    settings: BuiltinToolSettings | None = None,
) -> FastMCP:
    """Add RsInstrument's built-in tools to an existing FastMCP server."""
    for spec in create_builtin_tool_specs(settings):
        register_one_tool(fastmcp, spec)
    return fastmcp
