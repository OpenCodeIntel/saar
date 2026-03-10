"""Saar diff engine -- detect when AGENTS.md is stale vs the current codebase.

The #1 complaint about AI context files: they go stale. Developer writes
AGENTS.md, great for a week, then the codebase changes and the file becomes
misleading or wrong.

How it works:
    1. saar extract saves a compact DNA snapshot to .saar/snapshot.json
    2. saar diff re-runs lightweight detection (fast -- no tree-sitter for all files)
    3. Compares current state against snapshot
    4. Reports what changed in plain language with +/-/~ symbols

Snapshot design:
    Only stores fields that are auto-detectable AND meaningful to diff.
    Human-written tribal knowledge (interview answers) is intentionally excluded --
    we can't know if those are stale, only the developer knows.

Fields tracked:
    - detected_framework
    - package_manager
    - auth_patterns (middleware_used)
    - database orm + rls
    - exception_classes
    - frontend framework + state management
    - verify_workflow
    - total_functions (rough magnitude, not exact)
    - extract_timestamp (when the snapshot was taken)
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from saar.models import CodebaseDNA

logger = logging.getLogger(__name__)

_SNAPSHOT_FILENAME = ".saar/snapshot.json"
_SNAPSHOT_VERSION = 1


# ---------------------------------------------------------------------------
# Snapshot -- compact representation of detectable DNA state
# ---------------------------------------------------------------------------

@dataclass
class DnaSnapshot:
    """Compact snapshot of auto-detectable DNA fields."""
    version: int = _SNAPSHOT_VERSION
    extract_timestamp: str = ""
    detected_framework: Optional[str] = None
    package_manager: Optional[str] = None
    auth_middleware: list = field(default_factory=list)
    database_orm: Optional[str] = None
    database_has_rls: bool = False
    exception_classes: list = field(default_factory=list)
    frontend_framework: Optional[str] = None
    frontend_state_management: Optional[str] = None
    verify_workflow: Optional[str] = None
    # rough magnitude bucket -- not exact to avoid noise from minor refactors
    # "small" <200, "medium" 200-1000, "large" 1000-5000, "xlarge" >5000
    functions_magnitude: str = "unknown"

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "extract_timestamp": self.extract_timestamp,
            "detected_framework": self.detected_framework,
            "package_manager": self.package_manager,
            "auth_middleware": self.auth_middleware,
            "database_orm": self.database_orm,
            "database_has_rls": self.database_has_rls,
            "exception_classes": self.exception_classes,
            "frontend_framework": self.frontend_framework,
            "frontend_state_management": self.frontend_state_management,
            "verify_workflow": self.verify_workflow,
            "functions_magnitude": self.functions_magnitude,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DnaSnapshot":
        return cls(
            version=data.get("version", 1),
            extract_timestamp=data.get("extract_timestamp", ""),
            detected_framework=data.get("detected_framework"),
            package_manager=data.get("package_manager"),
            auth_middleware=data.get("auth_middleware", []),
            database_orm=data.get("database_orm"),
            database_has_rls=data.get("database_has_rls", False),
            exception_classes=data.get("exception_classes", []),
            frontend_framework=data.get("frontend_framework"),
            frontend_state_management=data.get("frontend_state_management"),
            verify_workflow=data.get("verify_workflow"),
            functions_magnitude=data.get("functions_magnitude", "unknown"),
        )


def _magnitude_bucket(total_functions: int) -> str:
    if total_functions < 200:
        return "small"
    if total_functions < 1000:
        return "medium"
    if total_functions < 5000:
        return "large"
    return "xlarge"


def snapshot_from_dna(dna: CodebaseDNA) -> DnaSnapshot:
    """Build a DnaSnapshot from a freshly extracted CodebaseDNA."""
    fp = dna.frontend_patterns

    return DnaSnapshot(
        version=_SNAPSHOT_VERSION,
        extract_timestamp=datetime.now(timezone.utc).isoformat(),
        detected_framework=dna.detected_framework,
        package_manager=fp.package_manager if fp else None,
        auth_middleware=list(dna.auth_patterns.middleware_used),
        database_orm=dna.database_patterns.orm_used,
        database_has_rls=dna.database_patterns.has_rls,
        exception_classes=list(dna.error_patterns.exception_classes),
        frontend_framework=fp.framework if fp else None,
        frontend_state_management=fp.state_management if fp else None,
        verify_workflow=dna.verify_workflow,
        functions_magnitude=_magnitude_bucket(dna.total_functions),
    )


# ---------------------------------------------------------------------------
# Snapshot persistence
# ---------------------------------------------------------------------------

def save_snapshot(repo_path: Path, dna: CodebaseDNA) -> None:
    """Save a DNA snapshot to .saar/snapshot.json after extraction."""
    snap = snapshot_from_dna(dna)
    cache_dir = repo_path / ".saar"
    cache_dir.mkdir(exist_ok=True)
    snap_file = repo_path / _SNAPSHOT_FILENAME
    snap_file.write_text(json.dumps(snap.to_dict(), indent=2), encoding="utf-8")
    logger.debug("Saved DNA snapshot to %s", snap_file)


def load_snapshot(repo_path: Path) -> Optional[DnaSnapshot]:
    """Load the last saved DNA snapshot. Returns None if no snapshot exists."""
    snap_file = repo_path / _SNAPSHOT_FILENAME
    if not snap_file.exists():
        return None
    try:
        data = json.loads(snap_file.read_text(encoding="utf-8"))
        if data.get("version") != _SNAPSHOT_VERSION:
            logger.debug("Snapshot version mismatch, ignoring")
            return None
        return DnaSnapshot.from_dict(data)
    except Exception as e:
        logger.debug("Failed to load snapshot: %s", e)
        return None


# ---------------------------------------------------------------------------
# Diff -- compare snapshot against current DNA
# ---------------------------------------------------------------------------

@dataclass
class DiffChange:
    """A single detected change between snapshot and current DNA."""
    symbol: str      # "+" added, "-" removed, "~" changed
    field: str       # human-readable field name
    old_value: str   # what it was
    new_value: str   # what it is now


def diff_snapshots(old: DnaSnapshot, new: DnaSnapshot) -> list[DiffChange]:
    """Compare two snapshots and return a list of meaningful changes."""
    changes: list[DiffChange] = []

    # -- framework --
    if old.detected_framework != new.detected_framework:
        changes.append(DiffChange(
            symbol="~",
            field="Framework",
            old_value=old.detected_framework or "none",
            new_value=new.detected_framework or "none",
        ))

    # -- package manager --
    if old.package_manager != new.package_manager:
        changes.append(DiffChange(
            symbol="~",
            field="Package manager",
            old_value=old.package_manager or "unknown",
            new_value=new.package_manager or "unknown",
        ))

    # -- auth patterns --
    old_auth = set(old.auth_middleware)
    new_auth = set(new.auth_middleware)
    for added in sorted(new_auth - old_auth):
        changes.append(DiffChange("+", "Auth pattern", "", added))
    for removed in sorted(old_auth - new_auth):
        changes.append(DiffChange("-", "Auth pattern", removed, ""))

    # -- database --
    if old.database_orm != new.database_orm:
        changes.append(DiffChange(
            symbol="~",
            field="Database ORM",
            old_value=old.database_orm or "none",
            new_value=new.database_orm or "none",
        ))
    if old.database_has_rls != new.database_has_rls:
        changes.append(DiffChange(
            symbol="+" if new.database_has_rls else "-",
            field="Row Level Security",
            old_value=str(old.database_has_rls),
            new_value=str(new.database_has_rls),
        ))

    # -- exceptions --
    old_exc = set(old.exception_classes)
    new_exc = set(new.exception_classes)
    for added in sorted(new_exc - old_exc):
        changes.append(DiffChange("+", "Exception class", "", added))
    for removed in sorted(old_exc - new_exc):
        changes.append(DiffChange("-", "Exception class", removed, ""))

    # -- frontend --
    if old.frontend_framework != new.frontend_framework:
        changes.append(DiffChange(
            symbol="~",
            field="Frontend framework",
            old_value=old.frontend_framework or "none",
            new_value=new.frontend_framework or "none",
        ))
    if old.frontend_state_management != new.frontend_state_management:
        changes.append(DiffChange(
            symbol="~",
            field="State management",
            old_value=old.frontend_state_management or "none",
            new_value=new.frontend_state_management or "none",
        ))

    # -- verify workflow --
    if old.verify_workflow != new.verify_workflow:
        if new.verify_workflow and not old.verify_workflow:
            changes.append(DiffChange("+", "Verify workflow", "", new.verify_workflow))
        elif old.verify_workflow and not new.verify_workflow:
            changes.append(DiffChange("-", "Verify workflow", old.verify_workflow, ""))
        else:
            changes.append(DiffChange(
                "~", "Verify workflow",
                old.verify_workflow or "",
                new.verify_workflow or "",
            ))

    # -- scale shift -- only flag if magnitude bucket changed
    if old.functions_magnitude != new.functions_magnitude:
        changes.append(DiffChange(
            symbol="~",
            field="Codebase scale",
            old_value=old.functions_magnitude,
            new_value=new.functions_magnitude,
        ))

    return changes


def format_diff_output(
    changes: list[DiffChange],
    snapshot: DnaSnapshot,
    repo_name: str = "",
) -> str:
    """Format diff results as human-readable terminal output."""
    lines: list[str] = []

    # Header
    if snapshot.extract_timestamp:
        try:
            ts = datetime.fromisoformat(snapshot.extract_timestamp)
            from datetime import timezone as tz
            now = datetime.now(tz.utc)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=tz.utc)
            delta = now - ts
            days = delta.days
            hours = delta.seconds // 3600
            if days > 0:
                age = f"{days} day{'s' if days != 1 else ''} ago"
            elif hours > 0:
                age = f"{hours} hour{'s' if hours != 1 else ''} ago"
            else:
                age = "less than an hour ago"
            lines.append(f"  AGENTS.md last generated: {age}")
        except Exception:
            lines.append(f"  AGENTS.md last generated: {snapshot.extract_timestamp}")
    else:
        lines.append("  AGENTS.md last generated: unknown")

    lines.append("")

    if not changes:
        lines.append("  No changes detected -- AGENTS.md is up to date")
        return "\n".join(lines)

    lines.append(f"  Changed since last extract ({len(changes)} change{'s' if len(changes) != 1 else ''}):")
    for change in changes:
        if change.symbol == "+":
            lines.append(f"  + {change.field} added: {change.new_value}")
        elif change.symbol == "-":
            lines.append(f"  - {change.field} removed: {change.old_value}")
        else:
            lines.append(f"  ~ {change.field} changed: {change.old_value} -> {change.new_value}")

    lines.append("")
    lines.append("  Recommendation: re-run `saar extract` to update AGENTS.md")
    lines.append(f"  ({len(changes)} section{'s' if len(changes) != 1 else ''} would change)")

    return "\n".join(lines)
