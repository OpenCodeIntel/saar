"""Token budget enforcement for generated AI context files.

Research context (why this exists):
    ETH Zurich study (5,694 PRs): auto-generated context files >100 lines
    reduced agent task success by 3% and increased cost by 20%.
    LLMs reliably follow ~150 instructions. Claude Code burns ~50 before
    AGENTS.md even loads. That leaves ~100 slots for our content.

Default cap: 100 lines.
--verbose / --budget 0: unlimited.

Design:
    Sections marked as PROTECTED are always included regardless of budget.
    These are human-written or contain the highest-value tribal knowledge.
    Auto-generated bulk content (Project Structure, Circular Deps) is cut first.

    The function works on already-rendered text -- it does NOT re-render.
    It splits on ## section headers, applies priority ordering, and reassembles
    within the budget. Protected sections are appended after the budget note.
"""
from __future__ import annotations

# Lines cap below which we never bother truncating (avoids truncating small repos)
_MIN_LINES_TO_TRUNCATE = 20

# Section header prefixes that are ALWAYS included, never cut.
# These contain human-written tribal knowledge and project-specific rules.
_PROTECTED_SECTION_PREFIXES = (
    "## Tribal Knowledge",
    "## Project-Specific Rules",
    "## How to Verify",
)

# Section header prefixes ranked lowest priority -- cut first when over budget.
# Project Structure is the biggest offender: monorepos generate 100s of lines.
_LOW_PRIORITY_SECTION_PREFIXES = (
    "## Project Structure",
    "## Circular Dependencies",
    "## Preferred imports",
)

_TRUNCATION_NOTE = (
    "\n> [{omitted} lines omitted -- run `saar extract --verbose` for full output]\n"
)


def apply_budget(text: str, max_lines: int) -> str:
    """Apply a line budget to rendered AGENTS.md / CLAUDE.md content.

    Args:
        text: Fully rendered content string (without SAAR markers).
        max_lines: Maximum lines allowed. 0 or negative = unlimited.

    Returns:
        Content string within budget, with a truncation note if lines were cut.
        Protected sections (Tribal Knowledge, Project Rules) are always included.
    """
    if max_lines <= 0:
        return text

    lines = text.splitlines(keepends=True)
    total = len(lines)

    if total <= max_lines or total <= _MIN_LINES_TO_TRUNCATE:
        return text

    # Split into sections. Each section = (header_line_index, lines[])
    sections = _split_into_sections(lines)

    # Separate protected sections out -- they always appear at the end
    protected: list[list[str]] = []
    regular: list[list[str]] = []

    for section_lines in sections:
        header = section_lines[0].strip() if section_lines else ""
        if any(header.startswith(p) for p in _PROTECTED_SECTION_PREFIXES):
            protected.append(section_lines)
        else:
            regular.append(section_lines)

    # Sort regular sections: low-priority ones go to the end (cut first)
    def _priority(section_lines: list[str]) -> int:
        header = section_lines[0].strip() if section_lines else ""
        if any(header.startswith(p) for p in _LOW_PRIORITY_SECTION_PREFIXES):
            return 99  # sort last = cut first
        return 0

    regular.sort(key=_priority)

    # Count lines reserved for protected sections + truncation note
    protected_line_count = sum(len(s) for s in protected) + 2  # +2 for note
    available = max_lines - protected_line_count

    # Fill regular sections within available budget
    kept: list[list[str]] = []
    used = 0
    omitted = 0

    for section_lines in regular:
        section_len = len(section_lines)
        if used + section_len <= available:
            kept.append(section_lines)
            used += section_len
        else:
            omitted += section_len

    # Reassemble: kept sections (in original order) + note + protected
    # Re-sort kept back to original document order
    original_order = {id(s): i for i, s in enumerate(sections)}
    kept.sort(key=lambda s: original_order.get(id(s), 999))

    result_lines: list[str] = []
    for section_lines in kept:
        result_lines.extend(section_lines)

    if omitted > 0:
        note = _TRUNCATION_NOTE.format(omitted=omitted)
        result_lines.append(note)

    for section_lines in protected:
        result_lines.extend(section_lines)

    return "".join(result_lines)


def _split_into_sections(lines: list[str]) -> list[list[str]]:
    """Split a list of lines into sections delimited by ## headers.

    The preamble (lines before the first ## header) is treated as
    its own section with an empty header line.
    """
    sections: list[list[str]] = []
    current: list[str] = []

    for line in lines:
        if line.startswith("## ") and current:
            sections.append(current)
            current = [line]
        else:
            current.append(line)

    if current:
        sections.append(current)

    return sections
