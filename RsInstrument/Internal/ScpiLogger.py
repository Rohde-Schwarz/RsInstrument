"""Interface for SCPI communication logging."""

from enum import Enum
from datetime import datetime
import re
import string
from typing import Tuple, List
from textwrap import wrap

from .Utilities import get_plural_string, shorten_string_middle, escape_nonprintable_chars, size_to_kb_mb_string, calculate_chunks_count
from .InstrumentErrors import RsInstrException
from .Conversions import list_to_csv_str


class LoggingMode(Enum):
    """Determines the format of the logging message."""
    Off = 0  # Don't write messages to log
    On = 1  # Write message to log
    Errors = 2  # Only log errors. This is like 'Off', with the exception, that VisaIOErrors are logged.
    Default = 3  # Default mode


def _convert_ts_to_datetime(timestamp: datetime or float) -> datetime:
    """Converts timestamp as float to datetime. For datetime tuple it just passes the value."""
    if isinstance(timestamp, float) or isinstance(timestamp, int):
        return datetime.fromtimestamp(timestamp)
    return timestamp


def get_timestamp_string(timestamp: datetime or float) -> str:
    """Returns the timestamp as string. The timestamp can be a datetime tuple or float seconds coming from the time.time()."""
    timestamp = _convert_ts_to_datetime(timestamp)
    cur_time = timestamp.strftime('%H:%M:%S.%f')[:-3]
    return cur_time


