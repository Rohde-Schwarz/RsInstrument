"""
Checking the installed options with literal search.
"""

from RsInstrument import *

instr = RsInstrument('TCPIP::192.168.56.101::hislip0')

# Get all the options as list, and check for the specific one.
if 'K1' in instr.instrument_options:
	print('Option K1 installed')

# Check for one option.
# Keep in mind, that if the 'K0' is present, all the K-options are reported as installed.
if instr.has_instr_option('K1'):
	print('Option K1 installed')
	
# Check whether the K0 is installed:
if instr.has_instr_option_k0():
	print('You are a lucky customer, your instrument has all the K-options available.')
	
# Check with a dedicated function for at least one option (logical OR).
if instr.has_instr_option('K1 / K1a / K1b'):
	print('At least one of the K1,K1a,K1b installed')

# Same as previous, but entered as a list of strings.
if instr.has_instr_option(['K1', 'K1a', 'K1b']):
	print('At least one of the K1,K1a,K1b installed')

instr.close()
