"""Generic markdown DNA output.

Renders a structured markdown document showing all detected
patterns. Used for stdout display and as the base format.
"""
from saar.models import CodebaseDNA


def render_markdown(dna: CodebaseDNA) -> str:
    """Render DNA as a structured markdown document."""
    md = f"# Codebase DNA: {dna.repo_name}\n\n"

    if dna.detected_framework:
        md += f"**Framework:** {dna.detected_framework}\n\n"

    md += _section_languages(dna)
    md += _section_codebase_stats(dna)
    md += _section_auth(dna)
    md += _section_services(dna)
    md += _section_database(dna)
    md += _section_errors(dna)
    md += _section_logging(dna)
    md += _section_naming(dna)
    md += _section_imports(dna)
    md += _section_api(dna)
    md += _section_tests(dna)
    md += _section_config(dna)
    md += _section_dependency_insights(dna)
    md += _section_team_rules(dna)

    return md


def _section_languages(dna: CodebaseDNA) -> str:
    if not dna.language_distribution:
        return ""
    out = "## Language Distribution\n"
    for lang, count in sorted(dna.language_distribution.items(), key=lambda x: -x[1]):
        out += f"- {lang}: {count} files\n"
    return out + "\n"


def _section_codebase_stats(dna: CodebaseDNA) -> str:
    if not (dna.total_functions or dna.total_classes):
        return ""
    out = "## Codebase Stats\n"
    out += f"**Functions:** {dna.total_functions:,} | **Classes:** {dna.total_classes:,}\n"
    if dna.async_adoption_pct > 0:
        out += f"**Async Adoption:** {dna.async_adoption_pct:.0f}%\n"
    if dna.type_hint_pct > 0:
        out += f"**Type Hint Coverage:** {dna.type_hint_pct:.0f}%\n"
    if dna.total_dependencies > 0:
        out += f"**Internal Dependencies:** {dna.total_dependencies:,}\n"
    return out + "\n"


def _section_dependency_insights(dna: CodebaseDNA) -> str:
    parts: list = []
    if dna.critical_files:
        parts.append("## Critical Files (highest dependents)\n")
        for item in dna.critical_files[:5]:
            parts.append(f"- `{item.get('file', '?')}` ({item.get('dependents', 0)} dependents)\n")
        parts.append("\n")
    if dna.circular_dependencies:
        parts.append(f"## Circular Dependencies ({len(dna.circular_dependencies)})\n")
        for pair in dna.circular_dependencies[:10]:
            parts.append(f"- `{pair[0]}` <-> `{pair[1]}`\n")
        parts.append("\n")
    return "".join(parts)


def _section_auth(dna: CodebaseDNA) -> str:
    ap = dna.auth_patterns
    if not (ap.middleware_used or ap.auth_decorators or ap.ownership_checks):
        return ""
    out = "## Authentication Patterns\n"
    if ap.middleware_used:
        out += f"**Middleware:** `{', '.join(ap.middleware_used)}`\n"
    if ap.auth_decorators:
        out += f"**Decorators:** `{', '.join(ap.auth_decorators)}`\n"
    if ap.ownership_checks:
        out += f"**Ownership Checks:** `{', '.join(ap.ownership_checks)}`\n"
    if ap.auth_context_type:
        out += f"**Auth Context:** `{ap.auth_context_type}`\n"
    return out + "\n"


def _section_services(dna: CodebaseDNA) -> str:
    sp = dna.service_patterns
    if not (sp.singleton_services or sp.dependencies_file):
        return ""
    out = "## Service Layer\n"
    if sp.singleton_services:
        out += f"**Singletons:** `{', '.join(sp.singleton_services)}`\n"
    if sp.dependencies_file:
        out += f"**Dependencies File:** `{sp.dependencies_file}`\n"
    if sp.injection_pattern:
        out += f"**Injection:** {sp.injection_pattern}\n"
    return out + "\n"


