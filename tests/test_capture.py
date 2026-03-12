"""Tests for saar capture and saar replay."""
from pathlib import Path
from datetime import datetime

from saar.capture import (
    classify_capture,
    record_capture,
    load_captures,
    save_captures,
    CaptureEntry,
)


# ── classify_capture ──────────────────────────────────────────────────────────

class TestClassifyCapture:
    def test_never_touch_goes_to_off_limits(self):
        assert classify_capture("never touch billing/ -- frozen") == "off_limits"

    def test_frozen_goes_to_off_limits(self):
        assert classify_capture("billing/ is frozen until Q3") == "off_limits"

    def test_equals_sign_goes_to_domain(self):
        assert classify_capture("Workspace = tenant, not a directory") == "domain_terms"

    def test_means_goes_to_domain(self):
        assert classify_capture("Team means organization in this codebase") == "domain_terms"

    def test_pytest_goes_to_verify(self):
        assert classify_capture("pytest tests/ -v before pushing") == "verify_workflow"

    def test_bun_run_goes_to_verify(self):
        assert classify_capture("bun run test before any commit") == "verify_workflow"

    def test_auth_keyword_goes_to_auth(self):
        assert classify_capture("always use require_auth decorator on endpoints") == "auth_gotchas"

    def test_jwt_goes_to_auth(self):
        assert classify_capture("JWT tokens expire in 1 hour -- don't cache them") == "auth_gotchas"

    def test_generic_rule_goes_to_never_do(self):
        # auth keyword present -> auth_gotchas (correct behaviour for exception rules)
        assert classify_capture("Claude created UserException -- already have AuthenticationError") == "auth_gotchas"

    def test_exception_duplication_no_auth_keyword(self):
        assert classify_capture("Claude created DuplicateError -- we already have ConflictError") == "never_do"

    def test_npm_in_bun_project_goes_to_never_do(self):
        assert classify_capture("Never use npm -- this project uses bun") == "never_do"

    def test_empty_string_defaults_never_do(self):
        assert classify_capture("") == "never_do"

    def test_case_insensitive(self):
        assert classify_capture("NEVER TOUCH core/auth.py") == "off_limits"


# ── record_capture ────────────────────────────────────────────────────────────

class TestRecordCapture:
    def test_first_capture_not_duplicate(self, tmp_path: Path):
        entry, is_dup = record_capture(tmp_path, "Never use npm", "never_do")
        assert not is_dup
        assert entry.count == 1
        assert entry.rule == "Never use npm"
        assert entry.category == "never_do"

    def test_duplicate_increments_count(self, tmp_path: Path):
        record_capture(tmp_path, "Never use npm", "never_do")
        entry, is_dup = record_capture(tmp_path, "Never use npm", "never_do")
        assert is_dup
        assert entry.count == 2

    def test_duplicate_detection_case_insensitive(self, tmp_path: Path):
        record_capture(tmp_path, "Never use npm", "never_do")
        entry, is_dup = record_capture(tmp_path, "never use npm", "never_do")
        assert is_dup
        assert entry.count == 2

    def test_different_rules_not_duplicate(self, tmp_path: Path):
        record_capture(tmp_path, "Never use npm", "never_do")
        entry, is_dup = record_capture(tmp_path, "Never use yarn", "never_do")
        assert not is_dup
        assert entry.count == 1

    def test_multiple_captures_persist(self, tmp_path: Path):
        record_capture(tmp_path, "Rule A", "never_do")
        record_capture(tmp_path, "Rule B", "domain_terms")
        record_capture(tmp_path, "Rule C", "off_limits")
        entries = load_captures(tmp_path)
        assert len(entries) == 3

    def test_captures_file_created(self, tmp_path: Path):
        record_capture(tmp_path, "Test rule", "never_do")
        assert (tmp_path / ".saar" / "captures.json").exists()

    def test_timestamp_is_iso(self, tmp_path: Path):
        entry, _ = record_capture(tmp_path, "test", "never_do")
        # should parse without error
        dt = datetime.fromisoformat(entry.captured_at)
        assert dt.year >= 2025


# ── load/save captures ────────────────────────────────────────────────────────

