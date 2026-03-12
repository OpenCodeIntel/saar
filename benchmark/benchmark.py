#!/usr/bin/env python3
"""saar benchmark -- OPE-99

Measures whether saar's AGENTS.md reduces Claude's convention violations
when making code changes to a real codebase.

Method:
  For each task, ask Claude to generate code twice:
    1. Without context (no AGENTS.md)
    2. With context (AGENTS.md prepended to the prompt)

  Then check the output against binary pass/fail convention rules.

  Score = violations_without - violations_with
  Positive = saar helped.

Usage:
  export ANTHROPIC_API_KEY=sk-ant-...
  python benchmark/benchmark.py
"""
from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path


REPO_PATH = Path("/tmp/repo1-fastapi-template")
AGENTS_MD_PATH = REPO_PATH / "AGENTS.md"
MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 1000
RUNS_PER_TASK = 3


# ── Checks ────────────────────────────────────────────────────────────────────

@dataclass
class Check:
    name: str
    description: str
    fn: object = field(repr=False)


def _check_uses_bun_not_npm(output: str) -> bool:
    has_npm = bool(re.search(r'\bnpm install\b|\bnpm i\b|\byarn add\b|\byarn install\b', output))
    return not has_npm


def _check_uses_httpexception(output: str) -> bool:
    has_httpexception = "HTTPException" in output
    has_wrong = bool(re.search(r'raise ValueError\b|raise Exception\(|raise RuntimeError\b', output))
    return not (has_wrong and not has_httpexception)


def _check_snake_case_python_functions(output: str) -> bool:
    for name in re.findall(r'\bdef\s+([a-zA-Z_]\w*)\s*\(', output):
        if name.startswith('_'):
            continue
        if name[0].islower() and any(c.isupper() for c in name):
            return False
    return True


def _check_uses_depends_auth(output: str) -> bool:
    has_depends = bool(re.search(r'Depends\s*\(\s*\w*(auth|user|current)\w*\s*\)', output, re.IGNORECASE))
    has_manual = bool(re.search(r'request\.headers\[.Authorization', output))
    return not (has_manual and not has_depends)


def _check_uses_cn_not_raw_classname(output: str) -> bool:
    has_cn = bool(re.search(r'\bcn\s*\(', output))
    has_raw = bool(re.search(r'className=\{`[^`]*\$\{[^}]+\}', output))
    return not (has_raw and not has_cn)


def _check_uses_usequery_not_fetch(output: str) -> bool:
    has_usequery = bool(re.search(r'\buseQuery\b|\buseMutation\b', output))
    has_bad = bool(re.search(r'useEffect[^)]*\n[^)]*fetch\s*\(', output))
    return not (has_bad and not has_usequery)


def _check_no_print_statements(output: str) -> bool:
    for block in re.findall(r'```python(.*?)```', output, re.DOTALL):
        if re.search(r'^\s*print\s*\(', block, re.MULTILINE):
            return False
    return True


def _check_uses_pytest_fixtures(output: str) -> bool:
    has_setup = bool(re.search(r'def setUp\s*\(|def tearDown\s*\(', output))
    has_fixture = bool(re.search(r'@pytest\.fixture|def conftest', output))
    return not (has_setup and not has_fixture)


# ── Tasks ─────────────────────────────────────────────────────────────────────

@dataclass
class Task:
    id: str
    title: str
    prompt: str
    checks: list[Check]


