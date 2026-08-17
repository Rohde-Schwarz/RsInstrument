"""Module required by IVI Python driver standard."""

from typing import Any

from ..Internal.Core import Core


class IviDirectIo:
    """Direct IO class required by the IVI-Python standard."""

    def __init__(self, core: Core):
        self._core = core

    @property
    def session(self) -> Any:
        """Returns the underlying instrument session, usually a VISA session."""
        return self._core.io.get_session_handle()

    @property
    def io_timeout_ms(self) -> int:
        """Return the timeout of the underlying instrument session in milliseconds."""
        return self._core.io.visa_timeout

    @io_timeout_ms.setter
    def io_timeout_ms(self, timeout_ms: int) -> None:
        """Sets the timeout of the underlying instrument session in milliseconds."""
        self._core.io.visa_timeout = timeout_ms

    def read_bytes(self) -> bytes:
        """Read a complete response from the instrument as bytes.
        The response message terminator is not included in the bytes object."""
        return self._core.io.read_all_bytes()

    def read_string(self) -> str:
        """Read a complete response from the instrument as a string.
        The response message terminator is not included in the string."""
        return self._core.io.read_str(block_check_status=True)

    def write_bytes(self, data: bytes) -> None:
        """Write bytes to the instrument followed by the normal message termination sequence.
        For IEEE 488.2 instruments the termination sequence is typically a line feed character with END asserted.
        The bytes must include a complete instrument message. The driver adds the termination sequence."""
        self._core.io.write_raw_bytes(data)

    def write_string(self, data: str) -> None:
        """Write a string to the instrument followed by the normal message termination sequence.
        For IEEE 488.2 instruments the termination sequence is typically a line feed character with END asserted.
        The string must include a complete instrument message. The driver adds the termination sequence."""
        self._core.io.write(data, block_check_status=True)

    def sync_from(self, source: 'IviDirectIo') -> None:
        """Synchronizes this object with the source."""
        pass
