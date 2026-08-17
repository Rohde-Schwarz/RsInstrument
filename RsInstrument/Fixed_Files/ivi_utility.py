"""Module required by IVI Python driver standard."""

from typing import List, Tuple

from ..Internal.Core import Core


class ErrorQueryResult:
    """Structure class for holding one error query result."""

    def __init__(self, code: int, message: str) -> None:
        self._code = code
        self._message = message

    @property
    def code(self) -> int:
        """Code of the error - negative for errors, positive for warnings."""
        return self._code

    @property
    def message(self) -> str:
        """String describing the error in the human-readable form."""
        return self._message


class IviUtility:
    """Utilities class required by the IVI-Python standard."""

    def __init__(self, core: Core):
        self._core = core

    @property
    def driver_version(self) -> str:
        """Returns the instrument driver version."""
        return self._core.driver_version

    @property
    def driver_vendor(self) -> str:
        """Returns the driver manufacturer: 'ROHDE&SCHWARZ'."""
        return "ROHDE&SCHWARZ"

    @property
    def instrument_manufacturer(self) -> str:
        """Returns the manufacturer of the instrument."""
        return self._core.io.manufacturer

    @property
    def instrument_model(self) -> str:
        """Returns the current instrument's full name e.g. 'FSW26'."""
        return self._core.io.full_model_name

    @property
    def query_instrument_status_enabled(self) -> bool:
        """Sets / returns Instrument Status Checking.
        When True (default is True), all the driver methods and properties are sending "SYSTem:ERRor?"
        at the end to immediately react on error that might have occurred.
        We recommend to keep the state checking ON all the time. Switch it OFF only in rare cases when you require maximum speed.
        The default state after initializing the session is ON."""
        return self._core.io.query_instr_status

    @query_instrument_status_enabled.setter
    def query_instrument_status_enabled(self, value) -> None:
        """Sets / returns Instrument Status Checking.
        When True (default is True), all the driver methods and properties are sending "SYSTem:ERRor?"
        at the end to immediately react on error that might have occurred.
        We recommend to keep the state checking ON all the time. Switch it OFF only in rare cases when you require maximum speed.
        The default state after initializing the session is ON."""
        self._core.io.query_instr_status = value

    @property
    def simulation_enabled(self) -> bool:
        """Read-only property indicating if simulation mode is enabled. This property is only settable in the driver's constructor options parameter 'Simulate'."""
        return self._core.simulating

    @property
    def supported_instrument_models(self) -> Tuple[str, ...]:
        """Returns models supported by the driver, one per element."""
        return self._core.supported_instr_models

    def reset(self) -> None:
        """Resets the instrument and clears its status.
        This is typically done by sending the ``*RST`` and ``*CLS`` SCPI Commands."""
        self._core.io.reset()

    def error_query(self) -> ErrorQueryResult | None:
        """Returns the last error in the instrument's error queue.
        Returns None if no error is present.

        Note: If status-error suppression rules are configured (see status_error_suppression_add_rule()),
        errors matching those rules are filtered out and will not be returned."""
        err = self._core.io.query_syst_error(include_code=True, enable_log=True)
        if err is None:
            return None
        # noinspection PyTypeChecker
        return ErrorQueryResult(err[0], err[1])

    def error_query_all(self) -> List[ErrorQueryResult]:
        """Returns all the errors currently reported in the instrument's error queue.
          If no error is present, the method returns an empty collection.

        Note: If status-error suppression rules are configured (see status_error_suppression_add_rule()),
        errors matching those rules are filtered out and will not appear in the returned collection."""
        errs = self._core.io.query_all_syst_errors(include_codes=True, enable_log=True)
        if errs is None:
            return []
        ret_val = [ErrorQueryResult(errs[x][0], errs[x][1]) for x in range(len(errs))]
        return ret_val

    def raise_on_device_error(self) -> None:
        """Calls error_query_all() and raises an exception if any instrument errors were detected."""
        self._core.io.check_status_always(log_ok_result=True)

    def sync_from(self, source: 'IviUtility') -> None:
        """Synchronizes this object with the source."""
        pass
