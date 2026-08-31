"""The unofficial tier. Off unless you ask for it twice.

This is the part that reaches what no official API will ever return: any public
profile's full history, followers and following, other people's stories, search,
your real inbox. It is also the part that can get an Instagram account
restricted, so it is gated at two separate layers:

  1. instagrapi is an optional dependency. A plain `uvx instagram-mcp` cannot
     import this module at all, whatever flags are passed.
  2. The server must be started with --unofficial.

The credential design is deliberate. An MCP client config is JSON that people
paste into issues, screenshots and Discord threads, and it is read by every MCP
server the client runs, not just this one. A password in there is a password
handed to all of them.

So there is no password here. `instagram-mcp login` runs once, interactively,
in a terminal, and writes a session file. The server only ever loads that file.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from .config import Settings
from .errors import InstagramError
from .safety import Pacer

INSTALL_HINT = (
    "The unofficial tier needs instagrapi, which is not installed by default. "
    'Install it with `uv tool install "instagram-mcp[unofficial]"`, or run '
    '`uvx --from "instagram-mcp[unofficial]" instagram-mcp`.'
)

LOGIN_HINT = (
    "No saved Instagram session. Run `instagram-mcp login` once in a terminal. "
    "It will ask for your username and password, handle two-factor if you have it "
    "on, and save a session file. Your password is never stored and never goes "
    "into any config file."
)


class UnofficialUnavailable(InstagramError):
    """The unofficial tier was asked for and cannot be provided."""


def _import_client():
    """Import instagrapi lazily, so the package installs and runs without it."""
    try:
        from instagrapi import Client  # noqa: PLC0415
    except ImportError as exc:  # pragma: no cover - depends on install shape
        raise UnofficialUnavailable(INSTALL_HINT) from exc
    return Client


def login_interactive(session_path: Path, username: str, password: str, code: str | None) -> str:
    """Log in and write a session file. Called by the CLI, never by a tool.

    Returns the username the session belongs to. Raises with a readable message
    on the three failures that actually happen: wrong password, two-factor
    needed, and a challenge.
    """
    from instagrapi.exceptions import (  # noqa: PLC0415
        BadPassword,
        ChallengeRequired,
        TwoFactorRequired,
    )

    client = _import_client()()
    client.delay_range = [1, 3]

    try:
        client.login(username, password, verification_code=code or "")
    except TwoFactorRequired as exc:
        raise RuntimeError(
            "This account has two-factor authentication on. Run the same command again "
            "with --code and the six digits from your authenticator app or SMS."
        ) from exc
    except BadPassword as exc:
        raise RuntimeError("Instagram rejected that username and password.") from exc
    except ChallengeRequired as exc:
        raise RuntimeError(
            "Instagram wants to verify this login. Open the Instagram app, approve the "
            "login prompt, then run this command again. If you keep getting challenged, "
            "the account is flagged and you should stop rather than retrying."
        ) from exc

    session_path.parent.mkdir(parents=True, exist_ok=True)
    client.dump_settings(session_path)
    # The session is a credential. Owner read and write only.
    session_path.chmod(0o600)
    return username


class Unofficial:
    """A paced, thread-offloaded wrapper around one instagrapi client.

    instagrapi is synchronous and does real network work, so every call goes
    through asyncio.to_thread. Calling it directly from the event loop would
    stall every other tool for the duration.
    """

    def __init__(self, settings: Settings):
        self._settings = settings
        self._pacer = Pacer(settings)
        self._client: Any | None = None
        self._lock = asyncio.Lock()

    @property
    def enabled(self) -> bool:
        return self._settings.unofficial

    def _require_enabled(self) -> None:
        if not self._settings.unofficial:
            raise UnofficialUnavailable(
                "This tool needs the unofficial tier, which is off. Restart the server "
                "with --unofficial to turn it on. Read the Risks section of the README "
                "first: this tier can get your Instagram account restricted, and you "
                "should point it at a secondary account rather than your main one."
            )

    async def client(self) -> Any:
        """Load the session once, then reuse it. Re-login is never automatic.

        A silent re-login on an expired session is how these tools get accounts
        flagged: it turns one bad credential into a login attempt on every
        subsequent call. If the session is dead, the user is told once.
        """
        self._require_enabled()
        async with self._lock:
            if self._client is not None:
                return self._client

            # Order matters. Without instagrapi, `instagram-mcp login` cannot run
            # either, so telling someone to log in first sends them round a loop
            # that ends in an import error.
            _import_client()

            path = self._settings.session_path
            if not path.exists():
                raise UnofficialUnavailable(LOGIN_HINT)

            def build() -> Any:
                from instagrapi.exceptions import ClientError, LoginRequired  # noqa: PLC0415

                client = _import_client()()
                client.delay_range = list(self._settings.pace_seconds)
                client.load_settings(path)
                try:
                    client.account_info()
                except (LoginRequired, ClientError) as exc:
                    raise UnofficialUnavailable(
                        "The saved session is no longer valid. Run `instagram-mcp login` "
                        f"again. Instagram said: {exc}"
                    ) from exc
                return client

            self._client = await asyncio.to_thread(build)
            return self._client

    async def run(self, method: str, /, *args: Any, **kwargs: Any) -> Any:
        """Pace, then call one instagrapi method off the event loop."""
        client = await self.client()
        await self._pacer.wait()

        def work() -> Any:
            from instagrapi.exceptions import (  # noqa: PLC0415
                ClientError,
                LoginRequired,
                PleaseWaitFewMinutes,
            )

            try:
                return getattr(client, method)(*args, **kwargs)
            except PleaseWaitFewMinutes as exc:
                raise UnofficialUnavailable(
                    "Instagram asked us to wait. This is the early warning before a "
                    "restriction: stop using the unofficial tier for a few hours rather "
                    "than retrying."
                ) from exc
            except LoginRequired as exc:
                raise UnofficialUnavailable(
                    "The session expired mid-call. Run `instagram-mcp login` again."
                ) from exc
            except ClientError as exc:
                raise UnofficialUnavailable(f"Instagram refused: {exc}") from exc

        return await asyncio.to_thread(work)

    def pacer_status(self) -> dict[str, Any]:
        return self._pacer.status()


def simplify(value: Any) -> Any:
    """Flatten instagrapi's pydantic models into plain JSON-safe values.

    instagrapi returns rich pydantic objects full of HttpUrl and datetime, and
    handing those to the MCP serialiser produces either a crash or an unreadable
    blob. One recursive pass fixes both.
    """
    if hasattr(value, "model_dump"):
        return simplify(value.model_dump())
    if isinstance(value, dict):
        return {k: simplify(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [simplify(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)
