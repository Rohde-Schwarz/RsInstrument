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

Built-in write rules ship in ``RsInstrument/mcp/data/default_write_rules.json`` (validated
at load). Optional ``--write-rules PATH`` loads a custom JSON file merged onto those
defaults by ``rule_id`` (custom entries win). Omit the flag to use shipped defaults only.
See *Write safety* below for the JSON shape and merge semantics.

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

* ``Instrument-Query-SCPI`` — SCPI query only. Any write segment (``;`` or newline
  separated, for example ``SYST:ERR?;*RST``) is rejected with
  ``gate: forbidden`` and ``rule_id: query_tool_rejects_writes``; there is no
  approval prompt. Use ``Instrument-Write-SCPI`` or ``Instrument-Batch-SCPI`` for writes.
* ``Instrument-Write-SCPI`` / ``Instrument-Reset`` — writes are gated by an MCP-only
  SCPI write policy before any instrument I/O. Soft-gated commands (for example
  SMW200A RF power above 0 dBm, VNA stimulus power, or ``*RST``) require human
  approval through MCP elicitation only. Hard-gated commands (for example SMW200A power
  above +20 dBm, or ``SYST:SEC:IMM``) return ``gate: forbidden`` and never send SCPI.
  There is no ``confirm`` tool parameter; clients must use elicitation. See *Write safety*.
* ``Instrument-Fetch-Errors`` — fetch (and typically clear) the instrument error queue.
* ``Instrument-Go-To-Local`` — explicitly sends the instrument back to local front-panel control (GTL).
* ``Instrument-Enable-User-Interaction`` — model-aware front-panel/display interaction
  (for example ``&NREN`` on signal generators, ``SYST:DISP:UPD ON`` on analyzers).
* ``Instrument-Get-Screenshot`` — returns JSON ``{"mime_type": "image/png", "data": "<base64>"}``
  using a model-family screenshot strategy (direct ``HCOPy:DATA?``, MXO display-update,
  analyzer file hardcopy with cleanup, or the generic fallback). The generic fallback reads
  ``MMEM:DATA?`` from the path the caller names, so that path must sit inside a configured
  ``--instrument-file-root``. With no root configured, a caller-named path is refused. The
  server default path needs no root. Screenshots above 16 MiB are refused.
* ``Instrument-Batch-SCPI`` — runs a list of SCPI entries with short-lived handles per entry.
  Matching IEEE headers (default ``*RST`` / ``*RCL``) use ``write_with_opc`` (never a raw
  ``*OPC?`` query). After the batch, the error queue is drained via
  ``query_all_errors_with_codes`` and appended as a ``<error-queue>`` result item.
  Each entry can be a plain string, a ``BatchScpiCommand``, or
  ``{"command": "...", "opc_timeout": 12000}``. An entry with an unquoted ``?`` anywhere
  is a query, including mixed messages such as ``OUTP ON;FREQ?``. Chained writes in such
  an entry are write-policy gated with elicitation; other entries are writes (write policy
  + elicitation).
* ``Instrument-Save-Recall`` — ``*SAV`` / ``*RCL`` for slots ``0..9``. Recall uses
  ``write_with_opc`` and is confirmation-gated.
* ``Instrument-File`` — sandboxed MMEM file transfer (``info``, list/exists/download/upload/read/delete).
  Disabled by default; enable with ``--transport stdio --file-root PATH`` and one or more
  ``--instrument-file-root PATH`` (or ``auto``; or ``BuiltinToolSettings`` / ``FileTransferPolicy``).
  See *Instrument-File (MMEM)* below.
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

Structured results
""""""""""""""""""

**Breaking change:** all built-in tools now return structured dicts instead of
JSON-encoded strings. FastMCP emits these as ``structuredContent`` and also mirrors them as a
JSON text in ``content`` for backwards-compatible clients. Each tool exposes an
``output_schema`` so ``list_tools`` callers can introspect the result shape.

Gate responses (``gate: forbidden``, ``gate: needs_confirmation``, ``gate: cancelled``) are
also plain dicts. They carry the keys ``gate``, ``rule_id``, ``command``, ``model``, and
``reason``; ``needs_confirmation`` responses also carry ``hint``.

Callers that previously parsed tool results with ``json.loads()`` must update to use the
returned dict directly::

    # Before (1.131.x and earlier)
    result_text = await client.call_tool("Instrument-Query-SCPI", {...})
    value = json.loads(result_text)["value"]

    # After (structured results)
    result = await client.call_tool("Instrument-Query-SCPI", {...})
    value = result.structured_content["value"]   # or result.content[0].text parsed as JSON

