# CLAUDE.md -- saar

144 functions, 24 classes.
Async adoption: 17%.
Type hint coverage: 89%.

## Coding Conventions

- Use `snake_case` for function names
- Use `PascalCase` for class names
- Use `UPPER_SNAKE_CASE` for constants

Preferred imports:
```
from saar.models import CodebaseDNA
import logging
from pathlib import Path
import re
import tree_sitter_python as tspython
import tree_sitter_javascript as tsjavascript
from tree_sitter import Language, Parser
from collections import Counter
```

## Logging

- Use `logging.getLogger(__name__)` for all logging, never `print()`

## Critical Files

These files have the most dependents -- understand them before editing:

- `saar/models.py` (8 dependents)
- `saar/dependency_analyzer.py` (2 dependents)
- `saar/style_analyzer.py` (2 dependents)
- `saar/extractor.py` (2 dependents)
- `saar/formatters/__init__.py` (2 dependents)
- `saar/formatters/copilot.py` (2 dependents)
- `saar/formatters/markdown.py` (2 dependents)
- `saar/formatters/claude_md.py` (2 dependents)

## Error Handling

- Always log exceptions before re-raising

## Testing

- Framework: pytest
- Test file pattern: `test_*.py`
- Fixture style: pytest fixtures
- Mock with: unittest.mock
- Shared fixtures live in `conftest.py`
- Run: `pytest tests/ -v`
