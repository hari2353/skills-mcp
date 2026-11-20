# Diagnostics

Every expected failure from this MCP server carries a stable code, a fix, and
this page. The wire format is:

```
[SKMCP_CODE] what went wrong (fix: what to do) (docs: docs/diagnostics.md#anchor)
```

| code | meaning | fix |
|---|---|---|
| `SKMCP_EMPTY_INPUT` | required text was blank | send non-blank input |
| `SKMCP_INPUT_TOO_LARGE` | text exceeded 8,000 chars | chunk upstream; never silently truncated |
| `SKMCP_ENGINE_REJECTED` | skills-engine returned 4xx | fix the request; do not retry unchanged |
| `SKMCP_ENGINE_UNREACHABLE` | connect/timeout after the one allowed GET retry | start the engine; check `SKILLS_ENGINE_URL` |
| `SKMCP_ENGINE_5XX` | engine returned 5xx after retry | wait for recovery, then retry |
| `SKMCP_ENGINE_BAD_RESPONSE` | engine body was not JSON | inspect the engine response/logs |

## SKMCP_EMPTY_INPUT

A tool received blank text. Send the actual JD, resume, skill name, or query.

## SKMCP_INPUT_TOO_LARGE

Input crossed `MAX_INPUT_CHARS` (8,000). Chunk it upstream. Truncation would
silently drop skills, so the server refuses instead.

## SKMCP_ENGINE_REJECTED

The engine answered 4xx. Its `detail` is in the message. Change the request;
the server does not retry writes, and retrying the same bad request cannot help.

## SKMCP_ENGINE_UNREACHABLE

The engine could not be reached after one retry of an idempotent GET. Start
`skills-engine` and confirm `SKILLS_ENGINE_URL` points at it.

## SKMCP_ENGINE_5XX

The engine failed server-side after the allowed retry. Wait for recovery.

## SKMCP_ENGINE_BAD_RESPONSE

The engine returned a body that is not valid JSON. Check the engine logs or
the URL — a proxy or wrong port often explains it.
