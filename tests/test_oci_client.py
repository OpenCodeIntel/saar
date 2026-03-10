"""Tests for OPE-173: saar extract --index flag and OCI client.

Testing strategy:
- oci_client.py: pure unit tests -- no real HTTP, mock urllib
- CLI: test --index with mocked OCI client
- Config: read/write ~/.saar/config.yaml round-trip
- Error handling: every failure mode must degrade gracefully
  (extract succeeds even when OCI fails)
"""
import json
from pathlib import Path
from unittest.mock import patch, MagicMock
from typer.testing import CliRunner

from saar.oci_client import (
    load_oci_config,
    save_oci_config,
    get_api_key,
    get_base_url,
    save_repo_id,
    load_repo_id,
    detect_git_url,
    detect_default_branch,
)
from saar.cli import app

runner = CliRunner()

_DEFAULT_BASE = "https://api.opencodeintel.com"


# ---------------------------------------------------------------------------
# Config read/write
# ---------------------------------------------------------------------------

class TestOCIConfig:

    def test_load_config_missing_file_returns_empty(self, tmp_path: Path):
        config_path = tmp_path / ".saar" / "config.yaml"
        with patch("saar.oci_client._CONFIG_PATH", config_path):
            result = load_oci_config()
        assert result == {}

    def test_save_and_load_round_trip(self, tmp_path: Path):
        config_path = tmp_path / ".saar" / "config.yaml"
        with patch("saar.oci_client._CONFIG_PATH", config_path):
            save_oci_config("ci_test_key_123", "https://api.example.com")
            result = load_oci_config()
        assert result["oci_api_key"] == "ci_test_key_123"
        assert result["oci_base_url"] == "https://api.example.com"

    def test_get_api_key_returns_none_when_missing(self, tmp_path: Path):
        config_path = tmp_path / ".saar" / "config.yaml"
        with patch("saar.oci_client._CONFIG_PATH", config_path):
            assert get_api_key() is None

    def test_get_api_key_returns_key_when_present(self, tmp_path: Path):
        config_path = tmp_path / ".saar" / "config.yaml"
        with patch("saar.oci_client._CONFIG_PATH", config_path):
            save_oci_config("ci_mykey")
            assert get_api_key() == "ci_mykey"

    def test_get_base_url_returns_default_when_not_configured(self, tmp_path: Path):
        config_path = tmp_path / ".saar" / "config.yaml"
        with patch("saar.oci_client._CONFIG_PATH", config_path):
            assert get_base_url() == _DEFAULT_BASE

    def test_get_base_url_returns_custom_when_configured(self, tmp_path: Path):
        config_path = tmp_path / ".saar" / "config.yaml"
        with patch("saar.oci_client._CONFIG_PATH", config_path):
            save_oci_config("ci_key", "https://custom.api.com")
            assert get_base_url() == "https://custom.api.com"

    def test_comments_ignored_in_config(self, tmp_path: Path):
        config_path = tmp_path / ".saar" / "config.yaml"
        config_path.parent.mkdir(parents=True)
        config_path.write_text(
            "# this is a comment\n"
            "oci_api_key: ci_real_key\n"
            "# another comment\n"
        )
        with patch("saar.oci_client._CONFIG_PATH", config_path):
            assert get_api_key() == "ci_real_key"

    def test_corrupt_config_returns_empty(self, tmp_path: Path):
        config_path = tmp_path / ".saar" / "config.yaml"
        config_path.parent.mkdir(parents=True)
        config_path.write_bytes(b"\xff\xfe bad bytes")
        with patch("saar.oci_client._CONFIG_PATH", config_path):
            result = load_oci_config()
        assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# Repo ID persistence
# ---------------------------------------------------------------------------

