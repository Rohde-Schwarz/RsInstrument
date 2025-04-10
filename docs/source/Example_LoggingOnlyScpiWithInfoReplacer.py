.. code-block:: python

    """
    Logging with customized log info string to the console.
    """
    
    from RsInstrument import *
    
    
    RsInstrument.assert_minimum_version('1.82.1')
    instr = RsInstrument('TCPIP::10.102.52.53::hislip0')
    
    # Switch ON logging to the console.
    instr.logger.log_to_console = True
    instr.logger.set_format_string('PAD_LEFT12(%START_TIME%) PAD_LEFT12(%DURATION%) PAD_LEFT9(%LOG_STRING_INFO%):  %SCPI_COMMAND%')
    
    # We will replace the 'Write' and 'Query' log string infos with only 'W' and 'Q' - full match and replace:
    instr.logger.log_info_replacer.put_full_replacer_item(match = 'Write', replace = 'W')
    instr.logger.log_info_replacer.put_full_replacer_item(match = 'Query', replace = 'Q')
    instr.logger.log_info_replacer.put_full_replacer_item(match = 'Clear status', replace = 'Cls')
    instr.logger.log_info_replacer.put_full_replacer_item(match = 'Status check', replace = 'Q_err')
    
    # If the full match does not fit your needs, use the regex search and replace:
    # This regex will replace the 'Query OPC' with 'Q_OPC' and 'Query integer' with 'Q_integer'
    instr.logger.log_info_replacer.put_regex_sr_replacer_item(r'^Query (.+)$', r'Q_\1')
    
    instr.logger.start()
    instr.reset()
    instr.query('*IDN?')
    instr.query_int('*STB?')
    
    # Close the session
    instr.close()