class TestLoadSaveCaptures:
    def test_load_empty_if_no_file(self, tmp_path: Path):
        entries = load_captures(tmp_path)
        assert entries == []

    def test_roundtrip(self, tmp_path: Path):
        entries = [
            CaptureEntry("Never use npm", "never_do", "2026-01-01T00:00:00+00:00", 3),
            CaptureEntry("Workspace = tenant", "domain_terms", "2026-01-02T00:00:00+00:00", 1),
        ]
        save_captures(tmp_path, entries)
        loaded = load_captures(tmp_path)
        assert len(loaded) == 2
        assert loaded[0].rule == "Never use npm"
        assert loaded[0].count == 3
        assert loaded[1].category == "domain_terms"

    def test_load_handles_corrupt_file(self, tmp_path: Path):
        f = tmp_path / ".saar" / "captures.json"
        f.parent.mkdir(exist_ok=True)
        f.write_text("this is not json", encoding="utf-8")
        entries = load_captures(tmp_path)
        assert entries == []  # graceful fallback


# ── capture entry serialization ───────────────────────────────────────────────

class TestCaptureEntry:
    def test_to_dict_and_from_dict(self):
        e = CaptureEntry("test rule", "never_do", "2026-01-01T00:00:00+00:00", 5)
        d = e.to_dict()
        restored = CaptureEntry.from_dict(d)
        assert restored.rule == e.rule
        assert restored.category == e.category
        assert restored.count == e.count

    def test_from_dict_default_count(self):
        d = {"rule": "test", "category": "never_do", "captured_at": "2026-01-01T00:00:00+00:00"}
        e = CaptureEntry.from_dict(d)
        assert e.count == 1


# ── CLI smoke tests ───────────────────────────────────────────────────────────

class TestCaptureCLI:
    def test_capture_help(self):
        from typer.testing import CliRunner
        from saar.cli import app
        import re
        runner = CliRunner()
        result = runner.invoke(app, ["capture", "--help"])
        assert result.exit_code == 0
        clean = re.sub(r"\x1b\[[0-9;]*m", "", result.output)
        assert "capture" in clean.lower()

    def test_replay_help(self):
        from typer.testing import CliRunner
        from saar.cli import app
        import re
        runner = CliRunner()
        result = runner.invoke(app, ["replay", "--help"])
        assert result.exit_code == 0
        clean = re.sub(r"\x1b\[[0-9;]*m", "", result.output)
        assert "replay" in clean.lower()

    def test_replay_empty_repo(self, tmp_path: Path):
        from typer.testing import CliRunner
        from saar.cli import app
        runner = CliRunner()
        result = runner.invoke(app, ["replay", str(tmp_path)])
        assert result.exit_code == 0
        assert "No captures" in result.output

    def test_capture_no_regen(self, tmp_path: Path):
        """capture --no-regen should save the rule without running extraction."""
        from typer.testing import CliRunner
        from saar.cli import app
        runner = CliRunner()
        result = runner.invoke(app, [
            "capture", "Never use npm -- use bun",
            "--repo", str(tmp_path),
            "--no-regen",
        ])
        assert result.exit_code == 0
        assert "captured" in result.output
        # check capture was saved
        entries = load_captures(tmp_path)
        assert len(entries) == 1
        assert "bun" in entries[0].rule

    def test_capture_category_override(self, tmp_path: Path):
        """--category flag should override auto-detection."""
        from typer.testing import CliRunner
        from saar.cli import app
        runner = CliRunner()
        runner.invoke(app, [
            "capture", "Workspace = tenant",
            "--repo", str(tmp_path),
            "--category", "never_do",
            "--no-regen",
        ])
        entries = load_captures(tmp_path)
        assert entries[0].category == "never_do"

    def test_replay_shows_repeat_mistakes(self, tmp_path: Path):
        """replay should highlight rules captured multiple times."""
        # Manually create captures.json with a repeat
        save_captures(tmp_path, [
            CaptureEntry("Never use npm", "never_do", "2026-01-01T00:00:00+00:00", 3),
            CaptureEntry("Workspace = tenant", "domain_terms", "2026-01-02T00:00:00+00:00", 1),
        ])
        from typer.testing import CliRunner
        from saar.cli import app
        runner = CliRunner()
        result = runner.invoke(app, ["replay", str(tmp_path)])
        assert result.exit_code == 0
        assert "×3" in result.output
        assert "Repeat" in result.output
