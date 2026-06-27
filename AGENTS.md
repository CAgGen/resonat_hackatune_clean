# AGENTS.md

Working agreement for AI agents (Claude Code, Codex, others) on this repo.
The full skills live in [`.claude/skills/`](.claude/skills/) as `SKILL.md` files —
Claude Code auto-discovers them; on other tools, read the referenced file when its
trigger applies. **User instructions always override these.**

## Always on

**Be lazy — ship the minimal thing that works.** ([`.claude/skills/ponytail/SKILL.md`](.claude/skills/ponytail/SKILL.md))
Climb the ladder, stop at the first rung that holds: does it need to exist (YAGNI) →
stdlib → native platform feature → already-installed dep → one line → minimal code.
No unrequested abstractions, no scaffolding "for later", fewest files, shortest diff.
Mark deliberate shortcuts with a `ponytail:` comment naming the ceiling and upgrade path.

**Code carefully — surgical, no overcomplication.** ([`.claude/skills/karpathy-guidelines/SKILL.md`](.claude/skills/karpathy-guidelines/SKILL.md))
Surface assumptions and ask when unclear (don't pick silently). Minimum code, nothing
speculative. Touch only what the request needs; match existing style; don't refactor what
isn't broken; remove only the orphans your own change created.

**Verify before claiming done.** ([`.claude/skills/superpowers/SKILL.md`](.claude/skills/superpowers/SKILL.md) §5)
No "passing / fixed / done" without running the proving command fresh in that same turn and
reading its output. Confidence is not evidence.

## Situational — read the skill when the trigger hits

| When you're about to… | Apply | File |
|---|---|---|
| build a feature / change behavior | **Brainstorm first** — design + user approval before code | superpowers §1 |
| write implementation code | **TDD** — failing test first, watch it fail, then minimal code | superpowers §2 |
| fix a bug / test failure | **Systematic debugging** — root cause before any fix | superpowers §3 |
| turn a spec into work | **Writing plans** — exact paths, complete code, bite-sized steps | superpowers §4 |

All four are in [`.claude/skills/superpowers/SKILL.md`](.claude/skills/superpowers/SKILL.md).

## Project specifics

- Backend: Python 3.13 + FastAPI, managed by `uv` (run from `backend/`); tests `uv run pytest`.
- Frontend: React + TypeScript + Vite (`frontend/`).
- Memory is two markdown files per user, **no database** (see `PRD-night.md` §3).
- Cyanite REST is isolated in `backend/cyanite.py`; everything else monkeypatches it to stay offline.
- One-shot startup: `./start.sh`. Dev details in [`GETTING_STARTED.md`](GETTING_STARTED.md).

> These skills are condensed from the ponytail, andrej-karpathy-skills, and superpowers
> plugins (MIT) so collaborators get the behavioral core without installing them.
