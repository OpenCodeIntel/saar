"""Tests for OPE-174: saar diff -- staleness detection.

Tests cover:
- Snapshot creation from DNA
- Snapshot save/load round-trip
- Diff between two snapshots (all change types)
- No false positives when nothing changed
- Output formatting
- CLI integration: no snapshot, clean, with changes
"""
from pathlib import Path
from datetime import datetime, timezone, timedelta
from typer.testing import CliRunner

from saar.differ import (
    DnaSnapshot,
    DiffChange,
    snapshot_from_dna,
    save_snapshot,
    load_snapshot,
    diff_snapshots,
    format_diff_output,
    _magnitude_bucket,
)
from saar.models import (
    CodebaseDNA, AuthPattern, DatabasePattern, ErrorPattern,
    FrontendPattern,
)
from saar.cli import app

runner = CliRunner()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_dna(**kwargs) -> CodebaseDNA:
    return CodebaseDNA(repo_name="test", **kwargs)


def fastapi_dna() -> CodebaseDNA:
    return make_dna(
        detected_framework="fastapi",
        auth_patterns=AuthPattern(middleware_used=["require_auth", "public_auth"]),
        database_patterns=DatabasePattern(orm_used="Supabase", has_rls=True),
        error_patterns=ErrorPattern(exception_classes=["AuthError", "LimitError"]),
        frontend_patterns=FrontendPattern(
            framework="React",
            package_manager="bun",
            state_management="TanStack Query",
        ),
        verify_workflow="pytest tests/ -v && bun run build",
        total_functions=1200,
    )


def old_ts() -> str:
    """Timestamp 6 days ago."""
    ts = datetime.now(timezone.utc) - timedelta(days=6)
    return ts.isoformat()


# ---------------------------------------------------------------------------
# _magnitude_bucket
# ---------------------------------------------------------------------------

class TestMagnitudeBucket:
    def test_small(self):
        assert _magnitude_bucket(0) == "small"
        assert _magnitude_bucket(199) == "small"

    def test_medium(self):
        assert _magnitude_bucket(200) == "medium"
        assert _magnitude_bucket(999) == "medium"

    def test_large(self):
        assert _magnitude_bucket(1000) == "large"
        assert _magnitude_bucket(4999) == "large"

    def test_xlarge(self):
        assert _magnitude_bucket(5000) == "xlarge"


# ---------------------------------------------------------------------------
# snapshot_from_dna
# ---------------------------------------------------------------------------

class TestSnapshotFromDna:

    def test_captures_framework(self):
        snap = snapshot_from_dna(fastapi_dna())
        assert snap.detected_framework == "fastapi"

    def test_captures_package_manager(self):
        snap = snapshot_from_dna(fastapi_dna())
        assert snap.package_manager == "bun"

    def test_captures_auth_middleware(self):
        snap = snapshot_from_dna(fastapi_dna())
        assert "require_auth" in snap.auth_middleware
        assert "public_auth" in snap.auth_middleware

    def test_captures_database_orm(self):
        snap = snapshot_from_dna(fastapi_dna())
        assert snap.database_orm == "Supabase"

    def test_captures_rls(self):
        snap = snapshot_from_dna(fastapi_dna())
        assert snap.database_has_rls is True

    def test_captures_exception_classes(self):
        snap = snapshot_from_dna(fastapi_dna())
        assert "AuthError" in snap.exception_classes
        assert "LimitError" in snap.exception_classes

    def test_captures_verify_workflow(self):
        snap = snapshot_from_dna(fastapi_dna())
        assert "pytest" in snap.verify_workflow

    def test_captures_functions_magnitude(self):
        snap = snapshot_from_dna(fastapi_dna())
        assert snap.functions_magnitude == "large"  # 1200 functions

    def test_timestamp_is_set(self):
        snap = snapshot_from_dna(fastapi_dna())
        assert snap.extract_timestamp != ""
        # must be parseable
        datetime.fromisoformat(snap.extract_timestamp)

    def test_empty_dna_does_not_crash(self):
        snap = snapshot_from_dna(make_dna())
        assert snap.detected_framework is None
        assert snap.auth_middleware == []


# ---------------------------------------------------------------------------
# save/load round-trip
# ---------------------------------------------------------------------------