Write safety (elicitation)
""""""""""""""""""""""""""

Write / Batch / Reset / Save-Recall / File tools evaluate each write against
``ScpiWritePolicy`` using a per-resource ``*IDN?`` model cache (30 s TTL for a known
model; a brief TTL when the model is still unknown after IDN failure).

**Breaking change:** the ``confirm`` parameter was removed from ``Instrument-Write-SCPI``,
``Instrument-Reset``, ``Instrument-Batch-SCPI``, ``Instrument-Save-Recall``, and
``Instrument-File``. An LLM could set ``confirm`` to bypass the write policy. Approval is
only through MCP elicitation. FastMCP rejects unknown tool arguments: clients that still
send ``confirm`` get a tool validation error (unexpected keyword argument). For trusted
deployments, exclude a shipped rule via ``exclude_rules`` in a rules file,
``--exclude-write-rule``, or ``excluded_write_rule_ids`` (see below). A custom overlay
cannot replace a shipped ``forbidden`` rule; exclusions are the only supported escape
hatch for those ids (a warning is logged when you exclude one).

Confirmation uses dual-path elicitation:

* **Handshake protocol** (MCP ≤ 2025-11-25): the tool pauses mid-call with
  ``ctx.elicit(..., response_type=bool)``.
* **Modern protocol** (MCP 2026-07-28+): the tool returns an ``InputRequiredResult`` /
  ``ElicitRequest`` guard; the client re-issues the same ``tools/call`` with answers in
  ``input_responses``. The answer must use the key from the prompt. Each prompt carries a
  random key that the server issues when it asks, and that key is accepted once, within
  5 minutes. A key the client computes in advance is ignored, so it cannot approve a write
  before the server has shown it.

When approval is requested, the elicitation message shows the VISA ``resource``, the
**exact command** the instrument receives, the reason, and every resolved write statement.
Resource, command, reason and each statement are JSON-encoded, so they cannot add lines to
the prompt. A request with more than 25 write statements, or a statement longer than 500
characters, is refused and must be split into smaller requests.

Approval is bound to the resource and the exact command text, so an approval for one spelling
does not cover a different one that normalizes to the same statement. Before the write runs, the
instrument's identity is queried again, bypassing the cache. The write proceeds only if it
is now allowed, or if it still needs confirmation under the same rule that was approved.
Anything else fails closed.

``Instrument-Batch-SCPI`` returns a continuation ``request_state`` when a gated entry needs
approval. The state is signed with a key that exists only in the server process, and it is
bound to the commands it covers and expires 10 minutes after it is issued. The client must
send it back unchanged and must resend the same batch. A tampered, mismatched, or expired
state is rejected with an error, and nothing in the batch runs. A server restart also
invalidates the state, so the batch must be restarted.

When elicitation is unavailable or not used, the write is **not** executed and the tool
returns:

.. code-block:: json

    {
      "gate": "needs_confirmation",
      "rule_id": "smw200a_pow_soft",
      "command": "SOUR:POW 5",
      "model": "SMW200A",
      "reason": "RF output power 5.0 dBm exceeds the soft limit of 0 dBm for SMW200A. Approve to proceed.",
      "hint": "This write needs user approval through MCP elicitation, which the client did not provide. The write was not executed."
    }

Forbidden responses use ``"gate": "forbidden"``; declined elicitation uses
``"gate": "cancelled"``. Core ``RsInstrument.write`` is not gated — only the MCP tools.

**Query vs batch:** ``Instrument-Query-SCPI`` rejects any chained write segment without
prompting. ``Instrument-Write-SCPI`` rejects any message with an unquoted ``?`` (rule
``write_tool_rejects_queries``), because a query response would stay unread on the bus.
Query-shaped ``Instrument-Batch-SCPI`` entries still run chained writes through the write
policy and elicitation before executing the query.

**Steps outside the write policy:** ``Instrument-Get-Screenshot``,
``Instrument-Enable-User-Interaction``, and ``Instrument-Go-To-Local`` send fixed,
model-specific SCPI sequences (for example ``MMEMory:NAME``, ``HCOPy:IMMediate``, GTL, or
display-update commands). They are not evaluated by the write policy. Only the caller-named
screenshot file path is checked, as described under ``Instrument-Get-Screenshot``.

**Save and recall:** ``*SAV`` (rule ``global_confirm_sav``) and ``*RCL`` (rule
``global_confirm_rcl``) both require confirmation.

