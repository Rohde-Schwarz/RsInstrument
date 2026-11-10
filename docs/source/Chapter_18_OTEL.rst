.. _GettingStarted_OTEL:

OpenTelemetry Tracing and Metrics
========================================

RsInstrument includes optional OpenTelemetry (OTEL) instrumentation that wraps every SCPI write and query with a trace span and records round-trip times in a histogram. This gives you:

- **Latency histograms per firmware version** — spot drift across releases on a Grafana heatmap
- **Automatic span correlation with pytest** — every SCPI call appears as a child of the current test span
- **Zero overhead when disabled** — when no OTEL exporter is configured, the instrumentation is a no-op

.. note::
    The OTEL integration is fully optional. ``RsInstrument`` works exactly the same without it. The ``otel`` extra only pulls in ``opentelemetry-api`` and ``opentelemetry-sdk``.

    Import ``setup_otel`` and ``teardown_otel`` from the ``RsInstrument.otel``
    submodule — they are **not** re-exported from the top-level ``RsInstrument``
    package, so existing code that does not use OTEL is unaffected.


Installation
""""""""""""""""""""""""""""""""""""""""""

Install ``RsInstrument`` with the ``otel`` extra:

.. code-block:: shell

    pip install RsInstrument[otel]


Quick start
""""""""""""""""""""""""""""""""""""""""""

.. literalinclude:: Example_OTEL_BasicSetup.py
   :language: python
   :linenos:

That is all you need. Every ``write()`` and ``query()`` call now produces a span and a histogram data point.

MCP inbound propagation
""""""""""""""""""""""""""""""""""""""""""

When you run the optional MCP server with ``RsInstrument[mcp,otel]``, distributed tracing for MCP ``tools/call`` follows **FastMCP** (see `OpenTelemetry and tracing (FastMCP) <https://gofastmcp.com/servers/telemetry>`__ and `fastmcp.telemetry <https://gofastmcp.com/python-sdk/fastmcp-telemetry>`__): put ``traceparent`` / ``tracestate`` on **top-level** request ``meta`` as documented there. Nested ``meta.otel`` is not supported by RsInstrument; see :ref:`MCP Server <MCP>`. SCPI spans from ``RsInstrument.otel`` still require ``setup_otel()`` in the server process.


Configuration
""""""""""""""""""""""""""""""""""""""""""

``setup_otel()`` accepts keyword arguments that map directly to the standard OTEL environment variables.
This is the recommended approach -- no need to touch ``os.environ`` yourself:

.. code-block:: python

    from RsInstrument.otel import setup_otel

    setup_otel(
        traces_exporter="otlp",
        otlp_endpoint="http://localhost:4318",
        service_name="my-test-bench",
    )

.. list-table:: ``setup_otel`` Keyword Arguments
   :header-rows: 1
   :widths: 28 37 35

   * - Keyword
     - Environment Variable
     - Example
   * - ``traces_exporter``
     - ``OTEL_TRACES_EXPORTER``
     - ``"otlp"``, ``"console"``
   * - ``otlp_endpoint``
     - ``OTEL_EXPORTER_OTLP_ENDPOINT``
     - ``"http://localhost:4318"``
   * - ``otlp_traces_endpoint``
     - ``OTEL_EXPORTER_OTLP_TRACES_ENDPOINT``
     - ``"http://localhost:4318/v1/traces"``
   * - ``otlp_protocol``
     - ``OTEL_EXPORTER_OTLP_PROTOCOL``
     - ``"grpc"``, ``"http/protobuf"``
   * - ``otlp_headers``
     - ``OTEL_EXPORTER_OTLP_HEADERS``
     - ``"Authorization=Bearer token"``
   * - ``service_name``
     - ``OTEL_SERVICE_NAME``
     - ``"scpi-bench"``
   * - ``resource_attributes``
     - ``OTEL_RESOURCE_ATTRIBUTES``
     - ``"env=prod,team=rf"``

Only non-``None`` kwargs are written, so existing environment variables are preserved unless explicitly overridden.

The following environment variables can also be set outside of code and are read automatically:

