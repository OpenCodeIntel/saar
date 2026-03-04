# saar

Extract the essence of your codebase. Auto-generate AI context files that actually reflect how your team writes code.

```bash
pipx install saar
saar extract ./my-repo
```

---

## The problem

AI coding tools know everything about every codebase except yours.

They write `npm install` in your bun repo. They invent exception classes you already have. They touch frozen modules. Every session starts from zero -- no memory of your conventions, your gotchas, your patterns. You spend the session correcting the same mistakes.

The fix is a context file (CLAUDE.md, AGENTS.md, .cursorrules) that tells your AI assistant how your specific codebase works. But nobody writes these well. You forget the exception class buried in auth.py. You forget the service singleton pattern. You forget the rule you added six months ago. The file goes stale the week after you write it.

Saar generates it automatically, keeps it updated, and lets you accumulate corrections over time.

---

## How it works

```
saar extract ./my-repo
```

Three things happen:

1. **Static analysis** -- tree-sitter AST parsing across every Python and TypeScript/JavaScript file. Detects auth patterns, service architecture, exception classes, database conventions, naming conventions, dependency graph, critical files.

2. **Guided interview** -- 4-7 questions that capture what static analysis cannot. Domain vocabulary, gotchas, off-limits files, verification workflow. Answers cached in `.saar/config.json`, never asked again.

3. **AGENTS.md generated** -- cross-tool standard read by Claude Code, Cursor, Copilot, Codex, Gemini CLI. Also generates CLAUDE.md, .cursorrules, copilot-instructions.md on request.

Runs locally. Your code never leaves your machine. No API keys required.

---

## Real output

Running on our own codebase (saar itself):

```
saar analyzing saar...
Found 24 code files (15 app, 9 test)
Style: 252 functions, 38 classes, 21% async, 92% typed
Graph built: 24 nodes, 46 edges, 0 cycles
DNA extraction complete: 0.75s
```

Generated AGENTS.md (auto-detected section):

```markdown
252 functions, 38 classes, 21% async, 92% type-hinted.
Languages: python (24 files)

## Coding Conventions
- Functions: snake_case
- Classes: PascalCase
- Constants: UPPER_SNAKE_CASE

## Critical Files
- saar/models.py (14 dependents)
- saar/interview.py (3 dependents)
- saar/cli.py (3 dependents)

## Testing
- Framework: pytest
- Pattern: test_*.py
- Shared fixtures in conftest.py
```

Plus tribal knowledge from the interview:

```markdown
## Tribal Knowledge

This project: CLI tool that extracts codebase DNA and generates AI context files

### Never Do
- Never add external infrastructure dependencies (no network calls)
- Never use print() -- always use logging

### Domain Vocabulary
- DNA = extracted architectural patterns of a codebase
- Tribal knowledge = context only humans can provide

### Off-Limits Files
- saar/models.py -- core data contract, discuss before changing
```

---

## Accumulating corrections

The highest-value content in any context file is the corrections -- things AI got wrong, rules discovered the hard way. Saar has a command for this:

```bash
# AI just tried to use npm in your bun repo
saar add "Never use npm -- this project uses bun only"

# Claude modified a frozen module
saar add --off-limits "billing/ -- legacy Stripe integration, frozen until Q3"

# AI used generic exceptions instead of your domain ones
saar add --domain "AuthenticationError -- use this, not HTTPException, for auth failures"

# Re-generate with the new rule
saar extract . --no-interview
```

Each correction is appended as a bullet to your tribal knowledge. Every subsequent generation includes it. The file gets better every time AI makes a mistake.

---

## AI enrichment

Raw corrections get polished into precise, actionable rules:

```bash
# Set ANTHROPIC_API_KEY, then:
saar enrich
```

Turns `"don't touch billing it's messy"` into:

```
NEVER modify billing/ -- legacy Stripe integration, no test coverage,
frozen until Q3 migration. Changes require DBA review.
```

Or run enrichment inline:

```bash
saar extract . --enrich
```

---

## All commands

```bash
# generate AGENTS.md (default -- cross-tool standard)
saar extract ./my-repo

# generate specific formats
saar extract ./my-repo --format claude          # CLAUDE.md
saar extract ./my-repo --format cursorrules     # .cursorrules
saar extract ./my-repo --format copilot         # copilot-instructions.md
saar extract ./my-repo --format all             # all four

# skip the interview (use cached answers or auto-detect only)
saar extract ./my-repo --no-interview

# add a correction without re-running analysis
saar add "Never use sync functions in async endpoints"
saar add --domain "Workspace = tenant, not a directory"
saar add --off-limits "core/auth.py -- clock-skew workaround"
saar add --verify "pytest -x && docker compose up && curl localhost:8000/health"

# AI enrichment of raw answers via Claude
saar enrich
saar enrich --dry-run          # preview without saving
saar extract . --enrich        # enrich inline during extraction

# write to a specific directory
saar extract ./my-repo -o ./docs/

# overwrite existing files
saar extract ./my-repo --force

# exclude directories beyond defaults
saar extract ./my-repo --exclude vendor legacy
```

---

## Preservation markers

Generated files include markers that separate auto-detected content from anything you write manually:

```markdown
<!-- SAAR:AUTO-START -->
[auto-detected content -- updated on every re-run]
<!-- SAAR:AUTO-END -->

[your manual additions -- never touched]
```

Re-running `saar extract` updates the auto section and leaves everything below the markers untouched. Add team-specific rules below the end marker -- they persist forever.

---

## Custom exclusions

Create `.saarignore` in your repo root using the same syntax as `.gitignore`:

```
# .saarignore
vendor/
legacy/
generated/
backend/repos/
```

Saar already skips `node_modules/`, `venv/`, `dist/`, `build/`, `.git/`, and everything in `.gitignore`. `.saarignore` adds project-specific exclusions on top.

---

## What it detects

**From Python files:**
- Framework (FastAPI, Flask, Django)
- Auth patterns -- middleware, decorators, auth context type
- Service architecture -- singletons, dependency injection, wiring file
- Database -- ORM, primary key type, timestamps, Row Level Security, cascade deletes
- Error handling -- exception class hierarchy, HTTP exception usage, logging on error
- Logging -- logger import pattern, structured logging
- Config -- env loading, settings pattern, secrets handling
- Naming conventions -- function/class/constant/file style

**From TypeScript/JavaScript files:**
- Framework (Next.js, Express, React)
- Function counting -- arrow functions, methods, declarations
- Naming conventions -- camelCase vs PascalCase detection
- Common imports -- top patterns across the codebase

**From the dependency graph:**
- Import resolution -- which files import which
- Critical files -- highest dependent count (understand before editing)
- Circular dependencies -- flagged explicitly
- Impact analysis -- what breaks if you change a file

**From team rules files:**
- Auto-includes CLAUDE.md, .cursorrules, .codeintel/rules.md, CONVENTIONS.md, copilot-instructions.md

---

## Installation

```bash
# recommended -- no venv needed
pipx install saar

# or
pip install saar
```

Requires Python 3.10+.

On Mac, use `pipx` to avoid the `externally-managed-environment` error.

---

## Development

```bash
git clone https://github.com/OpenCodeIntel/saar.git
cd saar
python -m venv venv && source venv/bin/activate
pip install -e ".[dev]"
pytest tests/ -v
ruff check saar/ tests/
```

AI enrichment requires `anthropic`:

```bash
pip install saar[enrich]
export ANTHROPIC_API_KEY=your-key
saar enrich
```

---

## License

MIT. Built by [OpenCodeIntel](https://opencodeintel.com).
