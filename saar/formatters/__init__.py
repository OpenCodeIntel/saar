"""Output formatters for different AI config file formats.

Each formatter takes a CodebaseDNA and returns a string in the
target format. The render() function dispatches to the right one.
"""
from saar.models import CodebaseDNA
from saar.formatters.agents_md import render_agents_md
from saar.formatters.markdown import render_markdown
from saar.formatters.claude_md import render_claude_md
from saar.formatters.cursorrules import render_cursorrules
from saar.formatters.copilot import render_copilot


_RENDERERS = {
    "agents": render_agents_md,
    "markdown": render_markdown,
    "claude": render_claude_md,
    "cursorrules": render_cursorrules,
    "copilot": render_copilot,
}


def render(dna: CodebaseDNA, format: str, budget: int = 100) -> str:
    """Render DNA in the given format, applying a line budget.

    Args:
        dna: Extracted codebase DNA.
        format: Output format key (agents, claude, cursorrules, copilot, markdown).
        budget: Max lines in output. 0 = unlimited (--verbose mode).

    Raises:
        KeyError: Unknown format string.
    """
    from saar.formatters.budget import apply_budget

    renderer = _RENDERERS.get(format)
    if renderer is None:
        raise KeyError(f"Unknown format: {format}. Options: {list(_RENDERERS.keys())}")
    text = renderer(dna)
    # markdown format goes to stdout for human reading -- no budget applied
    if format == "markdown":
        return text
    return apply_budget(text, budget)
