"""
Suppress instrument errors with certain code with the Suppress Context-manager.
"""

from RsInstrument import *

RsInstrument.assert_minimum_version('1.102.0')
instr = RsInstrument('TCPIP::192.168.1.110::hislip0', True, True)

with instr.instr_err_suppressor(suppress_only_codes=-200) as supp:
    # This will raise the exception anyway, because the Undefined Header error has code -113
    instr.write('MY:MISSpelled:COMMand')

if supp.get_errors_occurred():
    print("Errors occurred: ")
    for err in supp.get_all_errors():
        print(err)
