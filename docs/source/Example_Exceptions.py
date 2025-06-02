"""
How to deal with RsInstrument exceptions.
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
try:
    # Dealing with commands that potentially generate instrument errors:
    # Switching the status checking OFF temporarily.
    # We use the InstrumentErrorSuppression context-manager that does it for us:
    with instr.instr_err_suppressor() as supp:
        instr.write('MY:MISSpelled:COMMand')
    if supp.get_errors_occurred():
        print("Errors occurred: ")
        for err in supp.get_all_errors():
            print(err)

    # Here for this query we use the reduced VISA timeout to prevent long waiting
    with instr.instr_err_suppressor(visa_tout_ms=500) as supp:
        idn = instr.query('*IDaN')
    if supp.get_errors_occurred():
        print("Errors occurred: ")
        for err in supp.get_all_errors():
            print(err)

except StatusException as e:
    # Instrument status error
    print(e.args[0])
    print('Nothing to see here, moving on...')

except TimeoutException as e:
    # Timeout error
    print(e.args[0])
    print('That took a long time...')

except RsInstrException as e:
    # RsInstrException is a base class for all the RsInstrument exceptions
    print(e.args[0])
    print('Some other RsInstrument error...')

finally:
    instr.close()
