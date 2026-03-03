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
)
console = Console()
logger = logging.getLogger(__name__)


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


def version_callback(value: bool) -> None:
    if value:
        console.print(f"saar {__version__}")
        raise typer.Exit()


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
    verbose: bool = typer.Option(
        False,
        "--verbose", "-v",
        help="Show detailed analysis progress.",
    ),
    version: Optional[bool] = typer.Option(
        None,
        "--version", "-V",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """Analyze a codebase and extract its architectural DNA."""
    log_level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(level=log_level, format="%(message)s")

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

    # -- format and output --
    from saar.formatters import render

    for fmt in target_formats:
        text = render(dna, fmt.value)
        target = _resolve_output_path(fmt, output, repo_path)

        if target is None:
            # markdown goes to stdout -- no markers needed
            console.print(text)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
            _write_with_markers(target, text, force=force, console=console)

    console.print("[bold green]done[/bold green]")


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

    # Splice: keep everything before the start marker and after the end marker
    before = existing[:start_idx]
    after = existing[end_idx + len(_MARKER_END):]
    target.write_text(before + wrapped + after, encoding="utf-8")
    console.print(f"  [green]updated[/green] {target} (preserved manual edits)")
