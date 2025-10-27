Multithreading
========================================

You are at the party, many people talking over each other. Not every person can deal with such crosstalk, neither can measurement instruments. For this reason, RsInstrument has a feature of scheduling the access to your instrument by using so-called **Locks**. Locks make sure that there can be just one client at a time 'talking' to your instrument. Talking in this context means completing one communication step - one command write or write/read or write/read/error check.

To describe how it works, and where it matters, we take three typical multithread scenarios:

One instrument session, accessed from multiple threads
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
You are all set - the lock is a part of your instrument session. Check out the following example - it will execute properly, although the instrument gets 10 queries at the same time:

.. literalinclude:: Example_MultithreadOneSession.py
   :language: python
   :linenos:

Shared instrument session, accessed from multiple threads
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
Same as in the previous case, you are all set. The session carries the lock with it. You have two objects, talking to the same instrument from multiple threads. Since the instrument session is shared, the same lock applies to both objects causing the exclusive access to the instrument.

Try the following example:

.. literalinclude:: Example_MultithreadSharedSession.py
   :language: python
   :linenos:

As you see, everything works fine. If you want to simulate some party crosstalk, uncomment the line ``instr2.clear_lock()``. This causes the instr2 session lock to break away from the instr1 session lock. Although the instr1 still tries to schedule its instrument access, the instr2 tries to do the same at the same time, which leads to all the fun stuff happening.

Multiple instrument sessions accessed from multiple threads
"""""""""""""""""""""""""""""""""""""""""""""""""""""""""""""
Here, there are two possible scenarios depending on the instrument's capabilities:

- You are lucky, because you instrument handles each remote session completely separately. An example of such instrument is SMW200A. In this case, you have no need for session locking.
- Your instrument handles all sessions with one set of in/out buffers. You need to lock the session for the duration of a talk. And you are lucky again, because the RsInstrument takes care of it for you. The text below describes this scenario.

Run the following example:

.. literalinclude:: Example_MultithreadMultipleSessions.py
   :language: python
   :linenos:

You have two completely independent sessions that want to talk to the same instrument at the same time. This will not go well, unless they share the same session lock. The key command to achieve this is ``instr2.assign_lock(instr1.get_lock())``
Comment that line, and see how it goes. If despite commenting the line the example runs without issues, you are lucky to have an instrument similar to the SMW200A.