# Security

## Reporting a vulnerability

[Report it privately](https://github.com/thenavidm/instagram-mcp/security/advisories/new).
Please do not open a public issue for a security problem: an issue is visible to
everyone the moment you file it, including whoever would use the bug.

Include what you did, what happened, and what you expected. A proof of concept
helps. Reporters are credited in the fix notes unless they would rather not be.

## What this server holds

**Instagram access tokens**, either in `IG_ACCESS_TOKEN` or in the JSON file at
`IG_ACCOUNTS_FILE`. A long-lived token is the account. Anyone holding one can
post as you, read your comments, and send DMs within Instagram's rules.

**A session file** if the unofficial tier is enabled, at `session.json` in the
data directory. This is a logged-in Instagram session and is more sensitive than
a token, because it is not scoped.

**A local SQLite store** of follower counts and post engagement readings, plus
an audit log of every attempted write.

None of it leaves your machine. The only network calls are to Instagram and, on
the unofficial tier, to Instagram's private endpoints. There is no telemetry and
no phone-home.

Treat the data directory the way you would treat a password manager file.

## The threat this server takes most seriously

**Prompt injection through comments and DMs.**

Every text field written by another person, comments, captions, biographies,
message bodies, is wrapped in an untrusted-content fence before it reaches the
model, with an instruction to report it rather than obey it. The fence is closed
explicitly, and an attempt to close it early from inside the content is
neutralised.

This matters because "summarise my comments" is one of the first things anyone
asks, and a comment is text a stranger chose, aimed at an agent that can post.

The framing reduces the risk. It does not eliminate it. Do not run this server
with writes enabled and no human in the loop on an account that takes public
comments.

## Write safety

Writes are on by default, because publishing is the point of the server. A
server where every write needs a flag teaches the operator to pass that flag
permanently, which is worse than no protection because it looks like protection.

Three graduated mechanisms instead:

**`confirm: true` on the irreversible tools.** Publishing, deleting a comment,
sending a DM. The model sets it deliberately after reading why. Reversible
actions such as replying and hiding do not require it, because confirming
everything trains the reflex that makes confirmation on a real deletion
worthless.

**`IG_READ_ONLY=1` removes every write tool.** Not a refusal at call time: the
tools are never registered, so they do not appear in the list. A model cannot
call a tool it cannot see, and cannot argue with a refusal it never receives.

**`IG_AUDIT_LOG=<path>` records every attempted write**, allowed and refused
alike, one JSON line each. The model has no tool to read or edit that file.

Three tools are deliberately not implemented: `follow_user`, `unfollow_user` and
`bulk_like`. They are what growth-hack tooling ships and they are the three
actions most likely to get an account restricted. `unofficial_status` reports
them as absent on purpose, so it is a decision on the record.

## The unofficial tier

Driving Instagram's private API is against Instagram's terms of service and can
get an account restricted or permanently banned.

It is not installed by default, it is off unless explicitly enabled, and it
prints a warning on stderr at startup. It paces itself with a randomised delay
and a local hourly ceiling below Instagram's own, because accounts are
restricted for machine-speed patterns more than for volume.

Use a secondary account. Not your main one.

## Running it over HTTP

`--http` has no authentication of its own. It is meant to sit behind TLS and an
authenticating reverse proxy.

Do not expose it directly. It holds tokens for your Instagram accounts, and an
open endpoint hands them to anyone who finds it.

## Supported versions

The latest published version gets fixes. Given the size of this project, older
versions do not.
