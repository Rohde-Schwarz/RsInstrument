12. Transferring Files
========================================

Instrument -> PC
""""""""""""""""""""""""""""""""""""""""""""""""""""
You just did a perfect measurement, saved the results as a screenshot to the instrument's storage drive.
Now you want to transfer it to your PC.
With RsInstrument, no problem, just figure out where the screenshot was stored on the instrument. In our case, it is *var/user/instr_screenshot.png*:

.. code-block:: python

    instr.read_file_from_instrument_to_pc(
        r'/var/user/instr_screenshot.png',
        r'c:\temp\pc_screenshot.png')

PC -> Instrument
""""""""""""""""""""""""""""""""""""""""""""""""""""
Another common scenario: Your cool test program contains a setup file you want to transfer to your instrument:
Here is the RsInstrument one-liner split into 3 lines:

.. code-block:: python
    
    instr.send_file_from_pc_to_instrument(
        'c:\MyCoolTestProgram\instr_setup.sav',
        r'/var/appdata/instr_setup.sav')

.. tip::

	| You want to delete a file on the instrument, and get an **error**, because it does not exist?
	| Or you want to write a file and get an **error** that the file exists and can not be overwritten?
	| Not anymore, use the file detection methods:
		
	.. code-block:: python
    
		# Let's see if you exist...
		i_exist = instr.file_exist(r'/var/appdata/instr_setup.sav')

		# Give me your size or give me nothing...
		my_size = instr.get_file_size(r'/var/appdata/instr_setup.sav')
