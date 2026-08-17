"""
Checking the installed options with regular expressions search.
"""

from RsInstrument import *

instr = RsInstrument('TCPIP::192.168.56.101::hislip0')

# Check for one option.
# Keep in mind, that if the 'K0' is present, all the K-options are reported as installed.
if instr.has_instr_option_regex('K1.'):
    print('Option K10 or K11 or K12 up to K19 installed')

# Check with a dedicated function for at least one option (logical OR).
if instr.has_instr_option_regex('K1. / K2..'):
    print('At least one of the K10..K19, K200..K299 installed')

# Same as previous, but entered as a list of strings.
if instr.has_instr_option_regex(['K1.', 'K2..']):
    print('At least one of the K10..K19, K200..K299 installed')

instr.close()
