"""Dependency graph builder using tree-sitter AST parsing.

Extracts imports from Python and JS/TS files, resolves them to
internal files, builds a dependency graph, and calculates metrics
like critical files and circular dependencies.
"""
import logging
import re
from collections import deque
from pathlib import Path
from typing import Dict, List, Optional, Set

import tree_sitter_python as tspython
import tree_sitter_javascript as tsjavascript
from tree_sitter import Language, Parser


def _path_should_skip(file_path: Path, repo_path: Path, skip: Set[str]) -> bool:
    """Check whether a file falls under a skip directory.

    Handles both simple names and multi-component paths like 'backend/repos'.
    """
    parts = file_path.parts
    try:
        rel_parts = file_path.relative_to(repo_path).parts
    except ValueError:
        rel_parts = parts

    for s in skip:
        if "/" in s or "\\" in s:
            skip_parts = tuple(s.replace("\\", "/").split("/"))
            if rel_parts[:len(skip_parts)] == skip_parts:
                return True
        else:
            if s in parts:
                return True
    return False


logger = logging.getLogger(__name__)


class DependencyAnalyzer:
    """Build and analyze dependency graphs for a codebase."""

    SKIP_DIRS = {
        "node_modules", ".git", "__pycache__", "venv", "env",
        "dist", "build", ".next", "coverage", ".venv", "site-packages",
    }

    def __init__(self) -> None:
        try:
            self.parsers = {
                "python": Parser(Language(tspython.language())),
                "javascript": Parser(Language(tsjavascript.language())),
                "typescript": Parser(Language(tsjavascript.language())),
            }
        except TypeError:
            py_lang = Language(tspython.language())
            js_lang = Language(tsjavascript.language())
            self.parsers = {}
            for name, lang in [("python", py_lang), ("javascript", js_lang), ("typescript", js_lang)]:
                p = Parser()
                p.language = lang
                self.parsers[name] = p

    def _detect_language(self, file_path: str) -> str:
        ext = Path(file_path).suffix.lower()
        return {
            ".py": "python", ".js": "javascript", ".jsx": "javascript",
            ".ts": "typescript", ".tsx": "typescript",
        }.get(ext, "unknown")

    # -- AST import extraction --------------------------------------------

    def _extract_python_imports(self, node, source: bytes) -> Set[str]:
        imports: Set[str] = set()
        if node.type in ("import_statement", "import_from_statement"):
            text = source[node.start_byte:node.end_byte].decode("utf-8")
            if text.startswith("from"):
                match = re.match(r"from\s+([\w.]+)\s+import", text)
                if match:
                    imports.add(match.group(1))
            elif text.startswith("import"):
                for mod_list in re.findall(r"import\s+([\w.,\s]+)", text):
                    for mod in mod_list.split(","):
                        mod = mod.strip().split(" as ")[0]
                        if mod:
                            imports.add(mod)
        for child in node.children:
            imports.update(self._extract_python_imports(child, source))
        return imports

    def _extract_js_imports(self, node, source: bytes) -> Set[str]:
        imports: Set[str] = set()
        if node.type == "import_statement":
            text = source[node.start_byte:node.end_byte].decode("utf-8")
            matches = re.findall(r"from\s+[\"']([^\"']+)[\"']", text)
            if not matches:
                matches = re.findall(r"import\s+[\"']([^\"']+)[\"']", text)
            imports.update(matches)
        if node.type == "export_statement":
            text = source[node.start_byte:node.end_byte].decode("utf-8")
            imports.update(re.findall(r"from\s+[\"']([^\"']+)[\"']", text))
        if node.type == "call_expression":
            text = source[node.start_byte:node.end_byte].decode("utf-8")
            if "require(" in text:
                match = re.search(r"require\([\"']([^\"']+)[\"']\)", text)
                if match:
                    imports.add(match.group(1))
        for child in node.children:
            imports.update(self._extract_js_imports(child, source))
        return imports

    # -- single file analysis ---------------------------------------------

    def analyze_file(self, file_path: str) -> Dict:
        """Analyze a single file's imports."""
        language = self._detect_language(file_path)
        if language not in self.parsers:
            return {"file": file_path, "imports": [], "language": language}

        try:
            source = Path(file_path).read_bytes()
            # Suppress stderr during tree-sitter parsing -- some large/complex files
            # cause tree-sitter to print internal warnings we can't control otherwise
            import os as _os
            import sys as _sys
            _devnull = open(_os.devnull, "w")
            _old_stderr = _sys.stderr
            _sys.stderr = _devnull
            try:
                tree = self.parsers[language].parse(source)
            finally:
                _sys.stderr = _old_stderr
                _devnull.close()

            if language == "python":
                imports = self._extract_python_imports(tree.root_node, source)
            else:
                imports = self._extract_js_imports(tree.root_node, source)

            return {
                "file": file_path,
                "imports": list(imports),
                "language": language,
                "import_count": len(imports),
            }
        except RecursionError:
            # large/circular files exceed Python's recursion limit -- log at DEBUG
            # so it doesn't pollute user-facing terminal output (OPE-182)
            logger.debug("Skipped %s (recursion limit -- file too complex)", file_path)
            return {"file": file_path, "imports": [], "language": language}
        except Exception as e:
            logger.debug("Error analyzing %s: %s", file_path, e)
            return {"file": file_path, "imports": [], "language": language}

    # -- import resolution ------------------------------------------------

    def _resolve_import(
        self, import_path: str, source_file: str,
        internal_files: Set[str], repo_path: Path,
    ) -> Optional[str]:
        """Resolve an import to an internal file path, or None if external."""
        # single-word imports without dots are usually external (os, sys, json)
        # but check if they resolve to an internal file first
        if not import_path.startswith(".") and "." not in import_path and "/" not in import_path:
            # check if it maps to a local file before dismissing
            for ext in (".py", ".js", ".ts"):
                if import_path + ext in internal_files:
                    return import_path + ext
            return None

        source_dir = Path(source_file).parent

        # relative imports
        if import_path.startswith("."):
            clean = import_path.lstrip("./")
            potential = source_dir / clean
            for ext in ("", ".ts", ".tsx", ".js", ".jsx", ".py"):
                if str(potential) + ext in internal_files:
                    return str(potential) + ext
                idx = str(potential / ("index" + ext))
                if idx in internal_files:
                    return idx

        # absolute python imports (dotted path -> file path)
        module_path = import_path.replace(".", "/")
        for ext in (".py", ".js", ".ts"):
            if module_path + ext in internal_files:
                return module_path + ext
            init = f"{module_path}/__init__.py"
            if init in internal_files:
                return init

        return None

    # -- graph building ---------------------------------------------------

    def build_graph(self, repo_path: str, extra_skip_dirs: set = None) -> Dict:
        """Build complete dependency graph for a repository.

        Returns dict with nodes, edges, metrics, and circular deps.
        """
        path = Path(repo_path)
        skip = self.SKIP_DIRS | (extra_skip_dirs or set())
        extensions = {".py", ".js", ".jsx", ".ts", ".tsx"}

        code_files: List[Path] = []
        for fp in path.rglob("*"):
            if fp.is_file() and fp.suffix in extensions:
                if not _path_should_skip(fp, path, skip):
                    code_files.append(fp)

        logger.info("Building dependency graph: %d files", len(code_files))

        file_deps: Dict[str, List[str]] = {}
        all_imports: Set[str] = set()

        for fp in code_files:
            # always use forward slashes for internal keys -- Windows compat
            rel = fp.relative_to(path).as_posix()
            analysis = self.analyze_file(str(fp))
            file_deps[rel] = analysis["imports"]
            all_imports.update(analysis["imports"])

        internal_files = set(file_deps.keys())

        # build nodes
        nodes = [
            {
                "id": fp,
                "label": Path(fp).name,
                "language": self._detect_language(fp),
                "import_count": len(file_deps[fp]),
            }
            for fp in file_deps
        ]

        # resolve imports to internal files -> edges
        edges: List[Dict] = []
        for source, imports in file_deps.items():
            for imp in imports:
                target = self._resolve_import(imp, source, internal_files, path)
                if target:
                    edges.append({"source": source, "target": target})

        # metrics
        metrics = self._calculate_metrics(file_deps, edges)

        # circular dependency detection
        circular = self._find_circular_deps(edges)

        logger.info("Graph built: %d nodes, %d edges, %d cycles", len(nodes), len(edges), len(circular))

        return {
            "nodes": nodes,
            "edges": edges,
            "metrics": metrics,
            "circular_dependencies": circular,
            "total_files": len(nodes),
            "total_dependencies": len(edges),
        }

    # -- metrics ----------------------------------------------------------

    def _calculate_metrics(self, deps: Dict, edges: List[Dict]) -> Dict:
        in_degree: Dict[str, int] = {}
        out_degree: Dict[str, int] = {}

        for edge in edges:
            out_degree[edge["source"]] = out_degree.get(edge["source"], 0) + 1
            in_degree[edge["target"]] = in_degree.get(edge["target"], 0) + 1

        critical = sorted(in_degree.items(), key=lambda x: x[1], reverse=True)[:10]
        complex_ = sorted(out_degree.items(), key=lambda x: x[1], reverse=True)[:10]

        return {
            "most_critical_files": [{"file": f, "dependents": d} for f, d in critical],
            "most_complex_files": [{"file": f, "dependencies": d} for f, d in complex_],
            "avg_dependencies": sum(out_degree.values()) / len(out_degree) if out_degree else 0,
            "total_edges": len(edges),
        }

    def _find_circular_deps(self, edges: List[Dict]) -> List[List[str]]:
        """Detect circular dependencies (direct A->B->A cycles)."""
        edge_set: Set[tuple] = {(e["source"], e["target"]) for e in edges}
        circular: List[List[str]] = []
        seen: Set[tuple] = set()

        for src, tgt in edge_set:
            pair = tuple(sorted((src, tgt)))
            if pair in seen:
                continue
            if (tgt, src) in edge_set:
                circular.append([src, tgt])
                seen.add(pair)

        return circular

    # -- impact analysis --------------------------------------------------

    def get_file_impact(self, file_path: str, graph_data: Dict) -> Dict:
        """Calculate impact of changing a specific file."""
        deps_map: Dict[str, List[str]] = {}
        rev_map: Dict[str, List[str]] = {}

        for edge in graph_data["edges"]:
            deps_map.setdefault(edge["source"], []).append(edge["target"])
            rev_map.setdefault(edge["target"], []).append(edge["source"])

        direct = rev_map.get(file_path, [])
        transitive = self._find_transitive(file_path, rev_map)
        direct_deps = deps_map.get(file_path, [])

        if len(transitive) > 10:
            risk = "high"
        elif len(transitive) > 3:
            risk = "medium"
        else:
            risk = "low"

        return {
            "file": file_path,
            "direct_dependents": direct,
            "all_dependents": transitive,
            "direct_dependencies": direct_deps,
            "risk_level": risk,
            "impact_summary": f"{len(transitive)} files affected" if transitive else "Safe to modify",
        }

    def _find_transitive(self, file_path: str, rev_map: Dict) -> List[str]:
        """BFS to find all transitive dependents."""
        visited: Set[str] = set()
        queue: deque = deque([file_path])

        while queue:
            current = queue.popleft()
            if current in visited:
                continue
            visited.add(current)
            for dep in rev_map.get(current, []):
                if dep not in visited:
                    queue.append(dep)

        visited.discard(file_path)
        return list(visited)
