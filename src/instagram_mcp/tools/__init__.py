"""Tool registration.

Split by tier and by what the tools touch, not by Graph endpoint, because the
question a reader has is "what can this reach and what does it risk", never
"which edge does this call".
"""

from __future__ import annotations

from mcp.server import MCPServer

from ..runtime import Runtime
from . import discover, engage, own, publish
from . import unofficial as unofficial_tools


def register_all(server: MCPServer, runtime: Runtime) -> None:
    own.register(server, runtime)
    publish.register(server, runtime)
    engage.register(server, runtime)
    discover.register(server, runtime)
    unofficial_tools.register(server, runtime)
