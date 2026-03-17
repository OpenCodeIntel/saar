<!-- SAAR:AUTO-START -->
# CLAUDE.md -- saar

808 functions, 137 classes.
Async adoption: 14%.
Type hint coverage: 85%.


## Frontend

**Stack:** React + TypeScript + Vite
- Package manager: `bun` -- always use `bun install`, never npm/yarn
- Styling: Tailwind CSS -- no raw CSS files
## Coding Conventions

- Use `snake_case` for function names
- Use `PascalCase` for class names
- Use `UPPER_SNAKE_CASE` for constants
- Use `snake_case` for file names

Preferred imports:
```
from __future__ import annotations
from pathlib import Path
import re
from typing import Optional
import logging
from saar.models import CodebaseDNA
import json
import os
import typer
from rich.console import Console
```

## Logging

- Use `logging.getLogger(__name__)` for all logging, never `print()`

## Critical Files

These files have the most dependents -- understand them before editing:

- `saar/models.py` (27 dependents)
- `saar/cli.py` (10 dependents)
- `saar/extractor.py` (8 dependents)
- `saar/formatters/agents_md.py` (7 dependents)
- `saar/interview.py` (5 dependents)
- `saar/differ.py` (5 dependents)
- `saar/formatters/_tribal.py` (4 dependents)
- `saar/formatters/claude_md.py` (4 dependents)

## Error Handling

- Use existing exceptions: `OCIAPIError, OCIAuthError`
- Always log exceptions before re-raising


> [33 lines omitted -- run `saar extract --verbose` for full output]
## Tribal Knowledge

*Captured via `saar` interview -- human knowledge static analysis cannot detect.*

**This project:** CLI tool that extracts codebase DNA and generates AI context files (AGENTS.md, CLAUDE.md, .cursorrules) -- no server, no account, no API key required

### Never Do

- Always run tests inside venv: source venv/bin/activate && pytest tests/ -v -- system Python missing typer causes 4 collection errors
- 499 tests must pass before any commit
- Push directly to OpenCodeIntel/saar main (no fork). Never commit venv/ dist/ __pycache__
- Never add external infrastructure dependencies (no Supabase, Redis, network calls in core path)
- saar/cli.py is 1514 lines -- extract helpers to separate modules, never add more logic directly
- extractor.py is 1579 lines -- all methods share self._file_cache, never break this when adding languages
- benchmark/ contains OPE-99 results -- never delete benchmark_results.json or benchmark_report.md
- saar has NO web auth -- ignore any detected Depends(reusable_oauth2), it is a false positive from test fixtures
- Always run ruff check saar/ tests/ before committing -- CI will fail on F541 (f-string without placeholders) and other lint errors. Run: source venv/bin/activate && ruff check saar/ tests/ && pytest tests/ -q
- saar/cli.py is now 68 lines -- command logic lives in saar/commands/ (extract, maintain, quality, explore)
- saar/extractor.py is now 621 lines -- pattern logic lives in saar/extractors/ (backend, conventions, frontend, project)
- Never add command logic to cli.py -- it only registers app.command() calls
- Never add extraction logic to extractor.py -- DNAExtractor delegates to saar/extractors/ modules via self._safe_read_file

### Domain Vocabulary

- DNA = extracted architectural patterns of a codebase (not genetic material)
- Tribal knowledge = context only humans can provide: gotchas, domain terms, verification workflows -- static analysis cannot detect this
- SAAR:AUTO-START/END markers = preservation markers separating auto-generated from human-written sections in generated files
- budget = line cap on generated output (default 100 lines, --verbose for full)

### Verification Workflow

source venv/bin/activate && pytest tests/ -v -- all 499 tests must pass. Then: saar extract . --no-interview to verify CLI output is clean

### Off-Limits Files

> AI must never modify these:

- saar/models.py -- core data contract, CodebaseDNA and all dataclasses, never modify without discussion

### Additional Context

This repo dogfoods itself -- after any formatter change regenerate all context files: saar extract . --force --no-interview
<!-- SAAR:AUTO-END -->
