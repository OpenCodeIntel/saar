"""Tests for the dependency analyzer."""
from pathlib import Path

from saar.dependency_analyzer import DependencyAnalyzer


class TestDependencyAnalyzer:
    def test_build_graph_returns_dict(self, tmp_repo: Path):
        result = DependencyAnalyzer().build_graph(str(tmp_repo))
        assert "nodes" in result
        assert "edges" in result
        assert "metrics" in result
        assert "circular_dependencies" in result

    def test_finds_nodes(self, tmp_repo: Path):
        result = DependencyAnalyzer().build_graph(str(tmp_repo))
        file_ids = [n["id"] for n in result["nodes"]]
        assert any("main.py" in str(Path(f)) for f in file_ids)

    def test_resolves_internal_imports(self, tmp_repo: Path):
        result = DependencyAnalyzer().build_graph(str(tmp_repo))
        # dependencies.py imports from services/user_service.py
        edges = result["edges"]
        sources = [e["source"] for e in edges]
        # use Path for cross-platform comparison
        assert any(Path(s).name == "dependencies.py" for s in sources)

    def test_detects_circular_deps(self, tmp_path: Path):
        """Two files importing each other should be flagged."""
        (tmp_path / "a.py").write_text("from b import something\n")
        (tmp_path / "b.py").write_text("from a import something\n")

        result = DependencyAnalyzer().build_graph(str(tmp_path))
        assert len(result["circular_dependencies"]) > 0

    def test_metrics_calculated(self, tmp_repo: Path):
        result = DependencyAnalyzer().build_graph(str(tmp_repo))
        metrics = result["metrics"]
        assert "most_critical_files" in metrics
        assert "avg_dependencies" in metrics

    def test_single_file_analysis(self, tmp_repo: Path):
        main = tmp_repo / "main.py"
        result = DependencyAnalyzer().analyze_file(str(main))
        assert "fastapi" in result["imports"]
        assert result["language"] == "python"

    def test_file_impact(self, tmp_repo: Path):
        graph = DependencyAnalyzer().build_graph(str(tmp_repo))
        # pick a file that exists in the graph
        if graph["nodes"]:
            fp = graph["nodes"][0]["id"]
            impact = DependencyAnalyzer().get_file_impact(fp, graph)
            assert "risk_level" in impact
            assert impact["risk_level"] in ("low", "medium", "high")

    def test_empty_repo(self, tmp_path: Path):
        result = DependencyAnalyzer().build_graph(str(tmp_path))
        assert result["total_files"] == 0
