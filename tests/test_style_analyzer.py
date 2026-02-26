"""Tests for the style analyzer."""
from pathlib import Path

from saar.style_analyzer import StyleAnalyzer


class TestStyleAnalyzer:
    def test_analyze_returns_dict(self, tmp_repo: Path):
        result = StyleAnalyzer().analyze(str(tmp_repo))
        assert "summary" in result
        assert "naming_conventions" in result
        assert "top_imports" in result

    def test_counts_functions(self, tmp_repo: Path):
        result = StyleAnalyzer().analyze(str(tmp_repo))
        assert result["summary"]["total_functions"] >= 2

    def test_detects_async(self, tmp_repo: Path):
        # tmp_repo has async def get_items in main.py
        result = StyleAnalyzer().analyze(str(tmp_repo))
        assert result["summary"]["async_pct"] > 0

    def test_detects_type_hints(self, tmp_repo: Path):
        # user_service.py has -> dict type hint
        result = StyleAnalyzer().analyze(str(tmp_repo))
        assert result["summary"]["typed_pct"] > 0

    def test_extracts_imports(self, tmp_repo: Path):
        result = StyleAnalyzer().analyze(str(tmp_repo))
        modules = [i["module"] for i in result["top_imports"]]
        assert "logging" in modules

    def test_empty_repo(self, tmp_path: Path):
        result = StyleAnalyzer().analyze(str(tmp_path))
        assert result["summary"]["total_files_analyzed"] == 0
