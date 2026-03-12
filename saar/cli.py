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
        "  [dim]Saved to .saar/config.json. "
        "Re-run [bold]saar .[/bold] to regenerate context files.[/dim]"
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

    console.print()
    console.print(
        "  [bold green]Claude knows your project.[/bold green]"
        "  [dim]Drop AGENTS.md in your repo root — it's picked up automatically.[/dim]"
    )


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

    # Show relative path if inside cwd, otherwise just filename -- never full absolute path
    def _display_path(p: Path) -> str:
        try:
            return str(p.relative_to(Path.cwd()))
        except ValueError:
            return p.name

    def _line_count(text: str) -> int:
        return len([ln for ln in text.splitlines() if ln.strip()])

    if not target.exists():
        target.write_text(wrapped, encoding="utf-8")
        console.print(
            f"  [green]wrote[/green] {_display_path(target)}"
            f"  [dim]({_line_count(wrapped)} lines)[/dim]"
        )
        return

    existing = target.read_text(encoding="utf-8")

    if force:
        # full overwrite -- discard everything including manual edits
        target.write_text(wrapped, encoding="utf-8")
        console.print(
            f"  [green]wrote[/green] {_display_path(target)}"
            f"  [dim]({_line_count(wrapped)} lines)[/dim]"
        )
        return

    start_idx = existing.find(_MARKER_START)
    end_idx = existing.find(_MARKER_END)

    if start_idx == -1 or end_idx == -1:
        # No saar markers -- file exists but has never been written by saar.
        # This means it's either hand-crafted or written by another tool.
        # We must NOT silently overwrite hand-crafted files. (OPE-181)
        existing_lines = _line_count(existing)

        if existing_lines >= 5 and not force:
            # Substantial hand-crafted file -- protect it.
            # In interactive mode: ask. In non-interactive: skip with clear message.
            import sys
            import os
            is_tty = sys.stdin.isatty() and sys.stdout.isatty()
            ci = any(os.environ.get(v) for v in [
                "CI", "GITHUB_ACTIONS", "GITLAB_CI", "JENKINS_URL",
                "CIRCLECI", "TRAVIS", "BUILDKITE",
            ])
            interactive = is_tty and not ci

            if interactive:
                try:
                    import questionary
                    answer = questionary.confirm(
                        f"{_display_path(target)} exists ({existing_lines} lines, "
                        "not generated by saar). Overwrite it?",
                        default=False,
                    ).ask()
                    if not answer:
                        console.print(
                            f"  [yellow]skipped[/yellow] {_display_path(target)}  "
                            "[dim]Use --force to overwrite.[/dim]"
                        )
                        return
                except Exception:
                    # questionary not available -- fall through to skip
                    console.print(
                        f"  [yellow]skipped[/yellow] {_display_path(target)}  "
                        f"[dim]({existing_lines} lines, not generated by saar). "
                        "Use --force to overwrite.[/dim]"
                    )
                    return
            else:
                # Non-interactive (CI / --no-interview): never overwrite silently.
                console.print(
                    f"  [yellow]skipped[/yellow] {_display_path(target)}  "
                    f"[dim]({existing_lines} lines, not generated by saar). "
                    "Use --force to overwrite.[/dim]"
                )
                return

        # Either force=True, or the file is essentially empty (<5 lines).
        # Safe to write.
        target.write_text(wrapped, encoding="utf-8")
        console.print(
            f"  [green]wrote[/green] {_display_path(target)}"
            f"  [dim]({_line_count(wrapped)} lines)[/dim]"
        )
        return

    # Splice: keep everything before the start marker and after the end marker.
    # Splice: keep before START + new auto block + after END.
    # rfind() would be wrong here: it would swallow manual content sitting between
    # the legitimate END and an orphaned END. (OPE-169)
    before = existing[:start_idx]
    after = existing[end_idx + len(_MARKER_END):]

    # Strip orphaned SAAR markers and leading blank lines. (OPE-179)
    after = after.replace(_MARKER_START, "").replace(_MARKER_END, "")
    after = after.lstrip("\n")

    final = before + wrapped + ("\n" + after if after.strip() else "")
    target.write_text(final, encoding="utf-8")
    console.print(
        f"  [green]updated[/green] {_display_path(target)}"
        f"  [dim]({_line_count(final)} lines, manual edits preserved)[/dim]"
    )


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


# ──────────────────────────────────────────────────────────────────────────────
# saar stats
# ──────────────────────────────────────────────────────────────────────────────

