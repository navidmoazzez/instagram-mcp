"""What every tool needs, assembled once and passed in.

Tools take a Runtime rather than reaching for module-level globals, so a test
can build one against a fake transport without touching the network or the
user's real session file.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .config import Settings, Tier
from .graph import GraphClient
from .store import Store
from .unofficial import Unofficial


@dataclass
class Runtime:
    settings: Settings
    graph: GraphClient
    store: Store
    unofficial: Unofficial

    async def aclose(self) -> None:
        await self.graph.aclose()
        self.store.close()


def result(tier: Tier, **payload: Any) -> dict[str, Any]:
    """Every tool answers in this envelope.

    `source` is the point. A model that cannot tell official data from scraped
    data will happily present a private-API guess as an official metric, and the
    person reading it has no way to know. One field fixes that, and it costs
    nothing.
    """
    return {"source": tier.value, **payload}
