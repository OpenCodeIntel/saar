<!-- SAAR:AUTO-START -->
# CLAUDE.md -- saar

289 functions, 48 classes.
Async adoption: 20%.
Type hint coverage: 92%.

## Coding Conventions

- Use `snake_case` for function names
- Use `PascalCase` for class names
- Use `UPPER_SNAKE_CASE` for constants
- Use `snake_case` for file names

Preferred imports:
```
import logging
from saar.models import CodebaseDNA
from pathlib import Path
from typing import Optional
import re
import tree_sitter_python as tspython
import tree_sitter_javascript as tsjavascript
from tree_sitter import Language, Parser
import json
import os
```

## Logging

- Use `logging.getLogger(__name__)` for all logging, never `print()`

## Critical Files

These files have the most dependents -- understand them before editing:

- `saar/models.py` (15 dependents)
- `saar/formatters/agents_md.py` (5 dependents)
- `saar/formatters/_tribal.py` (4 dependents)
- `saar/extractor.py` (3 dependents)
- `saar/formatters/claude_md.py` (3 dependents)
- `saar/cli.py` (3 dependents)
- `saar/interview.py` (3 dependents)
- `saar/dependency_analyzer.py` (2 dependents)

## Error Handling

- Always log exceptions before re-raising

## Testing

- Framework: pytest
- Test file pattern: `test_*.py`
- Fixture style: pytest fixtures
- Mock with: unittest.mock
- Shared fixtures live in `conftest.py`
- Run: `pytest tests/ -v`

## Tribal Knowledge

*Captured via `saar` interview -- human knowledge static analysis cannot detect.*

**This project:** CLI tool that extracts codebase DNA and generates AI context files (AGENTS.md, CLAUDE.md, .cursorrules)

### Never Do

- Never add external infrastructure dependencies (no Supabase, Redis, network calls). Never use print() -- always use logging. Never commit venv/ or dist/.
- Never use sync functions in async endpoints -- blocks the event loop

### Domain Vocabulary

- DNA = extracted architectural patterns of a codebase. Tribal knowledge = context only humans can provide (gotchas, domain terms, verification workflows).
- DNA = extracted architectural patterns, not genetic material

### Verification Workflow

pytest tests/ -v -- all 121 tests must pass. Then: saar . --format agents --no-interview to verify CLI output is clean.

### Off-Limits Files

> AI must never modify these:

- saar/models.py -- core data contract, discuss before changing

### Additional Context

This repo dogfoods itself -- always regenerate CLAUDE.md after formatter changes using: saar . --format claude --force --no-interview
<!-- SAAR:AUTO-END -->