.. list-table:: Additional Environment Variables
   :header-rows: 1
   :widths: 35 65

   * - Variable
     - Description
   * - ``RS_INSTRUMENT_OTEL_ENABLED``
     - Master override. Set to ``true`` or ``false`` to force-enable or force-disable, regardless of the standard variables.
   * - ``RS_INSTRUMENT_OTEL_ATTRIBUTES``
     - Comma-separated ``key=value`` pairs added to every span (e.g. ``dut.rack=A3,test.suite=regression``).

You can also pass per-setup attributes in code:

.. code-block:: python

    from RsInstrument.otel import setup_otel

    setup_otel(extra_attributes={"test.suite": "phase_noise"})


What gets traced
""""""""""""""""""""""""""""""""""""""""""

``setup_otel()`` patches three categories of methods on ``RsInstrument``:

1. **Write methods** (12) — ``write()``, ``write_str()``, ``write_int()``, ``write_with_opc()``, etc. Direction: ``write``.
2. **Query methods** (24) — ``query()``, ``query_str()``, ``query_float()``, ``query_with_opc()``, etc. Direction: ``query``.
3. **Fixed-command methods** (5) — ``reset()`` (``*RST``), ``query_opc()`` (``*OPC?``), ``clear_status()`` (``*CLS``), ``self_test()`` (``*TST?``), ``check_status()`` (``SYST:ERR?``).

Each span carries these attributes:

.. list-table:: Span Attributes
   :header-rows: 1
   :widths: 35 65

   * - Attribute
     - Example
   * - ``instrument.scpi.command``
     - ``FREQ:CENT 1E9``
   * - ``instrument.scpi.direction``
     - ``write`` or ``query``
   * - ``instrument.firmware_version``
     - ``5.30.305.57``
   * - ``instrument.resource_name``
     - ``TCPIP::192.168.1.1::INSTR``
   * - ``instrument.model``
     - ``SMBV100B``
   * - ``instrument.serial_number``
     - ``100012``
   * - ``instrument.material_number``
     - ``1423.1003K02``
   * - ``instrument.host``
     - ``smbv100b-104445`` (empty if unknown)

.. list-table:: Histogram Attributes (``instrument.scpi.latency``)
   :header-rows: 1
   :widths: 35 65

   * - Attribute
     - Example
   * - ``command``
     - ``FREQ:CENT`` (first token)
   * - ``direction``
     - ``write`` or ``query``
   * - ``firmware_version``
     - ``5.30.305.57``
   * - ``instrument.model``
     - ``SMBV100B``
   * - ``instrument.material_number``
     - ``1423.1003K02``
   * - ``instrument.host``
     - ``smbv100b-104445`` (empty if unknown)
   * - ``error.type``
     - absent on success, otherwise the exception class name, e.g. ``TimeoutException``

Failed calls are recorded in the histogram as well, with ``error.type`` set. Successful calls omit the attribute, following the OpenTelemetry convention.

Error counter
""""""""""""""""""""""""""""""""""""""""""

Every SCPI operation that raises an ``Exception`` increments the counter ``instrument.scpi.errors`` (unit ``{error}``). The counter carries the same attributes as the latency histogram, and ``error.type`` is always non-empty.

- ``error.type`` is ``type(exc).__name__`` of the exception that escaped the wrapped call, for example ``TimeoutException`` or ``StatusException``. Chained exceptions are not walked; the outermost class name is used.
- ``KeyboardInterrupt`` and ``GeneratorExit`` are not ``Exception`` subclasses. They do not mark the span, are recorded in the histogram without ``error.type`` and do not increment the counter.
- The metric names are available as the constants ``SCPI_LATENCY_METRIC`` and ``SCPI_ERRORS_METRIC`` in ``RsInstrument.otel.instrumentor``, which allows feature detection.

Host attribute
""""""""""""""""""""""""""""""""""""""""""

``instrument.host`` is derived from the VISA resource string and always set (empty string when no host can be determined):

