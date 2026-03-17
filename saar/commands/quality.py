"""Quality commands: stats, lint, check.

These commands measure and enforce AGENTS.md quality.
  stats -- score AGENTS.md 0-100 with category breakdown
  lint  -- find specific violations (SA001-SA005) with line numbers
  check -- CI health check, exits 1 if stale or missing required sections
"""
from __future__ import annotations

import json as _json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

console = Console()


def cmd_stats(
    repo_path: Path = typer.Argument(Path("."), help="Path to the repository.", exists=True, file_okay=False, dir_okay=True, resolve_path=True),
    file: Optional[Path] = typer.Option(None, "--file", "-f", help="Specific context file (default: AGENTS.md)."),
) -> None:
    """Score your AGENTS.md quality: 0-100. See what's missing and why.

    Examples:

      saar stats

      saar stats ./my-repo

      saar stats --file ./CLAUDE.md
    """
    from saar.scorer import score_agents_md
    from rich.table import Table
    from rich import box

    target_file = file or (repo_path / "AGENTS.md")
    if not target_file.exists():
        fallback = repo_path / "CLAUDE.md"
        if not file and fallback.exists():
            target_file = fallback
        else:
            console.print(f"\n  [yellow]No AGENTS.md found in {repo_path.name}[/yellow]\n  Run [bold]saar extract .[/bold] to generate one.\n")
            raise typer.Exit(code=1)

    result = score_agents_md(target_file, repo_path)
    score = result.total_score
    grade = result.grade
    project_type = result.project_type

    # Normalize to 100 -- a CLI project scoring 88/88 IS 100%, display it honestly
    possible_max = result.coverage_max + 60
    display_score = round(score * 100 / possible_max) if possible_max > 0 else score

    if display_score >= 85:
        score_color, verdict = "green", "Excellent -- AI will follow this well"
    elif display_score >= 70:
        score_color, verdict = "cyan", "Good -- a few improvements would help"
    elif display_score >= 50:
        score_color, verdict = "yellow", "Needs work -- missing key sections"
    else:
        score_color, verdict = "red", "Poor -- AI will likely ignore this"

    type_hint = f"  [dim]({project_type} — auth/exceptions not required)[/dim]" if project_type in ("library", "cli") else ""

    console.print()
    console.print(f"  [bold]saar stats[/bold] — [cyan]{target_file.name}[/cyan]  [{score_color}][bold]{display_score}/100[/bold][/{score_color}]  [dim]({grade})[/dim]{type_hint}")
    console.print(f"  [dim]{verdict}[/dim]")
    console.print()

    filled = round(display_score / 5)
    bar = f"  [{score_color}]{'█' * filled}[/{score_color}][dim]{'░' * (20 - filled)}[/dim]  {display_score}/100"
    console.print(bar)
    console.print()

    def _pts_fmt(earned: int, max_pts: int) -> str:
        if earned == max_pts: return f"[green]{earned}[/green]"
        if earned >= max_pts * 0.6: return f"[yellow]{earned}[/yellow]"
        return f"[red]{earned}[/red]"

    table = Table(show_header=True, box=box.SIMPLE, padding=(0, 2))
    table.add_column("Category", style="dim", width=20)
    table.add_column("Score", width=10)
    table.add_column("Max", width=6, style="dim")
    table.add_column("", width=30)
    table.add_row("Size", _pts_fmt(result.size_score, 20), "20", f"[dim]{result.line_count} lines[/dim]")
    table.add_row("Freshness", _pts_fmt(result.freshness_score, 20), "20", f"[dim]{'never indexed' if result.freshness_days is None else str(result.freshness_days) + ' days ago'}[/dim]")
    table.add_row("Coverage", _pts_fmt(result.coverage_score, result.coverage_max), str(result.coverage_max), f"[dim]{sum(1 for s in result.section_scores if s.present)}/{len(result.section_scores)} sections present[/dim]")
    table.add_row("Precision", _pts_fmt(result.precision_score, 20), "20", f"[dim]{len(result.generic_lines)} generic lines found[/dim]")
    console.print(table)

    console.print("  [bold]Sections[/bold]")
    for ss in result.section_scores:
        icon = "[green]✓[/green]" if ss.present else "[red]✗[/red]"
        pts = f"[dim]+{ss.points_max}pts[/dim]" if ss.present else "[dim]missing[/dim]"
        console.print(f"    {icon}  {ss.name:<30} {pts}")
    console.print()

    if result.tips:
        console.print("  [bold]How to improve[/bold]")
        for i, tip in enumerate(result.tips[:5], 1):
            console.print(f"    [dim]{i}.[/dim] {tip}")
        if len(result.tips) > 5:
            console.print(f"    [dim]... and {len(result.tips) - 5} more[/dim]")
    else:
        console.print("  [green]No improvements needed -- this is a great context file![/green]")

    console.print()
    if score >= 80:
        console.print(f"  [dim]Share it: \"My AGENTS.md scored {display_score}/100 with saar — getsaar.com\"[/dim]")
        console.print()


