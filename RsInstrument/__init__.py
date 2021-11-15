"""VISA communication interface for SCPI-based instrument remote control.
    :version: 1.19.0.75
    :copyright: 2020 by Rohde & Schwarz GMBH & Co. KG
    :license: MIT, see LICENSE for more details.
"""


__version__ = '1.19.0.75'

# Main class
from RsInstrument.RsInstrument import RsInstrument

# Bin data format
from RsInstrument.RsInstrument import BinFloatFormat, BinIntFormat

# Exceptions
from RsInstrument.Internal.InstrumentErrors import RsInstrException, TimeoutException, StatusException, UnexpectedResponseException, ResourceError, DriverValueError

# Callback Event Argument prototypes
from RsInstrument.Internal.IoTransferEventArgs import IoTransferEventArgs

# Logging Mode
from RsInstrument.Internal.ScpiLogger import LoggingMode
