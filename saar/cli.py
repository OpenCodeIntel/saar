"""saar CLI entry point.

Registers all commands from their respective modules.
This file should stay thin -- command logic lives in saar/commands/.

  commands/extract.py  -- extract, and all file-writing helpers
  commands/maintain.py -- add, diff, enrich
  commands/quality.py  -- stats, lint, check
  commands/explore.py  -- init, scan, capture, replay
"""
from __future__ import annotations

from typing import Optional

import typer
from rich.console import Console

from saar import __version__
from saar.commands.extract import OutputFormat, cmd_extract  # noqa: F401 (re-exported)
from saar.commands.extract import (  # noqa: F401 -- re-exported for backward compat
    write_with_markers as _write_with_markers,
    write_cursor_mdc as _write_cursor_mdc,
    detect_ai_tools as _detect_ai_tools,
)
from saar.commands.maintain import cmd_add, cmd_diff, cmd_enrich
from saar.commands.quality import cmd_stats, cmd_check, cmd_lint
from saar.commands.explore import cmd_init, cmd_scan, cmd_capture, cmd_replay

console = Console()

app = typer.Typer(
    name="saar",
    help="Extract the essence of your codebase.",
    no_args_is_help=True,
    invoke_without_command=False,
)


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"saar {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Optional[bool] = typer.Option(
        None, "--version", "-V",
        callback=_version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """saar -- extract the essence of your codebase."""


# ── Register commands ─────────────────────────────────────────────────────────
app.command(name="extract")(cmd_extract)
app.command(name="add")(cmd_add)
app.command(name="diff")(cmd_diff)
app.command(name="enrich")(cmd_enrich)
app.command(name="stats")(cmd_stats)
app.command(name="check")(cmd_check)
app.command(name="lint")(cmd_lint)
app.command(name="init")(cmd_init)
app.command(name="scan")(cmd_scan)
app.command(name="capture")(cmd_capture)
app.command(name="replay")(cmd_replay)
