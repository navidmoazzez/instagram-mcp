# Instagram MCP

Give any AI agent access to Instagram. Read your own accounts, research any
Business or Creator account on the platform, publish, and answer comments, from
Claude, ChatGPT, Cursor, or any MCP client.

Three tiers of access behind one tool surface, and every answer tells you which
tier it came from.

Built by [Navid Moazzez](https://navid.me).

```
You: which of my last 20 posts is still growing, and what are my
     three closest competitors doing that I am not?

Claude: Reading your account, then comparing.

  Still climbing (likes gained since the last reading)
    "The 4 AI tools I actually pay for"     +412  posted 6 days ago
    "Nobody talks about this part"          +198  posted 3 days ago

  Competitors, median engagement over their last 12 posts
    @a   118k followers   4.1%   carousels, 7 to 9 slides
    @b    64k followers   3.3%   reels under 20 seconds
    @c   210k followers   1.2%   single images

  The one thing all three do that you do not: the first slide is a
  question, not a claim.
```

## Contents

| | Section | |
|---|---|---|
| 1 | [What you can ask it](#1-what-you-can-ask-it) | Real prompts, not features |
| 2 | [The three tiers](#2-the-three-tiers) | Read this before installing |
| 3 | [Install](#3-install) | Every client, copy and paste |
| 4 | [Getting a token](#4-getting-a-token) | The part everyone gives up on |
| 5 | [Tools](#5-tools) | All 45, by tier |
| 6 | [Safety](#6-safety) | Why it cannot write by default |
| 7 | [The unofficial tier](#7-the-unofficial-tier) | Extra reach, real risk |
| 8 | [Your data](#8-your-data) | What is stored and where |
| 9 | [Risks](#9-risks) | Read this before you install |
| 10 | [Troubleshooting](#10-troubleshooting) | Start with `doctor` |
| 11 | [Build from source](#11-build-from-source) | Contributing |

---

## 1. What you can ask it

- Which of my posts from the last month is still gaining likes?
- How many followers did I gain this week, and which post caused it?
- Compare @a, @b and @c. Who has the best engagement rate, and what do they post?
- What is working on #aitools right now?
- Read every comment from my last ten posts and tell me what people keep asking.
- Draft a reply to each comment that deserves one, in my voice. Do not post them.
- Stage this carousel as a container so I can look at it before it goes live.
- How many of today's 100 API posts have I used?

The first two are the point. Instagram will tell you your follower count right
now. It will not tell you what it was on Monday. This server remembers what it
reads, so it can answer the version of the question people actually have.

---

## 2. The three tiers

Instagram does not have one API. It has two, plus a private one, and they reach
completely different things. Every other MCP server picks one and does not tell
you which.

| Tier | What it reaches | Runs where | Risk |
|---|---|---|---|
| **Instagram Login** | only accounts you own | anywhere | none |
| **Facebook Login** | the above, plus public data on any Business or Creator account, plus hashtags | anywhere | none |
| **Unofficial** | any public account, the real inbox, search | a machine you control | your account can be restricted |

Most people want the middle one and do not know it exists. `discover_account`
is an official, free, documented Graph endpoint that returns any Business or
Creator account's follower count, biography and recent posts with engagement.
No scraping, no risk, no browser.

The unofficial tier is off unless you turn it on, and it is not even installed
by default.

Every tool result carries a `source` field naming the tier that answered, so a
model can never present a scraped guess as an official metric.

---

## 3. Install

### Step 1: get it

**Official tiers only.** This is what most people want.

```bash
uv tool install instagram-mcp
```

Or run it without installing:

```bash
uvx instagram-mcp
```

**With the unofficial tier.** Only if you have read [section 9](#9-risks).

```bash
uv tool install "instagram-mcp[unofficial]"
```

No `uv` yet:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Check it worked:

```bash
instagram-mcp --version
```

### Step 2: get a token

See [section 4](#4-getting-a-token). Then check it:

```bash
instagram-mcp doctor
```

`doctor` is the whole troubleshooting story. It tests every token, names which
insight metrics your account still answers, and tells you whether
`business_discovery` works on your app. Run it before anything else.

### Step 3: add it to your client

Add `"--allow-write"` to the arguments if you want it to publish and reply as
well as read. It is read-only without that.

#### Claude Code

```bash
claude mcp add --transport stdio instagram \
  --env IG_ACCESS_TOKEN=your_token \
  --env IG_USER_ID=your_ig_user_id \
  -- instagram-mcp
```

Everything after `--` is passed to the binary untouched, so writes look like
this:

```bash
claude mcp add --transport stdio instagram \
  --env IG_ACCESS_TOKEN=your_token \
  --env IG_USER_ID=your_ig_user_id \
  -- instagram-mcp --allow-write
```

By default this applies to the current project only. To use it everywhere, add
`--scope user`.

| Command | What it does |
|---|---|
| `claude mcp list` | List every configured server |
| `claude mcp get instagram` | Show this server's status |
| `/mcp` | Check the connection from inside a session |

#### Claude Desktop

| Platform | Config path |
|---|---|
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |

```json
{
  "mcpServers": {
    "instagram": {
      "command": "/Users/you/.local/bin/instagram-mcp",
      "env": {
        "IG_ACCESS_TOKEN": "your_token",
        "IG_USER_ID": "your_ig_user_id"
      }
    }
  }
}
```

The path must be absolute. Claude Desktop does not inherit your shell PATH, so
a bare command name will fail. Get the absolute path with
`which instagram-mcp` on macOS or `where instagram-mcp` on Windows. On Windows,
escape the backslashes.

Quit Claude Desktop completely and reopen it.

#### claude.ai and other remote clients

Run it over HTTP:

```bash
instagram-mcp --http --host 0.0.0.0 --port 8000
```

Then add `https://your-host/mcp` as a custom connector. Put it behind TLS and
an authenticating proxy. This server holds tokens for your Instagram accounts
and has no authentication of its own.

#### Cursor

`.cursor/mcp.json`:

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

#### VS Code, Windsurf, Zed, Cline, Codex CLI, Gemini CLI

All of them take the same three things: the command `instagram-mcp`, any flags
as arguments, and the environment variables above. See
[docs/clients.md](docs/clients.md) for the exact file and key names.

### Multiple accounts

Point `IG_ACCOUNTS_FILE` at a JSON array instead of setting a single token.
Mixed tiers in one file are fine and expected.

```json
[
  {
    "account_name": "thenavidm",
    "user_id": "17841400000000000",
    "access_token": "IGQV...",
    "host": "graph.instagram.com"
  },
  {
    "account_name": "thenavidai",
    "user_id": "17841400000000001",
    "access_token": "EAAG...",
    "host": "graph.facebook.com"
  }
]
```

Every tool takes an optional `account` argument. When you leave it out, the
`IG_PREFERRED` order decides, and an exact name match beats a prefix match.

```bash
IG_PREFERRED=thenavidm,thenavidai
```

---

## 4. Getting a token

This is where most people give up. There is a command for it.

First, in the Meta developer dashboard: create an app, add the Instagram
product, and generate a short-lived user token in Graph API Explorer with these
scopes.

| Path | Scopes |
|---|---|
| Facebook Login (recommended) | `instagram_basic`, `instagram_content_publish`, `instagram_manage_insights`, `instagram_manage_comments`, `pages_show_list`, `pages_read_engagement` |
| Instagram Login | `instagram_business_basic`, `instagram_business_content_publish`, `instagram_business_manage_comments`, `instagram_business_manage_messages` |

Then run this, and it does the rest:

```bash
instagram-mcp token \
  --app-id YOUR_APP_ID \
  --app-secret YOUR_APP_SECRET \
  --short-token THE_SHORT_LIVED_TOKEN \
  --path facebook
```

It exchanges the short-lived token for a long-lived one, finds every Page you
manage with a linked Instagram account, and prints a ready-to-paste
`IG_ACCOUNTS_FILE`.

Pick `--path facebook` unless you have a reason not to. It is the only path
that reaches `discover_account` and the hashtag tools, and the Page tokens it
returns do not expire.

Instagram Login tokens expire after 60 days. Extend them:

```bash
instagram-mcp refresh
```

Your account is a Business or Creator account, not a personal one. Instagram's
API does not work on personal accounts at all, on any tier except the
unofficial one.

---

## 5. Tools

45 tools. Everything is read-only until you start the server with
`--allow-write`.

### Your accounts (Instagram Login or Facebook Login)

| Tool | What it does |
|---|---|
| `list_accounts` | Every connected account with live follower counts and which tier it reaches |
| `whoami` | Verify one token, return the live profile |
| `token_status` | When each token expires and whether it can be refreshed |
| `get_media` | Recent posts with permalinks and engagement |
| `list_all_media` | Every post, paging until the history is exhausted |
| `get_media_by_id` | One post, full fields |
| `list_tagged_media` | Posts by other accounts that tagged you |
| `list_stories` | Stories live right now |
| `get_media_insights` | Reach, saves, shares and interactions for one post |
| `get_account_insights` | Account-level reach and profile views over a period |
| `get_publishing_limit` | How many of the 100 daily API posts you have used |
| `growth_history` | Follower counts over time, from local readings |
| `post_movement` | Which posts are still gaining, and by how much |

`growth_history` and `post_movement` read the local store, not Instagram. They
are empty until the server has taken readings on more than one day, and they
cannot be back-filled.

### Publishing (needs `--allow-write`)

| Tool | What it does |
|---|---|
| `create_container` | Stage media without posting. The only draft-like state Instagram has |
| `publish_container` | Publish a staged container |
| `post` | Stage, wait for processing, publish, in one call |
| `post_carousel` | 2 to 10 images |
| `publish_reel` | A reel from a public video URL, with an optional cover |
| `publish_story` | An image or video story |

Instagram has no native scheduling. Anything that claims to schedule a post is
holding the job somewhere else and publishing it at the time.

### Comments and messages

| Tool | Needs write |
|---|---|
| `get_comments` | no |
| `get_comment_replies` | no |
| `read_all_comments` | no |
| `list_conversations` | no |
| `get_conversation` | no |
| `reply_to_comment` | yes |
| `hide_comment` | yes |
| `delete_comment` | yes, and it is permanent |
| `send_dm` | yes |
| `private_reply_to_comment` | yes |

`read_all_comments` pulls comments across your recent posts in one call. It is
what comment triage and sentiment questions actually need, and doing it through
`get_comments` in a loop burns the context window before it answers anything.

Instagram only allows a DM inside a 24-hour window opened by the other person
messaging you, or as one private reply to a comment. There is no official way
to message somebody cold.

### Research (needs Facebook Login)

| Tool | What it does |
|---|---|
| `discover_account` | Public profile and recent posts for any Business or Creator account |
| `compare_accounts` | Up to 10 accounts side by side with median engagement |
| `search_hashtag` | Resolve a hashtag to its id, remembering the result |
| `hashtag_top_media` | What is performing on a hashtag right now |
| `hashtag_recent_media` | What is being posted on a hashtag right now |

Two limits worth knowing before you plan around them. `business_discovery` sees
Business and Creator accounts only, never personal or private ones. And
Instagram caps you at 30 unique hashtags per rolling 7 days, so resolved
hashtag ids are stored on disk and reused rather than spending another one.

### Unofficial (needs `--unofficial`)

| Tool | What it does |
|---|---|
| `unofficial_status` | Whether the tier is on, session state, pacing, and what is deliberately missing |
| `unofficial_profile` | Any public account, including personal ones |
| `unofficial_posts` | Any public account's posts |
| `unofficial_stories` | Somebody else's live stories |
| `unofficial_followers` | Followers, capped at 200 |
| `unofficial_following` | Following, capped at 200 |
| `unofficial_search_accounts` | Account search |
| `unofficial_post_comments` | Comments on any public post |
| `unofficial_inbox` | Your real inbox, including message requests |
| `unofficial_thread` | Messages in one thread |
| `unofficial_send_dm` | A DM with no window and no prior contact. Needs `--allow-write` too |

**Deliberately not implemented: `follow_user`, `unfollow_user`, `bulk_like`.**
Those three are what get accounts restricted fastest and they are what every
growth-hack tool ships. This is a decision, not a gap, and it is not going to
change.

---

## 6. Safety

Instagram is not a private notebook. It is a public surface where strangers
write text that your agent will read, and where a single bad write is visible
to your whole audience. Four separate problems, four separate mechanisms.

**Writes are off by default.** Nothing publishes, replies, hides, deletes or
sends unless the server was started with `--allow-write`. A misread instruction
cannot post to your feed on a default install.

**Comments and DMs are framed as untrusted.** Every piece of text written by
somebody else comes back wrapped in an explicit fence telling the model to
report it and not to obey it. A comment on a public post is the most trivially
injectable surface an agent will ever be handed, and "summarise my comments" is
one of the first things anyone asks.

**Every write is logged.** An append-only file records what was done, to what,
and when. No tool can read or edit it, so there is always a record of what an
agent did in your name.

**The unofficial tier paces itself.** Human-ish delays between calls and a
local hourly ceiling, lower than Instagram's own. Instagram restricts accounts
for machine-speed access patterns more than for volume.

---

## 7. The unofficial tier

This tier logs in as you, the way the phone app does, and reaches everything
the official APIs refuse: any public account's full history, followers and
following, other people's stories, search, and your real inbox.

It is gated twice. The library it needs is not installed by default, and the
server refuses to use it without `--unofficial`.

Log in once, in a terminal:

```bash
instagram-mcp login
```

It asks for your username and password, handles two-factor, and writes a
session file with owner-only permissions. **Your password is never stored and
never goes into any config file.**

That matters more than it sounds. An MCP client config is a JSON file people
paste into issues, screenshots and Discord threads, and it is read by every MCP
server your client runs, not just this one. A password does not belong in it,
so this server never asks for one there.

Then start the server with the flag:

```bash
instagram-mcp --unofficial
```

**Use a secondary account.** Not the one with your audience on it. Read
[section 9](#9-risks) first.

---

## 8. Your data

Everything stays on your machine. This server has no backend and phones nothing
home.

| Platform | Location |
|---|---|
| macOS | `~/Library/Application Support/instagram-mcp/` |
| Linux | `~/.local/share/instagram-mcp/` |
| Windows | `%LOCALAPPDATA%\instagram-mcp\` |

| File | What is in it |
|---|---|
| `instagram-mcp.db` | Follower and engagement readings over time, and hashtag ids |
| `session.json` | The unofficial tier's session. Owner-only permissions. Only if you ran `login` |
| `audit.log` | Every write, append-only |

Override the directory with `IG_MCP_DATA_DIR`.

Nothing here is a cache. Reads always go to Instagram and the store is written
as a side effect, so a stale row can never be served as a live answer.

---

## 9. Risks

**The unofficial tier can get your Instagram account restricted or disabled.**
This is not a theoretical risk and it is not rare. Instagram detects automated
access and acts on it. If your account is your business, an account you cannot
recover is worse than any question this server can answer for you. Use a
secondary account. The pacing here reduces the risk and does not remove it.

**The unofficial tier is against Instagram's Terms of Use.** That is a fact, and
no disclaimer changes it. You accept it by passing the flag.

**Your agent will read text written by strangers.** Comments and DMs are framed
as untrusted before they reach the model, which is a strong mitigation and not a
guarantee. Do not combine `--unofficial`, `--allow-write` and an unattended
agent loop.

**Tokens are credentials.** A long-lived Instagram token can post as you. It
lives in your MCP client config or an accounts file. Treat that file the way you
treat an SSH key, and never commit it.

**`delete_comment` is permanent.** There is no undo. Prefer `hide_comment`,
which leaves the comment visible to whoever wrote it.

The official tiers carry none of this. If you never pass `--unofficial`, the
worst case here is an expired token.

---

## 10. Troubleshooting

Run this first. It answers most of it.

```bash
instagram-mcp doctor
```

| Symptom | Cause |
|---|---|
| "No Instagram account configured" | `IG_ACCESS_TOKEN` and `IG_USER_ID` are not reaching the server. Client configs do not inherit your shell environment |
| Every call fails with code 190 | The token expired. Run `instagram-mcp refresh`, or re-mint with `instagram-mcp token` |
| `discover_account` says it needs Facebook Login | You are on an Instagram Login token. Re-run `instagram-mcp token --path facebook` |
| An insights call fails on one metric | Meta retired it. `doctor` names the working set. Pass `metrics=` to override |
| DM tools return a permissions error | Reading DMs needs Advanced Access through Meta App Review on most apps |
| An unofficial tool says the session is invalid | Run `instagram-mcp login` again. If Instagram keeps challenging you, stop rather than retrying |
| "Instagram asked us to wait" | The early warning before a restriction. Stop using the unofficial tier for a few hours |
| Claude Desktop shows no tools | The command path is not absolute, or the app was not fully quit and reopened |

---

## 11. Build from source

```bash
git clone https://github.com/thenavidm/instagram-mcp.git
cd instagram-mcp
uv sync --all-extras
uv run pytest
uv run ruff check .
```

The tests run against a fake HTTP transport and never touch the network or your
session file.

Layout:

| Path | What it is |
|---|---|
| `src/instagram_mcp/config.py` | Settings, accounts, and the tier model |
| `src/instagram_mcp/graph.py` | The official HTTP layer, both hosts |
| `src/instagram_mcp/safety.py` | Write gating, pacing, audit log, injection framing |
| `src/instagram_mcp/store.py` | SQLite, so the server can answer "what changed" |
| `src/instagram_mcp/unofficial.py` | instagrapi, behind the flag |
| `src/instagram_mcp/tools/` | One module per tier |

Read `safety.py` first. It is the argument for using this one.

## About the author

Navid Moazzez is a leading AI business strategist and the host of the AI Creator Summit, watched by 100,000+ creators. He helps creators and founders master AI and build their own AI Operating System (AI OS) to automate their business and life. This Instagram MCP server is one piece of that system.

**Links**

- Personal website: [navid.me](https://navid.me)
- Store: [navid.bio](https://navid.bio)
- AI OS Starter Kit: [aios.guide](https://aios.guide)
- AI OS Workshop: [aiosworkshop.com](https://aiosworkshop.com)
- AI Creator OS: [aicreatoros.co](https://aicreatoros.co)
- AI Tools Library: [aitoolslibrary.io](https://aitoolslibrary.io)
- Video Gear Guide: [videogear.guide](https://videogear.guide)
- Navid Media: [navid.media](https://navid.media)
- YouTube: [@thenavidm](https://youtube.com/@thenavidm?sub_confirmation=1) and [@thenavidai](https://youtube.com/@thenavidai?sub_confirmation=1)
- X: [@thenavidm](https://x.com/thenavidm)
- Instagram: [@thenavidm](https://instagram.com/thenavidm)
- LinkedIn: [thenavidm](https://linkedin.com/in/thenavidm)

## Dependencies

| Library | Licence | What it does |
|---|---|---|
| [Python MCP SDK](https://github.com/modelcontextprotocol/python-sdk) | MIT | The MCP server, stdio and streamable HTTP |
| [httpx2](https://github.com/encode/httpx) | BSD-3-Clause | The Graph API calls |
| [instagrapi](https://github.com/subzeroid/instagrapi) | MIT | The unofficial tier. Optional, not installed by default |

## License

[MIT](./LICENSE). Free to use, modify, and share.

---

© 2026 NM Media. Made with ❤️ by [Navid Moazzez](https://navid.me).
