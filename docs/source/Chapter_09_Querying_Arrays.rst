9. Querying Arrays
========================================

Often you need to query an array of numbers from your instrument, for example a spectrum analyzer trace or an oscilloscope waveform.
Many programmers stick to transferring such arrays in ASCII format, because of the simplicity. Although simple, it is quite inefficient: one float 32-bit number can take up to 12 characters (bytes), compared to 4 bytes in a binary form. Well, with RsInstrument do not worry about the complexity: we have one method for binary or ascii array transfer.

Querying Float Arrays
""""""""""""""""""""""""""""""""""""""""""""""""""""
Let us look at the example below. The method doing all the magic is ``query_bin_or_ascii_float_list()``. In the 'waveform' variable, we get back a list of float numbers:

.. include:: Example_QueryFloatArray_ASCII.py

You might say: *I would do this with a simple 'query-string-and-split-on-commas'...* and you are right. The magic happens when we want the same waveform in binary form.
One additional setting we need though - the binary data from the instrument does not contain information about its encoding. Is it 4 bytes float, or 8 bytes float? Low Endian or Big Endian? This, we specify with the property ``bin_float_numbers_format``:

.. include:: Example_QueryFloatArray_Bin.py

.. tip::
    To find out in which format your instrument sends the binary data, check out the format settings: **FORM REAL,32** means floats, 4 bytes per number. It might be tricky to find out whether to swap the endianness. We recommend you simply try it out - there are only two options. If you see too many NaN values returned, you probably chose the wrong one:

    - ``BinFloatFormat.Single_4bytes`` means the instrument and the control PC use the same endianness
    - ``BinFloatFormat.Single_4bytes_swapped`` means they use opposite endianness

    The same is valid for double arrays: settings **FORM REAL,64** corresponds to either ``BinFloatFormat.Double_8bytes`` or ``BinFloatFormat.Double_8bytes_swapped``

Querying Integer Arrays
""""""""""""""""""""""""""""""""""""""""""""""""""""
For performance reasons, we split querying float and integer arrays into two separate methods. The following example shows both ascii and binary array query. Here, the magic method is ``query_bin_or_ascii_int_list()`` returning list of integers:

.. include:: Example_QueryIntArray_AsciiBin.py