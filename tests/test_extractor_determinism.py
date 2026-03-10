

class TestDeterministicOutput:
    """OPE-170: saar output must be identical across runs on same codebase.

    Root cause: list(set(...)) iteration order is randomized per Python process
    (hash randomization since Python 3.3). rglob/glob return filesystem order
    which is non-deterministic on Linux/macOS ext4.

    Fix: sorted(set(...)) everywhere, sorted(rglob(...)) for file traversal.
    """

    def _extract_dna(self, repo_path):
        from saar.extractor import DNAExtractor
        extractor = DNAExtractor()
        return extractor.extract(str(repo_path))

    def test_exception_classes_order_is_stable(self, tmp_path):
        """Exception classes must always appear in the same sorted order."""
        # Create a repo with multiple exception classes
        (tmp_path / "exceptions.py").write_text(
            "class ZebraError(Exception): pass\n"
            "class AppleError(Exception): pass\n"
            "class MangoError(Exception): pass\n"
            "class BananaException(Exception): pass\n"
        )
        results = []
        for _ in range(5):
            dna = self._extract_dna(tmp_path)
            results.append(dna.error_patterns.exception_classes)

        # All 5 runs must produce identical lists
        for i in range(1, 5):
            assert results[0] == results[i], (
                f"OPE-170: exception_classes non-deterministic.\n"
                f"Run 1: {results[0]}\nRun {i+1}: {results[i]}"
            )
        # Must be sorted alphabetically
        assert results[0] == sorted(results[0]), (
            f"OPE-170: exception_classes not sorted: {results[0]}"
        )

    def test_auth_patterns_order_is_stable(self, tmp_path):
        """Auth middleware and decorators must always appear in sorted order."""
        (tmp_path / "main.py").write_text(
            "from fastapi import Depends\n"
            "def require_auth(): pass\n"
            "def public_auth(): pass\n"
            "def get_items(auth=Depends(require_auth)): pass\n"
            "def get_public(auth=Depends(public_auth)): pass\n"
        )
        results = []
        for _ in range(5):
            dna = self._extract_dna(tmp_path)
            results.append({
                "middleware": dna.auth_patterns.middleware_used,
                "decorators": dna.auth_patterns.auth_decorators,
            })

        for i in range(1, 5):
            assert results[0] == results[i], (
                f"OPE-170: auth patterns non-deterministic.\n"
                f"Run 1: {results[0]}\nRun {i+1}: {results[i]}"
            )

    def test_full_extraction_is_deterministic(self, tmp_path):
        """Five consecutive extractions on same repo must produce identical DNA."""
        # Build a realistic multi-file repo
        (tmp_path / "main.py").write_text(
            "from fastapi import FastAPI, Depends\nimport logging\n"
            "logger = logging.getLogger(__name__)\n"
            "app = FastAPI()\n"
            "def require_auth(): pass\n"
            "@app.get('/api/v1/items')\n"
            "async def get_items(auth=Depends(require_auth)): return []\n"
        )
        services = tmp_path / "services"
        services.mkdir()
        (services / "__init__.py").write_text("")
        (services / "user_service.py").write_text(
            "class UserService:\n"
            "    def get(self, uid: str) -> dict: return {}\n"
            "user_svc = UserService()\n"
        )
        (tmp_path / "exceptions.py").write_text(
            "class TokenError(Exception): pass\n"
            "class AuthError(Exception): pass\n"
            "class LimitError(Exception): pass\n"
        )
        (tmp_path / "dependencies.py").write_text(
            "from services.user_service import UserService\n"
            "user_service = UserService()\n"
        )

        # Extract 5 times and collect key fields
        snapshots = []
        for _ in range(5):
            dna = self._extract_dna(tmp_path)
            snapshots.append({
                "exceptions": dna.error_patterns.exception_classes,
                "middleware": dna.auth_patterns.middleware_used,
                "decorators": dna.auth_patterns.auth_decorators,
                "total_functions": dna.total_functions,
            })

        for i in range(1, 5):
            assert snapshots[0] == snapshots[i], (
                f"OPE-170: full extraction non-deterministic between run 1 and run {i+1}.\n"
                f"Run 1:    {snapshots[0]}\n"
                f"Run {i+1}: {snapshots[i]}"
            )

    def test_no_list_set_in_extractor_source(self):
        """Source-level check: list(set(...)) must never appear in extractor.py.

        list(set(...)) produces non-deterministic iteration order due to Python
        hash randomization. Always use sorted(set(...)) instead.
        """
        import ast
        from pathlib import Path

        source = (Path(__file__).parent.parent / "saar" / "extractor.py").read_text()

        # Check for the pattern list(set( in the source as a string
        # (AST would be more precise but string search catches it fast)
        violations = []
        for lineno, line in enumerate(source.splitlines(), start=1):
            stripped = line.strip()
            if "list(set(" in stripped and not stripped.startswith("#"):
                violations.append(f"  line {lineno}: {stripped}")

        assert not violations, (
            "OPE-170: list(set(...)) found in extractor.py -- use sorted(set(...)) instead:\n"
            + "\n".join(violations)
        )
