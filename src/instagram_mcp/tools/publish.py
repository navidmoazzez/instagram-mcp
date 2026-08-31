"""Tier 1: publishing. These tools work by default and disappear under IG_READ_ONLY.

The ones that put something public take confirm=True, because a post cannot be
unpublished from a chat window. create_container does not: staging is the safe
half of the pair and confirming it would train the reflex that makes the
confirmation on publish worthless.

Instagram publishing is two calls, always. You create a media container, then
you publish it. The container never appears in the app and is discarded unused
after 24 hours, which makes it the closest thing Instagram has to a draft and
the only way to stage something for review before it goes live.

There is no native scheduling. Anything that claims to schedule an Instagram
post is holding the job somewhere else and publishing it at the time. This
server does not pretend otherwise.
"""

from __future__ import annotations

from typing import Any

from mcp.server import MCPServer
from mcp.types import ToolAnnotations

from ..config import pick
from ..errors import InstagramError
from ..runtime import Runtime, result
from ..safety import audit, require_confirm, require_write, write_gate

WRITE = ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=True)


def register(server: MCPServer, runtime: Runtime) -> None:
    settings = runtime.settings
    write = write_gate(server, settings)
    graph = runtime.graph

    async def _create(target: Any, fields: dict[str, Any]) -> str:
        body = await graph.call(target, f"/{target.user_id}/media", fields, "POST")
        container = body.get("id")
        if not container:
            raise InstagramError(
                f"Instagram accepted the container call but returned no id: {body}"
            )
        return str(container)

    async def _publish(target: Any, container_id: str) -> dict[str, Any]:
        await graph.wait_ready(target, container_id)
        body = await graph.call(
            target, f"/{target.user_id}/media_publish", {"creation_id": container_id}, "POST"
        )
        media_id = str(body.get("id"))
        detail = await graph.call(
            target, f"/{media_id}", {"fields": "id,permalink,timestamp,media_type"}
        )
        audit(settings, "publish", {"account": target.name, "media_id": media_id})
        return detail

    @write(
        description=(
            "Stage media without posting it. Nothing appears in the app and the container "
            "expires unused after 24 hours. This is the only draft-like state Instagram has, "
            "so use it when a human should see something before it goes live."
        ),
        annotations=WRITE,
    )
    async def create_container(
        caption: str | None = None,
        image_url: str | None = None,
        video_url: str | None = None,
        media_type: str = "IMAGE",
        cover_url: str | None = None,
        location_id: str | None = None,
        is_carousel_item: bool = False,
        account: str | None = None,
    ) -> dict[str, Any]:
        require_write(settings, "create_container")
        if media_type not in ("IMAGE", "REELS", "STORIES"):
            raise InstagramError("media_type must be IMAGE, REELS or STORIES.")
        if not image_url and not video_url:
            raise InstagramError(
                "Pass image_url or video_url. Meta fetches the file from that URL."
            )

        target = pick(settings, account)
        container = await _create(
            target,
            {
                "caption": caption,
                "image_url": image_url,
                "video_url": video_url,
                # IMAGE is the default and Graph rejects it as an explicit value.
                "media_type": None if media_type == "IMAGE" else media_type,
                "cover_url": cover_url,
                "location_id": location_id,
                "is_carousel_item": "true" if is_carousel_item else None,
            },
        )
        audit(settings, "create_container", {"account": target.name, "container_id": container})
        return result(
            target.tier,
            container_id=container,
            published=False,
            note="Not live. Call publish_container with this id to post it.",
        )

    @write(
        description="Publish a staged container. This makes it live and cannot be undone.",
        annotations=WRITE,
    )
    async def publish_container(
        container_id: str, account: str | None = None, confirm: bool = False
    ) -> dict[str, Any]:
        require_write(settings, "publish_container")
        require_confirm(
            confirm, "publish_container", "posts publicly to the account and cannot be undone."
        )
        target = pick(settings, account)
        return result(target.tier, **await _publish(target, container_id))

    @write(
        description=(
            "Publish in one step: stage, wait for processing, publish. Use create_container "
            "instead when a person should approve the post first."
        ),
        annotations=WRITE,
    )
    async def post(
        caption: str | None = None,
        image_url: str | None = None,
        video_url: str | None = None,
        media_type: str = "IMAGE",
        account: str | None = None,
        confirm: bool = False,
    ) -> dict[str, Any]:
        require_write(settings, "post")
        require_confirm(confirm, "post", "publishes immediately and cannot be undone.")
        if media_type not in ("IMAGE", "REELS", "STORIES"):
            raise InstagramError("media_type must be IMAGE, REELS or STORIES.")
        if not image_url and not video_url:
            raise InstagramError(
                "Pass image_url or video_url. Meta fetches the file from that URL."
            )

        target = pick(settings, account)
        container = await _create(
            target,
            {
                "caption": caption,
                "image_url": image_url,
                "video_url": video_url,
                "media_type": None if media_type == "IMAGE" else media_type,
            },
        )
        return result(target.tier, **await _publish(target, container))

    @write(description="Publish a carousel of 2 to 10 images.", annotations=WRITE)
    async def post_carousel(
        image_urls: list[str],
        caption: str | None = None,
        account: str | None = None,
        confirm: bool = False,
    ) -> dict[str, Any]:
        require_write(settings, "post_carousel")
        require_confirm(confirm, "post_carousel", "publishes immediately and cannot be undone.")
        if not 2 <= len(image_urls) <= 10:
            raise InstagramError(f"A carousel takes 2 to 10 images. You passed {len(image_urls)}.")

        target = pick(settings, account)
        # Children are created in sequence on purpose. Meta rate limits container
        # creation per account, and firing ten at once earns a 4 where ten in a
        # row does not.
        children = [
            await _create(target, {"image_url": url, "is_carousel_item": "true"})
            for url in image_urls
        ]
        parent = await _create(
            target,
            {"media_type": "CAROUSEL", "caption": caption, "children": ",".join(children)},
        )
        detail = await _publish(target, parent)
        return result(target.tier, items=len(children), **detail)

    @write(
        description="Publish a reel from a public video URL, with an optional cover frame.",
        annotations=WRITE,
    )
    async def publish_reel(
        video_url: str,
        caption: str | None = None,
        cover_url: str | None = None,
        share_to_feed: bool = True,
        account: str | None = None,
        confirm: bool = False,
    ) -> dict[str, Any]:
        require_write(settings, "publish_reel")
        require_confirm(confirm, "publish_reel", "publishes immediately and cannot be undone.")
        target = pick(settings, account)
        container = await _create(
            target,
            {
                "media_type": "REELS",
                "video_url": video_url,
                "caption": caption,
                "cover_url": cover_url,
                "share_to_feed": "true" if share_to_feed else "false",
            },
        )
        return result(target.tier, **await _publish(target, container))

    @write(
        description="Publish an image or video story. It disappears after 24 hours.",
        annotations=WRITE,
    )
    async def publish_story(
        image_url: str | None = None,
        video_url: str | None = None,
        account: str | None = None,
        confirm: bool = False,
    ) -> dict[str, Any]:
        require_write(settings, "publish_story")
        require_confirm(confirm, "publish_story", "posts a story visible for 24 hours.")
        if not image_url and not video_url:
            raise InstagramError("A story needs image_url or video_url.")
        target = pick(settings, account)
        container = await _create(
            target, {"media_type": "STORIES", "image_url": image_url, "video_url": video_url}
        )
        detail = await _publish(target, container)
        return result(target.tier, expires_in_hours=24, **detail)
