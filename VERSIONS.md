# Instagram MCP Versions

| Component | Version | Last Updated |
|-----------|---------|--------------|
| instagram-mcp | 0.1.0 | 2026-08-31 |

---

## 0.1.0

First release.

### What it does

Gives any AI agent access to Instagram across three tiers of access, behind one
tool surface, with every result labelled by the tier that answered it.

45 tools. stdio and streamable HTTP, so it works in Claude Code, Claude Desktop,
Cursor, VS Code, Windsurf, Zed, Cline, Codex CLI, Gemini CLI, and over HTTP from
claude.ai and ChatGPT.

### The three tiers

| Tier | Reaches | Risk |
|---|---|---|
| Instagram Login | accounts you own | none |
| Facebook Login | the above, plus public data on any Business or Creator account, plus hashtags | none |
| Unofficial | any public account, the real inbox, search | account restriction |

The Facebook Login tier is the one worth knowing about. `discover_account`
and `compare_accounts` answer competitor questions officially, for free, with no
scraping.

### Safety

- Read-only unless started with `--allow-write`.
- The unofficial tier needs `--unofficial`, and its library is not installed by
  default, so a plain install cannot reach it at all.
- Comments, captions, biographies and DMs are wrapped in an untrusted-content
  fence before they reach the model.
- Every write appends to an audit log the model cannot read or edit.
- The unofficial tier paces itself and stops at a local hourly ceiling.
- `follow_user`, `unfollow_user` and `bulk_like` are deliberately absent.
- `instagram-mcp login` never stores a password, and no password ever goes into
  an MCP client config.

### Notable

- Multiple accounts on one server, with a preference order where an exact name
  match beats a prefix match.
- Automatic token refresh, so the integration does not die at day 60.
- A local SQLite store, so `growth_history` and `post_movement` can answer what
  changed rather than only what is true right now.
- `instagram-mcp doctor` tests every token, names which insight metrics your
  account still answers, and checks whether `business_discovery` works on your
  app.
- `instagram-mcp token` does the short-lived to long-lived exchange and prints a
  ready-to-paste accounts file.

### Verified at build time

- Graph API v26.0 is the newest live version. v27.0 does not resolve.
- The Python MCP SDK is 2.1.1, where `FastMCP` was renamed to `MCPServer` and
  `mcp.server.fastmcp` no longer exists.
- Only exceptions subclassing the SDK's `ToolError` have their message
  forwarded to the model. Everything else is replaced with a generic string, so
  every anticipated failure here inherits from it.
- instagrapi 2.18.18 is current and actively maintained.

### Not verified

- `business_discovery` was not tested against a live Page-linked token. The code
  path is written and `instagram-mcp doctor` tests it in one command. Run that
  before relying on the Facebook Login tier.
- Insight metric names change between Graph versions. `doctor` reports the
  working set per account, and every insights tool takes a `metrics` override.
