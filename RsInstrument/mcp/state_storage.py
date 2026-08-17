"""IEEE 488.2 *SAV / *RCL save and recall tool."""

from __future__ import annotations

import asyncio
import typing

from RsInstrument import RsInstrument
from RsInstrument.mcp._common import safe_tool
from RsInstrument.mcp.scpi_write_policy import ScpiWritePolicy
from RsInstrument.mcp.write_elicitation import _authorize_write

_SLOT_MIN = 0
_SLOT_MAX = 9


def _validate_slot(slot: int) -> None:
    if not isinstance(slot, int) or isinstance(slot, bool):
        raise ValueError(f"slot must be an integer in {_SLOT_MIN}..{_SLOT_MAX}")
    if slot < _SLOT_MIN or slot > _SLOT_MAX:
        raise ValueError(f"slot must be in {_SLOT_MIN}..{_SLOT_MAX}, got {slot}")


def make_instrument_save_recall(
    write_policy: ScpiWritePolicy | None = None,
) -> typing.Callable[..., typing.Any]:
    """Build policy-gated ``Instrument-Save-Recall``."""
    policy = write_policy or ScpiWritePolicy.defaults()

    @safe_tool
    async def instrument_save_recall(
        ctx: typing.Any,
        action: typing.Literal["save", "recall"],
        slot: int,
        resource: str,
        opc_timeout: int = 5000,
        confirm: bool = False,
    ) -> typing.Any:
        """Save or recall instrument state via ``*SAV`` / ``*RCL`` (slots 0..9)."""
        _validate_slot(slot)
        if action == "save":
            command = f"*SAV {slot}"
        elif action == "recall":
            command = f"*RCL {slot}"
        else:
            raise ValueError(f"Unsupported action: {action!r}")

        decision = await _authorize_write(
            ctx,
            command=command,
            resource=resource,
            confirm=confirm,
            policy=policy,
        )
        if decision is not None:
            return decision

        def _run() -> str:
            with RsInstrument(resource) as inst:
                if action == "recall":
                    inst.write_with_opc(command, timeout=opc_timeout)
                else:
                    inst.opc_timeout = opc_timeout
                    inst.write(command)
            return f"{action.capitalize()} slot {slot} completed."

        return await asyncio.to_thread(_run)

    return instrument_save_recall