**Shipped rules and custom overlays:** defaults load from
``RsInstrument/mcp/data/default_write_rules.json``. Merge a custom file with
``--write-rules`` / ``ScpiWritePolicy.from_file`` by ``rule_id`` (custom wins). Custom
files may include ``"$schema": "<path>/write_rules.schema.json"`` (schema ships beside the
defaults) for editor validation. Rule fields include ``models``: a list of
case-insensitive substrings matched against the IDN model (empty list = all models).
``model_substr`` is a deprecated alias folded into ``models``.

If ``*IDN?`` fails (unknown model), model-scoped rules apply conservatively.

A custom rule that reuses the ``rule_id`` of a shipped rule with ``outcome: forbidden`` is
ignored with a warning; only exclusions remove such a rule.

Shipped pattern rules also include global MMEM confirmations:
``global_confirm_mmem_cdir`` (``MMEM:CDIR`` / ``MMEM:MSIS``),
``global_confirm_mmem_copy`` (``COPY`` / ``MOVE``),
``global_confirm_mmem_dir_ops`` (``RDIR`` / ``MDIR`` / ``NAME``), in addition to upload
and delete. Enable rules for RF output, IQ output, preamp, and VNA stimulus/receiver
paths treat numeric boolean forms as ON (for example ``+1``, ``01``, ``1.0``, ``1E0``) as
well as ``ON``.

**Scoped exclusions:** a rules file may set ``exclude_rules`` to a list of ``rule_id``
strings or objects ``{rule_id, models?, resources?}``. Empty ``models`` / ``resources``
mean global scope for that field. ``models`` are case-insensitive substrings of the IDN
model; ``resources`` are case-insensitive ``fnmatch`` globs on the VISA resource string.
Model-scoped exclusions never match when the model is still unknown after IDN failure.
Resource-scoped exclusions from the CLI use ``--exclude-write-rule RULE_ID[@GLOB]``
(repeatable; split on the first ``@``).

To drop default rules without replacing the whole policy, use
``ScpiWritePolicy.defaults(exclude_rule_ids=...)``, ``--exclude-write-rule`` (global id
or ``RULE_ID@GLOB``), ``exclude_rules`` in JSON, or
``BuiltinToolSettings.create(excluded_write_rule_ids=...)``. The latter applies to the
built-in policy and to a custom ``write_policy`` (ids are removed via ``without_rules``).
Scoped exclusions from JSON or CLI are merged via ``with_exclusions``. Empty
``pattern_rules`` / ``value_rules`` in a custom file leave defaults unchanged for that list.

**VNA confirmation rules** (models ZNA, ZNB, ZNBT, ZNB3000, ZNC, ZND, ZNL, ZNLE, ZNH, ZVA,
ZVB, ZVT, ZVL): ``vna_confirm_stimulus_power_enable``,
``vna_confirm_stimulus_generator_enable``, ``vna_confirm_receiver_attenuation``,
``vna_confirm_receiver_attenuation_zvr``, ``vna_confirm_receiver_preamp``,
``vna_confirm_receiver_gain_all``, ``vna_confirm_receiver_gain_port``,
``vna_confirm_receiver_gain_ifg`` — stimulus power/generator enable, receiver attenuation,
preamp enable, and high-gain (LNOise) paths require confirmation.

Chained SCPI statements
""""""""""""""""""""""""

MCP write tools split a command string on ``;``, ``\r``, ``\n``, and ``\r\n`` to produce
individual statements.  Before applying policy rules each statement is resolved to its
**absolute SCPI header path** following the IEEE 488.2 / SCPI compound-header rules:

* **Absolute (leading** ``:``)  — the leading colon is stripped and the compound path
  resets to the new header.  Example: ``OUTP:STAT OFF;:SYST:SEC:IMM`` — the second
  statement resolves to ``SYST:SEC:IMM`` at root level.
* **Common command (leading** ``*``)  — the statement is used as-is (e.g. ``*RST``)
  and does **not** alter the tracked path.  A relative segment after a common command
  still uses the parent of the header that preceded the common command.
* **Newline (``\r``, ``\n``, or ``\r\n``)** — starts a new program message; the path
  resets to root and the next segment is treated as absolute.
