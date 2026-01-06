# workman

Workman is a pure compiler: it compiles a domain operation (`op`, `payload`, `ctx`) into a Storacle execution plan.

- Input: `op: str`, `payload: dict`, `ctx: dict` (and optional `pins`)
- Output: a `storacle.plan/1.0.0` JSON object containing:
  - assertion ops (`assert.exists` / `assert.not_exists`)
  - a write op (`wal.append`)

This package does not execute plans and does not talk to storage backends.
