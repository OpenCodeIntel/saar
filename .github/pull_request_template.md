## What does this PR do?

<!-- One paragraph. What problem does it solve? -->

## Why?

<!-- Why is this change needed? -->
<!-- Closes OPE-XXX  ← add Linear issue here, auto-closes on merge -->

## Type of change

- [ ] Bug fix
- [ ] New feature / command
- [ ] Refactor (no behavior change)
- [ ] Docs / chore
- [ ] New extraction pattern (saar/extractors/)
- [ ] Formatter change (saar/formatters/)

## Module affected

<!-- saar knows its own structure. Tick what you touched. -->
- [ ] `saar/commands/` — CLI command logic
- [ ] `saar/extractors/` — Pattern extraction
- [ ] `saar/formatters/` — Output generation
- [ ] `saar/linter.py` — AGENTS.md quality rules
- [ ] `saar/scorer.py` — Quality scoring
- [ ] `saar/models.py` — ⚠️ Core data contract (discuss before touching)

## Verification

<!-- saar dogfoods itself. Run these before opening the PR. -->

```bash
source venv/bin/activate

# 1. Lint
ruff check saar/ tests/

# 2. Tests — 548 must pass
pytest tests/ -q

# 3. Dogfood — saar must extract itself cleanly with no stale warnings
saar extract . --no-interview

# 4. If you changed a formatter, regenerate all context files
saar extract . --force --no-interview
```

## Checklist

- [ ] `ruff check saar/ tests/` passes (no E/F violations)
- [ ] `pytest tests/ -q` → 548 passed
- [ ] `saar extract . --no-interview` runs clean (no stale fact warnings)
- [ ] Did NOT modify `saar/models.py` without discussion
- [ ] Did NOT add external dependencies (no Supabase, Redis, network calls in core path)
- [ ] Version bumped in `pyproject.toml` + `saar/__init__.py` (if shipping a release)
