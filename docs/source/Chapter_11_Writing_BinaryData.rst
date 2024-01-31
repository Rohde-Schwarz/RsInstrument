11. Writing Binary Data
========================================

Writing from bytes data
""""""""""""""""""""""""""""""""""""""""""""""""""""
We take an example for a Signal generator waveform data file. First, we construct a ``wform_data`` as ``bytes``, and then send it with ``write_bin_block()``:

.. code-block:: python

    # MyWaveform.wv is an instrument file name under which this data is stored
    smw.write_bin_block("SOUR:BB:ARB:WAV:DATA 'MyWaveform.wv',", wform_data)

.. note::
    Notice the ``write_bin_block()`` has two parameters:

    - string parameter ``cmd`` for the SCPI command
    - bytes parameter ``payload`` for the actual data to send

Writing from PC files
""""""""""""""""""""""""""""""""""""""""""""""""""""
Similar to querying binary data to a file, you can write binary data from a file. The second parameter is the source PC file path with content which you want to send:

.. code-block:: python

    smw.write_bin_block_from_file("SOUR:BB:ARB:WAV:DATA 'MyWaveform.wv',", r"c:\temp\wform_data.wv")
