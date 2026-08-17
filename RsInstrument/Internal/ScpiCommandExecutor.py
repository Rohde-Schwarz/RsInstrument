"""SCPI command execution helper for RsInstrument."""

from __future__ import annotations

import re
from typing import Protocol


class _ScpiInstrument(Protocol):
    """Protocol for the RsInstrument methods used by the executor."""

    def write(self, cmd: str) -> None:
        """Writes a SCPI command in a standard way."""
        ...

    def query(self, query: str) -> str:
        """Queries a SCPI response in a standard way."""
        ...

    def write_with_opc(self, cmd: str, timeout: int | None = None) -> None:
        """Writes a SCPI command with OPC synchronization."""
        ...

    def query_with_opc(self, query: str, timeout: int | None = None) -> str:
        """Queries a SCPI response with OPC synchronization."""
        ...


class ScpiCommandExecutor:
    """Dispatch one SCPI command string to the matching RsInstrument I/O method."""

    _opc_write_suffix_regex = re.compile(
        r"(?P<base_command>.+?)(?P<opc_suffix>;\*OPC)?$",
        re.IGNORECASE,
    )

    _opc_suffix_optimized_regex = re.compile(
        r"(?P<base_command>.+?)(?P<opc_suffix>;\*OPC\??)?$",
        re.IGNORECASE,
    )

    def __init__(self, instrument: _ScpiInstrument, command: str, optimize_opc_execute: bool) -> None:
        """Create an executor for one instrument and one command string.
        If optimize_opc_execute is true, the *OPC or *OPC? at the end of the command are treated the same way.
        If the optimize_opc_execute is false, the *OPC triggers the _with_opc calls, while the *OPC? is treated as a standard query."""
        self._instrument = instrument
        self._optimize_opc_execute = optimize_opc_execute
        self._cmd_to_send, self._with_opc = self._detect_cmd_send_mode(command.strip())

    def execute(self) -> str | None:
        """Executes the command/query and returns query responses.
        For write commands, the method returns None."""
        if "?" in self._cmd_to_send:
            if self._with_opc:
                return self._instrument.query_with_opc(self._cmd_to_send)
            else:
                return self._instrument.query(self._cmd_to_send)
        else:
            if self._with_opc:
                self._instrument.write_with_opc(self._cmd_to_send)
            else:
                self._instrument.write(self._cmd_to_send)
            return None

    def _detect_cmd_send_mode(self, command: str) -> tuple[str, bool]:
        """Based on the presence of *OPC / *OPC?, and the property optimize_opc_execute,
        the method returns the command to send and the mode to send."""
        if ';' not in command:
            return command, False

        if self._optimize_opc_execute:
            match = self._opc_suffix_optimized_regex.fullmatch(command)
        else:
            match = self._opc_write_suffix_regex.fullmatch(command)

        if match is None:
            raise ValueError(f"Unexpected SCPI command format: {command!r}")

        return match.group("base_command"), match.group("opc_suffix") is not None
