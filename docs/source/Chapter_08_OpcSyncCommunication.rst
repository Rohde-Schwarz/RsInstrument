8. OPC-synchronized I/O Communication
========================================

Now we are getting to the cool stuff: OPC-synchronized communication. OPC stands for OPeration Completed. The idea is: use one method (write or query), which sends the command, and polls the instrument's status subsystem until it indicates: **"I'm finished"**. The main advantage is, you can use this mechanism for commands that take several seconds, or minutes to complete, and you are still able to interrupt the process if needed. You can also perform other operations with the instrument in a parallel thread.

Now, you might say: **"This sounds complicated, I'll never use it"**. That is where the RsInstrument comes in: all the **write/query** methods we learned in the previous chapter have their ``_with_opc`` siblings. For example: ``write_str()`` has ``write_str_with_opc()``. You can use them just like the normal write/query with one difference: They all have an optional parameter ``timeout``, where you define the maximum time to wait. If you omit it, it uses a value from ``opc_timeout`` property.
Important difference between the meaning of ``visa_timeout`` and ``opc_timeout``:

- ``visa_timeout`` is a VISA IO communication timeout. **It does not play any role in the** ``_with_opc()`` methods. It only defines timeout for the standard ``query_xxx()`` methods. We recommend to keep it to maximum of 10000 ms.
- ``opc_timeout`` is a RsInstrument internal timeout, that serves as a default value to all the ``_with_opc()`` methods. If you explicitly define it in the method API, it is valid only for that one method call.

That was too much theory... now an example:

.. include:: Example_MethodsWithOpc.py