class TestSnapshotPersistence:

    def test_save_creates_file(self, tmp_path: Path):
        dna = fastapi_dna()
        save_snapshot(tmp_path, dna)
        assert (tmp_path / ".saar" / "snapshot.json").exists()

    def test_load_returns_none_when_no_file(self, tmp_path: Path):
        result = load_snapshot(tmp_path)
        assert result is None

    def test_round_trip_preserves_all_fields(self, tmp_path: Path):
        dna = fastapi_dna()
        save_snapshot(tmp_path, dna)
        loaded = load_snapshot(tmp_path)
        assert loaded is not None
        assert loaded.detected_framework == "fastapi"
        assert loaded.package_manager == "bun"
        assert "require_auth" in loaded.auth_middleware
        assert loaded.database_orm == "Supabase"
        assert loaded.database_has_rls is True
        assert "AuthError" in loaded.exception_classes
        assert loaded.functions_magnitude == "large"

    def test_load_corrupt_file_returns_none(self, tmp_path: Path):
        saar_dir = tmp_path / ".saar"
        saar_dir.mkdir()
        (saar_dir / "snapshot.json").write_text("not json")
        result = load_snapshot(tmp_path)
        assert result is None

    def test_save_overwrites_existing(self, tmp_path: Path):
        dna1 = make_dna(detected_framework="flask")
        save_snapshot(tmp_path, dna1)
        dna2 = make_dna(detected_framework="fastapi")
        save_snapshot(tmp_path, dna2)
        loaded = load_snapshot(tmp_path)
        assert loaded.detected_framework == "fastapi"


# ---------------------------------------------------------------------------
# diff_snapshots -- change detection
# ---------------------------------------------------------------------------

class TestDiffSnapshots:

    def _snap(self, **kwargs) -> DnaSnapshot:
        base = snapshot_from_dna(fastapi_dna())
        for k, v in kwargs.items():
            setattr(base, k, v)
        return base

    def test_identical_snapshots_produce_no_changes(self):
        snap = self._snap()
        changes = diff_snapshots(snap, snap)
        assert changes == []

    def test_framework_change_detected(self):
        old = self._snap(detected_framework="flask")
        new = self._snap(detected_framework="fastapi")
        changes = diff_snapshots(old, new)
        assert any(c.field == "Framework" and c.symbol == "~" for c in changes)

    def test_package_manager_change_detected(self):
        old = self._snap(package_manager="npm")
        new = self._snap(package_manager="bun")
        changes = diff_snapshots(old, new)
        assert any(c.field == "Package manager" for c in changes)

    def test_new_auth_pattern_detected(self):
        old = self._snap(auth_middleware=["require_auth"])
        new = self._snap(auth_middleware=["require_auth", "admin_auth"])
        changes = diff_snapshots(old, new)
        assert any(c.symbol == "+" and c.field == "Auth pattern" and c.new_value == "admin_auth" for c in changes)

    def test_removed_auth_pattern_detected(self):
        old = self._snap(auth_middleware=["require_auth", "public_auth"])
        new = self._snap(auth_middleware=["require_auth"])
        changes = diff_snapshots(old, new)
        assert any(c.symbol == "-" and c.field == "Auth pattern" and c.old_value == "public_auth" for c in changes)

    def test_new_exception_class_detected(self):
        old = self._snap(exception_classes=["AuthError"])
        new = self._snap(exception_classes=["AuthError", "RateLimitError"])
        changes = diff_snapshots(old, new)
        assert any(c.symbol == "+" and "RateLimitError" in c.new_value for c in changes)

    def test_removed_exception_class_detected(self):
        old = self._snap(exception_classes=["AuthError", "LegacyError"])
        new = self._snap(exception_classes=["AuthError"])
        changes = diff_snapshots(old, new)
        assert any(c.symbol == "-" and "LegacyError" in c.old_value for c in changes)

    def test_rls_enabled_detected(self):
        old = self._snap(database_has_rls=False)
        new = self._snap(database_has_rls=True)
        changes = diff_snapshots(old, new)
        assert any(c.field == "Row Level Security" and c.symbol == "+" for c in changes)

    def test_rls_disabled_detected(self):
        old = self._snap(database_has_rls=True)
        new = self._snap(database_has_rls=False)
        changes = diff_snapshots(old, new)
        assert any(c.field == "Row Level Security" and c.symbol == "-" for c in changes)

    def test_verify_workflow_added(self):
        old = self._snap(verify_workflow=None)
        new = self._snap(verify_workflow="pytest tests/ -v")
        changes = diff_snapshots(old, new)
        assert any(c.symbol == "+" and c.field == "Verify workflow" for c in changes)

    def test_verify_workflow_changed(self):
        old = self._snap(verify_workflow="pytest")
        new = self._snap(verify_workflow="pytest tests/ -v && docker up")
        changes = diff_snapshots(old, new)
        assert any(c.symbol == "~" and c.field == "Verify workflow" for c in changes)

    def test_scale_change_detected(self):
        old = self._snap(functions_magnitude="small")
        new = self._snap(functions_magnitude="large")
        changes = diff_snapshots(old, new)
        assert any(c.field == "Codebase scale" for c in changes)

    def test_multiple_changes_all_returned(self):
        old = self._snap(detected_framework="flask", package_manager="npm")
        new = self._snap(detected_framework="fastapi", package_manager="bun")
        changes = diff_snapshots(old, new)
        assert len(changes) >= 2

    def test_returns_list_of_diff_changes(self):
        old = self._snap(detected_framework="flask")
        new = self._snap(detected_framework="fastapi")
        changes = diff_snapshots(old, new)
        assert all(isinstance(c, DiffChange) for c in changes)


