"""saar capture -- learn from every mistake Claude makes.

Unlike `saar add` (which adds a rule and stops), `saar capture`:
  1. Categorizes the mistake automatically
  2. Adds the rule to tribal knowledge
  3. Immediately regenerates AGENTS.md -- no manual re-run needed
  4. Records the capture in a persistent log (.saar/captures.json)
  5. Shows a mini diff so you see exactly what changed

The capture log powers `saar replay`:
  - Shows all captured rules in this repo, with timestamps and counts
  - Surfaces patterns: "Claude has made this mistake 3 times"
  - Becomes the most valuable part of your AGENTS.md over time

Design principle:
  The lowest-friction path from "Claude just got this wrong" to
  "Claude will never get this wrong again" -- one command, done.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

_CAPTURES_FILE = ".saar/captures.json"


# ── Capture categories ────────────────────────────────────────────────────────

# Keywords that suggest each category -- used to auto-classify.
# Order matters: checked top to bottom, first match wins.
_CATEGORY_SIGNALS: list[tuple[str, list[str]]] = [
    ("off_limits", [
        "never touch", "never modify", "do not modify", "frozen",
        "off-limits", "off_limits", "don't change", "hands off",
        "locked", "legacy", "do not edit",
    ]),
    ("domain_terms", [
        " = ", " means ", " refers to ", "is called", "terminology",
        "not a ", "not the ", "workspace", "tenant", "entity",
    ]),
    ("verify_workflow", [
        "pytest", "bun run", "pnpm run", "npm run", "yarn run",
        "make test", "cargo test", "go test", "verify", "run tests",
        "before pushing", "before committing",
    ]),
    ("auth_gotchas", [
        "auth", "authentication", "authorization", "jwt", "token",
        "require_auth", "login", "permission", "credential",
    ]),
    ("never_do", []),  # default -- catches everything else
]


def classify_capture(text: str) -> str:
    """Infer the best InterviewAnswers field for a captured rule."""
    lowered = text.lower()
    for field_name, signals in _CATEGORY_SIGNALS:
        if any(sig in lowered for sig in signals):
            return field_name
    return "never_do"


# ── Capture log ───────────────────────────────────────────────────────────────

@dataclass
class CaptureEntry:
    """A single captured mistake, with metadata."""
    rule: str
    category: str          # InterviewAnswers field name
    captured_at: str       # ISO timestamp
    count: int = 1         # how many times this exact rule was captured

    def to_dict(self) -> dict:
        return {
            "rule": self.rule,
            "category": self.category,
            "captured_at": self.captured_at,
            "count": self.count,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "CaptureEntry":
        return cls(
            rule=d["rule"],
            category=d["category"],
            captured_at=d["captured_at"],
            count=d.get("count", 1),
        )


def load_captures(repo_path: Path) -> list[CaptureEntry]:
    """Load capture log from .saar/captures.json."""
    capture_file = repo_path / _CAPTURES_FILE
    if not capture_file.exists():
        return []
    try:
        data = json.loads(capture_file.read_text(encoding="utf-8"))
        return [CaptureEntry.from_dict(e) for e in data.get("captures", [])]
    except Exception:
        return []


def save_captures(repo_path: Path, entries: list[CaptureEntry]) -> None:
    """Persist capture log to .saar/captures.json."""
    capture_file = repo_path / _CAPTURES_FILE
    capture_file.parent.mkdir(exist_ok=True)
    data = {"captures": [e.to_dict() for e in entries]}
    capture_file.write_text(json.dumps(data, indent=2), encoding="utf-8")


def record_capture(repo_path: Path, rule: str, category: str) -> tuple[CaptureEntry, bool]:
    """Add a capture to the log. Returns (entry, is_duplicate).

    If the exact rule already exists, increments its count instead of adding.
    """
    entries = load_captures(repo_path)
    now = datetime.now(timezone.utc).isoformat()

    # check for exact duplicate (case-insensitive)
    for entry in entries:
        if entry.rule.strip().lower() == rule.strip().lower():
            entry.count += 1
            entry.captured_at = now
            save_captures(repo_path, entries)
            return entry, True

    new_entry = CaptureEntry(rule=rule, category=category, captured_at=now)
    entries.append(new_entry)
    save_captures(repo_path, entries)
    return new_entry, False
