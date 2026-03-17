"""Extract command -- analyze a codebase and write AI context files.

Helpers:
  detect_ai_tools        -- find Cursor/.cursorrules/CLAUDE.md/Copilot in repo
  resolve_output_path    -- map OutputFormat to destination file path
  write_with_markers     -- write generated content preserving manual edits
  write_cursor_mdc       -- write .cursor/rules/*.mdc files (Cursor v2)
  show_detection_summary -- display what saar found, confirm with user
  print_no_files_error   -- helpful error when no supported files found
  run_oci_indexing       -- post-extract OCI index trigger (--index flag)
"""
from __future__ import annotations

import logging
import os
import sys
from enum import Enum
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console

console = Console()

# ── Output format enum (shared across commands) ──────────────────────────────

class OutputFormat(str, Enum):
    agents = "agents"
    markdown = "markdown"
    claude = "claude"
    cursorrules = "cursorrules"
    cursor_mdc = "cursor-mdc"
    copilot = "copilot"
    all = "all"


# Maps format -> filename written (used to prevent inception loop)
FORMAT_FILENAMES: dict[OutputFormat, str] = {
    OutputFormat.agents: "AGENTS.md",
    OutputFormat.claude: "CLAUDE.md",
    OutputFormat.cursorrules: ".cursorrules",
    OutputFormat.copilot: ".github/copilot-instructions.md",
}

_MARKER_START = "<!-- SAAR:AUTO-START -->"
_MARKER_END = "<!-- SAAR:AUTO-END -->"

# ── Helpers ───────────────────────────────────────────────────────────────────

def _display_path(p: Path) -> str:
    """Relative path if inside cwd, otherwise just filename."""
    try:
        return str(p.relative_to(Path.cwd()))
    except ValueError:
        return p.name


def _line_count(text: str) -> int:
    return len([ln for ln in text.splitlines() if ln.strip()])


def detect_ai_tools(repo_path: Path) -> list[OutputFormat]:
    """Detect which AI tools exist in the repo and return their formats.

    Why: users who run Cursor shouldn't need to know about --format cursorrules.
    saar detects what's present and generates those formats automatically (OPE-141).
    """
    detected: list[OutputFormat] = []
    if (repo_path / ".cursor").is_dir():
        detected.append(OutputFormat.cursor_mdc)
    elif (repo_path / ".cursorrules").exists():
        detected.append(OutputFormat.cursorrules)
    if (repo_path / "CLAUDE.md").exists():
        detected.append(OutputFormat.claude)
    if (repo_path / ".github" / "copilot-instructions.md").exists():
        detected.append(OutputFormat.copilot)
    return detected


def resolve_output_path(fmt: OutputFormat, output_dir: Optional[Path], repo_path: Path) -> Optional[Path]:
    """Map OutputFormat to destination file path. None means stdout."""
    filename = FORMAT_FILENAMES.get(fmt)
    if filename is None:
        return (output_dir / "saar-dna.md") if output_dir else None
    return (output_dir or repo_path) / filename

def print_no_files_error(repo_path: Path) -> None:
    """Helpful error when no supported code files found.

    Shows what extensions ARE present instead of just 'extraction failed'.
    """
    extensions_found: dict[str, int] = {}
    for f in repo_path.rglob("*"):
        if f.is_file() and f.suffix and "node_modules" not in f.parts:
            ext = f.suffix.lower()
            extensions_found[ext] = extensions_found.get(ext, 0) + 1

    console.print()
    console.print(f"  [red]No code files found in {repo_path.name}[/red]")
    console.print()
    console.print("  saar analyzes: [cyan].py  .js  .jsx  .ts  .tsx  .sql[/cyan]")
    console.print()

    if extensions_found:
        top = sorted(extensions_found.items(), key=lambda x: -x[1])[:6]
        console.print(f"  Found in {repo_path.name}: [dim]{'  '.join(f'{e} ({n})' for e, n in top)}[/dim]")
        console.print()
        skipped = [d for d in ["dist", "build", "vendor", "venv", ".venv", "node_modules"] if (repo_path / d).is_dir()]
        if skipped:
            console.print(f"  [dim]Note: saar skips {', '.join(skipped)} by default.[/dim]")
            console.print()

    console.print("  [dim]Run with --verbose for full details.[/dim]")
    console.print()


