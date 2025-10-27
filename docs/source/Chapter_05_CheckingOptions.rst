Checking the installed options
========================================
If your instrument refuses to execute desired actions, and you do not know why - after all, the SCPI commands are in the User Manual, it's worth to check if the a special option is required.
RsInstrument provides several ways to do it. The following example shows the literal CASE-INSENSITIVE searching:

.. literalinclude:: Example_CheckingInstalledOptions.py
   :language: python
   :linenos:

.. note::
    | ``instr.instrument_options`` returns neatly sorted list of options, where the duplicates are removed, K-options are at the beginning, and the B-options at the end.
    | If for any reason you want to see how many times the K101 option was in the original Option's string, use the ``io.get_option_counts('K101')``

Regular expressions CASE-INSENSITIVE searching. The Regex must be fully matched. That means, for example, ``K1.`` only positively matches ``K10`` or ``K17``, but not ``K1`` or ``K110``

.. literalinclude:: Example_CheckingInstalledOptionsRegex.py
   :language: python
   :linenos:
   
If you wish to add or remove reported options, you can use ``add_instr_option()`` or ``remove_instr_option()``. The ``instr.instrument_options`` is re-sorted after each change in the list:

.. literalinclude:: Example_InstalledOptionsReportingChange.py
   :language: python
   :linenos:

.. note::
	It would be nice to install an instrument option with this small python script. Unfortunately, this is not the case - the script just manipulates the reported list of options. If you want to install an option on your instrument, you will have to buy it :-)