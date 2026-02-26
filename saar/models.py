"""Pattern dataclasses representing the architectural DNA of a codebase.

Each dataclass captures a specific category of patterns detected by
tree-sitter AST analysis. CodebaseDNA is the top-level container.
"""
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional


@dataclass
class AuthPattern:
    """Detected authentication patterns."""
    middleware_used: List[str] = field(default_factory=list)
    auth_decorators: List[str] = field(default_factory=list)
    ownership_checks: List[str] = field(default_factory=list)
    auth_context_type: Optional[str] = None


@dataclass
class ServicePattern:
    """Detected service layer patterns."""
    singleton_services: List[str] = field(default_factory=list)
    dependencies_file: Optional[str] = None
    service_base_classes: List[str] = field(default_factory=list)
    injection_pattern: Optional[str] = None


@dataclass
class DatabasePattern:
    """Detected database patterns."""
    orm_used: Optional[str] = None
    connection_pattern: Optional[str] = None
    has_rls: bool = False
    id_type: str = "unknown"
    timestamp_type: str = "unknown"
    cascade_deletes: bool = False


@dataclass
class ErrorPattern:
    """Detected error handling patterns."""
    exception_classes: List[str] = field(default_factory=list)
    http_exception_usage: bool = False
    error_response_format: Optional[str] = None
    logging_on_error: bool = False


@dataclass
class LoggingPattern:
    """Detected logging patterns."""
    logger_import: Optional[str] = None
    log_levels_used: List[str] = field(default_factory=list)
    structured_logging: bool = False
    metrics_tracking: bool = False


@dataclass
class NamingConventions:
    """Detected naming conventions."""
    function_style: str = "unknown"
    class_style: str = "unknown"
    constant_style: str = "unknown"
    file_style: str = "unknown"


@dataclass
class TestPattern:
    """Detected testing patterns."""
    framework: Optional[str] = None
    fixture_style: Optional[str] = None
    mock_library: Optional[str] = None
    test_file_pattern: str = "test_*.py"
    has_conftest: bool = False
    has_factories: bool = False
    coverage_config: bool = False


@dataclass
class ConfigPattern:
    """Detected configuration patterns."""
    env_loading: Optional[str] = None
    settings_pattern: Optional[str] = None
    secrets_handling: Optional[str] = None
    config_validation: bool = False


@dataclass
class CodebaseDNA:
    """Complete DNA profile of a codebase."""
    repo_name: str
    detected_framework: Optional[str] = None
    language_distribution: Dict[str, int] = field(default_factory=dict)
    auth_patterns: AuthPattern = field(default_factory=AuthPattern)
    service_patterns: ServicePattern = field(default_factory=ServicePattern)
    database_patterns: DatabasePattern = field(default_factory=DatabasePattern)
    error_patterns: ErrorPattern = field(default_factory=ErrorPattern)
    logging_patterns: LoggingPattern = field(default_factory=LoggingPattern)
    naming_conventions: NamingConventions = field(default_factory=NamingConventions)
    test_patterns: TestPattern = field(default_factory=TestPattern)
    config_patterns: ConfigPattern = field(default_factory=ConfigPattern)
    middleware_patterns: List[str] = field(default_factory=list)
    common_imports: List[str] = field(default_factory=list)
    skip_directories: List[str] = field(default_factory=list)
    api_versioning: Optional[str] = None
    router_pattern: Optional[str] = None
    team_rules: Optional[str] = None
    team_rules_source: Optional[str] = None

    def to_dict(self) -> Dict:
        return asdict(self)