def write_with_markers(target: Path, generated: str, *, force: bool, console=None) -> None:
    """Write generated content preserving human edits outside SAAR markers.

    First write: wraps content in AUTO-START/END markers.
    Re-run: replaces only the auto-generated block, manual edits survive.
    --force: full overwrite, discards manual edits.
    """
    # Accept console kwarg for backward compat with tests and old call sites.
    # Use module-level console when not provided.
    from saar.commands.extract import console as _default_con
    _con = console if console is not None else _default_con
    wrapped = f"{_MARKER_START}\n{generated.rstrip()}\n{_MARKER_END}\n"

    if not target.exists():
        target.write_text(wrapped, encoding="utf-8")
        _con.print(f"  [green]wrote[/green] {_display_path(target)}  [dim]({_line_count(wrapped)} lines)[/dim]")
        return

    existing = target.read_text(encoding="utf-8")

    if force:
        target.write_text(wrapped, encoding="utf-8")
        _con.print(f"  [green]wrote[/green] {_display_path(target)}  [dim]({_line_count(wrapped)} lines)[/dim]")
        return

    start_idx = existing.find(_MARKER_START)
    end_idx = existing.find(_MARKER_END)

    if start_idx == -1 or end_idx == -1:
        _handle_unmarked_file(target, existing, wrapped, force, _con)
        return

    # Splice new auto block between manual content (OPE-169, OPE-179)
    before = existing[:start_idx]
    after = existing[end_idx + len(_MARKER_END):]
    after = after.replace(_MARKER_START, "").replace(_MARKER_END, "").lstrip("\n")
    final = before + wrapped + ("\n" + after if after.strip() else "")
    target.write_text(final, encoding="utf-8")
    _con.print(f"  [green]updated[/green] {_display_path(target)}  [dim]({_line_count(final)} lines, manual edits preserved)[/dim]")


def _handle_unmarked_file(target: Path, existing: str, wrapped: str, force: bool, console=None) -> None:
    """Handle writing to a file that has no saar markers -- may be hand-crafted (OPE-181)."""
    from saar.commands.extract import console as _default_con
    _con = console if console is not None else _default_con
    existing_lines = _line_count(existing)

    if existing_lines >= 5 and not force:
        is_interactive = sys.stdin.isatty() and sys.stdout.isatty()
        is_ci = any(os.environ.get(v) for v in ["CI", "GITHUB_ACTIONS", "GITLAB_CI", "JENKINS_URL", "CIRCLECI", "TRAVIS", "BUILDKITE"])

        if is_interactive and not is_ci:
            try:
                import questionary
                if not questionary.confirm(f"{_display_path(target)} exists ({existing_lines} lines, not generated by saar). Overwrite it?", default=False).ask():
                    _con.print(f"  [yellow]skipped[/yellow] {_display_path(target)}  [dim]Use --force to overwrite.[/dim]")
                    return
            except Exception:
                _con.print(f"  [yellow]skipped[/yellow] {_display_path(target)}  [dim]({existing_lines} lines, not generated by saar). Use --force.[/dim]")
                return
        else:
            _con.print(f"  [yellow]skipped[/yellow] {_display_path(target)}  [dim]({existing_lines} lines, not generated by saar). Use --force.[/dim]")
            return

    target.write_text(wrapped, encoding="utf-8")
    _con.print(f"  [green]wrote[/green] {_display_path(target)}  [dim]({_line_count(wrapped)} lines)[/dim]")

