"""Explore commands: init, scan, capture, replay.

  init    -- bootstrap AGENTS.md for a brand-new project before any code
  scan    -- scan any GitHub URL or local path without full extraction
  capture -- record a Claude mistake and prevent it from happening again
  replay  -- review all captured mistakes and what saar learned
"""
from __future__ import annotations

import tempfile
import subprocess
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

console = Console()


def cmd_init(
    repo_path: Path = typer.Argument(Path("."), help="Path to the project directory.", exists=True, file_okay=False, dir_okay=True, resolve_path=True),
    force: bool = typer.Option(False, "--force", help="Overwrite existing AGENTS.md."),
) -> None:
    """Bootstrap a new project's AGENTS.md before you have any code.

    5 quick questions. 60 seconds. Claude will know your project.

    Examples:

      saar init

      saar init ./my-new-saas
    """
    from saar.init_wizard import run_init_interview, render_init_agents_md

    target = repo_path / "AGENTS.md"
    if target.exists() and not force:
        console.print(f"\n  [yellow]AGENTS.md already exists[/yellow] in {repo_path.name}\n  Use [bold]saar extract .[/bold] to update from code.\n  Or use [bold]--force[/bold] to overwrite.\n")
        raise typer.Exit(code=0)

    console.print()
    console.print(f"  [bold]saar init[/bold] — new project setup for [cyan]{repo_path.name}[/cyan]")
    console.print("  [dim]5 quick questions. 60 seconds. Claude will know your project.[/dim]")
    console.print()

    answers = run_init_interview(console)
    if answers is None:
        console.print("[dim]Cancelled.[/dim]")
        raise typer.Exit(code=0)

    content = render_init_agents_md(answers, repo_path.name)
    target.write_text(content, encoding="utf-8")
    line_count = len(content.splitlines())
    console.print()
    console.print(f"  [green]Wrote[/green]  {target}  [dim]({line_count} lines)[/dim]")
    console.print()
    console.print("  [bold]Next steps:[/bold]")
    console.print("  [dim]1.[/dim] Drop this in your repo root — Claude Code + Cursor pick it up automatically")
    console.print("  [dim]2.[/dim] Once you write code: [bold]saar extract .[/bold] to auto-detect your conventions")
    console.print("  [dim]3.[/dim] Add corrections anytime: [bold]saar add 'your rule here'[/bold]")
    console.print()


def cmd_scan(
    target: str = typer.Argument(..., help="GitHub URL or local path to scan."),
    no_interview: bool = typer.Option(True, "--interview/--no-interview", help="Run interview (default: skip)."),
    index: bool = typer.Option(False, "--index", help="Index into OCI after scanning."),
) -> None:
    """Scan any GitHub repo URL without cloning it manually.

    Shows detected stack, auth, exceptions, conventions.

    Examples:

      saar scan https://github.com/tiangolo/fastapi

      saar scan https://github.com/pallets/flask
    """
    is_url = target.startswith("https://") or target.startswith("git@")

    if is_url:
        console.print()
        console.print(f"  [bold]saar scan[/bold] — [cyan]{target}[/cyan]")
        console.print("  [dim]Cloning and scanning...[/dim]")
        console.print()
        with tempfile.TemporaryDirectory(prefix="saar_scan_") as tmpdir:
            tmp_path = Path(tmpdir) / "repo"
            try:
                result = subprocess.run(["git", "clone", "--depth=1", "--quiet", target, str(tmp_path)], capture_output=True, text=True, timeout=60)
                if result.returncode != 0:
                    console.print(f"  [red]Clone failed:[/red] {result.stderr.strip()}")
                    raise typer.Exit(code=1)
            except subprocess.TimeoutExpired:
                console.print("  [red]Clone timed out (60s). Try cloning manually first.[/red]")
                raise typer.Exit(code=1)
            except FileNotFoundError:
                console.print("  [red]git not found. Install git and try again.[/red]")
                raise typer.Exit(code=1)
            _run_scan(tmp_path, index=index)
    else:
        local = Path(target).resolve()
        if not local.exists():
            console.print(f"  [red]Path not found:[/red] {target}")
            raise typer.Exit(code=1)
        console.print()
        console.print(f"  [bold]saar scan[/bold] — [cyan]{local.name}[/cyan]")
        console.print()
        _run_scan(local, index=index)


def _run_scan(repo_path: Path, index: bool = False) -> None:
    """Internal: extract + show stats on a path."""
    from saar.extractor import DNAExtractor
    from saar.scorer import score_agents_md
    from saar.commands.extract import show_detection_summary
    from saar.formatters import render

    dna = DNAExtractor().extract(str(repo_path))
    if dna is None:
        console.print("  [red]Could not analyze this repository.[/red]")
        return

    show_detection_summary(dna, no_interview=True)

    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as tmp:
        tmp.write(render(dna, "agents", budget=100))
        tmp_path = Path(tmp.name)

    result = score_agents_md(tmp_path, repo_path)
    tmp_path.unlink(missing_ok=True)

    score = result.total_score
    color = "green" if score >= 85 else ("yellow" if score >= 60 else "red")
    console.print(f"  Estimated AGENTS.md quality: [{color}][bold]{score}/100[/bold][/{color}]")
    if result.missing_sections:
        console.print(f"  [dim]Missing: {', '.join(result.missing_sections)}[/dim]")
    console.print()
    console.print("  To generate AGENTS.md for your own project: [bold]pip install saar && saar extract .[/bold]")

    if index:
        from saar.commands.extract import run_oci_indexing
        run_oci_indexing(repo_path)


