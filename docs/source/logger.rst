.. _Logger:

RsInstrument.logger
====================

Check the usage in the Getting Started chapter :ref:`Logging <GettingStarted_Logging>`.

.. currentmodule:: RsInstrument.Internal.ScpiLogger

.. autoclass:: ScpiLogger()

   .. autoattribute:: mode
   .. automethod:: stop
   .. automethod:: start
   .. autoattribute:: default_mode
   .. autoattribute:: device_name
   .. automethod:: set_logging_target
   .. automethod:: get_logging_target
   .. automethod:: set_logging_target_global
   .. autoattribute:: log_to_console
   .. autoattribute:: log_to_udp
   .. autoattribute:: log_to_console_and_udp
   .. automethod:: info_raw
   .. automethod:: info
   .. automethod:: error
   .. automethod:: set_relative_timestamp
   .. automethod:: set_relative_timestamp_now
   .. automethod:: get_relative_timestamp
   .. automethod:: clear_relative_timestamp
   .. automethod:: set_time_offset_zero_on_first_entry
   .. automethod:: flush
   .. automethod:: sync_from
   .. autoattribute:: log_status_check_ok
   .. automethod:: clear_cached_entries
   .. automethod:: set_format_string
   .. automethod:: restore_format_string
   .. autoattribute:: abbreviated_max_len_ascii
   .. autoattribute:: abbreviated_max_len_bin
   .. autoattribute:: abbreviated_max_len_list
   .. autoattribute:: bin_line_block_size
   .. autoattribute:: udp_port
   .. autoattribute:: target_auto_flushing
   .. autoattribute:: log_info_replacer
   
.. autoclass:: LogInfoReplacer()
   
   .. automethod:: set_full_replacer
   .. automethod:: put_full_replacer_item
   .. automethod:: pop_full_replacer_item
   .. automethod:: set_regex_sr_replacer
   .. automethod:: put_regex_sr_replacer_item
   .. automethod:: pop_regex_sr_replacer_item
   .. automethod:: clear_replacers