def write_cursor_mdc(dna, base_dir: Path, *, force: bool, console=None) -> None:
    """Write .cursor/rules/*.mdc for Cursor v2. Fully regenerated each run (OPE-143).

    Hand-crafted .mdc files (no alwaysApply: field) are never overwritten (OPE-181).
    """
    from saar.commands.extract import console as _default_con
    _con = console if console is not None else _default_con
    from saar.formatters.cursor_mdc import render_cursor_mdc

    rules_dir = base_dir / ".cursor" / "rules"
    rules_dir.mkdir(parents=True, exist_ok=True)
    mdc_files = render_cursor_mdc(dna)
    if not mdc_files:
        return

    written, skipped = [], []
    for filename, content in mdc_files.items():
        target = rules_dir / filename
        if target.exists() and not force:
            if "alwaysApply:" not in target.read_text(encoding="utf-8"):
                skipped.append(filename)
                continue
        target.write_text(content, encoding="utf-8")
        written.append(filename)

    if written:
        _con.print(f"  [green]wrote[/green] .cursor/rules/  [dim]({', '.join(written)})[/dim]")
    if skipped:
        _con.print(f"  [yellow]skipped[/yellow] .cursor/rules/{skipped[0]}  [dim](hand-crafted — use --force)[/dim]")


def show_detection_summary(dna, no_interview: bool) -> bool:
    """Show detected stack, ask for confirmation in interactive mode.

    Returns True to proceed, False if user says detections are wrong.
    Always returns True in CI / --no-interview mode.
    """
    from rich.table import Table

    is_interactive = sys.stdin.isatty() and sys.stdout.isatty() and not no_interview
    is_ci = any(os.environ.get(v) for v in ["CI", "GITHUB_ACTIONS", "GITLAB_CI", "JENKINS_URL"])

    console.print()
    rows = _build_summary_rows(dna)

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column(style="dim", width=18)
    table.add_column()
    for label, value in rows:
        table.add_row(label, f"[cyan]{value}[/cyan]")
    console.print(table)

    for warning in getattr(dna, "analysis_warnings", []):
        console.print(f"  [yellow]⚠[/yellow]  [dim]{warning}[/dim]")
    console.print()

    if not is_interactive or is_ci:
        return True

    try:
        import questionary
        confirmed = questionary.confirm("Does this look right?", default=True).ask()
        if confirmed is None:
            return True
        if not confirmed:
            console.print("\n[dim]Use [bold]saar add \"correction here\"[/bold] to fix anything saar got wrong, then re-run.[/dim]\n")
            return False
        console.print()
        return True
    except ImportError:
        return True


def _build_summary_rows(dna) -> list[tuple[str, str]]:
    """Build display rows from extracted DNA."""
    rows = []

    backend = [p for p in [
        dna.detected_framework.title() if dna.detected_framework else None,
        f"Python ({dna.language_distribution.get('python', 0)} files)" if dna.language_distribution.get("python") else None,
        dna.database_patterns.orm_used or None,
        dna.test_patterns.framework or None,
    ] if p]
    if backend:
        rows.append(("Backend", "  ".join(backend)))

    fp = dna.frontend_patterns
    if fp:
        fe = [p for p in [fp.framework, fp.language, fp.build_tool, fp.component_library, fp.state_management, fp.test_framework] if p]
        if fe:
            rows.append(("Frontend", "  ".join(fe)))
        if fp.package_manager:
            rows.append(("Package manager", fp.package_manager))

    scale = [p for p in [
        f"{dna.total_functions:,} functions" if dna.total_functions else None,
        f"{sum(dna.language_distribution.values())} files" if dna.language_distribution else None,
        f"{dna.type_hint_pct:.0f}% typed" if dna.type_hint_pct else None,
    ] if p]
    if scale:
        rows.append(("Scale", "  ".join(scale)))

    if dna.auth_patterns.middleware_used or dna.auth_patterns.auth_decorators:
        seen: set[str] = set()
        auth = []
        for m in dna.auth_patterns.middleware_used[:2]:
            if m not in seen:
                auth.append(m); seen.add(m)
        for d in dna.auth_patterns.auth_decorators[:3]:
            name = d.split("(")[1].rstrip(")") if "(" in d else d
            if name and name not in seen:
                auth.append(name); seen.add(name)
        if auth:
            rows.append(("Auth", "  ".join(auth)))

    if dna.error_patterns.exception_classes:
        exc = dna.error_patterns.exception_classes
        text = ", ".join(exc[:4]) + (f" (+{len(exc) - 4} more)" if len(exc) > 4 else "")
        rows.append(("Exceptions", text))

    if dna.team_rules_source:
        rows.append(("Team rules", f"found in {dna.team_rules_source}"))

    return rows

