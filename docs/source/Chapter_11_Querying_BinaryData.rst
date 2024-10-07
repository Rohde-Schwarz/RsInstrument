Querying Binary Data
========================================

A common question from customers: How do I read binary data to a byte stream, or a file?

If you want to transfer files between PC and your instrument, check out the following chapter: :doc:`Transferring_Files <Chapter_13_TransferringFiles>`.


Querying to bytes
""""""""""""""""""""""""""""""""""""""""""""""""""""
Let us say you want to get raw (bytes) RTO waveform data. Call this method:

.. code-block:: python
    
    data = rto.query_bin_block('FORM REAL,32;:CHAN1:DATA?')
    
Querying to PC files
""""""""""""""""""""""""""""""""""""""""""""""""""""
Modern instrument can acquire gigabytes of data, which is often more than your program can hold in memory. The solution may be to save this data to a file. RsInstrument is smart enough to read big data in chunks, which it immediately writes into a file stream. This way, at any given moment your program only holds one chunk of data in memory. You can set the chunk size with the property ``data_chunk_size``. The initial value is 100 000 bytes.

We are going to read the RTO waveform into a PC file *c:\\temp\\rto_waveform_data.bin*:

.. code-block:: python
    
    rto.data_chunk_size = 10000
    rto.query_bin_block_to_file(
        'FORM REAL,32;:CHAN1:DATA?',
        r'c:\temp\rto_waveform_data.bin',
        append=False)
