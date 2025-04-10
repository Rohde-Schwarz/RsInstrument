"""VISA communication interface for SCPI-based instrument remote control.
    :version: 1.100.0
    :copyright: 2025 by Rohde & Schwarz GMBH & Co. KG
    :license: MIT, see LICENSE for more details.
"""


__version__ = '1.100.0'

# Main class
from RsInstrument.RsInstrument import RsInstrument

# Bin data format
from RsInstrument.RsInstrument import BinFloatFormat, BinIntFormat

# Opc-Sync Query Mechanism
from RsInstrument.Internal.InstrumentSettings import OpcSyncQueryMechanism

# Exceptions
from RsInstrument.Internal.InstrumentErrors import RsInstrException, TimeoutException, StatusException, UnexpectedResponseException, ResourceError, DriverValueError

# Callback Event Argument prototypes
from RsInstrument.Internal.IoTransferEventArgs import IoTransferEventArgs

# Logging Mode
from RsInstrument.Internal.ScpiLogger import LoggingMode

# Utilities
from RsInstrument.Internal.Utilities import size_to_kb_mb_gb_string, size_to_kb_mb_string
from RsInstrument.Internal.Utilities import value_to_si_string