@app.command()
def stats(
    repo_path: Path = typer.Argument(
        Path("."),
        help="Path to the repository. Defaults to current directory.",
        exists=True, file_okay=False, dir_okay=True, resolve_path=True,
    ),
    file: Optional[Path] = typer.Option(
        None, "--file", "-f",
        help="Path to specific context file (default: AGENTS.md in repo root).",
    ),
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
        # try CLAUDE.md as fallback
        fallback = repo_path / "CLAUDE.md"
        if fallback.exists():
            target_file = fallback
        else:
            console.print(
                f"\n  [yellow]No AGENTS.md found in {repo_path.name}[/yellow]\n"
                f"  Run [bold]saar extract .[/bold] to generate one.\n"
            )
            raise typer.Exit(code=1)

    result = score_agents_md(target_file, repo_path)

    # ── Score banner ────────────────────────────────────────────────────────
    score = result.total_score
    grade = result.grade
    project_type = result.project_type

    if score >= 85:
        score_color = "green"
        verdict = "Excellent -- AI will follow this well"
    elif score >= 70:
        score_color = "cyan"
        verdict = "Good -- a few improvements would help"
    elif score >= 50:
        score_color = "yellow"
        verdict = "Needs work -- missing key sections"
    else:
        score_color = "red"
        verdict = "Poor -- AI will likely ignore this"

    # show project type in dim when it's non-default (affects which sections matter)
    type_hint = ""
    if project_type in ("library", "cli"):
        type_hint = f"  [dim]({project_type} — auth/exceptions not required)[/dim]"

    console.print()
    console.print(
        f"  [bold]saar stats[/bold] — [cyan]{target_file.name}[/cyan]  "
        f"[{score_color}][bold]{score}/100[/bold][/{score_color}]  "
        f"[dim]({grade})[/dim]{type_hint}"
    )
    console.print(f"  [dim]{verdict}[/dim]")
    console.print()

    # ── Score bar ───────────────────────────────────────────────────────────
    filled = round(score / 5)   # 20 blocks total
    empty = 20 - filled
    bar_color = score_color
    bar = f"  [{bar_color}]{'█' * filled}[/{bar_color}][dim]{'░' * empty}[/dim]  {score}/100"
    console.print(bar)
    console.print()

    # ── Breakdown table ─────────────────────────────────────────────────────
    table = Table(show_header=True, box=box.SIMPLE, padding=(0, 2))
    table.add_column("Category", style="dim", width=20)
    table.add_column("Score", width=10)
    table.add_column("Max", width=6, style="dim")
    table.add_column("", width=30)

    def _pts_fmt(earned: int, max_pts: int) -> str:
        if earned == max_pts:
            return f"[green]{earned}[/green]"
        if earned >= max_pts * 0.6:
            return f"[yellow]{earned}[/yellow]"
        return f"[red]{earned}[/red]"

    table.add_row(
        "Size",
        _pts_fmt(result.size_score, 20),
        "20",
        f"[dim]{result.line_count} lines[/dim]"
    )
    table.add_row(
        "Freshness",
        _pts_fmt(result.freshness_score, 20),
        "20",
        f"[dim]{'never indexed' if result.freshness_days is None else (str(result.freshness_days) + ' days ago')}[/dim]"
    )
    table.add_row(
        "Coverage",
        _pts_fmt(result.coverage_score, result.coverage_max),
        str(result.coverage_max),
        f"[dim]{sum(1 for s in result.section_scores if s.present)}/{len(result.section_scores)} sections present[/dim]"
    )
    table.add_row(
        "Precision",
        _pts_fmt(result.precision_score, 20),
        "20",
        f"[dim]{len(result.generic_lines)} generic lines found[/dim]"
    )

    console.print(table)

    # ── Section coverage ────────────────────────────────────────────────────
    console.print("  [bold]Sections[/bold]")
    for ss in result.section_scores:
        icon = "[green]✓[/green]" if ss.present else "[red]✗[/red]"
        name = ss.name
        pts = f"[dim]+{ss.points_max}pts[/dim]" if ss.present else "[dim]missing[/dim]"
        console.print(f"    {icon}  {name:<30} {pts}")

    console.print()

    # ── Tips ─────────────────────────────────────────────────────────────────
    if result.tips:
        console.print("  [bold]How to improve[/bold]")
        for i, tip in enumerate(result.tips[:5], 1):
            console.print(f"    [dim]{i}.[/dim] {tip}")
        if len(result.tips) > 5:
            console.print(f"    [dim]... and {len(result.tips) - 5} more[/dim]")
    else:
        console.print("  [green]No improvements needed -- this is a great context file![/green]")

    console.print()

    # Share prompt for high scores
    if score >= 80:
        console.print(
            f"  [dim]Share it: \"My AGENTS.md scored {score}/100 with saar — getsaar.com\"[/dim]"
        )
        console.print()


# ──────────────────────────────────────────────────────────────────────────────
# saar init
# ──────────────────────────────────────────────────────────────────────────────

@app.command(name="init")
def init_cmd(
    repo_path: Path = typer.Argument(
        Path("."),
        help="Path to the new project directory. Defaults to current directory.",
        exists=True, file_okay=False, dir_okay=True, resolve_path=True,
    ),
    force: bool = typer.Option(
        False, "--force",
        help="Overwrite existing AGENTS.md.",
    ),
) -> None:
    """Bootstrap a new project's AGENTS.md before you have any code.

    Perfect for: new repos, hackathons, course projects, or any fresh start.
    Asks 5 quick questions, generates a solid starting point in 60 seconds.

    Examples:

      saar init

      saar init ./my-new-saas
    """
    from saar.init_wizard import run_init_interview, render_init_agents_md

    target = repo_path / "AGENTS.md"

    if target.exists() and not force:
        console.print(
            f"\n  [yellow]AGENTS.md already exists[/yellow] in {repo_path.name}\n"
            f"  Use [bold]saar extract .[/bold] to update it from your code.\n"
            f"  Or use [bold]--force[/bold] to overwrite.\n"
        )
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
    console.print(f"  [green]wrote[/green] {target}  ({line_count} lines)")
    console.print()
    console.print("  [bold]Next steps:[/bold]")
    console.print("  [dim]1.[/dim] Drop this in your repo root — Claude Code + Cursor pick it up automatically")
    console.print("  [dim]2.[/dim] Once you write code: [bold]saar extract .[/bold] to auto-detect your conventions")
    console.print("  [dim]3.[/dim] Add corrections anytime: [bold]saar add 'your rule here'[/bold]")
    console.print()


# ──────────────────────────────────────────────────────────────────────────────
# saar scan
# ──────────────────────────────────────────────────────────────────────────────

@app.command()
def scan(
    target: str = typer.Argument(
        ...,
        help="GitHub URL or local path to scan.",
    ),
    no_interview: bool = typer.Option(
        True, "--interview/--no-interview",
        help="Run interview (default: skip for scan).",
    ),
    index: bool = typer.Option(
        False, "--index",
        help="Index into OCI after scanning.",
    ),
) -> None:
    """Scan any GitHub repo URL without cloning it manually.

    Shows what saar detects — stack, auth, exceptions, conventions.
    Great for exploring open source repos or demoing saar.

    Examples:

      saar scan https://github.com/tiangolo/fastapi

      saar scan https://github.com/pallets/flask

      saar scan https://github.com/yourusername/your-repo
    """
    import tempfile
    import subprocess

    # -- detect if it's a URL or local path --
    is_url = target.startswith("https://") or target.startswith("git@")

    if is_url:
        console.print()
        console.print(f"  [bold]saar scan[/bold] — [cyan]{target}[/cyan]")
        console.print("  [dim]Cloning and scanning...[/dim]")
        console.print()

        with tempfile.TemporaryDirectory(prefix="saar_scan_") as tmpdir:
            tmp_path = Path(tmpdir) / "repo"

            # shallow clone -- fast
            try:
                result = subprocess.run(
                    ["git", "clone", "--depth=1", "--quiet", target, str(tmp_path)],
                    capture_output=True, text=True, timeout=60,
                )
                if result.returncode != 0:
                    console.print(f"  [red]Clone failed:[/red] {result.stderr.strip()}")
                    raise typer.Exit(code=1)
            except subprocess.TimeoutExpired:
                console.print("  [red]Clone timed out (60s). Try cloning manually first.[/red]")
                raise typer.Exit(code=1)
            except FileNotFoundError:
                console.print("  [red]git not found. Install git and try again.[/red]")
                raise typer.Exit(code=1)

            _run_scan(tmp_path, no_interview=True, index=index)
    else:
        local = Path(target).resolve()
        if not local.exists():
            console.print(f"  [red]Path not found:[/red] {target}")
            raise typer.Exit(code=1)
        console.print()
        console.print(f"  [bold]saar scan[/bold] — [cyan]{local.name}[/cyan]")
        console.print()
        _run_scan(local, no_interview=no_interview, index=index)


def _run_scan(repo_path: Path, no_interview: bool = True, index: bool = False) -> None:
    """Internal: run extraction + show stats on a path (used by scan command)."""
    from saar.extractor import DNAExtractor
    from saar.scorer import score_agents_md

    extractor = DNAExtractor()
    dna = extractor.extract(str(repo_path))

    if dna is None:
        console.print("  [red]Could not analyze this repository.[/red]")
        return

    # Show detection summary
    _show_detection_summary(dna, console, no_interview=True)

    # Generate AGENTS.md to a temp file and score it
    import tempfile
    from saar.formatters import render

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(render(dna, "agents", budget=100))
        tmp_path = Path(tmp.name)

    result = score_agents_md(tmp_path, repo_path)
    tmp_path.unlink(missing_ok=True)

    score = result.total_score
    if score >= 85:
        color = "green"
    elif score >= 60:
        color = "yellow"
    else:
        color = "red"

    console.print(
        f"  Estimated AGENTS.md quality: "
        f"[{color}][bold]{score}/100[/bold][/{color}]"
    )

    if result.missing_sections:
        console.print(
            f"  [dim]Missing: {', '.join(result.missing_sections)}[/dim]"
        )

    console.print()
    console.print(
        "  To generate AGENTS.md for your own project: "
        "[bold]pip install saar && saar extract .[/bold]"
    )

    if index:
        _run_oci_indexing(repo_path, console)


# ──────────────────────────────────────────────────────────────────────────────
# saar capture
# ──────────────────────────────────────────────────────────────────────────────

@app.command()
def capture(
    rule: str = typer.Argument(
        ...,
        help="What Claude got wrong. Plain language -- saar figures out the category.",
    ),
    repo_path: Path = typer.Option(
        Path("."),
        "--repo", "-r",
        help="Path to the repository. Defaults to current directory.",
        exists=True, file_okay=False, dir_okay=True, resolve_path=True,
    ),
    category: Optional[str] = typer.Option(
        None, "--category", "-c",
        help="Override auto-detected category: never_do | domain | off_limits | verify | auth",
    ),
    no_regen: bool = typer.Option(
        False, "--no-regen",
        help="Skip immediate AGENTS.md regeneration.",
    ),
) -> None:
    """Capture a mistake Claude made -- prevents it forever.

    Unlike `saar add`, capture:
    - Auto-detects the right category from your words
    - Immediately regenerates AGENTS.md (no manual re-run needed)
    - Records the mistake with timestamp in .saar/captures.json
    - Tracks repeat mistakes: shows when Claude made the same error before

    Examples:

      saar capture "Claude created UserException -- we already have AuthenticationError"

      saar capture "Claude used npm install -- this project uses bun"

      saar capture "Workspace means tenant, not a directory"

      saar capture "never touch billing/ -- legacy Stripe, frozen until Q3"
    """
    from saar.capture import classify_capture, record_capture
    from saar.interview import append_to_cache

    console.print()

    # -- classify ──────────────────────────────────────────────────────────────
    # map user-friendly aliases to InterviewAnswers field names
    _ALIAS_MAP = {
        "never": "never_do",
        "never_do": "never_do",
        "domain": "domain_terms",
        "domain_terms": "domain_terms",
        "off_limits": "off_limits",
        "off-limits": "off_limits",
        "verify": "verify_workflow",
        "verify_workflow": "verify_workflow",
        "auth": "auth_gotchas",
        "auth_gotchas": "auth_gotchas",
    }

    if category:
        field_name = _ALIAS_MAP.get(category.lower(), "never_do")
    else:
        field_name = classify_capture(rule)

    _FIELD_LABELS = {
        "never_do": "Never do",
        "domain_terms": "Domain vocabulary",
        "off_limits": "Off-limits",
        "verify_workflow": "Verification",
        "auth_gotchas": "Auth gotcha",
        "extra_context": "Context",
    }
    label = _FIELD_LABELS.get(field_name, "Never do")

    # -- record in capture log ─────────────────────────────────────────────────
    entry, is_duplicate = record_capture(repo_path, rule, field_name)

    # -- add to tribal knowledge ───────────────────────────────────────────────
    append_to_cache(repo_path, field_name, rule)

    # -- display ───────────────────────────────────────────────────────────────
    if is_duplicate:
        console.print(
            f"  [yellow]captured again[/yellow] [{label}] {rule}"
            f"  [dim](×{entry.count} total)[/dim]"
        )
        console.print(
            f"  [dim]Claude has made this mistake {entry.count} times."
            f" Rule already in AGENTS.md.[/dim]"
        )
    else:
        console.print(f"  [green]captured[/green] [{label}] {rule}")

    # -- immediately regenerate AGENTS.md ──────────────────────────────────────
    if no_regen:
        console.print(
            "  [dim]Skipped regeneration (--no-regen). "
            "Run [bold]saar extract . --no-interview[/bold] to update AGENTS.md.[/dim]"
        )
        console.print()
        return

    console.print("  [dim]Regenerating AGENTS.md...[/dim]")

    try:
        from saar.extractor import DNAExtractor
        from saar.formatters import render
        from saar.interview import load_cached

        extractor = DNAExtractor()
        dna = extractor.extract(str(repo_path))

        if dna is None:
            console.print(
                "  [yellow]Could not regenerate AGENTS.md "
                "(extraction failed). Rule was saved.[/yellow]"
            )
            console.print()
            return

        # load cached answers including the rule we just added
        answers = load_cached(repo_path)
        if answers:
            dna.interview = answers

        from saar.cli import _write_with_markers
        from saar.differ import save_snapshot

        text = render(dna, "agents", budget=100)
        target = repo_path / "AGENTS.md"

        _write_with_markers(target, text, force=False, console=console)
        save_snapshot(repo_path, dna)

        console.print()
        console.print(
            "  [bold green]Done.[/bold green]"
            "  AGENTS.md updated — Claude won't make this mistake again."
        )

    except Exception as e:
        console.print(
            f"  [yellow]Regeneration failed:[/yellow] {e}\n"
            "  Rule was saved. Run [bold]saar extract . --no-interview[/bold] manually."
        )

    console.print()


# ──────────────────────────────────────────────────────────────────────────────
# saar replay
# ──────────────────────────────────────────────────────────────────────────────

@app.command()
def replay(
    repo_path: Path = typer.Argument(
        Path("."),
        help="Path to the repository. Defaults to current directory.",
        exists=True, file_okay=False, dir_okay=True, resolve_path=True,
    ),
    all_captures: bool = typer.Option(
        False, "--all", "-a",
        help="Show all captures including single-occurrence ones.",
    ),
) -> None:
    """Show every mistake Claude has made in this repo -- and what saar learned.

    Surfaces patterns: rules captured multiple times mean Claude keeps
    making the same mistake. Those are your most important rules.

    Examples:

      saar replay

      saar replay --all
    """
    from saar.capture import load_captures
    from datetime import datetime, timezone

    entries = load_captures(repo_path)

    console.print()
    console.print(
        f"  [bold]saar replay[/bold] — [cyan]{repo_path.name}[/cyan]"
    )
    console.print()

    if not entries:
        console.print(
            "  [dim]No captures yet. When Claude gets something wrong, run:[/dim]\n"
            "  [bold]saar capture \"what Claude got wrong\"[/bold]"
        )
        console.print()
        return

    # sort by count desc, then by date desc
    sorted_entries = sorted(entries, key=lambda e: (-e.count, e.captured_at))

    # filter
    shown = sorted_entries if all_captures else [
        e for e in sorted_entries if e.count > 1
    ] or sorted_entries[:10]  # if no repeats, show 10 most recent

    _FIELD_LABELS = {
        "never_do": "Never do",
        "domain_terms": "Domain",
        "off_limits": "Off-limits",
        "verify_workflow": "Verify",
        "auth_gotchas": "Auth",
        "extra_context": "Context",
    }

    # -- repeat offenders first ────────────────────────────────────────────────
    repeats = [e for e in shown if e.count > 1]
    singles = [e for e in shown if e.count == 1]

    if repeats:
        console.print("  [bold red]Repeat mistakes[/bold red] — Claude keeps getting these wrong:\n")
        for e in repeats:
            label = _FIELD_LABELS.get(e.category, e.category)
            console.print(
                f"    [red]×{e.count}[/red]  [{label}] {e.rule}"
            )
        console.print()

    if singles:
        console.print("  [bold]Captured once:[/bold]\n")
        for e in singles[:8]:
            label = _FIELD_LABELS.get(e.category, e.category)
            # format date as relative
            try:
                dt = datetime.fromisoformat(e.captured_at)
                days = (datetime.now(timezone.utc) - dt).days
                age = "today" if days == 0 else f"{days}d ago"
            except Exception:
                age = ""
            console.print(f"    [dim]·[/dim]  [{label}] {e.rule}  [dim]{age}[/dim]")
        if len(singles) > 8 and not all_captures:
            console.print(
                f"    [dim]... and {len(singles) - 8} more. "
                "Run [bold]saar replay --all[/bold] to see everything.[/dim]"
            )
        console.print()

    total = len(entries)
    repeat_count = len(repeats)
    console.print(
        f"  [dim]{total} total captures. "
        f"{repeat_count} repeat mistakes. "
        f"All rules are in AGENTS.md.[/dim]"
    )
    console.print()
