# Saar

**Extract the essence of your codebase.**

Saar analyzes your codebase using tree-sitter AST parsing and auto-generates AI coding config files -- CLAUDE.md, .cursorrules, and copilot-instructions.md -- that actually reflect how your team writes code.

```bash
pip install saar
saar ./my-repo
```

## Why

AI coding tools generate code that doesn't match your project's conventions. The fix is config files like CLAUDE.md and .cursorrules, but nobody writes them well and nobody keeps them updated.

Saar does it automatically. Deep static analysis, not keyword matching. It parses your AST and detects auth patterns, service architecture, database conventions, error handling, naming rules, dependency structure, and more.

## Real output

Running `saar` on a FastAPI backend (82 Python files):

```
Framework: fastapi

Functions: 787 | Classes: 175
Async Adoption: 49%
Type Hint Coverage: 88%
Internal Dependencies: 199

Authentication: Depends(require_auth), Depends(public_auth)
Service Layer: 7 singletons wired via dependencies.py
Database: Supabase, UUID primary keys, TIMESTAMPTZ, RLS enabled
Testing: pytest with fixtures, unittest.mock
Config: python-dotenv, Pydantic Settings
```

Running on a Next.js app (22 TypeScript files):

```
Framework: nextjs

Functions: 12 | Classes: 0
Async Adoption: 28%
Type Hint Coverage: 64%
Internal Dependencies: 5
```

## What it detects

**Three analysis engines, all tree-sitter powered:**

- **DNA Extractor** -- auth patterns, service architecture, database conventions, error handling, logging, naming, config, API patterns, team rules detection
- **Style Analyzer** -- function/class counts, async adoption %, type hint coverage %, naming convention distribution, top imports
- **Dependency Analyzer** -- import graph, internal dependency resolution, circular dependency detection, critical files (most dependents), impact analysis

## Output formats

```bash
saar ./my-repo                          # markdown to stdout
saar ./my-repo --format claude          # generate CLAUDE.md
saar ./my-repo --format cursorrules     # generate .cursorrules
saar ./my-repo --format copilot         # generate copilot-instructions.md
saar ./my-repo --format all             # generate all three
saar ./my-repo -o ./output/             # write to directory
saar ./my-repo --format claude --force  # overwrite existing files
saar ./my-repo --exclude vendor data    # skip directories
```

## Smart defaults

- Auto-reads `.gitignore` to skip irrelevant directories
- Separates test code from application code (prevents false positives from test fixtures)
- Won't overwrite existing config files without `--force`
- Skips its own output files when reading team rules (no inception loop)

## How it works

Saar uses tree-sitter to parse every Python and JavaScript/TypeScript file into an AST. It walks the syntax tree to extract structural patterns -- not regex on raw text, not LLM inference. Zero hallucination because it reads the actual code structure.

Runs locally. Your code never leaves your machine. No API keys needed.

## Installation

```bash
pip install saar
```

Requires Python 3.10+.

## Development

```bash
git clone https://github.com/OpenCodeIntel/saar.git
cd saar
python -m venv venv && source venv/bin/activate
pip install -e ".[dev]"
pytest tests/ -v           # 75 tests
ruff check saar/ tests/    # lint
```

## License

MIT
