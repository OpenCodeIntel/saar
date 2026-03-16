<img src="https://capsule-render.vercel.app/api?type=waving&color=0:080C14,50:0D1420,100:080C14&height=220&text=saar&fontSize=90&fontColor=F4C343&animation=fadeIn&fontAlignY=38&desc=Your%20AI%20coding%20assistant%20doesn%27t%20know%20your%20codebase.%20saar%20fixes%20that%20in%2010%20seconds.&descSize=16&descAlignY=60&descColor=9E9A92" width="100%" />

<div align="center">

<br />

[![PyPI](https://img.shields.io/pypi/v/saar.svg?color=F4C343&labelColor=0D1420&style=flat-square)](https://pypi.org/project/saar/)
[![Downloads](https://img.shields.io/pypi/dm/saar.svg?labelColor=0D1420&color=4EFF9A&style=flat-square)](https://pypi.org/project/saar/)
[![Tests](https://img.shields.io/badge/tests-548%20passing-4EFF9A?labelColor=0D1420&style=flat-square)](https://github.com/OpenCodeIntel/saar/actions)
[![License: MIT](https://img.shields.io/badge/license-MIT-818CF8?labelColor=0D1420&style=flat-square)](./LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-60A5FA?labelColor=0D1420&style=flat-square)](https://www.python.org/downloads/)

<br />

[![Typing SVG](https://readme-typing-svg.demolab.com?font=JetBrains+Mono&size=14&duration=2800&pause=600&color=F4C343&center=true&vCenter=true&width=620&lines=Detects+your+package+manager+(bun%2C+pnpm%2C+npm%2C+uv);Finds+your+logging+library+(structlog%2C+winston%2C+pino);Maps+your+auth+patterns+(JwtAuthGuard%2C+require_auth);Catches+all+218+custom+exception+classes;Generates+AGENTS.md+in+10+seconds.+No+account.+No+API+key.)](https://git.io/typing-svg)

<br />

[**getsaar.com**](https://getsaar.com) &nbsp;·&nbsp; [**PyPI**](https://pypi.org/project/saar/) &nbsp;·&nbsp; [**Issues**](https://github.com/OpenCodeIntel/saar/issues) &nbsp;·&nbsp; [**OCI**](https://opencodeintel.com)

<br />

</div>

---

## What is saar?

saar is a CLI that analyzes your codebase and generates an `AGENTS.md` — a precise context file that every AI coding tool reads automatically.

One command. Claude Code, Cursor, claude.ai, Copilot, Gemini CLI — they all stop guessing and start knowing.

---

## The problem

I asked Claude to install a package. It said `npm install`. My project uses bun. The build broke. I spent 20 minutes confused.

This happens to every developer using AI tools. Every week.

- AI writes `npm install` in your `bun` repo
- AI invents a new exception class when you already have 218
- AI uses the wrong auth decorator from 10 available options
- AI uses `import logging` when your team standardized on `structlog`
- Every session starts from zero — no memory of how your project actually works

The fix exists: a context file that tells the AI exactly how your codebase works. But writing one well is hard, they go stale fast, and nobody maintains them.

**saar automates the hard part.**

---

## Quick start

```bash
pip install saar
cd your-project
saar extract .
```

Done. `AGENTS.md` is now in your project root. Every AI tool picks it up automatically.

**What you see when it runs:**

```
saar analyzing your-project...

  Backend     FastAPI  Python (47 files)
  Frontend    React  TypeScript  Vite  bun
  Auth        get_current_active_superuser  (from app.api.deps)
  Logging     structlog
  Exceptions  APIError, AuthenticationError, LimitCheckError (+6 more)
  Scale       694 functions  276 files  96% typed

  wrote AGENTS.md  (72 lines)
  Claude knows your project.
```

saar found your auth pattern, your logging library, your exception classes, and your package manager. You didn't tell it any of that.

---

## How it works

```
your repo
    │
    ▼
saar extract .
    │
    ├─ static analysis ──── detects stack, auth, logging, naming, exceptions
    │
    ├─ guided interview ─── 5 questions for tribal knowledge (off-limits files,
    │                        domain terms, gotchas — things code can't show)
    │
    └─ AGENTS.md ─────────── ~100 lines, every AI tool reads it automatically
                              Claude Code · Cursor · claude.ai · Copilot · Gemini CLI
```

saar generates short, precise files. Not 300-line dumps. ETH Zurich (Feb 2026, arxiv:2602.11988) showed that long LLM-generated context files *reduce* task success and increase costs 20%+. saar's default is 100 lines. Focused. Nothing wasted.

---

## Before / After

**Without saar** — claude.ai, no context:

```
Q: Add debug logging to the Python endpoint.

import logging
logger = logging.getLogger(__name__)
```

Wrong. This codebase uses structlog.

**With saar** — same question, AGENTS.md loaded:

```
Q: Add debug logging to the Python endpoint.

import structlog
logger = structlog.get_logger(__name__)
# structlog gives structured JSON output — standard for this project
```

Right. First try. No back-and-forth.

This is a real test result from a controlled eval on the PostHog codebase. 174 Python files use `import logging`. Claude follows the majority without context. AGENTS.md overrides it.

---

## When your codebase changes, saar tells you

```bash
saar diff .
```

```
saar checking your-project for changes...

  AGENTS.md last generated: 14 days ago

  Changed since last extract:
  ~ Package manager changed: npm → bun
  + New exception class: RateLimitError
  + New auth pattern detected

  Run saar extract . to update.
```

Your AGENTS.md was telling Claude to use `npm`. saar caught it before you committed broken code.

---

## Keep corrections over time

AI gets something wrong? Add it once. Never see that mistake again.

```bash
saar add "Never use npm — this project uses bun"
saar add --off-limits "billing/ — legacy Stripe integration, frozen until Q3"
saar add --domain "Workspace = tenant, not a directory"
saar add --verify "source venv/bin/activate && pytest tests/ -v"
```

No re-analysis. Each correction appends to `.saar/config.json` and gets included next time you run `saar extract`.


## saar vs everything else

| | saar | `/init` (Claude Code) | manual |
|---|---|---|---|
| Detects package manager | ✅ | ⚠️ basic | you write it |
| Detects logging library | ✅ | ❌ | you write it |
| Detects auth patterns | ✅ | ⚠️ basic | you write it |
| Detects exception classes | ✅ | ❌ | you write it |
| Guided interview (tribal knowledge) | ✅ | ❌ | you know it |
| Output size | ~100 lines | 300+ lines | up to you |
| Staleness detection (`saar diff`) | ✅ | ❌ | ❌ |
| Quality linting (`saar lint`) | ✅ | ❌ | ❌ |
| Works with all AI tools | ✅ | Claude only | ✅ |
| Free + fully local | ✅ | ✅ | ✅ |

Claude Code's `/init` is useful. But it generates bloated files that ETH Zurich showed *hurt* performance. saar generates focused files and keeps them honest over time.

---

## All commands

```bash
# Generate
saar extract .                         # AGENTS.md (default, ~100 lines)
saar extract . --format claude         # CLAUDE.md
saar extract . --format cursorrules    # .cursorrules
saar extract . --format all            # all formats at once
saar extract . --no-interview          # skip questions, use cached answers
saar extract . --verbose               # remove 100-line cap, full output
saar extract . --include packages/api  # monorepo subset

# Maintain
saar diff .                            # detect what changed since last extract
saar add "rule"                        # add correction without re-running
saar add --off-limits "path/"          # mark file/dir as off-limits for AI
saar add --domain "term = definition"  # add domain vocabulary
saar add --verify "command"            # set the verification workflow

# Quality
saar lint .                            # check AGENTS.md for SA001–SA005 violations
saar stats .                           # score your AGENTS.md (0–100)
saar check .                           # CI primitive: exits 1 if stale or incomplete

# AI enrichment (requires ANTHROPIC_API_KEY)
saar enrich                            # use Claude to sharpen raw interview answers

# OCI integration
saar extract . --index                 # generate AGENTS.md + index into OCI
```

---

## saar lint — quality checking for AGENTS.md

```bash
saar lint .

  AGENTS.md:5:1:  SA004  Generic filler: 'Write clean code' -- AI already knows this
  AGENTS.md:12:1: SA001  Duplicate rule: already appears on line 3

  Found 2 violations.  Run saar stats . for a full quality score.
```

Like ruff, but for your context file. Catches:

- `SA001` — duplicate rules
- `SA002` — orphaned section headers
- `SA003` — vague rules under 6 words
- `SA004` — generic filler (write clean code, follow best practices)
- `SA005` — emojis that waste instruction budget

---

## saar check — CI integration

```bash
# .github/workflows/ci.yml
- run: saar check .
```

Exits `0` if AGENTS.md is fresh and complete. Exits `1` with a specific message if not. Plug it into any CI pipeline. Never let a stale context file slip into production.

---

## OCI — semantic search via MCP

saar generates your AGENTS.md. [OpenCodeIntel (OCI)](https://opencodeintel.com) indexes your codebase for per-task context via MCP.

```bash
saar extract . --index
```

Once indexed, Claude Desktop and Claude Code get a new tool:

```
codeintel:get_context_for_task("add rate limiting to the settings endpoints")

→ Returns:
  - backend/routes/settings.py (94% relevance)
  - backend/middleware/auth.py (81% relevance)
  - Rule: use LimitCheckError, not a new exception
  - Rule: require_auth on all user endpoints
```

Instead of exploring 30k tokens of files, Claude gets the exact 3 files and 2 rules for the task.

→ [opencodeintel.com](https://opencodeintel.com) · [MCP setup](https://opencodeintel.com/docs/mcp)

---

## What saar detects

**Python** — FastAPI / Flask / Django · Auth middleware and decorators · Logging library (logging vs structlog vs loguru) · Exception class hierarchy · ORM patterns · Naming conventions

**TypeScript/JS** — React / Next.js / Express · Package manager (bun / pnpm / npm / yarn) · TanStack Query / SWR patterns · Component library · Custom hooks · Common imports

**Both** — Critical files (most depended-on) · Circular dependencies · Canonical examples per category · Existing team rules (reads CLAUDE.md, .cursorrules, CONVENTIONS.md)

---

## Installation

```bash
# Recommended
pipx install saar

# Standard
pip install saar

# With AI enrichment
pip install "saar[enrich]"
export ANTHROPIC_API_KEY=sk-ant-...
```

Requires Python 3.10+. No account. No API key for core features. Runs entirely on your machine.

---

## Contributing

saar is MIT licensed. Everything is public — commits, decisions, benchmarks.

```bash
git clone https://github.com/OpenCodeIntel/saar.git
cd saar
python -m venv venv && source venv/bin/activate
pip install -e ".[dev]"

# Run tests
pytest tests/ -v              # 548 tests

# Lint
ruff check saar/ tests/

# Verify saar on itself
saar extract . --no-interview
saar lint .
saar stats .
```

Good first issues: [`good first issue`](https://github.com/OpenCodeIntel/saar/issues?q=label%3A%22good+first+issue%22)

If you're building a feature, open an issue first. Saves everyone time.

---

## Why I built this

I'm Devanshu — MS Software Engineering at Northeastern, solo founder building this in the open.

I got tired of AI tools that sounded smart but didn't actually know my project. Every session: wrong package manager, wrong exception class, wrong import. The fix was obvious — give the AI a context file. The problem was nobody maintained those files, they went stale, and most were full of generic filler the AI already knew.

So I built saar. It generates the file, keeps it short, tells you when it's stale, and lints it for quality. It runs locally, costs nothing, and works with every AI tool you already use.

The code is all here. The benchmarks are all here. Nothing hidden.

---

## Community

- **Issues:** [github.com/OpenCodeIntel/saar/issues](https://github.com/OpenCodeIntel/saar/issues)
- **Discussions:** [github.com/OpenCodeIntel/saar/discussions](https://github.com/OpenCodeIntel/saar/discussions)
- **Website:** [getsaar.com](https://getsaar.com)
- **OCI platform:** [opencodeintel.com](https://opencodeintel.com)

---

## License

MIT. Free forever. Do whatever you want with it.

---

<div align="center">

**[getsaar.com](https://getsaar.com)** &nbsp;·&nbsp; **[PyPI](https://pypi.org/project/saar/)** &nbsp;·&nbsp; **[MIT License](./LICENSE)**

*If saar saved you time, a ⭐ helps others find it.*

</div>

<img src="https://capsule-render.vercel.app/api?type=waving&color=0:080C14,50:0D1420,100:080C14&height=100&section=footer" width="100%" />
