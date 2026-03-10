"""Tests for OPE-142: canonical example detection.

The extractor must:
- Identify the most-imported file per category (hooks, services, components, etc.)
- Require minimum 2 importers to qualify as canonical
- Handle empty/missing dependency data gracefully
- Produce sorted output (highest fan-in first)
- Never crash on malformed critical_files entries

The formatter must:
- Render a ## Canonical Examples section when examples exist
- Skip the section when no examples detected
- Format output as: "For new hooks, follow `path/to/file.ts` (N importers)"
"""
from pathlib import Path

from saar.extractor import DNAExtractor
from saar.models import CodebaseDNA
from saar.formatters.agents_md import render_agents_md
from saar.formatters.claude_md import render_claude_md


# ---------------------------------------------------------------------------
# Unit tests: _extract_canonical_examples
# ---------------------------------------------------------------------------

class TestExtractCanonicalExamples:

    def _run(self, critical_files: list) -> list:
        """Helper: build DNA with critical_files and run canonical extraction."""
        dna = CodebaseDNA(repo_name="test", critical_files=critical_files)
        extractor = DNAExtractor()
        extractor._extract_canonical_examples(dna)
        return dna.canonical_examples

    def test_empty_critical_files_returns_empty(self):
        result = self._run([])
        assert result == []

    def test_minimum_two_importers_required(self):
        """Files with only 1 importer must not be nominated as canonical."""
        result = self._run([
            {"file": "src/hooks/useData.ts", "dependents": 1},
        ])
        assert result == []

    def test_two_importers_qualifies(self):
        result = self._run([
            {"file": "src/hooks/useData.ts", "dependents": 2},
        ])
        assert len(result) == 1
        assert result[0]["file"] == "src/hooks/useData.ts"
        assert result[0]["category"] == "hooks"

    def test_hooks_category_detected(self):
        result = self._run([{"file": "src/hooks/useUserData.ts", "dependents": 5}])
        assert result[0]["category"] == "hooks"

    def test_services_category_detected(self):
        result = self._run([{"file": "src/services/authService.py", "dependents": 8}])
        assert result[0]["category"] == "services"

    def test_components_category_detected(self):
        result = self._run([{"file": "src/components/Button.tsx", "dependents": 15}])
        assert result[0]["category"] == "components"

    def test_tests_category_detected(self):
        result = self._run([{"file": "tests/test_auth.py", "dependents": 3}])
        assert result[0]["category"] == "tests"

    def test_routes_category_detected(self):
        result = self._run([{"file": "backend/routes/users.py", "dependents": 4}])
        assert result[0]["category"] == "routes"

    def test_middleware_category_detected(self):
        result = self._run([{"file": "backend/middleware/auth.py", "dependents": 10}])
        assert result[0]["category"] == "middleware"

    def test_only_highest_importers_per_category(self):
        """When multiple files match the same category, keep only the most imported."""
        result = self._run([
            {"file": "src/hooks/useLow.ts", "dependents": 3},
            {"file": "src/hooks/useHigh.ts", "dependents": 12},
            {"file": "src/hooks/useMid.ts", "dependents": 7},
        ])
        hooks = [r for r in result if r["category"] == "hooks"]
        assert len(hooks) == 1
        assert hooks[0]["file"] == "src/hooks/useHigh.ts"
        assert hooks[0]["import_count"] == 12

    def test_multiple_categories_all_detected(self):
        result = self._run([
            {"file": "src/hooks/useData.ts", "dependents": 5},
            {"file": "src/services/api.py", "dependents": 8},
            {"file": "src/components/Card.tsx", "dependents": 3},
        ])
        categories = {r["category"] for r in result}
        assert "hooks" in categories
        assert "services" in categories
        assert "components" in categories

    def test_sorted_by_import_count_descending(self):
        result = self._run([
            {"file": "src/hooks/useA.ts", "dependents": 3},
            {"file": "src/services/svcB.py", "dependents": 10},
            {"file": "src/components/CompC.tsx", "dependents": 6},
        ])
        counts = [r["import_count"] for r in result]
        assert counts == sorted(counts, reverse=True)

    def test_reason_contains_file_path(self):
        result = self._run([{"file": "src/hooks/useCached.ts", "dependents": 5}])
        assert "useCached.ts" in result[0]["reason"]

    def test_reason_contains_for_new_prefix(self):
        result = self._run([{"file": "src/hooks/useData.ts", "dependents": 5}])
        assert "For new hooks" in result[0]["reason"]

    def test_uncategorized_file_skipped(self):
        """Files that don't match any category should be silently ignored."""
        result = self._run([
            {"file": "config/settings.py", "dependents": 10},
        ])
        # config/ is not a known category
        assert result == []

    def test_windows_path_separators_handled(self):
        """Backslash paths (Windows) must be normalized before category matching."""
        result = self._run([
            {"file": "src\\hooks\\useData.ts", "dependents": 5},
        ])
        assert len(result) == 1
        assert result[0]["category"] == "hooks"

    def test_malformed_entry_does_not_crash(self):
        """Non-dict entries in critical_files must not crash."""
        result = self._run([
            "not-a-dict",
            None,
            {"file": "src/hooks/useData.ts", "dependents": 5},
        ])
        # Should produce at least the valid entry
        assert any(r.get("category") == "hooks" for r in result)

    def test_dna_canonical_examples_empty_by_default(self):
        dna = CodebaseDNA(repo_name="test")
        assert dna.canonical_examples == []


