Initiating instrument session
========================================

RsInstrument offers four different types of starting your remote-control session. We begin with the most typical case, and progress with more special ones.

Standard Session Initialization
""""""""""""""""""""""""""""""""""""""""""""""""""""
Initiating new instrument session happens, when you instantiate the RsInstrument object. Below, is a Hello World example. Different resource names are examples for different physical interfaces.

.. include:: Example_HelloWorld.py

.. note::
    If you are wondering about the ``ASRL1::INSTR`` - yes, it works too, but come on... it's 2024 :-)

Do not care about specialty of each session kind; RsInstrument handles all the necessary session settings for you. You have immediately access to many identification properties. Here are same of them:

.. code-block:: python
    
    idn_string: str
    driver_version: str
    visa_manufacturer: str
    full_instrument_model_name: str
    instrument_serial_number: str
    instrument_firmware_version: str
    instrument_options: List[str]

The constructor also contains optional boolean arguments ``id_query`` and ``reset``:

.. code-block:: python

    instr = RsInstrument('TCPIP::192.168.56.101::hislip0', id_query=True, reset=True)

- Setting ``id_query`` to True (default is True) checks, whether your instrument can be used with the RsInstrument module.
- Setting  ``reset`` to True (default is False) resets your instrument. It is equivalent to calling the ``reset()`` method.

If you tend to forget closing the session, use the context-manager. The session is closed even if the block inside ``with`` raises an exception:

.. include:: Example_HelloWorldWithContextManager.py

Selecting specific VISA
""""""""""""""""""""""""""""""""""""""""""""""""""""
Same as for the ``list_resources()`` function , RsInstrument allows you to choose which VISA to use:

.. include:: Example_DifferentVisas.py

No VISA Session
""""""""""""""""""""""""""""""""""""""""""""""""""""
We recommend using VISA whenever possible, preferably with HiSLIP session because of its low latency.
However, if you are a strict VISA-refuser, RsInstrument has something for you too:

**No VISA raw LAN socket**:

.. include:: Example_HelloWorld_SocketIO.py

.. warning::
    Not using VISA can cause problems by debugging when you want to use the communication Trace Tool. The good news is, you can easily switch to use VISA and back just by changing the constructor arguments. The rest of your code stays unchanged.

Simulating Session
""""""""""""""""""""""""""""""""""""""""""""""""""""
If a colleague is currently occupying your instrument, leave him in peace, and open a simulating session:

.. code-block:: python

    instr = RsInstrument('TCPIP::192.168.56.101::hislip0', True, True, "Simulate=True")

More ``option_string`` tokens are separated by comma:

.. code-block:: python

    instr = RsInstrument('TCPIP::192.168.56.101::hislip0', True, True, "SelectVisa='rs', Simulate=True")

.. note::
    Simulating session works as a database - when you write a command **SENSe:FREQ 10MHz**, the query **SENSe:FREQ?** returns **10MHz** back. For queries not preceded by set commands, the RsInstrument returns default values:

    - **'Simulating'** for string queries.
    - **0** for integer queries.
    - **0.0** for float queries.
    - **False** for boolean queries.

Shared Session
""""""""""""""""""""""""""""""""""""""""""""""""""""
In some scenarios, you want to have two independent objects talking to the same instrument. Rather than opening a second VISA connection, share the same one between two or more RsInstrument objects:

.. include:: Example_SessionSharing.py

.. note::
    The ``instr1`` is the object holding the 'master' session. If you call the ``instr1.close()``, the ``instr2`` loses its instrument session as well, and becomes pretty much useless.
