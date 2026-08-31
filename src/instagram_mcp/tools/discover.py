"""Tier 2: public data about accounts you do not own. Still official.

This is the tier that answers the question people actually have, which is not
"how did my post do" but "what is working for the three accounts I am competing
with".

business_discovery is a documented Graph edge. It costs nothing, carries no ban
risk, and runs anywhere a token runs. It is easy to overlook because it hangs
off the Facebook Login path rather than the Instagram one.

Two hard constraints, stated in the tool descriptions rather than buried:

  business_discovery sees Business and Creator accounts only. A personal account
  returns an error, and that is Meta's rule, not a bug here.

  ig_hashtag_search is capped at 30 unique hashtags per rolling 7 days per
  account. Resolved ids are therefore remembered on disk, because spending one
  of thirty on a tag you already looked up on Monday is a real loss.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

from mcp.server import MCPServer
from mcp.types import ToolAnnotations

from ..config import FACEBOOK_HOST, Tier, pick
from ..errors import InstagramError
from ..runtime import Runtime, result
from ..safety import frame_rows

READ = ToolAnnotations(readOnlyHint=True, openWorldHint=True)

DISCOVERY_PROFILE = (
    "followers_count,media_count,biography,name,username,profile_picture_url,website"
)
DISCOVERY_MEDIA = "id,caption,media_type,permalink,timestamp,like_count,comments_count"
HASHTAG_MEDIA_FIELDS = "id,caption,media_type,permalink,like_count,comments_count"

_NEEDS_FACEBOOK = (
    "This tool needs a Facebook Login token, because business_discovery and hashtag search "
    "live on graph.facebook.com and are not reachable with an Instagram Login token. "
    "Run `instagram-mcp token` and pick the Facebook path, then set IG_HOST=graph.facebook.com "
    "or add the account to your IG_ACCOUNTS_FILE with \"host\": \"graph.facebook.com\"."
)


def register(server: MCPServer, runtime: Runtime) -> None:
    settings = runtime.settings
    graph = runtime.graph
    store = runtime.store

    def _target(account: str | None):
        if not settings.has_facebook_login():
            raise InstagramError(_NEEDS_FACEBOOK)
        return pick(settings, account, host=FACEBOOK_HOST)

    async def _discover(target: Any, username: str, posts: int) -> dict[str, Any]:
        clean = username.strip().lstrip("@")
        fields = (
            f"business_discovery.username({clean})"
            f"{{{DISCOVERY_PROFILE},media.limit({posts}){{{DISCOVERY_MEDIA}}}}}"
        )
        body = await graph.call(target, f"/{target.user_id}", {"fields": fields})
        found = body.get("business_discovery") or {}
        if not found:
            raise InstagramError(
                f"Instagram returned nothing for @{clean}. business_discovery only sees "
                "Business and Creator accounts, so a personal or private account will always "
                "come back empty."
            )
        return found

    @server.tool(
        description=(
            "Public profile and recent posts with engagement for any Instagram Business or "
            "Creator account, by username. Official, free, and no risk to your account. "
            "Personal and private accounts are not reachable this way and never will be."
        ),
        annotations=READ,
    )
    async def discover_account(
        username: str, posts: int = 12, account: str | None = None
    ) -> dict[str, Any]:
        target = _target(account)
        found = await _discover(target, username, posts)
        media = (found.get("media") or {}).get("data") or []
        return result(
            Tier.FACEBOOK_LOGIN,
            username=found.get("username"),
            followers=found.get("followers_count"),
            posts_total=found.get("media_count"),
            name=found.get("name"),
            website=found.get("website"),
            biography=frame_rows([{"biography": found.get("biography")}])[0]["biography"],
            recent_media=frame_rows(media),
        )

    @server.tool(
        description=(
            "Several Business or Creator accounts side by side: followers, post count, and "
            "median engagement across their recent posts. This is the competitor question in "
            "one call rather than one call per account."
        ),
        annotations=READ,
    )
    async def compare_accounts(
        usernames: list[str], posts: int = 12, account: str | None = None
    ) -> dict[str, Any]:
        if not 1 <= len(usernames) <= 10:
            raise InstagramError("Pass between 1 and 10 usernames.")
        target = _target(account)

        async def one(name: str) -> dict[str, Any]:
            try:
                found = await _discover(target, name, posts)
            except Exception as exc:
                return {"username": name.lstrip("@"), "status": "error", "detail": str(exc)[:200]}

            media = (found.get("media") or {}).get("data") or []
            likes = sorted(int(m.get("like_count") or 0) for m in media)
            comments = sorted(int(m.get("comments_count") or 0) for m in media)
            followers = int(found.get("followers_count") or 0)
            median_likes = _median(likes)
            return {
                "username": found.get("username"),
                "status": "ok",
                "followers": followers,
                "posts_total": found.get("media_count"),
                "posts_sampled": len(media),
                "median_likes": median_likes,
                "median_comments": _median(comments),
                # Engagement rate over followers, on the sampled posts only. It is
                # the standard comparison and it is also the one people quote
                # without saying what it was measured on, so the denominator and
                # the sample size are both in the output.
                "engagement_rate_pct": (
                    round((median_likes + _median(comments)) / followers * 100, 3)
                    if followers
                    else None
                ),
            }

        rows = await asyncio.gather(*(one(u) for u in usernames))
        return result(
            Tier.FACEBOOK_LOGIN,
            compared=len(rows),
            note="Medians over the sampled posts, not lifetime averages.",
            accounts=sorted(
                rows, key=lambda r: int(r.get("followers") or 0), reverse=True
            ),
        )

    @server.tool(
        description=(
            "Resolve a hashtag name to its id. Instagram caps you at 30 unique hashtags per "
            "rolling 7 days per account, so ids resolved before are reused from disk and do "
            "not spend another one."
        ),
        annotations=READ,
    )
    async def search_hashtag(name: str, account: str | None = None) -> dict[str, Any]:
        clean = name.strip().lstrip("#").lower()
        if not clean:
            raise InstagramError("Pass a hashtag name.")

        if cached := await store.hashtag_id(clean):
            return result(Tier.FACEBOOK_LOGIN, hashtag=clean, id=cached, spent_quota=False)

        target = _target(account)
        body = await graph.call(
            target, "/ig_hashtag_search", {"user_id": target.user_id, "q": clean}
        )
        rows = body.get("data") or []
        if not rows:
            raise InstagramError(f"Instagram knows no hashtag called #{clean}.")

        hashtag_id = str(rows[0]["id"])
        await store.remember_hashtag(clean, hashtag_id)
        cutoff = (datetime.now(UTC) - timedelta(days=7)).isoformat()
        return result(
            Tier.FACEBOOK_LOGIN,
            hashtag=clean,
            id=hashtag_id,
            spent_quota=True,
            unique_hashtags_last_7_days=await store.hashtags_resolved_since(cutoff),
            quota=30,
        )

    async def _hashtag_media(
        edge: str, name: str, limit: int, account: str | None
    ) -> dict[str, Any]:
        clean = name.strip().lstrip("#").lower()
        target = _target(account)
        hashtag_id = await store.hashtag_id(clean)
        if not hashtag_id:
            body = await graph.call(
                target, "/ig_hashtag_search", {"user_id": target.user_id, "q": clean}
            )
            rows = body.get("data") or []
            if not rows:
                raise InstagramError(f"Instagram knows no hashtag called #{clean}.")
            hashtag_id = str(rows[0]["id"])
            await store.remember_hashtag(clean, hashtag_id)

        body = await graph.call(
            target,
            f"/{hashtag_id}/{edge}",
            {"user_id": target.user_id, "fields": HASHTAG_MEDIA_FIELDS, "limit": limit},
        )
        media = body.get("data") or []
        return result(
            Tier.FACEBOOK_LOGIN,
            hashtag=clean,
            edge=edge,
            count=len(media),
            media=frame_rows(media),
        )

    @server.tool(
        description="The top performing recent posts on a hashtag. What is working right now.",
        annotations=READ,
    )
    async def hashtag_top_media(
        hashtag: str, limit: int = 25, account: str | None = None
    ) -> dict[str, Any]:
        return await _hashtag_media("top_media", hashtag, limit, account)

    @server.tool(
        description="The most recent posts on a hashtag, in time order. What is being posted now.",
        annotations=READ,
    )
    async def hashtag_recent_media(
        hashtag: str, limit: int = 25, account: str | None = None
    ) -> dict[str, Any]:
        return await _hashtag_media("recent_media", hashtag, limit, account)


def _median(values: list[int]) -> int:
    """Median rather than mean, because one viral post makes a mean meaningless."""
    if not values:
        return 0
    mid = len(values) // 2
    if len(values) % 2:
        return values[mid]
    return (values[mid - 1] + values[mid]) // 2