_FIELD_LABELS = {
    "never_do": "Never do", "domain_terms": "Domain vocabulary",
    "off_limits": "Off-limits", "verify_workflow": "Verification",
    "auth_gotchas": "Auth gotcha", "extra_context": "Context",
}
_ALIAS_MAP = {
    "never": "never_do", "never_do": "never_do", "domain": "domain_terms",
    "domain_terms": "domain_terms", "off_limits": "off_limits",
    "off-limits": "off_limits", "verify": "verify_workflow",
    "verify_workflow": "verify_workflow", "auth": "auth_gotchas", "auth_gotchas": "auth_gotchas",
}


def cmd_capture(
    rule: str = typer.Argument(..., help="What Claude got wrong. Plain language."),
    repo_path: Path = typer.Option(Path("."), "--repo", "-r", help="Path to the repository.", exists=True, file_okay=False, dir_okay=True, resolve_path=True),
    category: Optional[str] = typer.Option(None, "--category", "-c", help="Override category: never_do | domain | off_limits | verify | auth"),
    no_regen: bool = typer.Option(False, "--no-regen", help="Skip immediate AGENTS.md regeneration."),
) -> None:
    """Capture a mistake Claude made -- prevents it forever.

    Auto-detects category, regenerates AGENTS.md immediately, records timestamp.

    Examples:

      saar capture "Claude created UserException -- we already have AuthenticationError"

      saar capture "Claude used npm install -- this project uses bun"
    """
    from saar.capture import classify_capture, record_capture
    from saar.interview import append_to_cache

    console.print()
    field_name = _ALIAS_MAP.get(category.lower(), "never_do") if category else classify_capture(rule)
    label = _FIELD_LABELS.get(field_name, "Never do")

    entry, is_duplicate = record_capture(repo_path, rule, field_name)
    append_to_cache(repo_path, field_name, rule)

    if is_duplicate:
        console.print(f"  [yellow]Captured again[/yellow]  [{label}] {rule}  [dim](×{entry.count} total)[/dim]")
        console.print(f"  [dim]Claude has made this mistake {entry.count} times. Rule already in AGENTS.md.[/dim]")
    else:
        console.print(f"  [green]Captured[/green]  [{label}] {rule}")

    if no_regen:
        console.print("  [dim]Skipped regeneration (--no-regen). Run [bold]saar extract . --no-interview[/bold] to update.[/dim]")
        console.print()
        return

    console.print("  [dim]Regenerating AGENTS.md...[/dim]")
    try:
        from saar.extractor import DNAExtractor
        from saar.formatters import render
        from saar.interview import load_cached
        from saar.commands.extract import write_with_markers
        from saar.differ import save_snapshot

        dna = DNAExtractor().extract(str(repo_path))
        if dna is None:
            console.print("  [yellow]Could not regenerate AGENTS.md (extraction failed). Rule was saved.[/yellow]")
            console.print()
            return

        answers = load_cached(repo_path)
        if answers:
            dna.interview = answers

        text = render(dna, "agents", budget=100)
        write_with_markers(repo_path / "AGENTS.md", text, force=False)
        save_snapshot(repo_path, dna)
        console.print()
        console.print("  [bold green]Done.[/bold green]  AGENTS.md updated — Claude won't make this mistake again.")
    except Exception as e:
        console.print(f"  [yellow]Regeneration failed:[/yellow] {e}\n  Rule was saved. Run [bold]saar extract . --no-interview[/bold] manually.")
    console.print()


def cmd_replay(
    repo_path: Path = typer.Argument(Path("."), help="Path to the repository.", exists=True, file_okay=False, dir_okay=True, resolve_path=True),
    all_captures: bool = typer.Option(False, "--all", "-a", help="Show all captures including single-occurrence ones."),
) -> None:
    """Show every mistake Claude has made in this repo and what saar learned.

    Repeat captures surface the most important rules.

    Examples:

      saar replay

      saar replay --all
    """
    from saar.capture import load_captures
    from datetime import datetime, timezone

    entries = load_captures(repo_path)
    console.print()
    console.print(f"  [bold]saar replay[/bold] — [cyan]{repo_path.name}[/cyan]")
    console.print()

    if not entries:
        console.print("  [dim]No captures yet. When Claude gets something wrong, run:[/dim]\n  [bold]saar capture \"what Claude got wrong\"[/bold]")
        console.print()
        return

    sorted_entries = sorted(entries, key=lambda e: (-e.count, e.captured_at))
    shown = sorted_entries if all_captures else ([e for e in sorted_entries if e.count > 1] or sorted_entries[:10])
    repeats = [e for e in shown if e.count > 1]
    singles = [e for e in shown if e.count == 1]

    if repeats:
        console.print("  [bold red]Repeat mistakes[/bold red] — Claude keeps getting these wrong:\n")
        for e in repeats:
            console.print(f"    [red]×{e.count}[/red]  [{_FIELD_LABELS.get(e.category, e.category)}] {e.rule}")
        console.print()

    if singles:
        console.print("  [bold]Captured once:[/bold]\n")
        for e in singles[:8]:
            try:
                dt = datetime.fromisoformat(e.captured_at)
                days = (datetime.now(timezone.utc) - dt).days
                age = "today" if days == 0 else f"{days}d ago"
            except Exception:
                age = ""
            console.print(f"    [dim]·[/dim]  [{_FIELD_LABELS.get(e.category, e.category)}] {e.rule}  [dim]{age}[/dim]")
        if len(singles) > 8 and not all_captures:
            console.print(f"    [dim]... and {len(singles) - 8} more. Run [bold]saar replay --all[/bold] to see everything.[/dim]")
        console.print()

    console.print(f"  [dim]{len(entries)} total captures. {len(repeats)} repeat mistakes. All rules are in AGENTS.md.[/dim]")
    console.print()
