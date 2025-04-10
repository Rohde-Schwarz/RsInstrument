.. code-block:: python

    """
    Find the instruments in your environment with the defined VISA implementation
    """
    
    from RsInstrument import *
    
    # In the optional parameter visa_select you can use e.g.: 'rs' or 'ni'
    # Rs Visa also finds any NRP-Zxx USB sensors
    instr_list = RsInstrument.list_resources('?*', 'rs')
    print(instr_list)
