.. code-block:: python

    """"
    Find the instruments in your environment
    """
    
    from RsInstrument import *
    
    # Use the instr_list string items as resource names in the RsInstrument constructor
    instr_list = RsInstrument.list_resources("?*")
    print(instr_list)
