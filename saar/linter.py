"""saar lint -- inline quality checker for AGENTS.md.

Like ruff, but for AI context files. Reports specific violations with
line numbers and rule codes so the developer knows exactly what to fix.

Rule codes:
  SA001  Duplicate rule -- exact line (case-insensitive) appears more than once.
         Duplicates waste instruction budget and confuse AI on which instance to follow.

  SA002  Orphaned section header -- a ## heading with no content below it.
         Empty sections look like intent but deliver nothing. AI skips them.

  SA003  Vague rule -- a bullet point under 6 words with no specific instruction.
         "Be careful" tells the AI nothing. Rules must be actionable.

  SA004  Generic filler -- matches known useless patterns (write clean code, etc.)
         These consume instruction budget without changing AI behavior.

  SA005  Emoji in rules -- emojis consume tokens and don't add meaning.
         ETH Zurich: every wasted token in a context file reduces instruction follow.

Design principles:
  - Zero false positives is more important than catching everything.
  - Every violation must be immediately actionable (has a fix hint).
  - Line numbers are always 1-indexed and accurate.
  - Checks are deterministic -- same file always produces same violations.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Re-use generic patterns from scorer for SA004
_GENERIC_PATTERNS = [
    r"write clean code",
    r"follow best practices",
    r"keep it simple",
    r"use meaningful names",
    r"add comments",
    r"handle errors",
    r"write tests",
    r"follow solid principles",
    r"don't repeat yourself",
    r"keep functions small",
]

_EMOJI_RE = re.compile(r"[\U0001F300-\U0001F9FF\U00002702-\U000027B0]")


@dataclass
class LintViolation:
    """A single diagnostic from saar lint."""
    line: int           # 1-indexed line number where violation appears
    code: str           # SA001 .. SA005
    message: str        # human-readable description
    fix: Optional[str]  # what the developer should do
    severity: str = "warning"

    def format(self, filename: str = "AGENTS.md") -> str:
        """Format like ruff: path:line:col: CODE message"""
        fix_hint = f" -- {self.fix}" if self.fix else ""
        return f"{filename}:{self.line}:1: {self.code} {self.message}{fix_hint}"


def lint_agents_md(content: str) -> list[LintViolation]:
    """Run all lint checks on the content of an AGENTS.md file.

    Returns a list of LintViolations, sorted by line number.
    Empty list = no violations.
    """
    violations: list[LintViolation] = []
    lines = content.splitlines()

    violations.extend(_check_sa001_duplicates(lines))
    violations.extend(_check_sa002_orphaned_headers(lines))
    violations.extend(_check_sa003_vague_rules(lines))
    violations.extend(_check_sa004_generic_filler(lines))
    violations.extend(_check_sa005_emojis(lines))

    return sorted(violations, key=lambda v: v.line)


def _check_sa001_duplicates(lines: list[str]) -> list[LintViolation]:
    """SA001: detect exact duplicate lines (case-insensitive, stripped).

    Only checks non-empty, non-header lines -- duplicate blank lines and
    duplicate section headers are different issues.
    """
    violations = []
    seen: dict[str, int] = {}   # normalised content -> first line number (1-indexed)

    for i, raw in enumerate(lines, start=1):
        stripped = raw.strip()
        # skip blank lines, markdown headers, HTML comments, code fences
        if not stripped or stripped.startswith("#") or stripped.startswith("<!--") or stripped.startswith("```"):
            continue

        normalised = stripped.lower()
        if normalised in seen:
            violations.append(LintViolation(
                line=i,
                code="SA001",
                message=f"Duplicate rule: already appears on line {seen[normalised]}",
                fix="Remove the duplicate -- keep the most specific version",
                severity="warning",
            ))
        else:
            seen[normalised] = i

    return violations


def _check_sa002_orphaned_headers(lines: list[str]) -> list[LintViolation]:
    """SA002: section header with no bullet/text content below it.

    A header is orphaned when the next non-blank line is another header
    or the file ends -- meaning the section has no content.
    """
    violations = []
    n = len(lines)

    for i, raw in enumerate(lines):
        stripped = raw.strip()
        if not stripped.startswith("##"):
            continue

        # look ahead for the first non-blank line
        next_content = None
        for j in range(i + 1, n):
            next_stripped = lines[j].strip()
            if next_stripped:
                next_content = next_stripped
                break

        # orphaned if next non-blank is another header or nothing follows
        is_orphaned = (
            next_content is None
            or next_content.startswith("##")
        )

        if is_orphaned:
            header_text = stripped.lstrip("#").strip()
            violations.append(LintViolation(
                line=i + 1,   # 1-indexed
                code="SA002",
                message=f"Orphaned section header: '{header_text}' has no content below it",
                fix="Add rules below this header or remove it",
                severity="warning",
            ))

    return violations


def _check_sa003_vague_rules(lines: list[str]) -> list[LintViolation]:
    """SA003: bullet point with fewer than 6 words -- too vague to be actionable.

    Only checks lines that look like bullet points (start with - or *).
    Code blocks and plain text lines are skipped.
    """
    violations = []
    in_code_block = False

    for i, raw in enumerate(lines, start=1):
        stripped = raw.strip()

        # track code blocks -- don't check inside them
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue

        # only check bullet points
        if not (stripped.startswith("- ") or stripped.startswith("* ")):
            continue

        # strip the bullet marker and count words
        rule_text = stripped[2:].strip()
        word_count = len(rule_text.split())

        # skip label:value convention entries like "Functions: `snake_case`"
        # these are metadata declarations, not actionable rules
        if re.match(r'^[A-Za-z][A-Za-z ]+:\s+', rule_text):
            continue

        # skip file reference entries like "`saar/models.py` (3 dependents)"
        # these are architecture metadata, not rules
        if rule_text.startswith("`") and "/" in rule_text:
            continue

        if word_count < 6 and word_count > 0:
            violations.append(LintViolation(
                line=i,
                code="SA003",
                message=f"Vague rule: '{rule_text}' ({word_count} words) -- not specific enough",
                fix="Expand with context: what, why, and when this rule applies",
                severity="warning",
            ))

    return violations


def _check_sa004_generic_filler(lines: list[str]) -> list[LintViolation]:
    """SA004: line matches a known generic filler pattern.

    These patterns have zero information value and consume instruction budget.
    """
    violations = []
    in_code_block = False

    for i, raw in enumerate(lines, start=1):
        stripped = raw.strip()

        if stripped.startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue

        for pattern in _GENERIC_PATTERNS:
            if re.search(pattern, stripped, re.IGNORECASE):
                violations.append(LintViolation(
                    line=i,
                    code="SA004",
                    message=f"Generic filler: '{stripped[:60]}' -- AI already knows this",
                    fix="Replace with a specific rule: what exactly, and why it matters here",
                    severity="warning",
                ))
                break  # one violation per line max

    return violations


def _check_sa005_emojis(lines: list[str]) -> list[LintViolation]:
    """SA005: emoji character in a rule line.

    Emojis consume tokens without adding meaning. They also break
    deterministic output (different renderers show different glyphs).
    """
    violations = []
    in_code_block = False

    for i, raw in enumerate(lines, start=1):
        stripped = raw.strip()

        if stripped.startswith("```"):
            in_code_block = not in_code_block
            continue
        if in_code_block:
            continue

        if _EMOJI_RE.search(stripped):
            violations.append(LintViolation(
                line=i,
                code="SA005",
                message="Emoji in rule -- wastes instruction budget, remove it",
                fix="Remove the emoji; the text should stand on its own",
                severity="warning",
            ))

    return violations


def lint_file(agents_path: Path) -> list[LintViolation]:
    """Lint an AGENTS.md file by path. Returns violations sorted by line."""
    if not agents_path.exists():
        return []
    content = agents_path.read_text(encoding="utf-8", errors="replace")
    return lint_agents_md(content)
