"""Maintenance commands: add, diff, enrich.

These commands keep AGENTS.md accurate over time after the initial extract.
  add    -- append a single rule without re-running analysis
  diff   -- detect what changed since last extract
  enrich -- use Claude to tighten raw tribal knowledge into precise rules
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

console = Console()


def cmd_add(
    correction: str = typer.Argument(..., help="The rule, correction, or context to add."),
    repo_path: Path = typer.Option(Path("."), "--repo", "-r", help="Path to the repository.", exists=True, file_okay=False, dir_okay=True, resolve_path=True),
    never_do: bool = typer.Option(False, "--never-do", "-n", help="Add as a never-do rule (default)."),
    domain: bool = typer.Option(False, "--domain", "-d", help="Add as a domain vocabulary term."),
    off_limits: bool = typer.Option(False, "--off-limits", "-x", help="Add as an off-limits file or module."),
    verify: bool = typer.Option(False, "--verify", "-w", help="Set the verification workflow."),
    context: bool = typer.Option(False, "--context", "-c", help="Add as additional context."),
) -> None:
    """Add a single rule or correction to tribal knowledge -- no re-analysis needed.

    Examples:

      saar add "Never use async def with boto3 -- blocks the event loop"

      saar add --domain "Workspace = tenant, not a directory"

      saar add --off-limits "core/auth.py -- clock-skew workaround, do not touch"

      saar add --verify "pytest -x && docker compose up && curl localhost:8000/health"
    """
    from saar.interview import append_to_cache

    if domain:
        field, label = "domain_terms", "Domain vocabulary"
    elif off_limits:
        field, label = "off_limits", "Off-limits"
    elif verify:
        field, label = "verify_workflow", "Verification workflow"
    elif context:
        field, label = "extra_context", "Additional context"
    else:
        # default: never_do -- most valuable correction type
        field, label = "never_do", "Never do"

    append_to_cache(repo_path, field, correction)
    console.print(f"  [green]added[/green] [{label}] {correction}")
    console.print("  [dim]Saved to .saar/config.json. Re-run [bold]saar .[/bold] to regenerate context files.[/dim]")


def cmd_diff(
    repo_path: Path = typer.Argument(Path("."), help="Path to the repository. Defaults to current directory.", exists=True, file_okay=False, dir_okay=True, resolve_path=True),
) -> None:
    """Detect when AGENTS.md is stale vs the current codebase.

    Examples:

      saar diff

      saar diff ./my-repo
    """
    from saar.differ import load_snapshot, snapshot_from_dna, diff_snapshots, format_diff_output
    from saar.extractor import DNAExtractor

    old_snapshot = load_snapshot(repo_path)
    if old_snapshot is None:
        console.print("[yellow]No snapshot found.[/yellow] Run [bold]saar extract[/bold] first to create a baseline.")
        raise typer.Exit(code=0)

    console.print(f"[bold]saar[/bold] checking [cyan]{repo_path.name}[/cyan] for changes...")

    extractor = DNAExtractor()
    dna = extractor.extract(str(repo_path))
    if dna is None:
        console.print("[red]Could not analyze codebase.[/red]")
        raise typer.Exit(code=1)

    new_snapshot = snapshot_from_dna(dna)
    changes = diff_snapshots(old_snapshot, new_snapshot)
    console.print(format_diff_output(changes, old_snapshot, repo_path.name))
    raise typer.Exit(code=1 if changes else 0)


def cmd_enrich(
    repo_path: Path = typer.Option(Path("."), "--repo", "-r", help="Path to the repository.", exists=True, file_okay=False, dir_okay=True, resolve_path=True),
    api_key: Optional[str] = typer.Option(None, "--api-key", help="Anthropic API key.", envvar="ANTHROPIC_API_KEY"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show enriched output without saving."),
) -> None:
    """Use Claude to tighten raw interview answers into precise, actionable rules.

    Requires ANTHROPIC_API_KEY environment variable.

    Example:

      saar add "don't touch billing it's messy"

      saar enrich

      # Result: "NEVER modify `billing/` -- legacy integration, no test coverage, frozen until Q3"
    """
    from saar.interview import load_cached, save_cache
    from saar.enricher import enrich_answers

    answers = load_cached(repo_path)
    if not answers:
        console.print("[yellow]No cached interview answers found.[/yellow]")
        console.print(f"[dim]Run [bold]saar extract {repo_path}[/bold] first, or use [bold]saar add[/bold] to add rules.[/dim]")
        raise typer.Exit(code=1)

    console.print("[bold]saar[/bold] enriching tribal knowledge via Claude...")
    enriched, was_enriched = enrich_answers(answers, dna=None, api_key=api_key)

    if not was_enriched:
        console.print("[yellow]Enrichment skipped.[/yellow] Check ANTHROPIC_API_KEY is set.")
        raise typer.Exit(code=1)

    if dry_run:
        console.print("\n[bold]Enriched output (dry run -- not saved):[/bold]\n")
        from saar.formatters._tribal import render_tribal_knowledge
        console.print(render_tribal_knowledge(enriched))
        return

    save_cache(repo_path, enriched)
    console.print("[bold green]done[/bold green] -- tribal knowledge enriched and saved.")
    console.print("[dim]Re-run [bold]saar extract .[/bold] --no-interview to regenerate context files.[/dim]")