class TestRepoIdPersistence:

    def test_save_and_load_repo_id(self, tmp_path: Path):
        save_repo_id(tmp_path, "abc-123")
        assert load_repo_id(tmp_path) == "abc-123"

    def test_load_returns_none_when_no_cache(self, tmp_path: Path):
        assert load_repo_id(tmp_path) is None

    def test_save_preserves_existing_cache_fields(self, tmp_path: Path):
        # Pre-populate cache with interview answers
        saar_dir = tmp_path / ".saar"
        saar_dir.mkdir()
        (saar_dir / "config.json").write_text(
            json.dumps({"version": 1, "answers": {"never_do": "never npm"}})
        )
        save_repo_id(tmp_path, "repo-xyz")
        cache = json.loads((saar_dir / "config.json").read_text())
        # repo_id added
        assert cache["oci_repo_id"] == "repo-xyz"
        # existing answers preserved
        assert cache["answers"]["never_do"] == "never npm"

    def test_save_overwrites_existing_repo_id(self, tmp_path: Path):
        save_repo_id(tmp_path, "old-id")
        save_repo_id(tmp_path, "new-id")
        assert load_repo_id(tmp_path) == "new-id"


# ---------------------------------------------------------------------------
# Git URL and branch detection
# ---------------------------------------------------------------------------

class TestGitDetection:

    def test_detect_git_url_ssh_converted_to_https(self, tmp_path: Path):
        with patch("saar.oci_client.subprocess") as mock_sub:
            mock_sub.run.return_value = MagicMock(
                returncode=0,
                stdout="git@github.com:DevanshuNEU/saar.git\n"
            )
            url = detect_git_url(tmp_path)
        assert url == "https://github.com/DevanshuNEU/saar.git"

    def test_detect_git_url_https_unchanged(self, tmp_path: Path):
        with patch("saar.oci_client.subprocess") as mock_sub:
            mock_sub.run.return_value = MagicMock(
                returncode=0,
                stdout="https://github.com/DevanshuNEU/saar.git\n"
            )
            url = detect_git_url(tmp_path)
        assert url == "https://github.com/DevanshuNEU/saar.git"

    def test_detect_git_url_returns_none_on_failure(self, tmp_path: Path):
        with patch("saar.oci_client.subprocess") as mock_sub:
            mock_sub.run.return_value = MagicMock(returncode=1, stdout="")
            url = detect_git_url(tmp_path)
        assert url is None

    def test_detect_git_url_returns_none_on_exception(self, tmp_path: Path):
        with patch("saar.oci_client.subprocess") as mock_sub:
            mock_sub.run.side_effect = Exception("git not found")
            url = detect_git_url(tmp_path)
        assert url is None

    def test_detect_branch_returns_main_on_failure(self, tmp_path: Path):
        with patch("saar.oci_client.subprocess") as mock_sub:
            mock_sub.run.side_effect = Exception("git not found")
            branch = detect_default_branch(tmp_path)
        assert branch == "main"

    def test_detect_branch_returns_detected_branch(self, tmp_path: Path):
        with patch("saar.oci_client.subprocess") as mock_sub:
            mock_sub.run.return_value = MagicMock(returncode=0, stdout="develop\n")
            branch = detect_default_branch(tmp_path)
        assert branch == "develop"


# ---------------------------------------------------------------------------
# CLI: --index flag behavior
# ---------------------------------------------------------------------------

