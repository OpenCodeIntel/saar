# v0.1.0 -- First Release

**Extract the essence of your codebase.**

`pip install saar && saar ./my-repo`

## What it does

Saar analyzes your codebase using tree-sitter AST parsing and auto-generates AI coding config files (CLAUDE.md, .cursorrules, copilot-instructions.md) that reflect how your team actually writes code.

## Three analysis engines

- **DNA Extractor** -- auth patterns, service architecture, database conventions, error handling, logging, naming, config, API patterns, team rules detection
- **Style Analyzer** -- function/class counts, async adoption %, type hint coverage %, naming conventions
- **Dependency Analyzer** -- import graph, circular dependency detection, critical files

## Output formats

```bash
saar ./my-repo                          # markdown to stdout
saar ./my-repo --format claude          # CLAUDE.md
saar ./my-repo --format cursorrules     # .cursorrules
saar ./my-repo --format copilot         # copilot-instructions.md
saar ./my-repo --format all             # all three
saar ./my-repo --exclude vendor data    # skip directories
```

## Smart defaults

- Auto-reads .gitignore to skip irrelevant directories
- Separates test code from app code (prevents false positives)
- Won't overwrite existing config files without --force
- Zero infrastructure dependencies -- runs locally, no API keys

## Stats

- 2,737 lines of code
- 75 tests passing
- Tested on 7 real repositories
- Python 3.10+