def _section_database(dna: CodebaseDNA) -> str:
    db = dna.database_patterns
    if not db.orm_used:
        return ""
    out = "## Database Patterns\n"
    out += f"**ORM:** {db.orm_used}\n"
    out += f"**ID Type:** `{db.id_type}` | **Timestamps:** `{db.timestamp_type}`\n"
    if db.has_rls:
        out += "**Row Level Security:** enabled\n"
    if db.cascade_deletes:
        out += "**Cascade Deletes:** yes\n"
    return out + "\n"


def _section_errors(dna: CodebaseDNA) -> str:
    ep = dna.error_patterns
    if not (ep.exception_classes or ep.http_exception_usage):
        return ""
    out = "## Error Handling\n"
    if ep.exception_classes:
        out += f"**Exceptions:** `{', '.join(ep.exception_classes)}`\n"
    out += f"**HTTP Exception:** {'yes' if ep.http_exception_usage else 'no'}\n"
    out += f"**Logs Errors:** {'yes' if ep.logging_on_error else 'no'}\n"
    return out + "\n"


def _section_logging(dna: CodebaseDNA) -> str:
    lp = dna.logging_patterns
    if not lp.logger_import:
        return ""
    out = "## Logging\n"
    out += f"**Import:** `{lp.logger_import}`\n"
    if lp.log_levels_used:
        out += f"**Levels:** {', '.join(lp.log_levels_used)}\n"
    if lp.structured_logging:
        out += "**Structured logging:** yes\n"
    return out + "\n"


def _section_naming(dna: CodebaseDNA) -> str:
    nc = dna.naming_conventions
    out = "## Naming Conventions\n"
    out += f"- Functions: `{nc.function_style}`\n"
    out += f"- Classes: `{nc.class_style}`\n"
    out += f"- Constants: `{nc.constant_style}`\n"
    out += f"- Files: `{nc.file_style}`\n"
    return out + "\n"


def _section_imports(dna: CodebaseDNA) -> str:
    if not dna.common_imports:
        return ""
    out = "## Common Imports\n```python\n"
    for imp in dna.common_imports[:15]:
        out += f"{imp}\n"
    return out + "```\n\n"


def _section_api(dna: CodebaseDNA) -> str:
    if not (dna.api_versioning or dna.router_pattern):
        return ""
    out = "## API Patterns\n"
    if dna.api_versioning:
        out += f"**Versioning:** `{dna.api_versioning}`\n"
    if dna.router_pattern:
        out += f"**Router:** `{dna.router_pattern}`\n"
    return out + "\n"


def _section_tests(dna: CodebaseDNA) -> str:
    tp = dna.test_patterns
    if not tp.framework:
        return ""
    out = "## Testing\n"
    out += f"**Framework:** {tp.framework}\n"
    if tp.fixture_style:
        out += f"**Fixtures:** {tp.fixture_style}\n"
    if tp.mock_library:
        out += f"**Mocking:** {tp.mock_library}\n"
    out += f"**Pattern:** `{tp.test_file_pattern}`\n"
    return out + "\n"


def _section_config(dna: CodebaseDNA) -> str:
    cp = dna.config_patterns
    if not (cp.env_loading or cp.settings_pattern):
        return ""
    out = "## Configuration\n"
    if cp.env_loading:
        out += f"**Env Loading:** {cp.env_loading}\n"
    if cp.settings_pattern:
        out += f"**Settings:** {cp.settings_pattern}\n"
    if cp.secrets_handling:
        out += f"**Secrets:** {cp.secrets_handling}\n"
    return out + "\n"


def _section_team_rules(dna: CodebaseDNA) -> str:
    if not dna.team_rules:
        return ""
    out = "## Team Rules\n"
    if dna.team_rules_source:
        out += f"*Source: `{dna.team_rules_source}`*\n\n"
    out += dna.team_rules + "\n"
    return out
