"""The official Graph API layer. Both hosts, one function.

Instagram Login and Facebook Login are the same protocol against different
hosts with different reach, so they share this module and differ only in the
`host` on the Account.

Two details here are easy to get wrong and expensive to get wrong:

  1. DELETE is a real HTTP method. Several servers, ours included, branch on
     GET versus everything-else and quietly send a POST when they meant a
     delete. Graph answers 200 to that POST and changes nothing, so the tool
     reports success while doing nothing at all.

  2. Graph error bodies are far more useful than their status codes. A 400 that
     means "your token expired" and a 400 that means "you asked for a metric
     that no longer exists" need different reactions from the caller, so the
     error text says which it was.
"""

from __future__ import annotations

import asyncio
from typing import Any, Literal

import httpx2

from .config import FACEBOOK_HOST, Account, Settings
from .errors import InstagramError

Method = Literal["GET", "POST", "DELETE"]

# Container processing. Reels and videos are transcoded asynchronously and
# publishing before the container reports FINISHED fails, so publishing polls.
_POLL_INTERVAL_SECONDS = 2.0
_POLL_MAX_ATTEMPTS = 40


class GraphError(InstagramError):
    """A Graph API call failed and the message says why in plain language."""

    def __init__(self, message: str, *, code: int | None = None, subcode: int | None = None):
        super().__init__(message)
        self.code = code
        self.subcode = subcode


def _explain(body: dict[str, Any], status: int, path: str) -> GraphError:
    """Turn a Graph error body into something a person can act on."""
    err = body.get("error") or {}
    message = err.get("message") or f"HTTP {status}"
    code = err.get("code")
    subcode = err.get("error_subcode")

    # The handful of failures that have a specific, actionable cause. Everything
    # else falls through with Meta's own wording, which is usually fine.
    hint = ""
    if code == 190:
        hint = (
            " Your access token is invalid or expired. Instagram Login tokens last 60 days: "
            "run `instagram-mcp refresh` before then, or re-mint with `instagram-mcp token`."
        )
    elif code == 10 or code == 200:
        hint = (
            " This is a permissions failure, not a bad request. The token is missing a scope, "
            "or the endpoint needs Advanced Access through Meta App Review."
        )
    elif code == 4 or code == 17 or code == 32:
        hint = " You are being rate limited by Meta. Wait, then retry."
    elif code == 100 and "metric" in message.lower():
        hint = (
            " Meta retires insight metrics between versions. Run `instagram-mcp doctor` "
            "to see which metrics this account still answers."
        )

    return GraphError(f"{path}: {message}{hint}", code=code, subcode=subcode)


class GraphClient:
    """A shared async HTTP client. One per process, closed on shutdown."""

    def __init__(self, settings: Settings, *, client: httpx2.AsyncClient | None = None):
        self._settings = settings
        self._client = client or httpx2.AsyncClient(timeout=30.0)
        self._owns_client = client is None

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    def _url(self, account: Account, path: str) -> str:
        return f"https://{account.host}/{self._settings.graph_version}{path}"

    async def call(
        self,
        account: Account,
        path: str,
        params: dict[str, Any] | None = None,
        method: Method = "GET",
    ) -> dict[str, Any]:
        """One Graph call. Empty and None values are dropped, never sent as ""."""
        payload = {k: v for k, v in (params or {}).items() if v not in (None, "")}
        payload["access_token"] = account.token

        if method == "GET":
            request = self._client.build_request("GET", self._url(account, path), params=payload)
        elif method == "POST":
            request = self._client.build_request("POST", self._url(account, path), data=payload)
        else:
            # A real DELETE, with the token in the query string. Sending it as a
            # body on a DELETE is not reliably read by Graph.
            request = self._client.build_request(
                "DELETE", self._url(account, path), params=payload
            )

        try:
            response = await self._client.send(request)
        except httpx2.HTTPError as exc:
            raise GraphError(f"{path}: could not reach {account.host}: {exc}") from exc

        try:
            body = response.json()
        except ValueError:
            body = {"raw": response.text[:500]}
        if not isinstance(body, dict):
            body = {"data": body}

        if response.status_code >= 400:
            raise _explain(body, response.status_code, path)
        return body

    async def paginate(
        self,
        account: Account,
        path: str,
        params: dict[str, Any] | None = None,
        *,
        max_items: int = 200,
        page_size: int = 100,
    ) -> list[dict[str, Any]]:
        """Follow cursors until max_items or the data runs out.

        Guarded on both the cap and a missing cursor. A cursor that repeats or
        goes missing would otherwise spin until the client times out, which is
        how "list everything" tools hang.
        """
        out: list[dict[str, Any]] = []
        after: str | None = None
        seen_cursors: set[str] = set()

        while len(out) < max_items:
            page = await self.call(
                account,
                path,
                {**(params or {}), "limit": min(page_size, max_items - len(out)), "after": after},
            )
            rows = page.get("data") or []
            if not isinstance(rows, list) or not rows:
                break
            out.extend(rows)

            after = ((page.get("paging") or {}).get("cursors") or {}).get("after")
            if not after or after in seen_cursors:
                break
            seen_cursors.add(after)

        return out[:max_items]

    async def wait_ready(self, account: Account, container_id: str) -> None:
        """Block until a media container finishes processing, or explain why not."""
        for _ in range(_POLL_MAX_ATTEMPTS):
            status = await self.call(
                account, f"/{container_id}", {"fields": "status_code,status"}
            )
            code = status.get("status_code")
            if code == "FINISHED":
                return
            if code in ("ERROR", "EXPIRED"):
                detail = status.get("status") or ""
                raise GraphError(f"Container {container_id} came back {code}. {detail}".strip())
            await asyncio.sleep(_POLL_INTERVAL_SECONDS)

        waited = int(_POLL_MAX_ATTEMPTS * _POLL_INTERVAL_SECONDS)
        raise GraphError(
            f"Container {container_id} was still processing after {waited}s. "
            "Large videos can take longer. The container is still valid for 24 hours, "
            "so call publish_container with this id once it finishes."
        )

    async def refresh_token(self, account: Account) -> dict[str, Any]:
        """Extend a long-lived token by another 60 days.

        The two hosts do this differently and neither documents it next to the
        other, which is why every reference server skips it and dies at day 60.
        """
        if account.host == FACEBOOK_HOST:
            raise GraphError(
                "Facebook Page tokens do not expire and cannot be refreshed this way. "
                "If yours stopped working, the underlying user token was revoked: re-run "
                "`instagram-mcp token`."
            )
        try:
            response = await self._client.get(
                f"https://{account.host}/refresh_access_token",
                params={"grant_type": "ig_refresh_token", "access_token": account.token},
            )
        except httpx2.HTTPError as exc:
            raise GraphError(f"Could not reach {account.host}: {exc}") from exc

        body = response.json() if response.content else {}
        if response.status_code >= 400:
            raise _explain(body if isinstance(body, dict) else {}, response.status_code, "refresh")
        return body
