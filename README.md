<div align="center">

<img src="https://getsaar.com/logo.png" alt="saar" width="80" />

# saar

**The open source tool that makes AI coding assistants actually know your codebase.**

Free. Local. Works with Claude Code, Cursor, Copilot, Gemini CLI — all at once.

[![PyPI version](https://img.shields.io/pypi/v/saar.svg?color=blue)](https://pypi.org/project/saar/)
[![Downloads](https://img.shields.io/pypi/dm/saar.svg)](https://pypi.org/project/saar/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)
[![CI](https://github.com/OpenCodeIntel/saar/actions/workflows/ci.yml/badge.svg)](https://github.com/OpenCodeIntel/saar/actions)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

[**Try it →**](https://getsaar.com) · [**Discord**](https://discord.gg/opencodeintel) · [**Docs**](https://getsaar.com/docs) · [**OCI: Semantic Search**](https://opencodeintel.com)

</div>

---

## The problem

Claude Code, Cursor, Copilot, and Gemini CLI are incredible tools. We use them every day.

But they have one fundamental flaw: **they don't know YOUR codebase.**

Every session starts from zero. The AI writes `npm install` in your `bun` repo. It invents `RateLimitException` when you already have `LimitCheckError`. It puts the file in the wrong folder. It uses the wrong auth decorator.

You spend 20 minutes correcting what should have taken 2.

> **ETH Zurich studied 5,694 pull requests and found AI tools increase costs 20%+ when they lack precise codebase context.** 66% of developers cite "almost right but not quite" as their #1 AI frustration. *(Stack Overflow 2025, 49,000 respondents)*

The fix is a context file — AGENTS.md, CLAUDE.md, .cursorrules — that tells your AI exactly how your codebase works. But nobody writes these well. They go stale. They're too long. The AI ignores them.

**saar fixes this in 30 seconds.**


---

## Install

```bash
pip install saar
```

That's it. No account. No API key. No config. Your code never leaves your machine.

---

## One command. Then AI just gets it.

![saar demo](saar_demo.gif)

```bash
cd my-project
saar extract .
```

**What happens in 11 seconds:**

```
saar analyzing my-project...

  Backend     FastAPI  Python (47 files)
  Frontend    React  TypeScript  Vite  TanStack Query
  Auth        require_auth  public_auth  (2 patterns)
  Exceptions  AuthenticationError, LimitCheckError,
              TokenExpiredError, NoteError (+6 more)
  Canonical   For new hooks: useUserData.ts (12 importers)
  Scale       1,274 functions  276 files  72% typed

  wrote AGENTS.md  (70 lines)
done
```

saar detected your stack, your auth pattern, all 9 of your custom exception classes, your canonical hook, and the right test command. **You didn't tell it any of that.**

Drop `AGENTS.md` in your repo root. Claude Code, Cursor, Copilot, and Gemini CLI all pick it up automatically.

---

## saar vs everything else

| | saar | `/init` (Claude Code) | Cursor @codebase | Manual |
|---|---|---|---|---|
| Detects auth patterns | ✅ | ⚠️ basic | ❌ | depends |
| Detects exception classes | ✅ | ❌ | ❌ | depends |
| Canonical example detection | ✅ | ❌ | ❌ | rarely |
| Output size | **70 lines** | 300+ lines | N/A | varies |
| ETH Zurich recommended | ✅ short+precise | ❌ too long | ❌ | ✅ if done right |
| Works with all AI tools | ✅ | Claude only | Cursor only | ✅ |
| Staleness detection | ✅ `saar diff` | ❌ | ❌ | ❌ |
| Free + local | ✅ | ✅ | ✅ | ✅ |

> *ETH Zurich (Feb 2026, arxiv:2602.11988): LLM-generated context files reduce task success and increase costs 20%+. Short, human-verified files improve performance 4%. saar generates short, precise files by default.*


---

## When your codebase changes, saar tells you

```bash
saar diff .
```

```
saar checking my-project for changes...
  AGENTS.md last generated: 14 days ago

  Changed since last extract (2 changes):
  ~ Package manager changed: npm → bun
  + Exception class added: RateLimitError

  Recommendation: re-run saar extract to update AGENTS.md
```

Nobody else has this. Your AGENTS.md was telling Claude to use `npm`. saar caught it.

---

## Accumulate corrections over time

Every time AI gets something wrong, add it without re-running analysis:

```bash
saar add "Never use npm — this project uses bun only"
saar add --off-limits "billing/ — legacy Stripe integration, frozen"
saar add --domain "Workspace = tenant, not a directory"
saar add --verify "pytest -x && docker compose up && curl localhost:8000/health"
```

Each correction makes the file better. The AI stops making the same mistake twice.

---

## All commands

```bash
saar extract .                        # generate AGENTS.md (default)
saar extract . --format claude        # CLAUDE.md
saar extract . --format cursorrules   # .cursorrules
saar extract . --format all           # all four formats at once
saar extract . --no-interview         # skip questions, use cache
saar extract . --verbose              # no line cap, full output
saar extract . --index                # also index into OCI for MCP search

saar diff .                           # detect AGENTS.md staleness
saar add "rule"                       # add correction without re-running
saar enrich                           # polish raw answers with Claude AI
```

---

## Index into OCI for semantic search via MCP

saar generates your AGENTS.md. [OpenCodeIntel (OCI)](https://opencodeintel.com) goes further — it indexes your codebase for per-task semantic search via MCP.

```bash
saar extract . --index
```

Once indexed, every AI tool with the OCI MCP server gets a new power:

```
> codeintel:get_context_for_task("add rate limiting to the settings endpoints")

## Context for: "add rate limiting to settings endpoints"

### Relevant files
- backend/routes/settings.py — settings endpoints (relevance: 94%)
- backend/services/user_limits.py — existing rate limiting logic (87%)
- backend/middleware/auth.py — require_auth pattern (81%)

### Rules that apply
- Use LimitCheckError, not a new exception class
- Use require_auth decorator on all user endpoints
- Never bypass RLS on the users table
```

**Before OCI:** Claude reads random files, guesses, gets it wrong.
**After OCI:** Claude gets the exact 3 files and 3 rules for this specific task. First try.

→ [Get started with OCI](https://opencodeintel.com) · [MCP setup guide](https://opencodeintel.com/docs/mcp)

---

## What saar detects

**Python:** FastAPI / Flask / Django · Auth middleware and decorators · Service singletons · ORM + RLS · Exception hierarchy · Logging patterns · Naming conventions

**TypeScript/JS:** React / Next.js / Express · TanStack Query / SWR · Component patterns · Custom hooks (canonical example detection) · Common imports

**Dependency graph:** Critical files (most depended-on) · Circular dependencies · Canonical examples per category (hooks, services, components, tests)

**Team rules:** Auto-includes CLAUDE.md, .cursorrules, AGENTS.md, CONVENTIONS.md if they exist


---

## Installation

```bash
# Recommended — no venv conflicts
pipx install saar

# Or standard
pip install saar

# With AI enrichment (optional)
pip install saar[enrich]
export ANTHROPIC_API_KEY=your-key
```

Requires Python 3.10+.

---

## Contributing

saar is MIT licensed and built in the open. Every commit, every decision, public.

```bash
git clone https://github.com/OpenCodeIntel/saar.git
cd saar
python -m venv venv && source venv/bin/activate
pip install -e ".[dev]"
pytest tests/ -v          # 386 tests
ruff check saar/ tests/   # lint
```

Good first issues are labeled [`good first issue`](https://github.com/OpenCodeIntel/saar/issues?q=is%3Aissue+is%3Aopen+label%3A%22good+first+issue%22) on GitHub.

---

## Why open source?

AI context files contain your team's tribal knowledge — your domain vocabulary, your gotchas, your architecture decisions. That knowledge belongs to you, not to a $252M venture-backed company.

- **Your code never leaves your machine** — saar runs entirely locally
- **Works with every AI tool** — not locked to Claude, Cursor, or Copilot
- **Inspect and modify everything** — MIT license, no black boxes
- **Self-host OCI** — the semantic search layer is open source too

> *"Bootstrapping context is not the challenge. Maintenance is."* — Packmind, Feb 2026

saar is the only tool that solves both.

---

## Built by

[Devanshu Chicholikar](https://github.com/DevanshuNEU) · MS Software Engineering, Northeastern University · Building [OpenCodeIntel](https://opencodeintel.com)

---

<div align="center">

**[getsaar.com](https://getsaar.com)** · **[opencodeintel.com](https://opencodeintel.com)** · **[PyPI](https://pypi.org/project/saar/)** · **[MIT License](./LICENSE)**

*If saar saved you time, a ⭐ on GitHub helps others find it.*

</div>