- The scheme must start with ``TCPIP`` (case-insensitive). The host is the second ``::`` token, stripped and lowercased.
- ``TCPIP0::SMBV100B-104445::inst0::INSTR`` gives ``smbv100b-104445``; ``TCPIP::10.1.2.3::5025::SOCKET`` gives ``10.1.2.3``; ``TCPIP::host::INSTR`` gives ``host``.
- IPv6 addresses must be bracketed: ``TCPIP::[fe80::1]::5025::SOCKET`` gives ``fe80::1``. Unbracketed IPv6 addresses are rejected when they produce more than three ``::`` tokens (``TCPIP::fe80::1::5025::SOCKET`` gives an empty string). A three-token unbracketed form such as ``TCPIP::fe80::1::INSTR`` cannot be told apart from a host name, so always bracket IPv6 addresses.
- A failing metric export call never replaces the exception raised by the SCPI operation.
- USB, GPIB, ASRL, empty and malformed resource names give an empty string.
- A device addressed once by hostname and once by IP address produces two different ``instrument.host`` values.

Prometheus converts the dots in attribute names to underscores. Example queries:

.. code-block:: text

    # Errors per firmware version and error class over 1 hour
    sum by (firmware_version, error_type) (increase(instrument_scpi_errors_total[1h]))

    # Timeout rate per instrument host
    sum by (instrument_host) (rate(instrument_scpi_errors_total{error_type="TimeoutException"}[5m]))

.. note::
   **Span vs. histogram attribute design** -- Spans carry full per-unit
   detail (``serial_number``, ``resource_name``) for trace-level debugging.
   The histogram uses only family (``model``), variant
   (``material_number``), ``host`` and ``error.type`` attributes to keep
   metric cardinality bounded.
   ``serial_number`` is the pure unit ID (e.g. ``100012``), split from
   the combined ``instrument_serial_number`` property
   (``1423.1003K02/100012``).  ``model`` always uses
   ``full_instrument_model_name`` (e.g. ``SMBV100B``), never the
   shortened ``instrument_model_name`` (``SMBV``).
   All values are cached from the initial ``*IDN?`` handshake -- no
   extra SCPI queries are needed.


Span hierarchy
""""""""""""""""""""""""""""""""""""""""""

Spans created by ``setup_otel()`` automatically become children of the active OTEL context. When used with ``pytest-opentelemetry``, this produces a tree like:

.. code-block:: text

    pytest session
      └── test_phase_noise                          (from pytest-opentelemetry)
           ├── SCPI write write            [*RST]              12ms
           ├── SCPI query query            [*IDN?]             45ms
           ├── SCPI write write_float      [FREQ:CENT 1E9]     8ms
           └── SCPI query query_float      [CALC:MARK:FUNC:PNOISE:RES?]  85ms


Pytest integration
""""""""""""""""""""""""""""""""""""""""""

The most common usage is a session-scoped fixture in ``conftest.py``:

.. literalinclude:: Example_OTEL_PytestIntegration.py
   :language: python
   :linenos:


Visualizing with Grafana
""""""""""""""""""""""""""""""""""""""""""

The ``instrument.scpi.latency`` histogram can be visualized as a **heatmap** in Grafana, grouped by ``firmware_version``. This makes it easy to detect latency drift across firmware releases.

- **Traces**: Use Jaeger, Grafana Tempo, or any OTLP-compatible trace backend to view the full span tree per test.
- **Metrics**: Use Prometheus (via the OTEL collector) or Grafana Mimir to store histograms and build dashboards.

.. tip::
    Group the heatmap by ``firmware_version`` to compare timing distributions across instrument software versions. A shift in the distribution signals firmware-induced latency changes.


Teardown
""""""""""""""""""""""""""""""""""""""""""

``teardown_otel()`` restores all original ``RsInstrument`` methods:

.. code-block:: python

    from RsInstrument.otel import teardown_otel

    teardown_otel()

This is useful in test cleanup or when you need to reconfigure the instrumentation at runtime.


Excluding methods
""""""""""""""""""""""""""""""""""""""""""

If certain methods are on a time-critical path and you do not want even the small overhead of span creation, exclude them:

.. code-block:: python

    from RsInstrument.otel import setup_otel

    setup_otel(exclude={"write", "write_str"})

Excluded methods are not patched and behave exactly as before.