def cmd_check(
    repo_path: Path = typer.Argument(Path("."), help="Path to the repository.", exists=True, file_okay=False, dir_okay=True, resolve_path=True),
    file: Optional[Path] = typer.Option(None, "--file", "-f", help="Specific context file."),
    max_age: int = typer.Option(14, "--max-age", help="Fail if AGENTS.md is older than this many days (0 = never fail on age).", min=0),
    as_json: bool = typer.Option(False, "--json", help="Output machine-readable JSON for CI parsers."),
) -> None:
    """Check AGENTS.md health for CI. Exits 0 if OK, 1 if issues found.

    Checks: file exists, not stale, required sections present.

    Examples:

      saar check

      saar check --max-age 7

      saar check --json
    """
    from saar.scorer import score_agents_md

    target_file = file or (repo_path / "AGENTS.md")
    if not target_file.exists():
        fallback = repo_path / "CLAUDE.md"
        if not file and fallback.exists():
            target_file = fallback
        else:
            issues = [f"No AGENTS.md found in {repo_path.name} -- run saar extract . to generate one"]
            if as_json:
                print(_json.dumps({"ok": False, "issues": issues, "score": 0}))
            else:
                console.print("\n  [red]saar check failed[/red]")
                for issue in issues:
                    console.print(f"  [yellow]{issue}[/yellow]")
                console.print()
            raise typer.Exit(code=1)

    result = score_agents_md(target_file, repo_path)
    issues: list[str] = []

    if max_age > 0 and result.freshness_days is not None and result.freshness_days > max_age:
        issues.append(f"AGENTS.md is {result.freshness_days} days old (max-age: {max_age}) -- run saar diff . to see what changed")

    _REQUIRED = {"Verification workflow", "Never-do rules", "Stack info"}
    for section in result.missing_sections:
        if section in _REQUIRED:
            issues.append(f"Missing section: {section} -- use `saar add` or re-run `saar extract .`")

    if as_json:
        print(_json.dumps({"ok": len(issues) == 0, "issues": issues, "score": result.total_score, "freshness_days": result.freshness_days, "missing_sections": result.missing_sections}))
    else:
        if issues:
            console.print(f"\n  [red]saar check failed[/red]  [dim]{target_file.name}[/dim]")
            for issue in issues:
                console.print(f"  [yellow]{issue}[/yellow]")
            console.print("\n  [dim]Run [bold]saar stats .[/bold] for a full quality breakdown.[/dim]\n")
        else:
            console.print(f"\n  [green]saar check passed[/green]  [dim]{target_file.name} is up to date[/dim]\n")

    raise typer.Exit(code=1 if issues else 0)


def cmd_lint(
    repo_path: Path = typer.Argument(Path("."), help="Path to the repository.", exists=True, file_okay=False, dir_okay=True, resolve_path=True),
    file: Optional[Path] = typer.Option(None, "--file", "-f", help="Specific context file."),
    as_json: bool = typer.Option(False, "--json", help="Output machine-readable JSON."),
) -> None:
    """Lint your AGENTS.md -- find duplicates, vague rules, and filler.

    Rule codes: SA001 Duplicate, SA002 Orphaned header, SA003 Vague rule,
                SA004 Generic filler, SA005 Emoji

    Examples:

      saar lint

      saar lint --json
    """
    from saar.linter import lint_file

    target_file = file or (repo_path / "AGENTS.md")
    if not target_file.exists():
        fallback = repo_path / "CLAUDE.md"
        if not file and fallback.exists():
            target_file = fallback
        else:
            if as_json:
                print(_json.dumps({"violations": [], "total": 0, "error": "No AGENTS.md found"}))
            else:
                console.print(f"\n  [yellow]No AGENTS.md found in {repo_path.name}[/yellow]\n  Run [bold]saar extract .[/bold] to generate one.\n")
            raise typer.Exit(code=1)

    violations = lint_file(target_file)
    fname = target_file.name

    if as_json:
        print(_json.dumps({"violations": [{"line": v.line, "code": v.code, "message": v.message, "fix": v.fix, "severity": v.severity} for v in violations], "total": len(violations)}))
        raise typer.Exit(code=1 if violations else 0)

    if not violations:
        console.print(f"\n  [green]saar lint passed[/green]  [dim]{fname} — no violations[/dim]\n")
        raise typer.Exit(code=0)

    console.print()
    for v in violations:
        color = "red" if v.severity == "error" else "yellow"
        console.print(f"  [dim]{fname}:{v.line}:1:[/dim]  [{color}]{v.code}[/{color}]  {v.message}")
        if v.fix:
            console.print(f"  [dim]  fix: {v.fix}[/dim]")

    total = len(violations)
    console.print(f"\n  [red]Found {total} {'violation' if total == 1 else 'violations'}.[/red]  [dim]Run [bold]saar stats .[/bold] for a full quality score.[/dim]\n")
    raise typer.Exit(code=1)