def run_oci_indexing(repo_path: Path) -> None:
    """Handle --index flag: add repo to OCI and trigger indexing.

    Fails gracefully -- AGENTS.md is already written before this runs.
    """
    from saar.oci_client import (
        get_api_key, get_base_url, detect_git_url, detect_default_branch,
        add_repository, poll_until_indexed, save_repo_id, load_repo_id,
        OCIAuthError, OCIAPIError,
    )

    console.print()
    console.print("[bold]OCI indexing[/bold]")

    api_key = get_api_key()
    if not api_key:
        console.print("  [yellow]No OCI API key found.[/yellow]\n  1. Go to [link=https://opencodeintel.com/dashboard/api-keys]opencodeintel.com/dashboard/api-keys[/link]\n  2. Save key: [dim]echo 'oci_api_key: ci_...' >> ~/.saar/config.yaml[/dim]\n  3. Re-run with [bold]--index[/bold]")
        return

    git_url = detect_git_url(repo_path)
    if not git_url:
        console.print("  [yellow]Could not detect git remote URL.[/yellow]\n  Add origin: [dim]git remote add origin https://github.com/you/repo.git[/dim]")
        return

    branch = detect_default_branch(repo_path)
    console.print(f"  repo:   [cyan]{git_url}[/cyan]\n  branch: [cyan]{branch}[/cyan]")

    try:
        repo_id = load_repo_id(repo_path)
        if repo_id:
            console.print(f"  [dim]Already in OCI (repo_id: {repo_id[:8]}...). Re-indexing...[/dim]")
        else:
            console.print("  Adding to OCI...")
            repo = add_repository(name=repo_path.name, git_url=git_url, branch=branch, api_key=api_key, base_url=get_base_url())
            repo_id = repo.get("id") or repo.get("repo_id")
            if not repo_id:
                raise OCIAPIError("No repo_id returned from API")
            save_repo_id(repo_path, repo_id)
            console.print(f"  [green]Added[/green] (id: {repo_id[:8]}...)")

        console.print("  Indexing...")
        result = poll_until_indexed(repo_id=repo_id, api_key=api_key, base_url=get_base_url(),
                                    on_tick=lambda e, s: console.print(f"  [dim]  {e}s -- {s}...[/dim]", end="\r"))
        functions = result.get("total_functions") or result.get("function_count", 0)
        console.print(f"\n  [green]Indexed[/green] {functions:,} functions")
        console.print("  [dim]Use codeintel:search_code in Claude Desktop / Claude Code to query via MCP.[/dim]")

    except OCIAuthError as e:
        console.print(f"  [red]Auth error:[/red] {e}\n  Get a new key at opencodeintel.com/dashboard/api-keys")
    except (OCIAPIError, Exception) as e:
        console.print(f"  [yellow]OCI indexing skipped:[/yellow] {e}\n  AGENTS.md was still generated successfully.")


# ── Main extract command ──────────────────────────────────────────────────────

