"""Saar CLI -- extract the essence of your codebase.

Usage:
    saar ./my-repo                      # markdown to stdout
    saar ./my-repo --format claude      # generate CLAUDE.md
    saar ./my-repo --format all         # generate all config files
    saar ./my-repo -o ./output/         # write to directory
    saar ./my-repo --format claude --force  # overwrite existing files
    saar ./my-repo --exclude data vendor    # skip directories
"""
import logging
from enum import Enum
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console

from saar import __version__

app = typer.Typer(
    name="saar",
    help="Extract the essence of your codebase.",
    no_args_is_help=True,
    # allow 'saar .' to work without typing 'saar extract .'
    invoke_without_command=False,
)
console = Console()
logger = logging.getLogger(__name__)


def version_callback(value: bool) -> None:
    if value:
        console.print(f"saar {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None,
        "--version", "-V",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """saar -- extract the essence of your codebase."""


class OutputFormat(str, Enum):
    """Supported output formats."""
    agents = "agents"
    markdown = "markdown"
    claude = "claude"
    cursorrules = "cursorrules"
    copilot = "copilot"
    all = "all"


# Maps output format -> the config file it writes (for inception prevention)
_FORMAT_FILENAMES = {
    OutputFormat.agents: "AGENTS.md",
    OutputFormat.claude: "CLAUDE.md",
    OutputFormat.cursorrules: ".cursorrules",
    OutputFormat.copilot: ".github/copilot-instructions.md",
}


def version_callback_old(value: bool) -> None:
    # moved to app-level @app.callback() -- kept for reference, not used
    pass


@app.command()
def enrich(
    repo_path: Path = typer.Option(
        Path("."),
        "--repo", "-r",
        help="Path to the repository. Defaults to current directory.",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    api_key: Optional[str] = typer.Option(
        None,
        "--api-key",
        help="Anthropic API key. Defaults to ANTHROPIC_API_KEY env var.",
        envvar="ANTHROPIC_API_KEY",
    ),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Show enriched output without saving to cache.",
    ),
) -> None:
    """Use Claude to tighten raw interview answers into precise, actionable rules.

    Reads from .saar/config.json, enriches with AI, saves back.
    Requires ANTHROPIC_API_KEY environment variable.

    Example:

      saar add "don't touch billing it's messy"

      saar enrich

      # billing/ rule is now: "NEVER modify `billing/` -- legacy integration,
      #   no test coverage, frozen until Q3 migration"
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
    pass


@app.command()
def add(
    correction: str = typer.Argument(
        ...,
        help="The rule, correction, or context to add.",
    ),
    repo_path: Path = typer.Option(
        Path("."),
        "--repo", "-r",
        help="Path to the repository. Defaults to current directory.",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    never_do: bool = typer.Option(
        False, "--never-do", "-n",
        help="Add as a never-do rule (default category).",
    ),
    domain: bool = typer.Option(
        False, "--domain", "-d",
        help="Add as a domain vocabulary term.",
    ),
    off_limits: bool = typer.Option(
        False, "--off-limits", "-x",
        help="Add as an off-limits file or module.",
    ),
    verify: bool = typer.Option(
        False, "--verify", "-w",
        help="Set the verification workflow.",
    ),
    context: bool = typer.Option(
        False, "--context", "-c",
        help="Add as additional context.",
    ),
) -> None:
    """Add a single rule or correction to tribal knowledge -- no re-analysis needed.

    Examples:

      saar add "Never use async def with boto3 -- blocks the event loop"

      saar add --domain "Workspace = tenant, not a directory"

      saar add --off-limits "core/auth.py -- clock-skew workaround, do not touch"

      saar add --verify "pytest -x && docker compose up && curl localhost:8000/health"
    """
    from saar.interview import append_to_cache

    # determine target field -- default is never_do (most valuable per Boris Cherny)
    if domain:
        field = "domain_terms"
        label = "Domain vocabulary"
    elif off_limits:
        field = "off_limits"
        label = "Off-limits"
    elif verify:
        field = "verify_workflow"
        label = "Verification workflow"
    elif context:
        field = "extra_context"
        label = "Additional context"
    else:
        # default: never_do -- this is the correction workflow
        field = "never_do"
        label = "Never do"

    append_to_cache(repo_path, field, correction)
    console.print(f"  [green]added[/green] [{label}] {correction}")
    console.print(
        f"  [dim]Saved to {repo_path / '.saar/config.json'}. "
        f"Re-run [bold]saar .[/bold] to regenerate context files.[/dim]"
    )


@app.command()
def diff(
    repo_path: Path = typer.Argument(
        Path("."),
        help="Path to the repository to check. Defaults to current directory.",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
) -> None:
    """Detect when AGENTS.md is stale vs the current codebase.

    Compares the DNA snapshot saved during the last extract against the
    current codebase state. Shows exactly what changed and whether
    AGENTS.md needs to be regenerated.

    Examples:

      saar diff

      saar diff ./my-repo
    """
    from saar.differ import load_snapshot, snapshot_from_dna, diff_snapshots, format_diff_output
    from saar.extractor import DNAExtractor

    # load existing snapshot
    old_snapshot = load_snapshot(repo_path)
    if old_snapshot is None:
        console.print(
            "[yellow]No snapshot found.[/yellow] "
            "Run [bold]saar extract[/bold] first to create a baseline."
        )
        raise typer.Exit(code=0)

    console.print(f"[bold]saar[/bold] checking [cyan]{repo_path.name}[/cyan] for changes...")

    # re-extract current DNA (fast -- same pipeline)
    extractor = DNAExtractor()
    dna = extractor.extract(str(repo_path))
    if dna is None:
        console.print("[red]Could not analyze codebase.[/red]")
        raise typer.Exit(code=1)

    # build current snapshot and diff
    new_snapshot = snapshot_from_dna(dna)
    changes = diff_snapshots(old_snapshot, new_snapshot)
    output = format_diff_output(changes, old_snapshot, repo_path.name)

    console.print(output)

    # exit code 1 if changes found (useful for CI)
    raise typer.Exit(code=1 if changes else 0)


@app.command()
def extract(
    repo_path: Path = typer.Argument(
        ...,
        help="Path to the repository to analyze.",
        exists=True,
        file_okay=False,
        dir_okay=True,
        resolve_path=True,
    ),
    format: OutputFormat = typer.Option(
        OutputFormat.agents,
        "--format", "-f",
        help="Output format. Default: agents (AGENTS.md -- cross-tool standard).",
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output", "-o",
        help="Output directory. Defaults to stdout for markdown, repo root for config files.",
    ),
    exclude: Optional[List[str]] = typer.Option(
        None,
        "--exclude", "-e",
        help="Directories to skip (e.g. --exclude data vendor repos).",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Overwrite existing config files. Without this, existing files are skipped.",
    ),
    no_interview: bool = typer.Option(
        False,
        "--no-interview", "--no-input", "-y",
        help="Skip the guided interview. Uses cached answers if available.",
    ),
    enrich_flag: bool = typer.Option(
        False,
        "--enrich",
        help="After interview, use Claude AI to tighten rules. Requires ANTHROPIC_API_KEY.",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose", "-v",
        help="Show full output without line cap. Also enables debug logs.",
    ),
    budget: int = typer.Option(
        100,
        "--budget",
        help="Max lines in generated file (default 100). 0 = unlimited. --verbose overrides to 0.",
        min=0,
    ),
    index: bool = typer.Option(
        False,
        "--index",
        help="After extraction, index this repo into OCI for AI-powered semantic search via MCP. Requires OCI API key in ~/.saar/config.yaml.",
    ),
) -> None:
    """Analyze a codebase and extract its architectural DNA."""
    log_level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(level=log_level, format="%(message)s")
    # --verbose disables line cap -- full output
    effective_budget = 0 if verbose else budget

    console.print(f"[bold]saar[/bold] analyzing [cyan]{repo_path.name}[/cyan]...")

    # Determine which config files we're writing so we don't read
    # them as "team rules" input (prevents inception loop)
    if format == OutputFormat.all:
        target_formats = [
            OutputFormat.agents,
            OutputFormat.claude,
            OutputFormat.cursorrules,
            OutputFormat.copilot,
        ]
    else:
        target_formats = [format]

    exclude_rules = [
        _FORMAT_FILENAMES[f] for f in target_formats if f in _FORMAT_FILENAMES
    ]

    # -- extract --
    from saar.extractor import DNAExtractor

    extractor = DNAExtractor()
    dna = extractor.extract(
        str(repo_path),
        exclude_dirs=exclude or None,
        exclude_rules_files=exclude_rules or None,
    )

    if dna is None:
        console.print("[red]Extraction failed. Use --verbose for details.[/red]")
        raise typer.Exit(code=1)

    # -- show detection summary and ask for confirmation --
    confirmed = _show_detection_summary(dna, console, no_interview)
    if not confirmed:
        raise typer.Exit(code=0)

    # -- guided interview -- captures tribal knowledge static analysis can't --
    from saar.interview import run_interview, save_cache

    answers = run_interview(
        dna=dna,
        repo_path=repo_path,
        no_interview=no_interview,
        console=console,
    )

    # -- optional AI enrichment -- tightens raw answers into precise rules --
    if answers and enrich_flag:
        from saar.enricher import enrich_answers
        console.print("[dim]Enriching tribal knowledge via Claude...[/dim]")
        enriched, was_enriched = enrich_answers(answers, dna=dna)
        if was_enriched:
            answers = enriched
            save_cache(repo_path, answers)
            console.print("[dim]Enrichment complete.[/dim]")
        else:
            console.print("[yellow]Enrichment skipped -- check ANTHROPIC_API_KEY.[/yellow]")

    if answers:
        dna.interview = answers

    # -- format and output --
    from saar.formatters import render

    for fmt in target_formats:
        text = render(dna, fmt.value, budget=effective_budget)
        target = _resolve_output_path(fmt, output, repo_path)

        if target is None:
            # markdown goes to stdout -- no markers needed
            console.print(text)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            _write_with_markers(target, text, force=force, console=console)

    # save DNA snapshot for saar diff (after writing files)
    try:
        from saar.differ import save_snapshot
        save_snapshot(repo_path, dna)
    except Exception:
        pass  # snapshot failure must never break extract

    # -- optional OCI indexing (--index flag) --
    if index:
        _run_oci_indexing(repo_path, console)

    console.print("[bold green]done[/bold green]")


def _show_detection_summary(dna, console, no_interview: bool) -> bool:
    """Show what saar detected and ask for confirmation.

    Returns True to proceed, False if user says detections are wrong.
    Non-interactive (CI / --no-interview): always returns True, prints compact summary.

    This is the trust-building step -- developers see exactly what saar
    understood about their codebase before any file is written.
    """
    import sys
    import os
    from rich.table import Table

    is_tty = sys.stdin.isatty() and sys.stdout.isatty()
    ci = any(os.environ.get(v) for v in ["CI", "GITHUB_ACTIONS", "GITLAB_CI", "JENKINS_URL"])
    interactive = is_tty and not ci and not no_interview

    console.print()

    rows = []

    # backend
    backend_parts = []
    if dna.detected_framework:
        backend_parts.append(dna.detected_framework.title())
    py_files = dna.language_distribution.get("python", 0)
    if py_files:
        backend_parts.append(f"Python ({py_files} files)")
    if dna.database_patterns.orm_used:
        backend_parts.append(dna.database_patterns.orm_used)
    if dna.test_patterns.framework:
        backend_parts.append(dna.test_patterns.framework)
    if backend_parts:
        rows.append(("Backend", "  ".join(backend_parts)))

    # frontend
    fp = dna.frontend_patterns
    if fp:
        fe_parts = []
        if fp.framework:
            fe_parts.append(fp.framework)
        if fp.language:
            fe_parts.append(fp.language)
        if fp.build_tool:
            fe_parts.append(fp.build_tool)
        if fp.component_library:
            fe_parts.append(fp.component_library)
        if fp.state_management:
            fe_parts.append(fp.state_management)
        if fp.test_framework:
            fe_parts.append(fp.test_framework)
        if fe_parts:
            rows.append(("Frontend", "  ".join(fe_parts)))
        if fp.package_manager:
            rows.append(("Package manager", fp.package_manager))

    # scale
    scale_parts = []
    if dna.total_functions:
        scale_parts.append(f"{dna.total_functions:,} functions")
    total_files = sum(dna.language_distribution.values())
    if total_files:
        scale_parts.append(f"{total_files} files")
    if dna.type_hint_pct:
        scale_parts.append(f"{dna.type_hint_pct:.0f}% typed")
    if scale_parts:
        rows.append(("Scale", "  ".join(scale_parts)))

    # auth patterns -- show actual decorator/middleware names, deduplicated
    if dna.auth_patterns.middleware_used or dna.auth_patterns.auth_decorators:
        auth_parts = []
        seen = set()
        for m in dna.auth_patterns.middleware_used[:2]:
            if m not in seen:
                auth_parts.append(m)
                seen.add(m)
        for d in dna.auth_patterns.auth_decorators[:3]:
            # extract function name from Depends(fn) -> fn
            name = d.split("(")[1].rstrip(")") if "(" in d else d
            if name and name not in seen:
                auth_parts.append(name)
                seen.add(name)
        if auth_parts:
            rows.append(("Auth", "  ".join(auth_parts)))

    # exception classes
    if dna.error_patterns.exception_classes:
        exc = ", ".join(dna.error_patterns.exception_classes[:4])
        if len(dna.error_patterns.exception_classes) > 4:
            exc += f" (+{len(dna.error_patterns.exception_classes) - 4} more)"
        rows.append(("Exceptions", exc))

    # team rules found
    if dna.team_rules_source:
        rows.append(("Team rules", f"found in {dna.team_rules_source}"))

    # print the summary table
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column(style="dim", width=18)
    table.add_column()
    for label, value in rows:
        table.add_row(label, f"[cyan]{value}[/cyan]")

    console.print(table)
    console.print()

    if not interactive:
        return True

    # ask for confirmation in interactive mode
    try:
        import questionary
        confirmed = questionary.confirm("Does this look right?", default=True).ask()
        if confirmed is None:
            # Ctrl+C -- proceed anyway
            return True
        if not confirmed:
            console.print(
                "\n[dim]Use [bold]saar add \"correction here\"[/bold] to fix "
                "anything saar got wrong, then re-run.[/dim]\n"
            )
            return False
        console.print()
        return True
    except ImportError:
        return True


def _resolve_output_path(
    fmt: OutputFormat, output_dir: Optional[Path], repo_path: Path
) -> Optional[Path]:
    """Determine where to write the output file, or None for stdout."""
    filename = _FORMAT_FILENAMES.get(fmt)

    if filename is None:
        if output_dir:
            return output_dir / "saar-dna.md"
        return None

    base = output_dir if output_dir else repo_path
    return base / filename


_MARKER_START = "<!-- SAAR:AUTO-START -->"
_MARKER_END = "<!-- SAAR:AUTO-END -->"


def _write_with_markers(
    target: Path, generated: str, *, force: bool, console: Console
) -> None:
    """Write generated content to target, preserving human edits outside markers.

    On first write: wraps content in SAAR:AUTO-START/END markers.
    On re-run: replaces only what's between the markers. Content the developer
    wrote outside the markers (before or after) is never touched.

    --force bypasses preservation and overwrites the whole file. Use it when
    you want a clean slate with no manual edits preserved.
    """
    wrapped = f"{_MARKER_START}\n{generated.rstrip()}\n{_MARKER_END}\n"

    if not target.exists():
        target.write_text(wrapped, encoding="utf-8")
        console.print(f"  [green]wrote[/green] {target}")
        return

    existing = target.read_text(encoding="utf-8")

    if force:
        # full overwrite -- discard everything including manual edits
        target.write_text(wrapped, encoding="utf-8")
        console.print(f"  [green]overwrote[/green] {target}")
        return

    start_idx = existing.find(_MARKER_START)
    end_idx = existing.find(_MARKER_END)

    if start_idx == -1 or end_idx == -1:
        # No markers -- file exists but was written before markers were introduced
        # (or is purely hand-written). Treat it like first write: prepend auto block.
        target.write_text(wrapped + "\n" + existing, encoding="utf-8")
        console.print(f"  [green]updated[/green] {target} (prepended auto block)")
        return

    # Splice: keep everything before the start marker and after the end marker.
    # Use find() for END to get the first legitimate closing marker (the one that
    # belongs to this auto-block). Then strip any orphaned SAAR markers from the
    # preserved manual content -- these can accumulate from old runs or copy-paste.
    # rfind() would be wrong here: it would swallow manual content sitting between
    # the legitimate END and an orphaned END. (OPE-169)
    before = existing[:start_idx]
    after = existing[end_idx + len(_MARKER_END):]

    # Strip any orphaned SAAR markers from the preserved manual section.
    after = after.replace(_MARKER_START, "").replace(_MARKER_END, "")

    target.write_text(before + wrapped + after, encoding="utf-8")
    console.print(f"  [green]updated[/green] {target} (preserved manual edits)")


def _run_oci_indexing(repo_path: Path, console) -> None:
    """Handle the --index flag: add repo to OCI and trigger indexing.

    Fails gracefully -- a failure here must never prevent saar extract
    from completing successfully. The AGENTS.md has already been written.
    """
    from saar.oci_client import (
        get_api_key, get_base_url,
        detect_git_url, detect_default_branch,
        add_repository, poll_until_indexed,
        save_repo_id, load_repo_id,
        OCIAuthError, OCIAPIError,
    )

    console.print()
    console.print("[bold]OCI indexing[/bold]")

    # -- check for API key --
    api_key = get_api_key()
    if not api_key:
        console.print(
            "  [yellow]No OCI API key found.[/yellow]\n"
            "  1. Go to [link=https://opencodeintel.com/dashboard/api-keys]opencodeintel.com/dashboard/api-keys[/link]\n"
            "  2. Generate a key and save it:\n"
            "     [dim]echo 'oci_api_key: ci_your_key_here' >> ~/.saar/config.yaml[/dim]\n"
            "  3. Re-run with [bold]--index[/bold]"
        )
        return

    base_url = get_base_url()

    # -- detect git URL --
    git_url = detect_git_url(repo_path)
    if not git_url:
        console.print(
            "  [yellow]Could not detect git remote URL.[/yellow]\n"
            "  Make sure this repo has an 'origin' remote:\n"
            "  [dim]git remote add origin https://github.com/you/your-repo.git[/dim]"
        )
        return

    branch = detect_default_branch(repo_path)
    repo_name = repo_path.name

    console.print(f"  repo:   [cyan]{git_url}[/cyan]")
    console.print(f"  branch: [cyan]{branch}[/cyan]")

    try:
        # Check if already indexed -- avoid duplicate repos
        existing_repo_id = load_repo_id(repo_path)
        if existing_repo_id:
            console.print(f"  [dim]Already in OCI (repo_id: {existing_repo_id[:8]}...). Re-indexing...[/dim]")
            repo_id = existing_repo_id
        else:
            # Add repo
            console.print("  Adding to OCI...")
            repo = add_repository(
                name=repo_name,
                git_url=git_url,
                branch=branch,
                api_key=api_key,
                base_url=base_url,
            )
            repo_id = repo.get("id") or repo.get("repo_id")
            if not repo_id:
                raise OCIAPIError("No repo_id returned from API")
            save_repo_id(repo_path, repo_id)
            console.print(f"  [green]Added[/green] (id: {repo_id[:8]}...)")

        # Trigger indexing
        console.print("  Indexing...")

        def on_tick(elapsed: int, status: str) -> None:
            console.print(f"  [dim]  {elapsed}s -- {status}...[/dim]", end="\r")

        result = poll_until_indexed(
            repo_id=repo_id,
            api_key=api_key,
            base_url=base_url,
            on_tick=on_tick,
        )

        functions = result.get("total_functions") or result.get("function_count", 0)
        console.print(f"\n  [green]Indexed[/green] {functions:,} functions")
        console.print(
            "  [dim]Use codeintel:search_code in Claude Desktop / Claude Code "
            "to query this repo via MCP.[/dim]"
        )

    except OCIAuthError as e:
        console.print(f"  [red]Auth error:[/red] {e}")
        console.print("  Get a new key at [link=https://opencodeintel.com/dashboard/api-keys]opencodeintel.com/dashboard/api-keys[/link]")
    except OCIAPIError as e:
        console.print(f"  [yellow]OCI indexing skipped:[/yellow] {e}")
        console.print("  AGENTS.md was still generated successfully.")
    except Exception as e:
        console.print(f"  [yellow]OCI indexing skipped:[/yellow] {e}")
        console.print("  AGENTS.md was still generated successfully.")
