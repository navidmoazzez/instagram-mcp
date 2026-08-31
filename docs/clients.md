# Client setup

Every MCP client needs the same three things: the command `instagram-mcp`, any
flags as arguments, and your credentials as environment variables. Only the file
and the key names differ.

Claude Code, Claude Desktop, Cursor and the HTTP setup are in the
[README](../README.md#3-install). This page covers the rest.

Clients change their config format more often than this server changes, so if a
block below does not match what your client expects, trust the client's own
documentation and open an issue here.

## The three things

| | Value |
|---|---|
| Command | `instagram-mcp`, or its absolute path if the client does not use your shell PATH |
| Arguments | `--allow-write` to enable writes, `--unofficial` for the private-API tier. Both optional |
| Environment | `IG_ACCESS_TOKEN` and `IG_USER_ID`, or `IG_ACCOUNTS_FILE` |

Get the absolute path with `which instagram-mcp` on macOS and Linux, or
`where instagram-mcp` on Windows.

## VS Code

`.vscode/mcp.json` in the workspace, or the user-level `mcp.json`. Note the key
is `servers`, not `mcpServers`.

```json
{
  "servers": {
    "instagram": {
      "type": "stdio",
      "command": "instagram-mcp",
      "env": {
        "IG_ACCESS_TOKEN": "your_token",
        "IG_USER_ID": "your_ig_user_id"
      }
    }
  }
}
```

## Windsurf

`~/.codeium/windsurf/mcp_config.json`

```json
{
  "mcpServers": {
    "instagram": {
      "command": "instagram-mcp",
      "env": {
        "IG_ACCESS_TOKEN": "your_token",
        "IG_USER_ID": "your_ig_user_id"
      }
    }
  }
}
```

## Cline

Open the MCP Servers panel, choose Configure MCP Servers, and edit
`cline_mcp_settings.json`.

```json
{
  "mcpServers": {
    "instagram": {
      "command": "instagram-mcp",
      "env": {
        "IG_ACCESS_TOKEN": "your_token",
        "IG_USER_ID": "your_ig_user_id"
      }
    }
  }
}
```

## Zed

`settings.json`. Zed calls them context servers.

```json
{
  "context_servers": {
    "instagram": {
      "source": "custom",
      "command": "instagram-mcp",
      "args": [],
      "env": {
        "IG_ACCESS_TOKEN": "your_token",
        "IG_USER_ID": "your_ig_user_id"
      }
    }
  }
}
```

## Codex CLI

`~/.codex/config.toml`

```toml
[mcp_servers.instagram]
command = "instagram-mcp"
args = []

[mcp_servers.instagram.env]
IG_ACCESS_TOKEN = "your_token"
IG_USER_ID = "your_ig_user_id"
```

## Gemini CLI

`~/.gemini/settings.json`

```json
{
  "mcpServers": {
    "instagram": {
      "command": "instagram-mcp",
      "env": {
        "IG_ACCESS_TOKEN": "your_token",
        "IG_USER_ID": "your_ig_user_id"
      }
    }
  }
}
```

## Anything else

If your client speaks MCP over stdio, it will work. If it only speaks HTTP, run
the server with `--http` and point the client at `http://127.0.0.1:8000/mcp`.

```bash
instagram-mcp --http --port 8000
```

Put it behind TLS and an authenticating proxy before exposing it beyond
localhost. This server holds tokens that can post as you and has no
authentication of its own.

## Enabling writes

Add the flag to the arguments, wherever your client puts them.

```json
{
  "command": "instagram-mcp",
  "args": ["--allow-write"]
}
```

Without it the server refuses every tool that publishes, replies, hides, deletes
or sends, and tells the model which flag is missing rather than failing
silently.

## Checking it worked

```bash
instagram-mcp doctor
```

If `doctor` is happy and your client still shows no tools, the problem is
almost always one of two things: the command is not an absolute path and the
client does not inherit your shell PATH, or the client was not fully quit and
reopened after the config change.
