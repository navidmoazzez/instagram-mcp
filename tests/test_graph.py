from __future__ import annotations

import httpx2
import pytest

from instagram_mcp.config import Account, Settings
from instagram_mcp.graph import GraphClient, GraphError


def build(handler) -> GraphClient:
    settings = Settings(accounts=[Account(name="a", user_id="1", token="t")])
    return GraphClient(settings, client=httpx2.AsyncClient(transport=httpx2.MockTransport(handler)))


ACCOUNT = Account(name="a", user_id="1", token="t")


async def test_delete_sends_a_real_delete():
    """The bug this server exists partly to not have.

    Branching on `method == "GET"` and treating everything else as a POST makes
    a delete return 200 and change nothing, so the tool reports success while
    the comment is still there.
    """
    seen = []

    def handler(request):
        seen.append(request.method)
        return httpx2.Response(200, json={"success": True})

    client = build(handler)
    await client.call(ACCOUNT, "/c1", {}, "DELETE")
    assert seen == ["DELETE"]
    await client.aclose()


async def test_post_sends_a_form_body_not_a_query_string():
    def handler(request):
        assert request.method == "POST"
        assert b"caption=hello" in request.content
        return httpx2.Response(200, json={"id": "1"})

    client = build(handler)
    await client.call(ACCOUNT, "/1/media", {"caption": "hello"}, "POST")
    await client.aclose()


async def test_empty_values_are_dropped_rather_than_sent_blank():
    def handler(request):
        assert "caption" not in request.url.params
        assert "location_id" not in request.url.params
        return httpx2.Response(200, json={})

    client = build(handler)
    await client.call(ACCOUNT, "/1/media", {"caption": None, "location_id": ""})
    await client.aclose()


async def test_expired_token_explains_the_fix():
    def handler(request):
        return httpx2.Response(400, json={"error": {"message": "Session expired", "code": 190}})

    client = build(handler)
    with pytest.raises(GraphError, match="refresh"):
        await client.call(ACCOUNT, "/me")
    await client.aclose()


async def test_permission_failure_is_named_as_one():
    def handler(request):
        return httpx2.Response(400, json={"error": {"message": "no", "code": 10}})

    client = build(handler)
    with pytest.raises(GraphError, match="App Review"):
        await client.call(ACCOUNT, "/me")
    await client.aclose()


async def test_pagination_stops_on_a_repeated_cursor():
    """A cursor that never advances would otherwise spin until the client times out."""
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx2.Response(
            200,
            json={"data": [{"id": str(calls["n"])}], "paging": {"cursors": {"after": "SAME"}}},
        )

    client = build(handler)
    rows = await client.paginate(ACCOUNT, "/1/media", max_items=100)
    assert calls["n"] == 2  # first page, then the repeat is detected
    assert len(rows) == 2
    await client.aclose()


async def test_pagination_respects_max_items():
    def handler(request):
        return httpx2.Response(
            200,
            json={
                "data": [{"id": str(i)} for i in range(100)],
                "paging": {"cursors": {"after": f"c{request.url.params.get('after', 0)}x"}},
            },
        )

    client = build(handler)
    rows = await client.paginate(ACCOUNT, "/1/media", max_items=150)
    assert len(rows) == 150
    await client.aclose()


async def test_facebook_page_tokens_are_not_refreshable():
    client = build(lambda r: httpx2.Response(200, json={}))
    fb = Account(name="a", user_id="1", token="t", host="graph.facebook.com")
    with pytest.raises(GraphError, match="do not expire"):
        await client.refresh_token(fb)
    await client.aclose()