* **Relative (everything else)**  — resolution depends on whether the segment's
  header is single-node or multi-node:

  * **Single-node header** (no ``:`` inside the raw keyword) is resolved uniquely:
    prepend the parent.  ``OUTP:STAT OFF;STAT ON`` → ``OUTP:STAT ON``, triggering
    the RF output enable rule.
  * **Multi-node header** (contains ``:`` but does not start with ``:``): **both**
    the raw form and the parent-resolved form are evaluated and the more restrictive
    outcome wins.  For example, ``OUTP:STAT OFF;PROT:STAT ON`` emits both
    ``PROT:STAT ON`` and ``OUTP:PROT:STAT ON``; any rule matching ``OUTP:PROT:STAT``
    therefore fires.  The raw form is retained for backward compatibility — patterns
    like ``SYST:ERR?;SOUR1:POW:STAT ON`` where the raw form already matches the
    intended rule continue to work unchanged.  The *instrument-correct* path tracker
    advances to the parent-resolved form so that subsequent single-node relatives
    (e.g. a trailing ``;STAT ON``) are resolved from the correct instrument root:
    ``SOUR:POW:STAT OFF;GEN:STAT OFF;STAT ON`` correctly gates
    ``SOUR:POW:GEN:STAT ON``, not ``GEN:STAT ON``.  The *raw* path tracker retains
    the raw header and is used to emit a backward-compat secondary form for those
    later single-node relatives.  Multi-node relative segments each contribute two
    entries to the statement list; single-node relatives following a diverged path
    also contribute two entries (relevant to the 25-statement approval-payload guard).

Query segments (header ending with ``?``) are **excluded** from the output but still
**advance the path tracker**, so a query within a chained message does not disrupt the
relative addressing of subsequent writes.

The approval prompt shows the exact command text the instrument receives, together with the
resolved statement list, so the human reviewer sees both the text and the fully qualified,
absolute command form. The approval response key is a digest of the resource and the exact
command text, followed by a nonce that the server generates for that prompt.

Example custom overlay (site policy forbids ``*RST`` globally):

.. literalinclude:: example_write_rules.json
   :language: json

Adding device-specific write policies
""""""""""""""""""""""""""""""""""""""

Use a JSON overlay file (``--write-rules PATH``) to add or tighten write rules for a
specific product family without modifying the shipped defaults.

**Step 1 — choose a rule_id prefix**

* ``global_`` — applies to every instrument (no ``models`` filter).
* ``<family>_`` — applies only to instruments whose IDN model string contains a family
  member substring (e.g., ``vna_``, ``emi_``, ``smw200a_``).

**Step 2 — define or choose a family under** ``families``

The ``families`` key maps a name to a list of case-insensitive model substrings.
Shipped families (``vna``, ``emi_receivers``, ``analyzers``) are available in any
custom file without re-listing. Redefining a shipped family logs a warning and
the custom definition wins.

**Step 3 — write the rule with** ``"models": ["@family_name"]``

.. code-block:: json

    {
      "$schema": "../../RsInstrument/mcp/data/write_rules.schema.json",
      "families": {
        "site_sources": ["SMR40", "SMR50"]
      },
      "pattern_rules": [
        {
          "rule_id": "site_source_confirm_output_enable",
          "pattern": "^OUTP(UT)?(:\\w+)*\\s+(ON|\\+?0*1(\\.0*)?(E[+-]?0*)?)(\\s|$)",
          "outcome": "needs_confirmation",
          "reason": "RF output enable on site source instruments requires lab approval.",
          "models": ["@site_sources"]
        }
      ],
      "value_rules": []
    }

To exclude an existing default rule for specific models, combine with ``exclude_rules``
(see the overlay example at the end of the previous section).

**Step 4 — validate** by adding ``"$schema": "<path>/write_rules.schema.json"`` (schema
ships beside the defaults) and opening the file in an editor with JSON Schema support.

**Step 5 — add tests** using the ``assert_rule_scope`` helper (in
``Testing_Custom/test_scpi_write_policy_analyzer.py``)::

    def test_my_rule_scope() -> None:
        assert_rule_scope(
            "OUTP ON",
            fires_on=["SMR40", ""],   # model match or unknown → conservative
            silent_on=["ZNA", "FSW"],  # known non-matching models → allowed
        )

    def test_my_rule_not_on_query() -> None:
        result = evaluate_write("OUTP?", model="SMR40", policy=policy)
        assert result.outcome == "allowed"

**Step 6 — run:** ``uv run pytest Testing_Custom -k policy``

To exclude a default rule for a subset of models or VISA resources, use
``exclude_rules`` in your overlay as shown in the example above.

Trust boundary
""""""""""""""