def get_timedelta_string(time_a: datetime or float, time_b: datetime or float) -> str:
    """Returns the time span as string."""
    time_a = _convert_ts_to_datetime(time_a)
    time_b = _convert_ts_to_datetime(time_b)
    if time_b < time_a:
        return '0.000 ms'
    diff = time_b - time_a
    if diff.seconds < 10:
        return f'{diff.total_seconds() * 1000:0.3f} ms'
    elif diff.seconds < 1000:
        a = diff.total_seconds()
        return f'{a:0.3f} secs'
    hours, remainder = divmod(diff.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f'{hours:02d}:{minutes:02d}:{seconds:02d}'


class Segment:
    """Segment of logs"""

    def __init__(self):
        self.error_present = False
        self.entries = []

    def add_to_segment(self, entry: str, error: bool) -> None:
        """Adds an entry to the current segment."""
        self.entries.append(entry)
        if error is True:
            self.error_present = True

    def empty(self) -> None:
        """Empties the list of entries for the current segment."""
        self.error_present = False
        self.entries = []

    def __del__(self):
        self.empty()


class CachedEntries:
    """Entries that are cached internally, in case no target is defined, but the logging is ON."""

    def __init__(self):
        self.entries: List[Tuple[str, bool]] = []
        self.truncated_count = 0
        self.clear()

    def append(self, entry: str, add_new_line: bool) -> None:
        """Appends one entry. If the list is longer than 1000 entries, the oldest one is deleted and truncated_count is increased by 1."""
        self.entries.append((entry, add_new_line))
        if len(self.entries) > 1000:
            self.entries.pop(0)
            self.truncated_count += 1
        return

    def clear(self) -> None:
        """Clears all the cached entries."""
        self.entries = []
        self.truncated_count = 0

    def __del__(self):
        self.clear()


class ScpiLogger:
    """Base class for SCPI logging"""

    def __init__(self, resource_name: str):
        if resource_name is None:
            raise RsInstrException('resource_name cannot be None')
        self._orig_resource_name = resource_name
        self._default_mode: LoggingMode = LoggingMode.Off
        self._mode: LoggingMode = self._default_mode
        self._log_target = None
        self._cached = CachedEntries()
        self._start_time: datetime or None = None
        self._end_time: datetime or None = None
        self._log_string_info: str = ''
        self._log_string: str = ''
        self._format_string: str = ''
        self._line_divider: str = '\n'
        self.restore_format_string()
        self._tab_var_re = re.compile(r'PAD_(LEFT|RIGHT)(\d+)\(%(START_TIME|END_TIME|DURATION|DEVICE_NAME|LOG_STRING_INFO|LOG_STRING)%\)')
        self._var_re = re.compile(r'%(START_TIME|END_TIME|DURATION|DEVICE_NAME|LOG_STRING_INFO|LOG_STRING)%')
        self._segment: Segment or None = None
        self._log_status_check_ok: bool = True
        # Printable chars set
        self._printable_chars = set(bytes(string.printable, 'ascii'))
        self._printable_chars.remove(10)
        self._printable_chars.remove(13)
        self._printable_chars.remove(32)
        self._printable_chars.remove(9)

        # Public properties
        self.log_to_console: bool = False
        """Sets the status of logging to the console. Default value is False."""
        self.device_name: str = resource_name
        """Use this property to change the resource name in the log from the default Resource Name (e.g. TCPIP::192.168.2.101::INSTR)
         to another name e.g. 'MySigGen1'."""
        self.abbreviated_max_len_ascii: int = 200
        """Defines the maximum length of one ASCII log entry. Default value is 200 characters."""
        self.abbreviated_max_len_list: int = 100
        """Defines the maximum length of one list entry. Default value is 100 elements."""
        self.abbreviated_max_len_bin: int = 2048
        """Defines the maximum length of one Binary log entry. Default value is 2048 bytes."""
        self.bin_line_block_size: int = 16
        """Defines number of bytes to display in one line. Default value is 16 bytes."""

    def __str__(self):
        value = f"ScpiLogger for '{self.device_name}'"
        if self.mode != LoggingMode.Off:
            value += f' mode: {self._mode.name}'
        else:
            value += f' OFF'
        if not self.log_to_console and self._log_target is None:
            return value
        value += f', target: '
        if self.log_to_console and self._log_target:
            value += 'console + stream'
        elif self.log_to_console:
            value += 'console'
        elif self._log_target:
            value += 'stream'
        return value

    def start_new_segment(self) -> None:
        """Only relevant for if the log mode is LoggingMode.Errors.
        In this mode, all the logging is delayed until you call end_current_segment()
        Then, only if an error occurred, the logs are flushed to the output log.
        In case no error occurred, the logs are deleted."""
        if self._segment:
            self.end_current_segment()
            raise RsInstrException('Segment was not property finished before the new one was started.')
        # Logging to segments is only started if the logging mode is set to LoggingMode.Errors
        # That causes in mode ON all the entries appear immediately, rather than being delayed until the segment is ended
        self._segment = None
        if self._mode == LoggingMode.Errors:
            self._segment = Segment()

    def end_current_segment(self) -> None:
        """Only relevant for if the log mode is LoggingMode.Errors.
        Calling this method causes the logger to either flush all the segment logs to the output log or delete them if no error occurred.
        This causes only the errors to be logged, but also with the appropriate context, so you can troubleshoot more easily."""
        if self._segment:
            curr_segment = self._segment
            self._segment = None
            if self._mode == LoggingMode.Errors and curr_segment.error_present:
                # If error mode is on, and the segment contains at least one error entry, write the segment entries to the log
                for entry in curr_segment.entries:
                    self._write_to_log(entry)

    def set_format_string(self, value: str, line_divider: str = '\n') -> None:
        """Sets new format string and line divider.
        If you just want to set the line divider, set the format string value=None
        The original format string is: ``PAD_LEFT12(%START_TIME%) PAD_LEFT25(%DEVICE_NAME%) PAD_LEFT12(%DURATION%)  %LOG_STRING_INFO%: %LOG_STRING%`` """
        if value is not None:
            self._format_string = value
        self._line_divider = line_divider

    def restore_format_string(self) -> None:
        """Restores the original format string and the line divider to LF """
        self._format_string = 'PAD_LEFT12(%START_TIME%) PAD_LEFT30(%DEVICE_NAME%) PAD_LEFT12(%DURATION%)  %LOG_STRING_INFO%: %LOG_STRING%'
        self._line_divider = '\n'

    def clear_cached_entries(self) -> None:
        """Clears potential cached log entries.
        Cached log entries are generated when the Logging is ON, but no target has been defined yet."""
        self._cached.clear()

    def set_logging_target(self, target, console_log: bool or None = None) -> None:
        """Sets logging target - the target must implement write() and flush().
        You can optionally set the console logging ON or OFF.
        """
        self._log_target = target
        if console_log is not None:
            self.log_to_console = console_log
        self._flush_cached_entries()

    @property
    def mode(self) -> LoggingMode:
        """Sets / returns the Logging mode.

        :Data Type: LoggingMode"""
        return self._mode

    @mode.setter
    def mode(self, value: LoggingMode) -> None:
        """Sets / returns the Logging mode."""
        if self._segment:
            raise RsInstrException(f"Can not change the logging mode when a log segment is active. End the segment with ScpiLogger.end_current_segment(). Device name: '{self.device_name}'")
        value = self._resolve_log_mode(value)
        if self.mode != LoggingMode.Off:
            # logging is ON. Check the internal log entries and flush them to the target
            self._flush_cached_entries()
        self._mode = value
        if self._mode == LoggingMode.Off and self._log_target:
            # Logging was switched off, flush the entries on the target
            self.flush()

    @property
    def log_status_check_ok(self) -> bool:
        """Sets / returns the current status of status checking OK.
        If True (default), the log contains logging of the status checking 'Status check: OK'.
        If False, the 'Status check: OK' is skipped - the log is more compact.
        Errors will still be logged.

        :Data Type: boolean"""
        return self._log_status_check_ok

    @log_status_check_ok.setter
    def log_status_check_ok(self, value: bool) -> None:
        """Sets new logging of status checking OK.
        If True (default), the log contains logging of the status checking 'Status check: OK'.
        If False, the 'Status check: OK' is skipped - the log is more compact.
        Errors will still be logged."""
        self._log_status_check_ok = value
        self.info(datetime.now(), None, 'Logging of \'Status Check OK\'', 'ON' if value is True else 'OFF')

    def _target_exists(self):
        """Returns true, if the target either console or file or stream exist."""
        return self._log_target is not None or self.log_to_console is True

    def _flush_cached_entries(self):
        """Flushes internal log to the log target. Returns true if flushed."""
        if not self._target_exists:
            return False
        if self._cached.truncated_count > 0:
            self._write_to_log(f'----- Missing {self._cached.truncated_count} oldest entries ----------')
        for entry in self._cached.entries:
            self._write_to_log(entry[0], add_new_line=entry[1])
        self.clear_cached_entries()
        return True

    def _resolve_log_mode(self, value: LoggingMode) -> LoggingMode:
        """Resolves the potential default mode."""
        if value == LoggingMode.Default:
            return self._default_mode
        else:
            return value

    @property
    def default_mode(self) -> LoggingMode:
        """Sets / returns the default logging mode.
        You can recall the default mode by calling the logger.mode = LoggingMode.Default

        :Data Type: LoggingMode
        """
        return self._default_mode

    @default_mode.setter
    def default_mode(self, value: LoggingMode) -> None:
        """Sets the default logging mode.
        You can recall the default mode by calling the logger.mode = LoggingMode.Default"""
        if value == LoggingMode.Default:
            raise ValueError('LoggingMode.Default can not be set here. Use a specific value.')
        self._default_mode = value

    def _write_to_log(self, content: str, add_new_line: bool = True, error: bool = False) -> None:
        """Logs the provided string to the target and optionally to the stdout"""
        # Check if the segment is active and if so, write the log only to the segment.
        if self._segment:
            self._segment.add_to_segment(content, error)
            return
        if not self._target_exists():
            # No target is defined yet, cache the entries internally for now
            self._cached.append(content, add_new_line)
            return
        if self.log_to_console:
            print(content)
        if self._log_target:
            new_line = self._line_divider if add_new_line else ''
            try:
                self._log_target.write(content + new_line)
            except Exception as e:
                msg = f'Error logging to the stream. Message: \'{content}\'. Error: {e.args[0]}'
                raise RsInstrException(msg)
        return

    def info_raw(self, log_entry: str, add_new_line: bool = True) -> None:
        """Method for logging the raw string without any formatting."""
        if self.mode == LoggingMode.Off:
            return
        if self._mode == LoggingMode.Errors:
            # For errors logging mode, log the info only if the segment is active.
            # That means, it might be logged eventually as a context when the segment ends with an error
            if not self._segment:
                return
        self._write_to_log(log_entry, add_new_line)

    def info(self, start_time: datetime or float or None, end_time: datetime or float or None, log_string_info: str, log_string: str) -> None:
        """Method for logging one info entry. For binary log_string, use the info_bin()"""
        if self.mode == LoggingMode.Off:
            return
        content = self._compose_log_string(start_time, end_time, log_string_info, log_string, self.abbreviated_max_len_ascii)
        self.info_raw(content, add_new_line=True)

    def info_bin(self, start_time: datetime or float or None, end_time: datetime or float or None, log_string_info: str, log_data: bytes) -> None:
        """Method for logging one info entry where the log_data is binary (bytes)."""
        if self.mode == LoggingMode.Off:
            return
        content = self._compose_log_string_bin(start_time, end_time, log_string_info, log_data)
        self.info_raw(content, add_new_line=True)

    def info_list(self, start_time: datetime or float or None, end_time: datetime or float or None, log_string_info: str, list_data: List) -> None:
        """Method for logging one info entry where the list_data is decimal List[]."""
        if self.mode == LoggingMode.Off:
            return
        delimiter = ', '
        if len(list_data) <= self.abbreviated_max_len_list:
            log_string = f'List size {len(list_data)}: {list_to_csv_str(list_data, delimiter=delimiter)}'
        else:
            chunk = self.abbreviated_max_len_list // 2
            log_string = f'List size {len(list_data)}, showing first and last {chunk} elements: '
            log_string += list_to_csv_str(list_data[:chunk], delimiter=delimiter)
            log_string += ' .... '
            log_string += list_to_csv_str(list_data[-chunk:], delimiter=delimiter)
        content = self._compose_log_string(start_time, end_time, log_string_info, log_string, None)
        self.info_raw(content, add_new_line=True)

    def error_raw(self, log_entry: str, add_new_line: bool = True) -> None:
        """Method for logging one error entry without any formatting. Setting the error flag to True."""
        if self.mode == LoggingMode.Off:
            return
        if self._segment:
            self._segment.error_present = True
        self._write_to_log(log_entry, add_new_line)

    def error(self, start_time: datetime or float or None, end_time: datetime or float or None, log_string_info: str, log_string: str) -> None:
        """Method for logging one error entry."""
        if self.mode == LoggingMode.Off:
            return
        content = self._compose_log_string(start_time, end_time, log_string_info, log_string, self.abbreviated_max_len_ascii)
        self.error_raw(content, add_new_line=True)

    def _adjust_log_strings(self, value: str) -> str:
        """Adjusts the log string to prevent repeating of the information in the fields."""
        # Prevent repeating of the device name:
        if 'DEVICE_NAME' in self._format_string:
            value = value.replace(f"'{self._orig_resource_name}': ", '')
            value = value.replace(f"'{self._orig_resource_name}' ", '')
            value = value.replace(f"'{self._orig_resource_name}'", '')
            value = value.replace(self._orig_resource_name, '')
        return value

    def _adjust_for_repeated_log_string_info(self, log_string_info: str, log_string) -> str:
        # Prevent repeating of the log string info in the log_string
        if 'LOG_STRING_INFO' in self._format_string:
            log_string = log_string.replace(f'{log_string_info}: ', '')
            log_string = log_string.replace(f'{log_string_info} ', '')
            log_string = log_string.replace(f'{log_string_info}', '')
            log_string = log_string.replace(log_string_info, '')
        return log_string

    def _compose_log_string(self, start_time: datetime or float, end_time: datetime or float, log_string_info: str, log_string: str, max_log_string_len: int = None) -> str:
        """Composes the log string with the format defined in the self._format_string"""
        self._start_time = start_time
        self._end_time = end_time
        self._log_string_info = self._adjust_log_strings(log_string_info)
        log_string = self._adjust_log_strings(log_string)
        log_string = self._adjust_for_repeated_log_string_info(log_string_info, log_string)
        orig_len = len(log_string)
        # Shorten the long log strings
        if max_log_string_len is not None:
            if orig_len > self.abbreviated_max_len_ascii:
                log_string = shorten_string_middle(log_string, max_log_string_len)
        self._log_string = log_string
        result_str = self._replace_log_string_variables(self._format_string)
        # Trimming the end
        result_str = result_str.rstrip(': ')
        result_str = escape_nonprintable_chars(result_str)
        return result_str

    def _compose_log_string_bin(self, start_time: datetime or float, end_time: datetime or float, log_string_info: str, log_data: bytes) -> str:
        """Composes the log string with the format defined in the self._format_string"""
        self._start_time = start_time
        self._end_time = end_time
        self._log_string_info = self._adjust_log_strings(log_string_info)
        self._log_string_info = escape_nonprintable_chars(self._log_string_info)
        self._log_string = self._compose_hexdump(log_data, offset_left=20)
        result_str = self._replace_log_string_variables(self._format_string)
        return result_str

    def _replace_log_string_variables(self, content) -> str:
        """Replaces all the variables in the entered log string with their actual values."""
        while True:
            m = self._tab_var_re.search(content)
            if m:
                pos_left = m.group(1) == 'LEFT'
                spaces = int(m.group(2).strip())
                var_name = m.group(3).strip().strip('%')
                value = self._get_log_string_variable_values(var_name)
                value = value.rjust(spaces) if pos_left else value.ljust(spaces)
                content = content[:m.start()] + value + content[m.end():]
                continue
            m = self._var_re.search(content)
            if m:
                var_name = m.group(1)
                value = self._get_log_string_variable_values(var_name)
                if not value:
                    print(f'Value: {value} var_name "{var_name}" log_info: {self._log_string_info}')
                content = content[:m.start()] + value + content[m.end():]
                continue
            break
        return content

    def _get_log_string_variable_values(self, name: str) -> str:
        """Returns the required variable value.
        Recognised names: START_TIME, END_TIME, DURATION, DEVICE_NAME, LOG_STRING_INFO, LOG_STRING"""
        if name == 'START_TIME':
            if self._start_time is None:
                return ''
            return get_timestamp_string(self._start_time)
        if name == 'END_TIME':
            if self._end_time is None:
                return ''
            return get_timestamp_string(self._end_time)
        if name == 'DURATION':
            if self._start_time is None or self._end_time is None:
                return ''
            return get_timedelta_string(self._start_time, self._end_time)
        if name == 'DEVICE_NAME':
            if self.device_name is None:
                return ''
            return self.device_name
        if name == 'LOG_STRING_INFO':
            if self._log_string_info is None:
                return ''
            return self._log_string_info
        if name == 'LOG_STRING':
            return self._log_string

    def _compose_hexdump(self, value: str or bytes, offset_left: int) -> str:
        """Composes hexdump string from string or bytes.
        The hex dump is organised in the groups of 16 bytes per line."""
        if isinstance(value, str):
            value = bytes(value, 'utf-8')
        size = len(value)
        line = f'{size_to_kb_mb_string(size, True)}'
        padding = ' ' * offset_left
        right_padding = self.bin_line_block_size * 3 - 1
        max_lines = calculate_chunks_count(self.abbreviated_max_len_bin, self.bin_line_block_size)
        lines_count = calculate_chunks_count(size, self.bin_line_block_size)
        skipping = False
        skip_start = 0
        skip_size = 0
        if lines_count > (max_lines + 1):
            # Skip the lines in the middle
            skip_start = max_lines // 2
            if skip_start == 0:
                skip_start = 1
            skip_size = lines_count - max_lines
            if skip_start > 0 and skip_size > 0:
                skipping = True
                line += f', showing {max_lines} blocks (1 block = {self.bin_line_block_size} bytes) out of {lines_count}, skipped {get_plural_string("block", skip_size)} in the middle'
                skip_start *= self.bin_line_block_size
                skip_size *= self.bin_line_block_size
        ix = 0
        end = 0
        line += self._line_divider
        while end < size:
            if skipping and ix >= skip_start:
                ix += skip_size
                line += padding + ('...' * self.bin_line_block_size) + self._line_divider
                skipping = False
            end = ix + self.bin_line_block_size
            if end >= size:
                end = size
            chunk = value[ix: end]
            cp = [chr(c) if c in self._printable_chars else '.' for c in chunk]
            line += padding + ' '.join(wrap(chunk.hex(), 2)).ljust(right_padding) + '    ' + ''.join(cp) + self._line_divider
            ix += self.bin_line_block_size
        return line

    def flush(self) -> None:
        """Flush all the entries."""
        if self._log_target:
            try:
                # The file might be already closed.
                self._log_target.flush()
            except ValueError:
                pass

    def __del__(self):
        self.flush()
