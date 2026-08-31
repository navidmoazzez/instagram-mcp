"""Every failure this server anticipates.

This module exists because of one detail in the MCP Python SDK that is easy to
miss and expensive to get wrong.

`MCPServer` only forwards the message of an exception that subclasses the SDK's
`ToolError`. Anything else is treated as a crash: the model is handed the string
"Error executing tool <name>" and the real message is withheld and logged
server-side. So a tool that raises a plain ValueError with a perfectly written
explanation shows the caller nothing at all.

Every deliberate failure here therefore inherits from ToolError, and the SDK
import happens in exactly one place so a move in a future SDK release is a
one-line fix rather than a hunt.
"""

from __future__ import annotations

from mcp.server.mcpserver.exceptions import ToolError


class InstagramError(ToolError):
    """A failure we saw coming, whose message is meant for the caller to read."""
