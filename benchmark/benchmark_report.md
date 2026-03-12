# saar benchmark results

**Repo:** `repo1-fastapi-template` (tiangolo/full-stack-fastapi-template)
**Model:** claude-sonnet-4-20250514
**Tasks:** {'backend_endpoint': {'title': 'Add a FastAPI endpoint to list user items', 'avg_violations_without': 0.0, 'avg_violations_with': 0.0, 'improvement': 0.0, 'checks': {'uses_httpexception': {'description': 'Errors use HTTPException', 'pass_rate_without_context': 1.0, 'pass_rate_with_context': 1.0, 'improvement': 0.0}, 'snake_case_functions': {'description': 'Python functions use snake_case', 'pass_rate_without_context': 1.0, 'pass_rate_with_context': 1.0, 'improvement': 0.0}, 'depends_auth': {'description': 'Auth uses Depends() not manual headers', 'pass_rate_without_context': 1.0, 'pass_rate_with_context': 1.0, 'improvement': 0.0}, 'no_print': {'description': 'Uses logging not print()', 'pass_rate_without_context': 1.0, 'pass_rate_with_context': 1.0, 'improvement': 0.0}}}, 'frontend_component': {'title': 'Add a React component for a user profile card', 'avg_violations_without': 1.0, 'avg_violations_with': 0.0, 'improvement': 1.0, 'checks': {'uses_usequery': {'description': 'Data fetching uses useQuery not raw fetch', 'pass_rate_without_context': 1.0, 'pass_rate_with_context': 1.0, 'improvement': 0.0}, 'uses_cn': {'description': 'Conditional classes use cn()', 'pass_rate_without_context': 0.0, 'pass_rate_with_context': 1.0, 'improvement': 1.0}}}, 'install_package': {'title': 'Install the date-fns package', 'avg_violations_without': 1.0, 'avg_violations_with': 0.0, 'improvement': 1.0, 'checks': {'uses_bun_not_npm': {'description': 'Install uses bun not npm/yarn', 'pass_rate_without_context': 0.0, 'pass_rate_with_context': 1.0, 'improvement': 1.0}}}, 'write_test': {'title': 'Write a pytest test for the items endpoint', 'avg_violations_without': 0.0, 'avg_violations_with': 0.0, 'improvement': 0.0, 'checks': {'uses_pytest_fixtures': {'description': 'Tests use pytest fixtures not setUp/tearDown', 'pass_rate_without_context': 1.0, 'pass_rate_with_context': 1.0, 'improvement': 0.0}, 'snake_case_functions': {'description': 'Test functions use snake_case', 'pass_rate_without_context': 1.0, 'pass_rate_with_context': 1.0, 'improvement': 0.0}}}, 'auth_endpoint': {'title': 'Add auth to an existing endpoint', 'avg_violations_without': 0.0, 'avg_violations_with': 0.0, 'improvement': 0.0, 'checks': {'depends_auth': {'description': 'Auth uses Depends() not manual headers', 'pass_rate_without_context': 1.0, 'pass_rate_with_context': 1.0, 'improvement': 0.0}, 'uses_httpexception': {'description': 'Errors use HTTPException', 'pass_rate_without_context': 1.0, 'pass_rate_with_context': 1.0, 'improvement': 0.0}}}}  |  **Runs per task:** 1
**Total checks:** 11 per condition

## Summary

| Condition | Checks passed | Avg violations/task |
|---|---|---|
| Without AGENTS.md | 9/11 (81.8%) | 0.4 |
| With AGENTS.md | 11/11 (100.0%) | 0.0 |
| **Improvement** | **+2 checks** | **100.0% fewer violations** |

## Per-task breakdown

### Add a FastAPI endpoint to list user items

Avg violations: 0.0 → 0.0 (0.0)

| Check | Without | With | Delta |
|---|---|---|---|
| Errors use HTTPException | 100% | 100% | 0% |
| Python functions use snake_case | 100% | 100% | 0% |
| Auth uses Depends() not manual headers | 100% | 100% | 0% |
| Uses logging not print() | 100% | 100% | 0% |

### Add a React component for a user profile card

Avg violations: 1.0 → 0.0 (+1.0)

| Check | Without | With | Delta |
|---|---|---|---|
| Data fetching uses useQuery not raw fetch | 100% | 100% | 0% |
| Conditional classes use cn() | 0% | 100% | +100% |

### Install the date-fns package

Avg violations: 1.0 → 0.0 (+1.0)

| Check | Without | With | Delta |
|---|---|---|---|
| Install uses bun not npm/yarn | 0% | 100% | +100% |

### Write a pytest test for the items endpoint

Avg violations: 0.0 → 0.0 (0.0)

| Check | Without | With | Delta |
|---|---|---|---|
| Tests use pytest fixtures not setUp/tearDown | 100% | 100% | 0% |
| Test functions use snake_case | 100% | 100% | 0% |

### Add auth to an existing endpoint

Avg violations: 0.0 → 0.0 (0.0)

| Check | Without | With | Delta |
|---|---|---|---|
| Auth uses Depends() not manual headers | 100% | 100% | 0% |
| Errors use HTTPException | 100% | 100% | 0% |

## What this means

Each check is a specific, binary convention from the codebase:
- Uses `bun` not `npm` (the package manager for this project)
- Uses `Depends()` for auth (FastAPI convention, not manual header parsing)
- Uses `snake_case` for Python functions
- Uses `HTTPException` for errors
- Uses `useQuery`/`useMutation` for data fetching (not raw fetch in useEffect)
- Uses `cn()` for Tailwind conditional classes

Without AGENTS.md, Claude relies on training data alone.
With AGENTS.md, Claude follows the specific conventions of this codebase.

Result: **100.0% fewer convention violations** with saar.