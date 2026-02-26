# CLAUDE.md -- Saar

Saar extracts the essence of a codebase and auto-generates AI config files.

## Code standards

- No emojis anywhere in code, comments, or output
- Type hints on all function signatures
- Files prefer <200 lines (exceptions allowed if cohesive -- extractor.py is one)
- Comments explain WHY not WHAT
- Commits: `type: description` (feat, fix, docs, refactor, test, chore)
- Python 3.10+ minimum, use modern syntax (match, `X | Y` unions, etc.)

## Project structure

```
saar/
  __init__.py          # version only
  cli.py               # Typer CLI entry point
  extractor.py         # core DNA extraction engine (tree-sitter)
  models.py            # 8 pattern dataclasses + CodebaseDNA
  formatters/
    __init__.py         # render() dispatcher
    markdown.py         # generic markdown output
    claude_md.py        # CLAUDE.md format
    cursorrules.py      # .cursorrules format
    copilot.py          # copilot-instructions.md format
tests/
  conftest.py           # shared fixtures
  test_extractor.py     # extraction logic
  test_formatters.py    # output formatting
  test_cli.py           # CLI integration
```

## Architecture rules

- Zero external infrastructure dependencies (no Supabase, Redis, Pinecone)
- Only dependencies: tree-sitter, typer, rich
- Models are pure dataclasses in models.py -- no methods beyond to_dict()
- Formatters are pure functions: `(CodebaseDNA) -> str`
- Extractor is a class because it holds parser state and file cache
- CLI imports extractor and formatters lazily for fast startup

## Conventions

- Use `logging.getLogger(__name__)` for all logging
- Use `.get()` for all dict access on external data (API responses, parsed content)
- Formatters never raise -- degrade gracefully on missing data
- Extractor methods prefixed with `_extract_` for pattern categories
- Tests use pytest, no unittest

## Testing

- Run: `pytest tests/ -v`
- All formatters testable without disk I/O (pass CodebaseDNA directly)
- Extractor tests use a fixtures directory with sample repo structures
- No mocking tree-sitter -- test against real parsed output

## CLI

- Entry point: `saar` (defined in pyproject.toml)
- All output goes through formatters -- CLI never builds strings directly
- `--verbose` enables DEBUG logging, default is WARNING
- Exit code 1 on extraction failure