# ---------------------------------------------------------------------------
# format_diff_output
# ---------------------------------------------------------------------------

class TestFormatDiffOutput:

    def _snap_with_old_ts(self) -> DnaSnapshot:
        snap = snapshot_from_dna(fastapi_dna())
        snap.extract_timestamp = old_ts()
        return snap

    def test_no_changes_says_up_to_date(self):
        snap = self._snap_with_old_ts()
        output = format_diff_output([], snap)
        assert "up to date" in output.lower()

    def test_shows_age_in_days(self):
        snap = self._snap_with_old_ts()
        output = format_diff_output([], snap)
        assert "6 day" in output or "days" in output

    def test_shows_change_count(self):
        changes = [
            DiffChange("+", "Auth pattern", "", "admin_auth"),
            DiffChange("~", "Framework", "flask", "fastapi"),
        ]
        snap = self._snap_with_old_ts()
        output = format_diff_output(changes, snap)
        assert "2 change" in output

    def test_plus_symbol_for_additions(self):
        changes = [DiffChange("+", "Auth pattern", "", "admin_auth")]
        output = format_diff_output(changes, snapshot_from_dna(fastapi_dna()))
        assert "+ Auth pattern" in output
        assert "admin_auth" in output

    def test_minus_symbol_for_removals(self):
        changes = [DiffChange("-", "Exception class", "LegacyError", "")]
        output = format_diff_output(changes, snapshot_from_dna(fastapi_dna()))
        assert "- Exception class" in output
        assert "LegacyError" in output

    def test_tilde_symbol_for_changes(self):
        changes = [DiffChange("~", "Framework", "flask", "fastapi")]
        output = format_diff_output(changes, snapshot_from_dna(fastapi_dna()))
        assert "~ Framework" in output
        assert "flask" in output
        assert "fastapi" in output

    def test_recommendation_to_rerun_shown_when_changes(self):
        changes = [DiffChange("~", "Framework", "flask", "fastapi")]
        output = format_diff_output(changes, snapshot_from_dna(fastapi_dna()))
        assert "saar extract" in output


# ---------------------------------------------------------------------------
# CLI integration tests
# ---------------------------------------------------------------------------

class TestDiffCLI:

    def test_no_snapshot_shows_helpful_message(self, tmp_path: Path):
        """With no snapshot, diff must tell user to run extract first."""
        # Create minimal repo
        (tmp_path / "main.py").write_text("def hello(): pass\n")
        result = runner.invoke(app, ["diff", str(tmp_path)])
        assert result.exit_code == 0
        assert "saar extract" in result.output

    def test_no_changes_exits_zero(self, tmp_repo: Path, tmp_path: Path):
        """After extract, diff on same repo should exit 0 (no changes)."""
        output_dir = tmp_path / "out"
        output_dir.mkdir()
        # First extract to create snapshot
        runner.invoke(app, [
            "extract", str(tmp_repo), "--no-interview",
            "--format", "agents", "-o", str(output_dir)
        ])
        # Diff same repo -- should be clean
        result = runner.invoke(app, ["diff", str(tmp_repo)])
        assert result.exit_code == 0
        assert "up to date" in result.output.lower() or "no changes" in result.output.lower()

    def test_extract_creates_snapshot_file(self, tmp_repo: Path, tmp_path: Path):
        """saar extract must create .saar/snapshot.json in the repo."""
        output_dir = tmp_path / "out"
        output_dir.mkdir()
        runner.invoke(app, [
            "extract", str(tmp_repo), "--no-interview",
            "--format", "agents", "-o", str(output_dir)
        ])
        assert (tmp_repo / ".saar" / "snapshot.json").exists()

    def test_diff_help_available(self):
        result = runner.invoke(app, ["diff", "--help"])
        assert result.exit_code == 0
        assert "stale" in result.output.lower() or "diff" in result.output.lower() or "detect" in result.output.lower()
