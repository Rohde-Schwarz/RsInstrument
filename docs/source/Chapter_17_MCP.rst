MCP Server
========================================

The module also provides a simple MCP server that allows remote control of R&S instruments without the need to install any VISA library on the agent side.

.. note::
    Please be aware that you need Python >= 3.10 to run the MCP server.

.. code-block:: shell

    RsInstrument-mcp --host localhost --port 8000 --transport streamable-http

Extend the built-in tools with your own using this blueprint:

.. literalinclude:: Example_CustomTools_MCP.py
   :language: python
   :linenos:

After starting the server, you can access the tools at http://localhost:8000/mcp.