TASKS: list[Task] = [
    Task(
        id="backend_endpoint",
        title="Add a FastAPI endpoint to list user items",
        prompt="""Write a new FastAPI endpoint to list items for the current user.
Endpoint: GET /api/v1/items, returns a list of items.
Show complete Python code including route, auth, and response model.""",
        checks=[
            Check("uses_httpexception", "Errors use HTTPException", _check_uses_httpexception),
            Check("snake_case_functions", "Python functions use snake_case", _check_snake_case_python_functions),
            Check("depends_auth", "Auth uses Depends() not manual headers", _check_uses_depends_auth),
            Check("no_print", "Uses logging not print()", _check_no_print_statements),
        ],
    ),
    Task(
        id="frontend_component",
        title="Add a React component for a user profile card",
        prompt="""Write a React TypeScript component UserProfileCard that:
- Fetches user data from /api/v1/users/me
- Shows name, email, avatar
- Loading state while fetching
- Conditional styling based on whether user is active
Show complete component code.""",
        checks=[
            Check("uses_usequery", "Data fetching uses useQuery not raw fetch", _check_uses_usequery_not_fetch),
            Check("uses_cn", "Conditional classes use cn()", _check_uses_cn_not_raw_classname),
        ],
    ),
    Task(
        id="install_package",
        title="Install the date-fns package",
        prompt="""I need to add the 'date-fns' library for date formatting.
Show the exact command to install it and how to import it in a TypeScript component.""",
        checks=[
            Check("uses_bun_not_npm", "Install uses bun not npm/yarn", _check_uses_bun_not_npm),
        ],
    ),
    Task(
        id="write_test",
        title="Write a pytest test for the items endpoint",
        prompt="""Write a pytest test for GET /api/v1/items.
Test: 1) Authenticated users can list their items. 2) Unauthenticated returns 401.
Show complete test code.""",
        checks=[
            Check("uses_pytest_fixtures", "Tests use pytest fixtures not setUp/tearDown", _check_uses_pytest_fixtures),
            Check("snake_case_functions", "Test functions use snake_case", _check_snake_case_python_functions),
        ],
    ),
    Task(
        id="auth_endpoint",
        title="Add auth to an existing endpoint",
        prompt="""The GET /api/v1/settings endpoint is currently public.
Make it require authentication so only logged-in users can access it.
Show the modified endpoint code.""",
        checks=[
            Check("depends_auth", "Auth uses Depends() not manual headers", _check_uses_depends_auth),
            Check("uses_httpexception", "Errors use HTTPException", _check_uses_httpexception),
        ],
    ),
]

TOTAL_CHECKS = sum(len(t.checks) for t in TASKS)


# ── Runner ────────────────────────────────────────────────────────────────────

@dataclass
class RunResult:
    task_id: str
    with_context: bool
    run_number: int
    output: str
    check_results: dict  # check_name -> bool
    violations: int
    latency_ms: float


def call_claude(prompt: str, system: str = "") -> tuple[str, float]:
    """Call Claude and return (response_text, latency_ms)."""
    import anthropic
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    start = time.time()
    msg = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=system or "You are a helpful software engineer.",
        messages=[{"role": "user", "content": prompt}],
    )
    latency_ms = (time.time() - start) * 1000
    return msg.content[0].text, latency_ms


def run_task(task: Task, agents_md: str, run_number: int) -> tuple[RunResult, RunResult]:
    """Run a task twice: without and with AGENTS.md context."""

    # WITHOUT context
    print(f"    run {run_number} WITHOUT context...", end=" ", flush=True)
    output_no_ctx, lat_no = call_claude(task.prompt)
    checks_no = {c.name: bool(c.fn(output_no_ctx)) for c in task.checks}
    violations_no = sum(1 for v in checks_no.values() if not v)
    print(f"violations={violations_no}")

    result_no = RunResult(
        task_id=task.id,
        with_context=False,
        run_number=run_number,
        output=output_no_ctx,
        check_results=checks_no,
        violations=violations_no,
        latency_ms=lat_no,
    )

    # WITH context -- prepend AGENTS.md as system prompt
    system_with_ctx = f"""You are a helpful software engineer working on this codebase.

CODEBASE CONTEXT (from AGENTS.md):
{agents_md}

Follow ALL conventions described above when writing code for this project."""

    print(f"    run {run_number} WITH context...", end=" ", flush=True)
    output_with_ctx, lat_with = call_claude(task.prompt, system=system_with_ctx)
    checks_with = {c.name: bool(c.fn(output_with_ctx)) for c in task.checks}
    violations_with = sum(1 for v in checks_with.values() if not v)
    print(f"violations={violations_with}")

    result_with = RunResult(
        task_id=task.id,
        with_context=True,
        run_number=run_number,
        output=output_with_ctx,
        check_results=checks_with,
        violations=violations_with,
        latency_ms=lat_with,
    )

    return result_no, result_with


