# Claude Code on this repo

How to run Claude Code on Business OS without wasting tokens. The permanent rules for the model
live in [`CLAUDE.md`](../CLAUDE.md) ("Working efficiently"); this page is for the owner.

Commands and settings below were checked against Claude Code 2.1.296 (2026-10-09). Run
`claude --version`; if yours is older and something is missing, run `/help` to see what it has.

## Which model for which work

| Work | Model |
|---|---|
| Architecture and major design decisions, multi-tenant and security design, DB schema and migrations, hard debugging and root-cause analysis, high-impact refactors | Opus |
| UI components and styling, responsive fixes, routine API endpoints and CRUD, unit tests, straightforward bug fixes, docs, routine refactors | Sonnet |

`CLAUDE.md` cannot switch the model. Only you can, with one of these:

- **In a session:** `/model opus`, `/model sonnet`, or `/model opusplan`. Takes effect from the next message.
- **When starting:** `claude --model sonnet` (or `opus`, `opusplan`).
- **As your default for this repo only:** add `"model": "opusplan"` to `.claude/settings.local.json`
  (gitignored, affects only your PC). Putting it in `~/.claude/settings.json` makes it your
  default everywhere.
- **Thinking depth:** `/effort` in a session, or `claude --effort <level>`. Lower effort on routine
  work saves output tokens; keep it high for design, security and debugging.

**`opusplan`** uses Opus while you are in plan mode (Shift+Tab until the footer says plan mode)
and Sonnet once you approve the plan and it starts editing. It fits MyBiz well: plan a slice
with Opus, implement it with Sonnet. For a pure UI or docs task, `/model sonnet` is simpler.

## Context hygiene

- `/clear` between unrelated tasks. Anything worth keeping goes into `docs/DECISIONS.md`,
  `docs/STATUS.md` or a PR first, so the next task can read it instead of the old conversation.
- `/compact` when a long task is still going but the conversation is large. You can steer it:
  `/compact keep the migration plan and failing test names`.
- `/context` shows what is filling the context window (instructions, skills, files, tool output).

## Measuring before and after

- `/usage` in a session shows usage for the session and your plan limits.
- In the Claude app project, compare the project usage report for a similar week before and
  after the change, per thread. Compare like with like: a design-heavy week and a docs week cost
  very differently whatever the settings.
- Cache reads are cheaper than fresh input but are not free, and they grow with every turn of a
  long conversation, because each turn re-reads the whole context. Shorter sessions (`/clear`)
  and smaller files read into context are what bring them down.