# ---------------------------------------------------------------------------
# Integration test: extractor on real repo
# ---------------------------------------------------------------------------

class TestCanonicalExamplesIntegration:

    def test_extraction_on_real_repo_does_not_crash(self, tmp_path: Path):
        """Full extraction pipeline must not crash even with no importable hooks."""
        # Create a minimal repo with hook-like files
        hooks = tmp_path / "hooks"
        hooks.mkdir()
        (hooks / "useData.ts").write_text(
            "export function useData() { return null; }\n"
        )
        services = tmp_path / "services"
        services.mkdir()
        (services / "api.py").write_text(
            "def get_data(): return {}\n"
        )
        # Import the hook from multiple places
        src = tmp_path / "src"
        src.mkdir()
        for i in range(3):
            (src / f"component_{i}.ts").write_text(
                "import { useData } from '../hooks/useData';\n"
            )

        extractor = DNAExtractor()
        dna = extractor.extract(str(tmp_path))
        # Must not crash, canonical_examples is a list
        assert isinstance(dna.canonical_examples, list)


# ---------------------------------------------------------------------------
# Formatter tests
# ---------------------------------------------------------------------------

class TestCanonicalExamplesFormatter:

    def _dna_with_examples(self) -> CodebaseDNA:
        dna = CodebaseDNA(repo_name="my-project")
        dna.canonical_examples = [
            {
                "category": "hooks",
                "file": "src/hooks/useUserData.ts",
                "import_count": 12,
                "reason": "For new hooks, follow `src/hooks/useUserData.ts`",
            },
            {
                "category": "services",
                "file": "src/services/authService.py",
                "import_count": 8,
                "reason": "For new services, follow `src/services/authService.py`",
            },
        ]
        return dna

    def test_agents_md_renders_canonical_section(self):
        result = render_agents_md(self._dna_with_examples())
        assert "## Canonical Examples" in result

    def test_agents_md_renders_hook_example(self):
        result = render_agents_md(self._dna_with_examples())
        assert "useUserData.ts" in result
        assert "12 importers" in result

    def test_agents_md_renders_service_example(self):
        result = render_agents_md(self._dna_with_examples())
        assert "authService.py" in result
        assert "8 importers" in result

    def test_agents_md_no_section_when_empty(self):
        dna = CodebaseDNA(repo_name="empty")
        result = render_agents_md(dna)
        assert "## Canonical Examples" not in result

    def test_claude_md_renders_canonical_section(self):
        result = render_claude_md(self._dna_with_examples())
        assert "## Canonical Examples" in result
        assert "useUserData.ts" in result

    def test_claude_md_no_section_when_empty(self):
        dna = CodebaseDNA(repo_name="empty")
        result = render_claude_md(dna)
        assert "## Canonical Examples" not in result

    def test_capped_at_six_examples(self):
        """Formatter must show at most 6 canonical examples to stay within budget."""
        dna = CodebaseDNA(repo_name="big-project")
        dna.canonical_examples = [
            {
                "category": f"cat{i}",
                "file": f"src/cat{i}/example.ts",
                "import_count": 10 - i,
                "reason": f"For new cat{i}, follow `src/cat{i}/example.ts`",
            }
            for i in range(10)
        ]
        result = render_agents_md(dna)
        # Count how many times "importers" appears -- each example has one
        importer_mentions = result.count("importers")
        assert importer_mentions <= 6, f"Expected max 6 examples, got {importer_mentions}"

    def test_reason_format_is_actionable(self):
        """Output must tell the developer what to do, not just what exists."""
        result = render_agents_md(self._dna_with_examples())
        assert "For new hooks" in result
        assert "For new services" in result
