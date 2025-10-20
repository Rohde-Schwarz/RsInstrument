"""
How to optimize instrument status (error) checking.
Example contains commands for a spectrum analyzer.
"""

from RsInstrument import *

RsInstrument.assert_minimum_version('1.102.0')
instr = None
# Try-catch for initialization. If an error occurs, the ResourceError is raised
try:
	instr = RsInstrument('TCPIP::192.168.1.110::hislip0', True, True)
except ResourceError as e:
	print(e.args[0])
	print('Your instrument is probably OFF...')
	# Exit now, no point of continuing
	exit(1)

# Single commands, keep the instrument stats checking ON
instr.write('SYSTem:DISPlay:UPDate ON')
instr.write('INITiate:CONTinuous OFF')

# Switch the error checking off for a group of commands logically belonging together
instr.instrument_status_checking = False

# Configuration
instr.write('SENSe1:FREQuency:SPAN 10E6')
instr.write('SENSe1:BANDwidth:RESolution 1000')
instr.write('SENSe1:BANDwidth:VIDeo 100')
# Check status after this group of configuration commands
instr.check_status()

# Measure spectrum peaks in a loop
for freq in [10E6, 20E6, 100E6, 200E6, 500E6, 1E9]:
	instr.write_float('SENS:FREQ:CENT ', freq)
	instr.write_with_opc("INITiate:IMMediate")
	instr.write('CALC1:MARK1:STAT ON')
	instr.write('CALC1:MARK1:MAX:PEAK')
	marker_x = instr.query_float('CALCulate:MARKer1:X?')
	si_freq = value_to_si_string(freq)  # Nice way to create SI-formatted numbers
	si_marker_x = value_to_si_string(marker_x)
	marker_y = instr.query_float('CALCulate:MARKer1:Y?')
	print(f'Center Frequency {si_freq}Hz, peak: [{si_marker_x}Hz, {marker_y} dBm]')
	# Check status after one cycle of a marker measurement
	instr.check_status()

instr.close()