def run_benchmark() -> dict:
    """Run all tasks RUNS_PER_TASK times each and return aggregated results."""
    if not AGENTS_MD_PATH.exists():
        raise FileNotFoundError(f"AGENTS.md not found at {AGENTS_MD_PATH}. Run: saar extract {REPO_PATH} --no-interview")

    agents_md = AGENTS_MD_PATH.read_text(encoding="utf-8")
    print(f"Loaded AGENTS.md ({len(agents_md.splitlines())} lines)")
    print(f"Running {len(TASKS)} tasks x {RUNS_PER_TASK} runs = {len(TASKS) * RUNS_PER_TASK * 2} Claude calls\n")

    all_results: list[RunResult] = []

    for task in TASKS:
        print(f"\n[{task.id}] {task.title}")
        for run_num in range(1, RUNS_PER_TASK + 1):
            r_no, r_with = run_task(task, agents_md, run_num)
            all_results.append(r_no)
            all_results.append(r_with)
            # small delay to avoid rate limiting
            time.sleep(1)

    return aggregate(all_results)


def aggregate(results: list[RunResult]) -> dict:
    """Aggregate per-task and overall statistics."""
    no_ctx = [r for r in results if not r.with_context]
    with_ctx = [r for r in results if r.with_context]

    def avg_violations(runs: list[RunResult]) -> float:
        return sum(r.violations for r in runs) / len(runs) if runs else 0

    # Per-task breakdown
    task_stats = {}
    for task in TASKS:
        t_no = [r for r in no_ctx if r.task_id == task.id]
        t_with = [r for r in with_ctx if r.task_id == task.id]

        # Per-check pass rates
        check_stats = {}
        for check in task.checks:
            no_pass = sum(1 for r in t_no if r.check_results.get(check.name)) / max(len(t_no), 1)
            with_pass = sum(1 for r in t_with if r.check_results.get(check.name)) / max(len(t_with), 1)
            check_stats[check.name] = {
                "description": check.description,
                "pass_rate_without_context": round(no_pass, 3),
                "pass_rate_with_context": round(with_pass, 3),
                "improvement": round(with_pass - no_pass, 3),
            }

        task_stats[task.id] = {
            "title": task.title,
            "avg_violations_without": round(avg_violations(t_no), 2),
            "avg_violations_with": round(avg_violations(t_with), 2),
            "improvement": round(avg_violations(t_no) - avg_violations(t_with), 2),
            "checks": check_stats,
        }

    overall_no = avg_violations(no_ctx)
    overall_with = avg_violations(with_ctx)

    # Total checks passed across all runs
    total_possible = TOTAL_CHECKS * RUNS_PER_TASK
    total_passed_no = sum(
        sum(1 for v in r.check_results.values() if v) for r in no_ctx
    )
    total_passed_with = sum(
        sum(1 for v in r.check_results.values() if v) for r in with_ctx
    )

    return {
        "model": MODEL,
        "repo": str(REPO_PATH),
        "runs_per_task": RUNS_PER_TASK,
        "tasks": len(TASKS),
        "total_checks_per_condition": total_possible,
        "overall": {
            "avg_violations_without_context": round(overall_no, 3),
            "avg_violations_with_context": round(overall_with, 3),
            "violation_reduction": round(overall_no - overall_with, 3),
            "violation_reduction_pct": round(
                (overall_no - overall_with) / max(overall_no, 0.001) * 100, 1
            ),
            "checks_passed_without": total_passed_no,
            "checks_passed_with": total_passed_with,
            "checks_passed_pct_without": round(total_passed_no / total_possible * 100, 1),
            "checks_passed_pct_with": round(total_passed_with / total_possible * 100, 1),
        },
        "tasks": task_stats,
        "raw_results": [asdict(r) for r in results],
    }