class TestIndexCLI:

    def test_extract_without_index_still_works(self, tmp_repo: Path, tmp_path: Path):
        """--index is optional, extract without it must not mention OCI."""
        output_dir = tmp_path / "out"
        output_dir.mkdir()
        result = runner.invoke(app, [
            "extract", str(tmp_repo), "--no-interview", "-o", str(output_dir)
        ])
        assert result.exit_code == 0
        assert "OCI" not in result.output

    def test_index_without_api_key_shows_help_message(self, tmp_repo: Path, tmp_path: Path):
        """With no API key configured, --index shows how to get one."""
        output_dir = tmp_path / "out"
        output_dir.mkdir()
        # Patch config path to an empty tmp dir so no key is found
        empty_config = tmp_path / "config.yaml"
        with patch("saar.oci_client._CONFIG_PATH", empty_config):
            result = runner.invoke(app, [
                "extract", str(tmp_repo), "--no-interview",
                "--index", "-o", str(output_dir)
            ])
        # Extract must still succeed
        assert result.exit_code == 0
        assert (output_dir / "AGENTS.md").exists()
        # Must show guidance
        assert "api-keys" in result.output or "API key" in result.output

    def test_index_oci_failure_does_not_break_extract(self, tmp_repo: Path, tmp_path: Path):
        """If OCI API call fails, AGENTS.md must still be written."""
        output_dir = tmp_path / "out"
        output_dir.mkdir()
        with patch("saar.oci_client._CONFIG_PATH", tmp_path / "cfg.yaml"), \
             patch("saar.oci_client.get_api_key", return_value="ci_fake_key"), \
             patch("saar.oci_client.detect_git_url", return_value="https://github.com/x/y.git"), \
             patch("saar.oci_client.detect_default_branch", return_value="main"), \
             patch("saar.oci_client.add_repository", side_effect=Exception("Network error")):
            result = runner.invoke(app, [
                "extract", str(tmp_repo), "--no-interview",
                "--index", "-o", str(output_dir)
            ])
        # Extract must succeed despite OCI failure
        assert result.exit_code == 0
        assert (output_dir / "AGENTS.md").exists()

    def test_index_no_git_remote_shows_guidance(self, tmp_repo: Path, tmp_path: Path):
        """If no git remote detected, must show helpful message."""
        output_dir = tmp_path / "out"
        output_dir.mkdir()
        with patch("saar.oci_client._CONFIG_PATH", tmp_path / "cfg.yaml"), \
             patch("saar.oci_client.get_api_key", return_value="ci_fake_key"), \
             patch("saar.oci_client.detect_git_url", return_value=None):
            result = runner.invoke(app, [
                "extract", str(tmp_repo), "--no-interview",
                "--index", "-o", str(output_dir)
            ])
        assert result.exit_code == 0
        assert (output_dir / "AGENTS.md").exists()
        assert "git remote" in result.output or "origin" in result.output

    def test_index_happy_path_shows_indexed_message(self, tmp_repo: Path, tmp_path: Path):
        """When OCI succeeds, must show indexed confirmation."""
        output_dir = tmp_path / "out"
        output_dir.mkdir()
        fake_repo = {"id": "repo-abc-123", "status": "indexed", "total_functions": 1261}
        with patch("saar.oci_client._CONFIG_PATH", tmp_path / "cfg.yaml"), \
             patch("saar.oci_client.get_api_key", return_value="ci_fake_key"), \
             patch("saar.oci_client.get_base_url", return_value=_DEFAULT_BASE), \
             patch("saar.oci_client.detect_git_url", return_value="https://github.com/x/y.git"), \
             patch("saar.oci_client.detect_default_branch", return_value="main"), \
             patch("saar.oci_client.load_repo_id", return_value=None), \
             patch("saar.oci_client.add_repository", return_value=fake_repo), \
             patch("saar.oci_client.save_repo_id"), \
             patch("saar.oci_client.poll_until_indexed", return_value=fake_repo):
            result = runner.invoke(app, [
                "extract", str(tmp_repo), "--no-interview",
                "--index", "-o", str(output_dir)
            ])
        assert result.exit_code == 0
        assert (output_dir / "AGENTS.md").exists()
        assert "1,261" in result.output or "Indexed" in result.output

    def test_index_saves_repo_id_to_saar_cache(self, tmp_repo: Path, tmp_path: Path):
        """Successful index must save repo_id to .saar/config.json."""
        output_dir = tmp_path / "out"
        output_dir.mkdir()
        fake_repo = {"id": "saved-repo-id", "status": "indexed", "total_functions": 500}

        saved_ids = []
        def capture_save(path, repo_id):
            saved_ids.append(repo_id)

        with patch("saar.oci_client._CONFIG_PATH", tmp_path / "cfg.yaml"), \
             patch("saar.oci_client.get_api_key", return_value="ci_fake_key"), \
             patch("saar.oci_client.get_base_url", return_value=_DEFAULT_BASE), \
             patch("saar.oci_client.detect_git_url", return_value="https://github.com/x/y.git"), \
             patch("saar.oci_client.detect_default_branch", return_value="main"), \
             patch("saar.oci_client.load_repo_id", return_value=None), \
             patch("saar.oci_client.add_repository", return_value=fake_repo), \
             patch("saar.oci_client.save_repo_id", side_effect=capture_save), \
             patch("saar.oci_client.poll_until_indexed", return_value=fake_repo):
            runner.invoke(app, [
                "extract", str(tmp_repo), "--no-interview",
                "--index", "-o", str(output_dir)
            ])
        assert "saved-repo-id" in saved_ids

    def test_index_help_available(self):
        result = runner.invoke(app, ["extract", "--help"])
        assert result.exit_code == 0
        assert "--index" in result.output
