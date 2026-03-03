"""Style analysis using tree-sitter AST parsing.

Extracts naming conventions, async adoption, type hint usage,
and import patterns by walking the actual syntax tree -- not regex.
"""
import logging
import re
from collections import Counter
from pathlib import Path
from typing import Dict, List, Set

import tree_sitter_python as tspython
import tree_sitter_javascript as tsjavascript
from tree_sitter import Language, Parser


def _path_should_skip(file_path: Path, repo_path: Path, skip: Set[str]) -> bool:
    """Check whether a file falls under a skip directory.

    Handles both simple names ('node_modules') and multi-component
    paths ('backend/repos') from gitignore patterns.
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


class StyleAnalyzer:
    """Analyze code style patterns across a repository."""

    SKIP_DIRS = {
        "node_modules", ".git", "__pycache__", "venv", "env",
        "dist", "build", ".next", "coverage", ".venv", "site-packages",
    }

    def __init__(self) -> None:
        self.parsers = {
            "python": Parser(Language(tspython.language())),
            "javascript": Parser(Language(tsjavascript.language())),
            "typescript": Parser(Language(tsjavascript.language())),
        }

    def _detect_language(self, file_path: str) -> str:
        ext = Path(file_path).suffix.lower()
        return {
            ".py": "python", ".js": "javascript", ".jsx": "javascript",
            ".ts": "typescript", ".tsx": "typescript",
        }.get(ext, "unknown")

    def _detect_naming_convention(self, name: str) -> str:
        """Classify a name into its naming convention."""
        if not name or name.startswith("_"):
            return "unknown"
        if "_" in name and name.islower():
            return "snake_case"
        if "_" in name and name.isupper():
            return "UPPER_SNAKE_CASE"
        if name[0].isupper() and "_" not in name:
            return "PascalCase"
        if name[0].islower() and "_" not in name and any(c.isupper() for c in name):
            return "camelCase"
        if name.islower() and "_" not in name:
            return "lowercase"
        return "mixed"

    def _extract_identifiers(self, node, source: bytes, id_type: str) -> List[str]:
        """Walk AST to extract function or class names.

        For Python: function_definition, class_definition.
        For JS/TS: function_declaration, method_definition, arrow_function
        (via variable_declarator parent), class_declaration.
        Arrow functions need special handling -- the name lives in the parent
        variable_declarator node, not the arrow_function node itself.
        """
        names: List[str] = []

        if id_type == "function":
            # Python named function
            if node.type == "function_definition":
                for child in node.children:
                    if child.type == "identifier":
                        names.append(source[child.start_byte:child.end_byte].decode("utf-8"))
                        break

            # JS/TS: function declaration -- function foo() {}
            elif node.type == "function_declaration":
                for child in node.children:
                    if child.type == "identifier":
                        names.append(source[child.start_byte:child.end_byte].decode("utf-8"))
                        break

            # JS/TS: class method -- method() {} or async method() {}
            elif node.type == "method_definition":
                for child in node.children:
                    if child.type in ("property_identifier", "identifier"):
                        names.append(source[child.start_byte:child.end_byte].decode("utf-8"))
                        break

            # JS/TS: const fn = () => {} -- name is in the variable_declarator
            # We emit the name here and skip recursing into the arrow_function child
            elif node.type == "variable_declarator":
                has_arrow = any(c.type == "arrow_function" for c in node.children)
                if has_arrow:
                    for child in node.children:
                        if child.type == "identifier":
                            names.append(source[child.start_byte:child.end_byte].decode("utf-8"))
                            break

        elif id_type == "class":
            # Python
            if node.type == "class_definition":
                for child in node.children:
                    if child.type == "identifier":
                        names.append(source[child.start_byte:child.end_byte].decode("utf-8"))
                        break
            # JS/TS
            elif node.type in ("class_declaration", "class"):
                for child in node.children:
                    if child.type == "type_identifier":
                        names.append(source[child.start_byte:child.end_byte].decode("utf-8"))
                        break

        for child in node.children:
            names.extend(self._extract_identifiers(child, source, id_type))
        return names

    def _extract_imports(self, node, source: bytes, language: str) -> List[str]:
        """Walk AST to extract import module names."""
        imports: List[str] = []

        if language == "python":
            if node.type in ("import_statement", "import_from_statement"):
                text = source[node.start_byte:node.end_byte].decode("utf-8")
                if "from" in text:
                    match = re.search(r"from\s+([\w.]+)", text)
                    if match:
                        imports.append(match.group(1))
                elif "import" in text:
                    for mod in re.findall(r"import\s+([\w.,\s]+)", text):
                        for m in mod.split(","):
                            m = m.strip().split(" as ")[0]
                            if m:
                                imports.append(m)
        else:
            if node.type == "import_statement":
                text = source[node.start_byte:node.end_byte].decode("utf-8")
                match = re.search(r"from\s+[\"']([^\"']+)[\"']", text)
                if match:
                    imports.append(match.group(1))

        for child in node.children:
            imports.extend(self._extract_imports(child, source, language))
        return imports

    def _check_async(self, source_text: str, language: str) -> bool:
        if language == "python":
            return "async def" in source_text or "await " in source_text
        return "async " in source_text or "await " in source_text

    def _check_type_hints(self, source_text: str, language: str) -> bool:
        if language == "python":
            return "->" in source_text or ": " in source_text
        return ": " in source_text and ("interface" in source_text or "type " in source_text)

    def analyze(self, repo_path: str, extra_skip_dirs: set = None) -> Dict:
        """Analyze coding style patterns across a repository.

        Returns a dict with summary stats, naming conventions,
        language distribution, top imports, and pattern metrics.
        """
        path = Path(repo_path)
        skip = self.SKIP_DIRS | (extra_skip_dirs or set())
        extensions = {".py", ".js", ".jsx", ".ts", ".tsx"}

        code_files: List[Path] = []
        for fp in path.rglob("*"):
            if fp.is_file() and fp.suffix in extensions:
                if not _path_should_skip(fp, path, skip):
                    code_files.append(fp)

        function_names: List[str] = []
        class_names: List[str] = []
        all_imports: List[str] = []
        async_files = 0
        typed_files = 0
        total_files = 0
        lang_dist: Counter = Counter()

        for fp in code_files:
            language = self._detect_language(str(fp))
            if language not in self.parsers:
                continue
            try:
                source = fp.read_bytes()
                source_text = source.decode("utf-8", errors="ignore")
                tree = self.parsers[language].parse(source)

                function_names.extend(self._extract_identifiers(tree.root_node, source, "function"))
                class_names.extend(self._extract_identifiers(tree.root_node, source, "class"))
                all_imports.extend(self._extract_imports(tree.root_node, source, language))

                if self._check_async(source_text, language):
                    async_files += 1
                if self._check_type_hints(source_text, language):
                    typed_files += 1

                total_files += 1
                lang_dist[language] += 1
            except Exception as e:
                logger.warning("Error analyzing %s: %s", fp, e)

        func_conv = Counter(self._detect_naming_convention(n) for n in function_names)
        class_conv = Counter(self._detect_naming_convention(n) for n in class_names)
        import_freq = Counter(all_imports)

        total_func = len(function_names)
        total_cls = len(class_names)
        def pct(n: int, d: int) -> str:
            return f"{n / d * 100:.0f}%" if d > 0 else "0%"

        return {
            "summary": {
                "total_files_analyzed": total_files,
                "total_functions": total_func,
                "total_classes": total_cls,
                "async_adoption": pct(async_files, total_files),
                "type_hints_usage": pct(typed_files, total_files),
                "async_pct": (async_files / total_files * 100) if total_files else 0,
                "typed_pct": (typed_files / total_files * 100) if total_files else 0,
            },
            "naming_conventions": {
                "functions": {
                    conv: {"count": count, "percentage": pct(count, total_func)}
                    for conv, count in func_conv.most_common(5)
                },
                "classes": {
                    conv: {"count": count, "percentage": pct(count, total_cls)}
                    for conv, count in class_conv.most_common(5)
                },
            },
            "language_distribution": dict(lang_dist),
            "top_imports": [
                {"module": mod, "count": cnt}
                for mod, cnt in import_freq.most_common(20)
            ],
        }
