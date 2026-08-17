.. _MCP:

MCP Server
========================================

The module also provides a simple MCP server that allows remote control of R&S instruments without the need to install any VISA library on the agent side.

.. note::
    Please be aware that you need Python >= 3.10 to run the MCP server.

First, install ``RsInstrument`` with the ``mcp`` extra to pull in the required dependencies:

.. code-block:: shell

    pip install RsInstrument[mcp]

To correlate MCP tool calls with distributed traces, also install the ``otel`` extra and enable tracing in your process before starting the server (see :ref:`GettingStarted_OTEL`):

.. code-block:: shell

    pip install RsInstrument[mcp,otel]

Then start the server:

.. code-block:: shell

    RsInstrument-mcp --host localhost --port 8000 --transport streamable-http

Optional ``--write-rules PATH`` loads a JSON write-policy file that is merged onto the
built-in rules by ``rule_id`` (file wins). Omit the flag to keep built-in defaults.
See *Write safety* below for the JSON shape.

Extend the built-in tools with your own using this blueprint:

.. literalinclude:: Example_CustomTools_MCP.py
   :language: python
   :linenos:

After starting the server, you can access the tools at http://localhost:8000/mcp.

Built-in tools and behavior
"""""""""""""""""""""""""""""

The default server registers these tools (names are stable identifiers for ``tools/call``).
Each built-in tool sets MCP ``ToolAnnotations`` hints (``readOnlyHint``, ``destructiveHint``,
``idempotentHint``, ``openWorldHint``) so clients can decide confirmation / retry UX.
All instrument tools use ``openWorldHint=True`` (VISA / external device).

* ``Instrument-Query-SCPI`` — read-only SCPI query.
* ``Instrument-Write-SCPI`` / ``Instrument-Reset`` — writes are gated by an MCP-only
  SCPI write policy before any instrument I/O. Soft-gated commands (for example
  SMW200A RF power above 0 dBm, or ``*RST``) require human confirmation via FastMCP
  `User Elicitation <https://gofastmcp.com/servers/elicitation>`__ when the client
  supports it, or a second call with ``confirm=true``. Hard-gated commands (for
  example SMW200A power above +20 dBm, or ``SYST:SEC:IMM``) return a
  ``gate: forbidden`` JSON payload and never send SCPI. See *Write safety* below.
* ``Instrument-Fetch-Errors`` — fetch (and typically clear) the instrument error queue.
* ``Instrument-Go-To-Local`` — explicitly sends the instrument back to local front-panel control (GTL).
* ``Instrument-Enable-User-Interaction`` — model-aware front-panel/display interaction
  (for example ``&NREN`` on signal generators, ``SYST:DISP:UPD ON`` on analyzers).
* ``Instrument-Get-Screenshot`` — returns JSON ``{"mime_type": "image/png", "data": "<base64>"}``
  using a model-family screenshot strategy (direct ``HCOPy:DATA?``, MXO display-update,
  analyzer file hardcopy with cleanup, or configurable fallback path).
* ``Instrument-Batch-SCPI`` — runs a list of SCPI entries with short-lived handles per entry.
  Matching IEEE headers (default ``*RST`` / ``*RCL``) use ``write_with_opc`` (never a raw
  ``*OPC?`` query). After the batch, the error queue is drained via
  ``query_all_errors_with_codes`` and appended as a ``<error-queue>`` result item.
  Each entry can be a plain string, a ``BatchScpiCommand``, or
  ``{"command": "...", "opc_timeout": 12000}``. Entries containing ``?`` are queries;
  others are writes (write policy + optional ``confirm=true``).
* ``Instrument-Save-Recall`` — ``*SAV`` / ``*RCL`` for slots ``0..9``. Recall uses
  ``write_with_opc`` and is confirmation-gated.
* ``Instrument-File`` — sandboxed MMEM file transfer (list/exists/download/upload/read/delete).
  Disabled by default; enable with ``--transport stdio --file-root PATH`` and one or more
  ``--instrument-file-root PATH`` (or ``BuiltinToolSettings`` / ``FileTransferPolicy``).
* ``Instrument-SCPI-Exists`` — when the instrument supports ``SYST:HELP:HEAD?``, matches a
  command path with exact, longest-prefix, or ordered-subsequence fragment matching;
  returns JSON ``exists``, ``matched_header``, ``matches``, ``match_type``, ``truncated``,
  and ``supported``.
* ``Instrument-Discovery`` — returns VISA-visible instruments as JSON, including network enrichment fields and top-level ``method_notes``. Default call uses a module-owned ``Discovery`` singleton with a 30 s in-memory TTL and enrichment enabled (``enrich_lxi`` / ``enrich_dns``). Set ``identify=true`` / ``refresh=true`` (or a non-default ``expression`` / ``visa_select``) for a live scan (``"source": "live"``). ``model`` / ``manufacturer`` filters require ``identify=true``. See chapter *Finding available instruments* and ``Example_DiscoveryMcp.py``.

Ownership boundary
"""""""""""""""""""

RsInstrument MCP owns generic VISA/SCPI transport, synchronization, status/error handling,
live command-tree matching, screenshots, local-control primitives, instrument file transfer,
and IEEE save/recall. Product-specific MCPs own manuals, help/RAG, panel diagrams, option
catalogs, and product workflow overlays. There is no connection pool: every operation uses a
bounded short-lived ``RsInstrument`` context.

Write safety (elicitation)
""""""""""""""""""""""""""

Write / Batch / Reset / Save-Recall / File tools evaluate each write against ``scpi_write_policy`` using a
per-resource ``*IDN?`` model cache (30 s TTL). Confirmation uses dual-path elicitation:

* **Handshake protocol** (MCP ≤ 2025-11-25): the tool pauses mid-call with
  ``ctx.elicit(..., response_type=bool)``.
* **Modern protocol** (MCP 2026-07-28+): the tool returns an ``InputRequiredResult`` /
  ``ElicitRequest`` guard; the client re-issues the same ``tools/call`` with answers in
  ``input_responses``. Modern support requires a client and server library that
  negotiate MCP 2026-07-28; otherwise the server falls through to handshake or the
  ``confirm=true`` fallback.

When elicitation is unavailable, the tool returns:

.. code-block:: json

    {
      "gate": "needs_confirmation",
      "rule_id": "smw200a_pow_soft",
      "command": "SOUR:POW 5",
      "model": "SMW200A",
      "reason": "RF output power 5.0 dBm exceeds the soft limit of 0 dBm for SMW200A. Approve to proceed.",
      "confirm_hint": "Re-call this tool with confirm=true to approve."
    }

Forbidden responses use ``"gate": "forbidden"``; declined elicitation uses
``"gate": "cancelled"``. Core ``RsInstrument.write`` is not gated — only the MCP tools.

Override or extend the built-in rules with a JSON file (``--write-rules`` /
``ScpiWritePolicy.from_file``). Empty ``pattern_rules`` / ``value_rules`` lists leave
defaults unchanged. To drop selected default rules, use
``ScpiWritePolicy.defaults(exclude_rule_ids=...)`` or
``BuiltinToolSettings.create(excluded_write_rule_ids=...)`` (applies only when no custom
``write_policy`` is supplied). File overlays still merge by ``rule_id`` (file wins):

.. literalinclude:: example_write_rules.json
   :language: json

To extend your own FastMCP server, call ``add_builtin_tools``:

.. code-block:: python

    from fastmcp import FastMCP
    from RsInstrument.mcp import BuiltinToolSettings, ScpiWritePolicy, add_builtin_tools

    server = FastMCP("my-instrument-server")
    settings = BuiltinToolSettings.create(
        write_policy=ScpiWritePolicy.from_file("write-rules.json"),
        excluded_tools={"Instrument-Discovery"},
    )
    add_builtin_tools(server, settings)

``excluded_tools`` contains stable built-in tool names and does not remove tools already
registered on the server. When no settings are supplied, all built-ins are
added with the default write / batch / device-profile / file-transfer policies.

Extension API (``RsInstrument.mcp``)
""""""""""""""""""""""""""""""""""""""

Import the assembly helpers from the package root. Tool *implementations* live in
submodules (``basic_tools``, ``batch``, ``device_io``, …); the root is the supported
way to run a server or attach the built-ins to your own FastMCP app.

.. list-table:: Public names on ``RsInstrument.mcp``
   :header-rows: 1
   :widths: 35 65

   * - Name
     - Use when
   * - ``run`` / ``create_fastmcp_server``
     - Start or build a full RsInstrument MCP server in process.
   * - ``main``
     - Console entry point for ``RsInstrument-mcp`` (not typically imported).
   * - ``add_builtin_tools``
     - Register all (or settings-filtered) built-ins on an existing FastMCP server.
   * - ``BuiltinToolSettings``
     - Bundle write / batch / device / file policies and ``excluded_tools``.
   * - ``ScpiWritePolicy`` / ``ScpiBatchPolicy`` / ``FileTransferPolicy``
     - Configure write gating, OPC batch headers, and MMEM sandboxing.
   * - ``DeviceIoProfile`` / ``DeviceIoProfileRegistry``
     - Product MCP: prepend model-family screenshot / local-control profiles.
   * - ``BatchScpiCommand``
     - Typed batch entry (command + optional per-entry ``opc_timeout``).
   * - ``create_builtin_tool_specs``
     - Fetch a fresh list of ``ToolSpec`` values with policies already bound.
   * - ``merge_tool_specs``
     - Concatenate / override tool lists (later same ``name`` wins).
   * - ``ToolSpec`` / ``safe_tool``
     - Describe and wrap custom tools for registration.

**Prefer** ``add_builtin_tools(server, settings)`` or
``run(..., builtin_settings=settings)`` when you only need the stock tools on a
server. Both call ``create_builtin_tool_specs`` for you, so write gating uses your
``ScpiWritePolicy``.

Fetching built-ins for custom registration
''''''''''''''''''''''''''''''''''''''''''

Use ``create_builtin_tool_specs(settings)`` when you need the built-in list
*without* registering it yet — for example to inspect names, drop or reorder
entries, or merge with product-specific tools before ``run`` /
``create_fastmcp_server``.

The verb-based name is intentional: each call builds **new** callables that close
over the settings you pass. Policy-bound tools are:

* ``Instrument-Write-SCPI``, ``Instrument-Reset``, ``Instrument-Batch-SCPI``,
  ``Instrument-Save-Recall``, ``Instrument-File`` — bind ``write_policy``
  (batch also binds ``batch_policy``; file also binds ``file_transfer``).
* ``Instrument-Enable-User-Interaction``, ``Instrument-Get-Screenshot`` — bind
  ``device_profiles``.

Read-only tools (query, fetch-errors, go-to-local, SCPI-exists, discovery) do not
close over write policy; they are still returned as part of the same list.

.. important::
   Do **not** import module-level write tools such as
   ``from RsInstrument.mcp.basic_tools import instrument_write_scpi`` and
   register them on a production server when you need custom write rules.
   Those aliases are created once with ``ScpiWritePolicy.defaults()`` for tests
   and simple experiments. They ignore ``BuiltinToolSettings`` /
   ``--write-rules``. Always take write-gated tools from
   ``create_builtin_tool_specs(settings)`` (or from ``add_builtin_tools`` /
   ``run``, which use that factory).

Composable registration (subset + custom tools):

.. literalinclude:: Example_ComposeBuiltinTools_MCP.py
   :language: python
   :linenos:

Custom tools can also be passed through the ``tools=`` argument of
``create_fastmcp_server`` / ``run`` while leaving ``include_builtin_tools=True``
(the default); later same-name entries replace built-ins. Pass
``include_builtin_tools=False`` when the ``tools=`` list already contains the
full set (as in the compose example). Use ``@safe_tool`` for exception-to-string
handling on both sync and async custom tools.

Product MCPs can prepend ``DeviceIoProfile`` entries via
``DeviceIoProfileRegistry.defaults(additional_profiles=...)`` and extend OPC-synced
batch headers via ``ScpiBatchPolicy.defaults(additional_opc_commands=...)``.
Pass those objects into ``BuiltinToolSettings.create(...)`` so
``create_builtin_tool_specs`` / ``add_builtin_tools`` pick them up.

Distributed tracing (OpenTelemetry)
""""""""""""""""""""""""""""""""""""""

The RsInstrument MCP server is built on **FastMCP**. For trace context over MCP, follow the **official FastMCP documentation** — do not invent alternate shapes for new integrations.

.. seealso::

   `OpenTelemetry and tracing (FastMCP) <https://gofastmcp.com/servers/telemetry>`__
      How server spans, client spans, and export configuration work.

   `fastmcp.telemetry API <https://gofastmcp.com/python-sdk/fastmcp-telemetry>`__
      ``inject_trace_context`` and ``extract_trace_context`` for MCP ``meta``.

**What you should do:** put W3C ``traceparent`` and optional ``tracestate`` on the **MCP ``tools/call`` params** ``meta`` / ``_meta`` at the **top level**, exactly as FastMCP documents (the same keys the HTTP W3C Trace Context headers use). The FastMCP **client** can merge those keys via ``inject_trace_context`` when calling tools; the **server** reads them when creating ``tools/call`` spans. That path is fully handled by FastMCP — no RsInstrument-specific contract.

**JSON-RPC example** (flat ``_meta``, matches FastMCP / W3C field names):

.. code-block:: json

    {
      "method": "tools/call",
      "params": {
        "name": "Instrument-Query-SCPI",
        "arguments": { "command": "*IDN?", "resource": "TCPIP0::1::INSTR" },
        "_meta": {
          "traceparent": "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01",
          "tracestate": "vendor=value"
        }
      }
    }

**Legacy note:** older material may show ``_meta.otel.traceparent``. That is **not** what FastMCP's ``extract_trace_context`` reads (it only inspects top-level ``traceparent`` / ``tracestate`` on ``meta``). New integrations should use the FastMCP-documented ``meta`` layout above.

Rules (RsInstrument server):

* Follow FastMCP for semantics of ``traceparent`` / ``tracestate`` (see the API doc linked above).
* Malformed values must not break tool calls; invalid propagation input is ignored by the OTEL stack without echoing raw header values.
* Trace context on MCP uses **params** ``_meta`` / ``meta`` only for this server (stdio, SSE, streamable-http); HTTP header fallback is not part of the RsInstrument MCP story.