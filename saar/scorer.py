"""saar stats -- AGENTS.md quality scorer.

Gives a 0-100 score for your context file quality.
Designed to be shareable: "my AGENTS.md score is 94/100"

Scoring rubric:
  Size (20pts)       50-100 lines = perfect. <20 = too sparse. >150 = too bloated.
  Freshness (20pts)  Based on saar diff snapshot age.
  Coverage (40pts)   Has tribal knowledge, verify workflow, never-do, auth, exceptions.
  Precision (20pts)  No generic filler lines. No emojis. No obvious truisms.

Why these weights:
  Coverage is 40pts because missing sections are the #1 reason AI ignores context files.
  Size is 20pts because ETH Zurich proved long files hurt performance.
  Freshness is 20pts because stale files are actively misleading.
  Precision is 20pts because generic rules waste the instruction budget.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# Generic filler that adds no value -- detected and penalised
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

# Sections that should exist for a complete context file
_EXPECTED_SECTIONS = {
    "verify": (
        ["how to verify", "verification", "verify changes", "run tests", "pytest", "bun run", "npm run test"],
        "Verification workflow",
        8,
    ),
    "never_do": (
        ["never", "never do", "never use", "never modify", "don't", "do not", "forbidden", "avoid"],
        "Never-do rules",
        8,
    ),
    "auth": (
        ["## auth", "auth pattern", "require_auth", "jwt", "@useguards", "authguard",
         "auth middleware", "auth decorator", "authentication:", "auth:"],
        "Auth patterns",
        6,
    ),
    "exceptions": (
        ["exception", "error class", "raise ", "errortype", "httperror"],
        "Exception classes",
        6,
    ),
    "tribal": (
        ["tribal knowledge", "domain", "workspace =", "tenant", "gotcha", "off-limits", "frozen"],
        "Tribal knowledge",
        8,
    ),
    "stack": (
        ["fastapi", "django", "flask", "react", "next.js", "typescript", "python", "bun", "npm", "pnpm"],
        "Stack info",
        4,
    ),
}


@dataclass
class SectionScore:
    name: str
    present: bool
    points_earned: int
    points_max: int
    tip: Optional[str] = None


@dataclass
class StatsResult:
    """Complete quality analysis of an AGENTS.md file."""
    file_path: Path
    total_score: int               # 0–100
    grade: str                     # A+ / A / B / C / D / F
    line_count: int
    size_score: int                # 0–20
    freshness_score: int           # 0–20
    coverage_score: int            # 0–40
    precision_score: int           # 0–20
    section_scores: list[SectionScore] = field(default_factory=list)
    freshness_days: Optional[int] = None
    generic_lines: list[str] = field(default_factory=list)
    missing_sections: list[str] = field(default_factory=list)
    tips: list[str] = field(default_factory=list)


def _grade(score: int) -> str:
    if score >= 95:
        return "A+"
    if score >= 85:
        return "A"
    if score >= 75:
        return "B"
    if score >= 60:
        return "C"
    if score >= 45:
        return "D"
    return "F"


def _score_size(lines: int) -> tuple[int, Optional[str]]:
    """Score based on line count. Optimal: 50-100."""
    if lines == 0:
        return 0, "File is empty"
    if lines < 20:
        return 5, f"Too sparse ({lines} lines) -- run saar extract . to fill it out"
    if lines < 50:
        return 14, f"A bit short ({lines} lines) -- consider adding tribal knowledge"
    if lines <= 100:
        return 20, None  # perfect
    if lines <= 150:
        return 14, f"Getting long ({lines} lines) -- consider trimming project structure section"
    if lines <= 250:
        return 8, f"Too long ({lines} lines) -- ETH Zurich: long files hurt AI performance. Run saar extract . with default budget"
    return 3, f"Way too long ({lines} lines) -- run saar extract . (default 100-line cap)"


def _score_freshness(repo_path: Path) -> tuple[int, Optional[int], Optional[str]]:
    """Score based on snapshot age. Returns (score, days_old, tip)."""
    from saar.differ import load_snapshot
    snap = load_snapshot(repo_path)
    if snap is None:
        return 10, None, "No snapshot found -- run saar extract . to create a baseline for staleness tracking"

    try:
        from datetime import datetime, timezone
        ts = datetime.fromisoformat(snap.extract_timestamp)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        days = (datetime.now(timezone.utc) - ts).days

        if days == 0:
            return 20, days, None
        if days <= 3:
            return 18, days, None
        if days <= 7:
            return 14, days, f"Last generated {days} days ago -- run saar diff . to check for changes"
        if days <= 14:
            return 8, days, f"Last generated {days} days ago -- likely stale. Run saar diff ."
        if days <= 30:
            return 4, days, f"Last generated {days} days ago -- probably outdated. Run saar extract ."
        return 0, days, f"Last generated {days} days ago -- regenerate now with saar extract ."
    except Exception:
        return 10, None, None


def _score_coverage(content: str) -> tuple[int, list[SectionScore], list[str]]:
    """Score based on which sections are present."""
    content_lower = content.lower()
    section_scores = []
    missing = []
    total = 0

    for key, (keywords, label, max_pts) in _EXPECTED_SECTIONS.items():
        present = any(kw in content_lower for kw in keywords)
        earned = max_pts if present else 0
        tip = None if present else f"Add {label.lower()} -- use `saar add` or re-run `saar extract .`"
        section_scores.append(SectionScore(label, present, earned, max_pts, tip))
        total += earned
        if not present:
            missing.append(label)

    return total, section_scores, missing


def _score_precision(content: str, lines: int) -> tuple[int, list[str]]:
    """Penalise generic filler lines and emojis."""
    if lines == 0:
        return 0, []

    generic_found = []
    for pattern in _GENERIC_PATTERNS:
        if re.search(pattern, content, re.IGNORECASE):
            generic_found.append(f'"{pattern}" -- generic, remove it')

    emoji_count = len(re.findall(
        r'[\U0001F300-\U0001F9FF\U00002702-\U000027B0]', content
    ))

    score = 20
    score -= min(len(generic_found) * 4, 16)  # -4 per generic line, max -16
    score -= min(emoji_count * 2, 4)            # -2 per emoji, max -4
    score = max(score, 0)

    return score, generic_found


def score_agents_md(agents_path: Path, repo_path: Optional[Path] = None) -> StatsResult:
    """Score an AGENTS.md (or any context file) and return full analysis."""
    if not agents_path.exists():
        return StatsResult(
            file_path=agents_path,
            total_score=0,
            grade="F",
            line_count=0,
            size_score=0,
            freshness_score=0,
            coverage_score=0,
            precision_score=0,
            tips=["File not found -- run saar extract . to generate it"],
        )

    content = agents_path.read_text(encoding="utf-8", errors="replace")
    lines = len([line for line in content.splitlines() if line.strip()])

    size_score, size_tip = _score_size(lines)

    _repo = repo_path or agents_path.parent
    freshness_score, days_old, freshness_tip = _score_freshness(_repo)

    coverage_score, section_scores, missing = _score_coverage(content)

    precision_score, generic_lines = _score_precision(content, lines)

    total = size_score + freshness_score + coverage_score + precision_score

    tips = []
    if size_tip:
        tips.append(size_tip)
    if freshness_tip:
        tips.append(freshness_tip)
    for ss in section_scores:
        if ss.tip:
            tips.append(ss.tip)
    for gl in generic_lines:
        tips.append(f"Remove generic rule: {gl}")

    return StatsResult(
        file_path=agents_path,
        total_score=total,
        grade=_grade(total),
        line_count=lines,
        size_score=size_score,
        freshness_score=freshness_score,
        coverage_score=coverage_score,
        precision_score=precision_score,
        section_scores=section_scores,
        freshness_days=days_old,
        generic_lines=generic_lines,
        missing_sections=missing,
        tips=tips,
    )
