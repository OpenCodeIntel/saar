# Saar

**Extract the essence of your codebase.**

Saar analyzes your codebase using tree-sitter AST parsing and auto-generates AI coding config files -- CLAUDE.md, .cursorrules, and copilot-instructions.md -- that actually reflect how your team writes code.

```bash
pip install saar
saar ./my-repo
```

## Why

AI coding tools (Cursor, Claude Code, Copilot) generate code that doesn't match your project's patterns. The fix is config files like CLAUDE.md and .cursorrules, but nobody writes them well and nobody keeps them updated.

Saar does it automatically. Deep static analysis, not keyword matching. It parses your AST and detects auth patterns, service architecture, database conventions, error handling, naming rules -- 8 categories of patterns.

## What it detects

- **Auth patterns** -- middleware, decorators, ownership checks
- **Service patterns** -- singletons, dependency injection, base classes
- **Database patterns** -- ORM, connection patterns, RLS, ID types
- **Error handling** -- exception classes, response formats, logging
- **Logging patterns** -- setup, levels, structured logging
- **Naming conventions** -- function/variable naming style distribution
- **Import patterns** -- common imports, dependency graph
- **Team rules** -- existing CLAUDE.md, .cursorrules, .editorconfig

## Output formats

```bash
saar ./my-repo                          # markdown to stdout
saar ./my-repo --format claude          # generate CLAUDE.md
saar ./my-repo --format cursorrules     # generate .cursorrules
saar ./my-repo --format copilot         # generate copilot-instructions.md
saar ./my-repo --format all             # generate all three
saar ./my-repo -o ./output/             # write to directory
```

## How it works

Saar uses tree-sitter to parse every Python and JavaScript file into an AST. It walks the syntax tree to extract structural patterns -- not regex, not keyword matching, not LLM inference. Zero hallucination because it reads the actual code structure.

Runs locally. Your code never leaves your machine. No API keys needed.

## Installation

```bash
pip install saar
```

Requires Python 3.10+.

## License

MIT
