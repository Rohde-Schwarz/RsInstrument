Finding available instruments
========================================

Similar to the pyvisa's ResourceManager, RsInstrument can search for available instruments:

.. literalinclude:: Example_FindInstrument.py
   :language: python
   :linenos:


If you have more VISAs installed, the one actually used by default is defined by a secret widget called VISA Conflict Manager. You can force your program to use a VISA of your choice:

.. literalinclude:: Example_FindInstrument_SelectVisa.py
   :language: python
   :linenos:

.. tip::
    We believe our R&S VISA is the best choice for our customers. Couple of reasons why:
    
    - Small footprint
    - Superior VXI-11 and HiSLIP performance
    - Integrated legacy sensors NRP-Zxx support
    - Additional VXI-11 and LXI devices search
    - Available for Windows, Linux, Mac OS

Structured discovery API
""""""""""""""""""""""""

``RsInstrument.discovery()`` returns an immutable ``DiscoverySnapshot`` of
``DiscoveredInstrument`` records. By default it only **finds** VISA resource
strings (no instrument traffic). Pass ``identify=True`` to opt into brief
``*IDN?`` queries.

.. literalinclude:: Example_Discovery.py
   :language: python
   :linenos:

Find versus identify:

* **Find** (default) — opens a fresh VISA ResourceManager, calls
  ``list_resources``, and closes the RM. Safe and fast.
* **Identify** (``identify=True``) — additionally opens each resource with
  ``no_lock``, queries ``*IDN?``, and closes the session. Identifications run
  in parallel worker threads (default up to 8) because they are I/O-bound.
  Failures are skipped (``identified=False``); busy instruments are not
  disturbed with an exclusive lock.

SocketIO (``visa_select='socketio'``) does not support VISA discovery; use
``'rs'``, ``'ni'``, or ``'@py'`` instead.

Network enrichment
""""""""""""""""""

Optional enrichment (off by default for ``RsInstrument.discovery()`` / ``run_discovery``;
enabled for the MCP ``Instrument-Discovery`` singleton) adds network metadata without
opening SCPI sessions for identity:

* Parse IPv4 from TCPIP VISA resources into ``DiscoveredInstrument.ip``
* Optional mDNS browse (requires ``RsInstrument[discovery]`` or ``[mcp]``, which pull in
  ``zeroconf``) and merge by IP (``discovery_source``: ``visa`` / ``mdns`` / ``both``)
* LXI HTTP ``GET /lxi/identification`` to fill sparse manufacturer/model/serial
* Reverse DNS (PTR) for ``hostname``

Additional fields on each record: ``ip``, ``hostname``, ``services``,
``discovery_source``, ``notes``. Snapshots also carry ``method_notes`` summarizing
each enrichment step (for example ``visa``, ``mdns``, ``lxi_http``, ``reverse_dns``).

Keyword-only switches on ``run_discovery`` / ``Discovery``:

* ``enrich_lxi`` / ``enrich_dns`` (default ``False``)
* ``mdns_timeout_s`` / ``lxi_timeout_s`` / ``dns_timeout_s`` (default ``2.0``)

Enrichment runs only on live scans; TTL cache hits return already-enriched snapshots.

TTL-cached discovery
""""""""""""""""""""

``Discovery`` is a pull-based helper with an optional TTL cache (default 30 s).
It caches ``DiscoverySnapshot`` results only — never ``RsInstrument`` sessions.
Live misses always open a fresh VISA ResourceManager. Use
``InMemoryDiscoveryCache`` (default) or ``FileDiscoveryCache`` for persistence.

.. literalinclude:: Example_DiscoveryCached.py
   :language: python
   :linenos:

MCP tool ``Instrument-Discovery``
""""""""""""""""""""""""""""""""""

When using the MCP server (``RsInstrument[mcp]``), the built-in
``Instrument-Discovery`` tool returns the same data as JSON. The default call
uses a module-owned ``Discovery`` singleton with a 30 s in-memory TTL; set
``identify`` / ``refresh`` for a live scan. See :ref:`MCP` and the example below.

.. literalinclude:: Example_DiscoveryMcp.py
   :language: python
   :linenos:
