"""Pattern dataclasses representing the architectural DNA of a codebase.

Each dataclass captures a specific category of patterns detected by
tree-sitter AST analysis. CodebaseDNA is the top-level container.
InterviewAnswers holds tribal knowledge captured via guided interview.
"""
from dataclasses import asdict, dataclass, field
from typing import Dict, List, Optional


@dataclass
class InterviewAnswers:
    """Tribal knowledge captured via guided interview.

    Static analysis cannot detect this content -- it requires a human.
    Cached to .saar/config.json so re-runs don't re-ask.
    """
    # universal (quick mode -- always asked)
    project_purpose: Optional[str] = None     # one-line description for role prompt
    never_do: Optional[str] = None            # absolute rules, accumulated corrections
    domain_terms: Optional[str] = None        # vocabulary with project-specific meanings
    verify_workflow: Optional[str] = None     # how to verify changes actually work

    # full mode extras
    auth_gotchas: Optional[str] = None        # auth-specific anti-patterns
    off_limits: Optional[str] = None          # files/modules AI must never touch
    extra_context: Optional[str] = None       # anything else the developer wants captured


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
class FrontendPattern:
    """Detected frontend stack patterns from package.json analysis."""
    framework: Optional[str] = None          # next, react, vue, nuxt, svelte, astro
    test_framework: Optional[str] = None     # vitest, jest, playwright, cypress
    test_command: Optional[str] = None       # e.g. "bun run test", "npx vitest"
    component_library: Optional[str] = None  # shadcn/ui, mui, chakra, antd
    state_management: Optional[str] = None   # tanstack-query, zustand, redux
    styling: Optional[str] = None           # tailwind, styled-components, emotion
    package_manager: Optional[str] = None   # bun, pnpm, yarn, npm
    build_tool: Optional[str] = None        # vite, webpack, turbopack
    language: Optional[str] = None          # typescript, javascript
    # React-specific coding patterns (detected from .tsx/.ts source files)
    uses_react_query: bool = False           # useQuery/useMutation detected in source
    avoids_fetch_in_effect: bool = False     # no raw fetch inside useEffect
    uses_cn_utility: bool = False            # cn() from @/lib/utils for class merging
    canonical_data_hook: Optional[str] = None  # most-used custom data hook
    has_custom_hooks: bool = False           # hooks/ directory with use* files
    shared_types_file: Optional[str] = None # types.ts / types/ directory found


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
    frontend_patterns: Optional[FrontendPattern] = None
    config_patterns: ConfigPattern = field(default_factory=ConfigPattern)
    middleware_patterns: List[str] = field(default_factory=list)
    common_imports: List[str] = field(default_factory=list)
    skip_directories: List[str] = field(default_factory=list)
    api_versioning: Optional[str] = None
    router_pattern: Optional[str] = None
    team_rules: Optional[str] = None
    team_rules_source: Optional[str] = None
    # project structure -- auto-generated directory tree with annotations
    project_structure: Optional[str] = None
    # verify workflow -- auto-detected commands to verify changes work
    verify_workflow: Optional[str] = None
    # interview -- tribal knowledge from guided questions
    interview: Optional[InterviewAnswers] = None
    # style analysis enrichments
    async_adoption_pct: float = 0.0
    type_hint_pct: float = 0.0
    total_functions: int = 0
    total_classes: int = 0
    # dependency graph enrichments
    circular_dependencies: List = field(default_factory=list)
    critical_files: List = field(default_factory=list)
    total_dependencies: int = 0
    # canonical examples -- most-imported file per category (OPE-142)
    # Each entry: {"category": str, "file": str, "import_count": int, "reason": str}
    canonical_examples: List = field(default_factory=list)
    # analysis warnings -- shown in detection summary (e.g. file limit hit)
    analysis_warnings: List[str] = field(default_factory=list)
    # deep extraction rules -- rules WITH reasoning, not just labels (OPE-96)
    # Each entry is a DeepRule-like dict: {text, confidence, category, evidence}
    deep_rules: List = field(default_factory=list)

    def to_dict(self) -> Dict:
        return asdict(self)