# ── Report generation ─────────────────────────────────────────────────────────

def generate_report(data: dict) -> str:
    """Generate a human-readable markdown report for the HN post."""
    o = data["overall"]
    lines = [
        "# saar benchmark results",
        "",
        f"**Repo:** `{Path(data['repo']).name}` (tiangolo/full-stack-fastapi-template)",
        f"**Model:** {data['model']}",
        f"**Tasks:** {data['tasks']}  |  **Runs per task:** {data['runs_per_task']}",
        f"**Total checks:** {data['total_checks_per_condition']} per condition",
        "",
        "## Summary",
        "",
        f"| Condition | Checks passed | Avg violations/task |",
        f"|---|---|---|",
        f"| Without AGENTS.md | {o['checks_passed_without']}/{data['total_checks_per_condition']} ({o['checks_passed_pct_without']}%) | {o['avg_violations_without_context']} |",
        f"| With AGENTS.md | {o['checks_passed_with']}/{data['total_checks_per_condition']} ({o['checks_passed_pct_with']}%) | {o['avg_violations_with_context']} |",
        f"| **Improvement** | **+{o['checks_passed_with'] - o['checks_passed_without']} checks** | **{o['violation_reduction_pct']}% fewer violations** |",
        "",
        "## Per-task breakdown",
        "",
    ]

    for task_id, t in data["tasks"].items():
        lines.append(f"### {t['title']}")
        lines.append("")
        lines.append(f"Avg violations: {t['avg_violations_without']} → {t['avg_violations_with']} ({'+' if t['improvement'] > 0 else ''}{t['improvement']})")
        lines.append("")
        lines.append("| Check | Without | With | Delta |")
        lines.append("|---|---|---|---|")
        for check_name, c in t["checks"].items():
            no_pct = f"{c['pass_rate_without_context']*100:.0f}%"
            with_pct = f"{c['pass_rate_with_context']*100:.0f}%"
            delta = c['improvement'] * 100
            delta_str = f"+{delta:.0f}%" if delta > 0 else f"{delta:.0f}%"
            lines.append(f"| {c['description']} | {no_pct} | {with_pct} | {delta_str} |")
        lines.append("")

    lines += [
        "## What this means",
        "",
        "Each check is a specific, binary convention from the codebase:",
        "- Uses `bun` not `npm` (the package manager for this project)",
        "- Uses `Depends()` for auth (FastAPI convention, not manual header parsing)",
        "- Uses `snake_case` for Python functions",
        "- Uses `HTTPException` for errors",
        "- Uses `useQuery`/`useMutation` for data fetching (not raw fetch in useEffect)",
        "- Uses `cn()` for Tailwind conditional classes",
        "",
        "Without AGENTS.md, Claude relies on training data alone.",
        "With AGENTS.md, Claude follows the specific conventions of this codebase.",
        "",
        f"Result: **{o['violation_reduction_pct']}% fewer convention violations** with saar.",
    ]

    return "\n".join(lines)


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY not set")
        sys.exit(1)

    print("=" * 60)
    print("saar benchmark -- OPE-99")
    print("=" * 60)

    results = run_benchmark()

    # Save raw results
    out_dir = Path(__file__).parent
    results_path = out_dir / "benchmark_results.json"
    results_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nRaw results saved to {results_path}")

    # Save report
    report = generate_report(results)
    report_path = out_dir / "benchmark_report.md"
    report_path.write_text(report, encoding="utf-8")
    print(f"Report saved to {report_path}")

    # Print summary
    o = results["overall"]
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"Without AGENTS.md: {o['checks_passed_pct_without']}% checks passed")
    print(f"With AGENTS.md:    {o['checks_passed_pct_with']}% checks passed")
    print(f"Improvement:       {o['violation_reduction_pct']}% fewer violations")
    print("=" * 60)
    print(f"\nFull report: {report_path}")
