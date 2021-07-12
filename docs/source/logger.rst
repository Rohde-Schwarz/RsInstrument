.. _Logger:

RsInstrument.logger
====================

Check the usage in the Getting Started chapter :ref:`Logging <GetingStarted_Logging>`.

.. currentmodule:: RsInstrument.Internal.ScpiLogger

.. autoclass:: ScpiLogger()

   .. autoattribute:: mode
   .. autoattribute:: default_mode
   .. autoattribute:: device_name
   .. automethod:: set_logging_target
   .. autoattribute:: log_to_console
   .. automethod:: info_raw
   .. automethod:: info
   .. automethod:: error
   .. autoattribute:: log_status_check_ok
   .. automethod:: clear_cached_entries
   .. automethod:: set_format_string
   .. automethod:: restore_format_string
   .. autoattribute:: abbreviated_max_len_ascii
   .. autoattribute:: abbreviated_max_len_bin
   .. autoattribute:: abbreviated_max_len_list
   .. autoattribute:: bin_line_block_size
