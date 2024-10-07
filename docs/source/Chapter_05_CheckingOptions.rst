Checking the installed options
========================================
If your instrument refuses to execute desired actions, and you do not know why - after all, the SCPI commands are in the User Manual, it's worth to check if the a special option is required.
RsInstrument provides several ways to do it. The following example shows the literal CASE-INSENSITIVE searching:

.. code-block:: python
    
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
    
.. note::
    ``instr.instrument_options`` returns neatly sorted list of options, where the duplicates are removed, K-options are at the beginning, and the B-options at the end.

Regular expressions CASE-INSENSITIVE searching. The Regex must be fully matched. That means, for example, ``K1.`` only positively matches ``K10`` or ``K17``, but not ``K1`` or ``K110``

.. code-block:: python
    
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
        
If you wish to add or remove certain option (from the ``instr.instrument_options``, not the actual instrument's options list), you can use ``add_instr_option()`` or ``remove_instr_option()``. The ``instr.instrument_options`` is re-sorted after each change in the list:

.. code-block:: python
    
    instr = RsInstrument('TCPIP::192.168.56.101::hislip0')
    
    # I want to remove the 'K0' and see if the individual K-options are reported as present.
    instr.remove_instr_option('K0')
    if not instr.has_instr_option_k0():
        print('We have definitely lost the K0, let us hope the individual options are still reported.')
        
    # 
    instr.add_instr_option('K0')
    if not instr.has_instr_option_k0():
        print('Now we have the K0 again :-)')