Elicitation approval answers and ``Instrument-Batch-SCPI`` ``request_state`` resume tokens
are supplied by the MCP client. The server signs ``request_state``. An approval answer counts
only for a key this server issued for the same resource and command, and only once and within
5 minutes. The approval text is not attested by a signature, so the client still decides
whether to approve. Treat the client as part of your trust boundary for write approval.

A batch that receives approval answers without a valid ``request_state`` stops and runs
nothing; the client must restart the batch.

Approvals and batch state are held in the memory of one server process. A deployment that
runs several server processes behind a load balancer must route each client to the same
process, or approvals and batch state issued by one process are rejected by the others.

Instrument-File (MMEM)
""""""""""""""""""""""

``Instrument-File`` is available only with ``--transport stdio``, ``--file-root`` (local
sandbox), and at least one ``--instrument-file-root`` path or ``auto``.

* **``info``** — returns ``mmem_supported``, live ``default_directory`` (from
  ``MMEM:CDIR?`` when readable), and ``allowed_dirs`` (effective instrument roots after
  policy, including the pinned auto root when ``auto`` is enabled).
* **``list``** without ``instrument_path`` — starts in the instrument current directory
  when that directory is allowed (from ``MMEM:CDIR?``).
* ``--instrument-file-root auto`` — on the first successful ``MMEM:CDIR?`` per VISA
  resource, pins that directory as the sole instrument root for the process lifetime.
  Later ``MMEM:CDIR`` changes or ``*RST`` do not move the pin (CDIR cache may be
  invalidated, but the sandbox boundary stays fixed). Different VISA aliases for the same
  physical instrument receive independent pins and caches. Explicit ``--instrument-file-root``
  paths take precedence over ``auto``. A root-level default directory (``/`` or
  ``C:\``) returns ``status: unsafe_default_directory``. Failed CDIR lookups are cached
  for 2 s (successful reads use a longer TTL). For ``upload`` / ``delete``, instrument
  paths are validated against the allow-list before any approval prompt.
* Devices without MMEM return ``status: mmem_unsupported`` for operations that need catalog
  or CDIR support.

Path checks accept ``\`` and ``/``, reject ``..``, use segment-boundary prefix matching, and
compare drive-letter paths case-insensitively.

Paths embedded in SCPI by built-in tools (for example screenshot or hardcopy file paths)
are validated before sending: single or double quotes, ``;``, CR/LF, NUL, and ``..``
segments are rejected.

**MMEM / default-directory notes** (from R&S SCPI documentation; defaults marked
*unverified* where not confirmed in the manual):

.. list-table::
   :header-rows: 1
   :widths: 18 10 10 62

   * - Family
     - MMEM
     - CDIR query
     - Default directory (when known)
   * - CMA180
     - yes
     - yes
     - ``\`` (MSIS default D:)
   * - CMP180 / CMP200 / CMX500
     - yes
     - yes
     - ``/``
   * - ESW / FPC / FPH / FPL / FSMR3000 / FSV3000 / FSWP / FSWX / RTH / VSE
     - yes
     - yes
     - *unverified*
   * - FSW
     - yes
     - yes+q
     - ``C:\R_S\INSTR\USER``
   * - MXO3 / MXO4 / MXO5
     - yes
     - yes+q
     - *unverified* (``/home/storage/userData``)
   * - RTO / RTP
     - yes
     - yes+q
     - *unverified* (CDIR reset ``\``)
   * - SMA100B / SMB100B / SMBV100B / SMCV100B / SMM100A
     - yes
     - yes
     - ``/var/user/`` (from HCOP docs)
   * - SMW200A
     - yes
     - yes+q
     - ``/var/user/``
   * - ZNA
     - yes
     - yes+q
     - ``C:\Users\Public\Documents\Rohde-Schwarz\ZNA``
   * - ZNB / ZNB3000 / ZNBT / ZND
     - yes
     - yes+q
     - ``C:\Users\Public\Documents\Rohde-Schwarz\Vna``
   * - ZNH
     - yes
     - yes
     - *unverified*
   * - NRPxxS(N) and other NRP sensors
     - no
     - no
     - n/a

Where only the set form of ``MMEM:CDIR`` is documented, ``MMEM:CDIR?`` may still work; a
failing ``MMEM:CDIR?`` is treated as an unknown default directory.

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

Read-only tools (query, fetch-errors, SCPI-exists, discovery) do not close over write
policy; they are still returned as part of the same list. ``Instrument-Go-To-Local`` is
annotated as a state-changing tool, because it restores front-panel control.

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