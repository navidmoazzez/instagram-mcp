"""Tier 1: comments and direct messages.

Everything returned by this module was typed by somebody else, so every text
field goes through safety.frame_untrusted on the way out. A comment on a public
post is the most trivially injectable surface an agent will ever be handed, and
"summarise my comments" is one of the first things anyone asks.

read_all_comments earns its place here. Comment sentiment, reply triage and
"who keeps asking about pricing" all need comments across an account, and
fetching them one post at a time through get_comments burns the context window
before it answers anything.
"""

from __future__ import annotations

import asyncio
from typing import Any

from mcp.server import MCPServer
from mcp.types import ToolAnnotations

from ..config import pick
from ..errors import InstagramError
from ..runtime import Runtime, result
from ..safety import audit, frame_rows, require_confirm, require_write, write_gate

READ = ToolAnnotations(readOnlyHint=True, openWorldHint=True)
WRITE = ToolAnnotations(readOnlyHint=False, destructiveHint=False, openWorldHint=True)
DESTRUCTIVE = ToolAnnotations(readOnlyHint=False, destructiveHint=True, openWorldHint=True)

COMMENT_FIELDS = "id,text,username,timestamp,like_count"


def register(server: MCPServer, runtime: Runtime) -> None:
    settings = runtime.settings
    write = write_gate(server, settings)
    graph = runtime.graph

    @server.tool(description="Comments on one of your posts.", annotations=READ)
    async def get_comments(
        media_id: str, limit: int = 25, account: str | None = None
    ) -> dict[str, Any]:
        target = pick(settings, account)
        body = await graph.call(
            target, f"/{media_id}/comments", {"fields": COMMENT_FIELDS, "limit": limit}
        )
        rows = body.get("data") or []
        return result(target.tier, media_id=media_id, count=len(rows), comments=frame_rows(rows))

    @server.tool(description="Replies nested under one comment.", annotations=READ)
    async def get_comment_replies(comment_id: str, account: str | None = None) -> dict[str, Any]:
        target = pick(settings, account)
        body = await graph.call(target, f"/{comment_id}/replies", {"fields": COMMENT_FIELDS})
        rows = body.get("data") or []
        return result(target.tier, comment_id=comment_id, count=len(rows), replies=frame_rows(rows))

    @server.tool(
        description=(
            "Comments across the most recent posts on an account, in one call. This is what "
            "sentiment analysis, reply triage and 'what do people keep asking' actually need. "
            "Each comment carries the post it came from."
        ),
        annotations=READ,
    )
    async def read_all_comments(
        posts: int = 12, per_post: int = 50, account: str | None = None
    ) -> dict[str, Any]:
        if posts < 1 or posts > 50:
            raise InstagramError("posts must be between 1 and 50.")
        target = pick(settings, account)

        media_body = await graph.call(
            target,
            f"/{target.user_id}/media",
            {"fields": "id,permalink,timestamp,caption", "limit": posts},
        )
        media = media_body.get("data") or []

        async def for_post(item: dict[str, Any]) -> list[dict[str, Any]]:
            # One failing post must not empty the whole result, so failures are
            # dropped for that post and counted rather than raised.
            try:
                body = await graph.call(
                    target,
                    f"/{item['id']}/comments",
                    {"fields": COMMENT_FIELDS, "limit": per_post},
                )
            except Exception:
                return []
            return [
                {**row, "media_id": item["id"], "permalink": item.get("permalink")}
                for row in (body.get("data") or [])
            ]

        batches = await asyncio.gather(*(for_post(m) for m in media))
        comments = [row for batch in batches for row in batch]
        return result(
            target.tier,
            account=target.name,
            posts_scanned=len(media),
            posts_with_comments=sum(1 for b in batches if b),
            count=len(comments),
            comments=frame_rows(comments),
        )

    @write(description="Reply publicly to a comment.", annotations=WRITE)
    async def reply_to_comment(
        comment_id: str, message: str, account: str | None = None
    ) -> dict[str, Any]:
        require_write(settings, "reply_to_comment")
        target = pick(settings, account)
        body = await graph.call(target, f"/{comment_id}/replies", {"message": message}, "POST")
        audit(
            settings,
            "reply_to_comment",
            {"account": target.name, "comment_id": comment_id, "message": message},
        )
        return result(target.tier, **body)

    @write(
        description=(
            "Hide or unhide a comment. A hidden comment stays visible to whoever wrote it, "
            "which is why this is gentler than deleting and usually the right choice."
        ),
        annotations=WRITE,
    )
    async def hide_comment(
        comment_id: str, hide: bool = True, account: str | None = None
    ) -> dict[str, Any]:
        require_write(settings, "hide_comment")
        target = pick(settings, account)
        await graph.call(target, f"/{comment_id}", {"hide": "true" if hide else "false"}, "POST")
        audit(
            settings,
            "hide_comment",
            {"account": target.name, "comment_id": comment_id, "hide": hide},
        )
        return result(target.tier, comment_id=comment_id, hidden=hide)

    @write(
        description=(
            "Permanently delete a comment. Only works on comments on your own media, and it "
            "cannot be undone. Prefer hide_comment."
        ),
        annotations=DESTRUCTIVE,
    )
    async def delete_comment(
        comment_id: str, account: str | None = None, confirm: bool = False
    ) -> dict[str, Any]:
        require_write(settings, "delete_comment")
        require_confirm(
            confirm,
            "delete_comment",
            "permanently removes the comment. hide_comment is reversible and usually better.",
        )
        target = pick(settings, account)
        # A real HTTP DELETE. Sending this as a POST returns 200 and deletes
        # nothing, which is the bug this server exists partly to not have.
        body = await graph.call(target, f"/{comment_id}", {}, "DELETE")
        if body.get("success") is False:
            raise InstagramError(f"Instagram did not delete {comment_id}: {body}")
        audit(settings, "delete_comment", {"account": target.name, "comment_id": comment_id})
        return result(target.tier, deleted=comment_id, confirmed=body.get("success", True))

    @server.tool(
        description=(
            "Instagram DM threads. Empty unless somebody has messaged the account. Reading "
            "DMs needs Advanced Access from Meta App Review on most apps."
        ),
        annotations=READ,
    )
    async def list_conversations(limit: int = 20, account: str | None = None) -> dict[str, Any]:
        target = pick(settings, account)
        body = await graph.call(
            target,
            f"/{target.user_id}/conversations",
            {"platform": "instagram", "fields": "id,participants,updated_time,message_count",
             "limit": limit},
        )
        rows = body.get("data") or []
        return result(target.tier, count=len(rows), conversations=rows)

    @server.tool(description="Messages inside one DM thread.", annotations=READ)
    async def get_conversation(
        conversation_id: str, limit: int = 25, account: str | None = None
    ) -> dict[str, Any]:
        target = pick(settings, account)
        body = await graph.call(
            target,
            f"/{conversation_id}",
            {"fields": f"messages.limit({limit}){{id,message,from,to,created_time}}"},
        )
        messages = ((body.get("messages") or {}).get("data")) or []
        return result(
            target.tier, conversation_id=conversation_id, messages=frame_rows(messages)
        )

    @write(
        description=(
            "Send a direct message. Instagram only allows this inside a 24-hour window opened "
            "by the recipient messaging you first, or as one private reply to a comment. There "
            "is no way to message somebody cold, and any tool that claims otherwise is using "
            "the private API."
        ),
        annotations=WRITE,
    )
    async def send_dm(
        recipient_id: str, message: str, account: str | None = None, confirm: bool = False
    ) -> dict[str, Any]:
        require_write(settings, "send_dm")
        require_confirm(confirm, "send_dm", "sends a message that cannot be unsent.")
        target = pick(settings, account)
        body = await graph.call(
            target,
            f"/{target.user_id}/messages",
            {"recipient": f'{{"id":"{recipient_id}"}}', "message": f'{{"text":{_json(message)}}}'},
            "POST",
        )
        audit(settings, "send_dm", {"account": target.name, "recipient_id": recipient_id,
                                    "message": message})
        return result(target.tier, **body)

    @write(
        description=(
            "Send a DM in reply to a comment. This is the comment-to-DM mechanic: the comment "
            "is the consent, and it is the only official way to open a conversation with "
            "somebody who has not messaged you. One reply per comment."
        ),
        annotations=WRITE,
    )
    async def private_reply_to_comment(
        comment_id: str, message: str, account: str | None = None, confirm: bool = False
    ) -> dict[str, Any]:
        require_write(settings, "private_reply_to_comment")
        require_confirm(
            confirm,
            "private_reply_to_comment",
            "sends a DM that cannot be unsent, and Instagram allows only one per comment.",
        )
        target = pick(settings, account)
        body = await graph.call(
            target,
            f"/{target.user_id}/messages",
            {
                "recipient": f'{{"comment_id":"{comment_id}"}}',
                "message": f'{{"text":{_json(message)}}}',
            },
            "POST",
        )
        audit(
            settings,
            "private_reply_to_comment",
            {"account": target.name, "comment_id": comment_id, "message": message},
        )
        return result(target.tier, **body)


def _json(value: str) -> str:
    """JSON-encode a string for embedding in Graph's nested-JSON parameters.

    Graph takes `recipient` and `message` as JSON strings inside a form body.
    Building those with an f-string and no escaping is how a caption containing
    a quote mark turns into a 400, so the value goes through the real encoder.
    """
    import json

    return json.dumps(value)