def cmd_extract(
    repo_path: Path = typer.Argument(Path("."), help="Path to the repository to analyze.", exists=True, file_okay=False, dir_okay=True, resolve_path=True),
    format: OutputFormat = typer.Option(OutputFormat.agents, "--format", "-f", help="Output format."),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Output directory."),
    exclude: Optional[List[str]] = typer.Option(None, "--exclude", "-e", help="Directories to skip."),
    include: Optional[List[str]] = typer.Option(None, "--include", "-i", help="Subdirectories to analyse (monorepo)."),
    force: bool = typer.Option(False, "--force", help="Overwrite existing config files."),
    no_interview: bool = typer.Option(False, "--no-interview", "--no-input", "-y", help="Skip guided interview."),
    enrich_flag: bool = typer.Option(False, "--enrich", help="Use Claude to tighten rules. Requires ANTHROPIC_API_KEY."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Remove 100-line cap, show full output."),
    budget: int = typer.Option(100, "--budget", help="Max lines in generated file (0 = unlimited).", min=0),
    index: bool = typer.Option(False, "--index", help="Index repo into OCI after extraction."),
) -> None:
    """Analyze a codebase and extract its architectural DNA."""
    logging.basicConfig(level=logging.DEBUG if verbose else logging.WARNING, format="%(message)s")
    effective_budget = 0 if verbose else budget

    console.print(f"[bold]saar[/bold] analyzing [cyan]{repo_path.name}[/cyan]...")
    if include:
        console.print(f"  [dim]subset: {' '.join(include)}[/dim]")

    # Build target format list (auto-detect tools present in repo)
    if format == OutputFormat.all:
        target_formats = [OutputFormat.agents, OutputFormat.claude, OutputFormat.cursorrules, OutputFormat.cursor_mdc, OutputFormat.copilot]
    else:
        target_formats = [format]
        if format == OutputFormat.agents:
            for fmt in detect_ai_tools(repo_path):
                if fmt not in target_formats:
                    target_formats.append(fmt)

    exclude_rules = [FORMAT_FILENAMES[f] for f in target_formats if f in FORMAT_FILENAMES]

    from saar.extractor import DNAExtractor
    dna = DNAExtractor().extract(str(repo_path), exclude_dirs=exclude or None, exclude_rules_files=exclude_rules or None, include_paths=include or None)

    if dna is None:
        print_no_files_error(repo_path)
        raise typer.Exit(code=1)

    if not show_detection_summary(dna, no_interview):
        raise typer.Exit(code=0)

    from saar.interview import run_interview, save_cache
    answers = run_interview(dna=dna, repo_path=repo_path, no_interview=no_interview, console=console)

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

    from saar.formatters import render
    for fmt in target_formats:
        if fmt == OutputFormat.cursor_mdc:
            write_cursor_mdc(dna, output or repo_path, force=force)
            continue
        text = render(dna, fmt.value, budget=effective_budget)
        target = resolve_output_path(fmt, output, repo_path)
        if target is None:
            console.print(text)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            write_with_markers(target, text, force=force)

    try:
        from saar.differ import save_snapshot
        save_snapshot(repo_path, dna)
    except Exception:
        pass

    if index:
        run_oci_indexing(repo_path)

    console.print()
    console.print("  [bold green]Claude knows your project.[/bold green]  [dim]Drop AGENTS.md in your repo root — it's picked up automatically.[/dim]")

    # -- post-extract dogfood check: warn on contradictions in tribal knowledge --
    # SA006 catches stale facts like "cli.py is 1514 lines" contradicting "cli.py is 68 lines".
    # We only surface errors (contradictions), not style warnings -- keep the signal clean.
    try:
        from saar.linter import lint_file
        agents_file = (output or repo_path) / "AGENTS.md"
        if agents_file.exists():
            violations = [v for v in lint_file(agents_file) if v.severity == "error"]
            if violations:
                console.print()
                console.print("  [yellow]Stale facts detected in tribal knowledge:[/yellow]")
                for v in violations[:3]:
                    console.print(f"  [dim]  line {v.line}:[/dim] {v.message}")
                    if v.fix:
                        console.print(f"  [dim]  fix: {v.fix}[/dim]")
                console.print("  [dim]Run [bold]saar lint .[/bold] for full details.[/dim]")
    except Exception:
        pass  # lint failure must never break extract
