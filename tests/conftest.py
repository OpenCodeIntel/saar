"""Shared test fixtures."""
import pytest
from pathlib import Path
from saar.models import (
    AuthPattern, CodebaseDNA, ConfigPattern, DatabasePattern,
    ErrorPattern, LoggingPattern, NamingConventions, ServicePattern,
    TestPattern,
)


@pytest.fixture
def sample_dna() -> CodebaseDNA:
    """A realistic CodebaseDNA for testing formatters."""
    return CodebaseDNA(
        repo_name="my-project",
        detected_framework="fastapi",
        language_distribution={"python": 45, "typescript": 20},
        auth_patterns=AuthPattern(
            middleware_used=["require_auth"],
            auth_decorators=["Depends(require_auth)"],
            ownership_checks=["verify_ownership"],
            auth_context_type="AuthContext",
        ),
        service_patterns=ServicePattern(
            singleton_services=["indexer = IndexerService()"],
            dependencies_file="dependencies.py",
            injection_pattern="Singleton in dependencies.py",
        ),
        database_patterns=DatabasePattern(
            orm_used="Supabase",
            id_type="UUID (gen_random_uuid())",
            timestamp_type="TIMESTAMPTZ",
            has_rls=True,
            cascade_deletes=True,
        ),
        error_patterns=ErrorPattern(
            exception_classes=["AppError", "AuthenticationError"],
            http_exception_usage=True,
            logging_on_error=True,
        ),
        logging_patterns=LoggingPattern(
            logger_import="logging.getLogger(__name__)",
            log_levels_used=["info", "error", "warning"],
            structured_logging=False,
        ),
        naming_conventions=NamingConventions(
            function_style="snake_case",
            class_style="PascalCase",
            constant_style="UPPER_SNAKE_CASE",
            file_style="snake_case",
        ),
        test_patterns=TestPattern(
            framework="pytest",
            fixture_style="pytest fixtures",
            mock_library="unittest.mock",
            test_file_pattern="test_*.py",
            has_conftest=True,
        ),
        config_patterns=ConfigPattern(
            env_loading="python-dotenv",
            settings_pattern="Pydantic Settings",
            secrets_handling="Environment variables",
            config_validation=True,
        ),
        middleware_patterns=["app.add_middleware()", "Depends(require_auth)"],
        common_imports=["from pathlib import Path", "import logging"],
        api_versioning="/api/v1 (from config)",
        router_pattern='APIRouter(prefix="/repos", tags=[...])',
        team_rules="- No emojis\n- Type hints on all functions",
        team_rules_source="CLAUDE.md",
    )


@pytest.fixture
def empty_dna() -> CodebaseDNA:
    """Minimal CodebaseDNA with no detected patterns."""
    return CodebaseDNA(repo_name="empty-project")


@pytest.fixture
def tmp_repo(tmp_path: Path) -> Path:
    """Create a minimal Python repo structure for extractor tests."""
    # main.py with FastAPI patterns
    main = tmp_path / "main.py"
    main.write_text(
        'from fastapi import FastAPI, Depends, HTTPException\n'
        'from pathlib import Path\n'
        'import logging\n\n'
        'logger = logging.getLogger(__name__)\n\n'
        'app = FastAPI()\n\n'
        'def require_auth():\n'
        '    """Auth dependency."""\n'
        '    pass\n\n'
        '@app.get("/api/v1/items")\n'
        'async def get_items(auth=Depends(require_auth)):\n'
        '    return []\n'
    )

    # services/user_service.py
    services = tmp_path / "services"
    services.mkdir()
    (services / "__init__.py").write_text("")
    (services / "user_service.py").write_text(
        'import logging\n\n'
        'logger = logging.getLogger(__name__)\n\n'
        'class UserService:\n'
        '    def get_user(self, user_id: str) -> dict:\n'
        '        return {"id": user_id}\n'
    )

    # dependencies.py with singleton
    (tmp_path / "dependencies.py").write_text(
        'from services.user_service import UserService\n\n'
        'user_service = UserService()\n'
    )

    # conftest.py
    (tmp_path / "conftest.py").write_text(
        'import pytest\n\n'
        '@pytest.fixture\n'
        'def client():\n'
        '    return None\n'
    )

    # test file
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "__init__.py").write_text("")
    (tests / "test_main.py").write_text(
        'import pytest\n'
        'from unittest.mock import patch\n\n'
        'def test_placeholder():\n'
        '    assert True\n'
    )

    # SQL migration
    migrations = tmp_path / "migrations"
    migrations.mkdir()
    (migrations / "001_init.sql").write_text(
        'CREATE TABLE users (\n'
        '    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,\n'
        '    created_at TIMESTAMPTZ DEFAULT now(),\n'
        '    email TEXT NOT NULL\n'
        ');\n'
        'ALTER TABLE users ENABLE ROW LEVEL SECURITY;\n'
    )

    # CLAUDE.md team rules
    (tmp_path / "CLAUDE.md").write_text(
        '# Project Rules\n\n'
        '- No emojis\n'
        '- Type hints required\n'
    )

    return tmp_path
