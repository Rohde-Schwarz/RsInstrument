"""
Changing how the installed options are reported.
This code does not actually install any option on the instrument :-)
"""

from RsInstrument import *

instr = RsInstrument('TCPIP::192.168.56.101::hislip0')

# I want to remove the 'K0' and see if the individual K-options are reported as present.
instr.remove_instr_option('K0')
if not instr.has_instr_option_k0():
    print('We have lost the K0, let us hope the individual options are still reported.')

instr.add_instr_option('K0')
if not instr.has_instr_option_k0():
    print('Now we have the K0 again :-)')
