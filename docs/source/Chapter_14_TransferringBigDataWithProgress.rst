Transferring Big Data with Progress
========================================

We can agree that it can be annoying using an application that shows no progress for long-lasting operations. The same is true for remote-control programs. Luckily, RsInstrument has this covered. And, this feature is quite universal - not just for big files transfer, but for any data in both directions.

RsInstrument allows you to register a function (programmer's fancy name is ``handler`` or ``callback``), which is then periodically invoked after transfer of one data chunk. You can define that chunk size, which gives you control over the callback invoke frequency. You can even slow down the transfer speed, if you want to process the data as they arrive (direction instrument -> PC).

To show this in praxis, we are going to use another *University-Professor-Example*: querying the **\*IDN?** with chunk size of 2 bytes and delay of 200ms between each chunk read:

.. include:: Example_QueryWithProgress.py

If you start it, you might wonder (or maybe not): why is the ``args.total_size = None``? The reason is, in this particular case the RsInstrument does not know the size of the complete response up-front. However, if you use the same mechanism for transfer of a known data size (for example, a file transfer), you get the information about the total size too, and hence you can calculate the progress as:

*progress [pct] = 100 \* args.transferred_size / args.total_size*

Snippet of transferring file from PC to instrument, the rest of the code is the same as in the previous example: 

.. code-block:: python

    instr.events.on_write_handler = my_transfer_handler
    instr.events.io_events_include_data = True
    instr.data_chunk_size = 1000
    instr.send_file_from_pc_to_instrument(
        r'c:\MyCoolTestProgram\my_big_file.bin', 
        r'/var/user/my_big_file.bin')
    # Unregister the event handler
    instr.events.on_write_handler = None
