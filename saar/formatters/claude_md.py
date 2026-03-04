"""CLAUDE.md formatter.

Outputs DNA in the format Claude Code expects: imperative instructions,
structured sections, actionable rules. Kept under ~300 lines per
Anthropic's recommendation for CLAUDE.md files.
"""
from saar.models import CodebaseDNA
from saar.formatters._tribal import render_tribal_knowledge
from saar.formatters.agents_md import _clean_team_rules


def render_claude_md(dna: CodebaseDNA) -> str:
    """Render DNA as a CLAUDE.md file."""
    lines = [f"# CLAUDE.md -- {dna.repo_name}\n"]

    if dna.detected_framework:
        lines.append(f"This is a {dna.detected_framework} project.\n")

    # -- codebase stats --
    if dna.total_functions or dna.total_classes:
        lines.append(f"{dna.total_functions:,} functions, {dna.total_classes:,} classes.")
        if dna.async_adoption_pct > 0:
            lines.append(f"Async adoption: {dna.async_adoption_pct:.0f}%.")
        if dna.type_hint_pct > 0:
            lines.append(f"Type hint coverage: {dna.type_hint_pct:.0f}%.")
        lines.append("")

    # -- frontend stack --
    fp = dna.frontend_patterns
    if fp:
        lines.append("\n## Frontend\n")
        stack_parts = []
        if fp.framework:
            stack_parts.append(fp.framework)
        if fp.language:
            stack_parts.append(fp.language)
        if fp.build_tool:
            stack_parts.append(fp.build_tool)
        if stack_parts:
            lines.append(f"**Stack:** {' + '.join(stack_parts)}")
        if fp.package_manager:
            pm = fp.package_manager
            lines.append(f"- Package manager: `{pm}` -- always use `{pm} install`, never npm/yarn")
        if fp.component_library:
            lines.append(f"- Component library: {fp.component_library} -- use over custom components")
        if fp.state_management:
            lines.append(f"- State management: {fp.state_management}")
        if fp.styling:
            lines.append(f"- Styling: {fp.styling} -- no raw CSS files")
        if fp.test_framework:
            test_line = f"- Frontend tests: {fp.test_framework}"
            if fp.test_command:
                test_line += f" (`{fp.test_command}`)"
            lines.append(test_line)

    # -- coding conventions as imperative rules --
    lines.append("## Coding Conventions\n")
    nc = dna.naming_conventions
    if nc.function_style != "unknown":
        lines.append(f"- Use `{nc.function_style}` for function names")
    if nc.class_style != "unknown":
        lines.append(f"- Use `{nc.class_style}` for class names")
    if nc.constant_style != "unknown":
        lines.append(f"- Use `{nc.constant_style}` for constants")
    if nc.file_style != "unknown":
        lines.append(f"- Use `{nc.file_style}` for file names")

    if dna.common_imports:
        lines.append("\nPreferred imports:")
        lines.append("```")
        for imp in dna.common_imports[:10]:
            lines.append(imp)
        lines.append("```")

    # -- logging conventions --
    lp = dna.logging_patterns
    if lp.logger_import or lp.log_levels_used:
        lines.append("\n## Logging\n")
        if lp.logger_import:
            lines.append(f"- Use `{lp.logger_import}` for all logging, never `print()`")
        if lp.structured_logging:
            lines.append("- Use structured logging (JSON format)")

    # -- critical files / project structure --
    if dna.critical_files:
        lines.append("\n## Critical Files\n")
        lines.append("These files have the most dependents -- understand them before editing:\n")
        for cf in dna.critical_files[:8]:
            f = cf.get("file", "") if isinstance(cf, dict) else cf
            d = cf.get("dependents", 0) if isinstance(cf, dict) else 0
            if f:
                dep_note = f" ({d} dependents)" if d else ""
                lines.append(f"- `{f}`{dep_note}")

    # -- architecture rules --
    if dna.service_patterns.singleton_services or dna.auth_patterns.middleware_used:
        lines.append("\n## Architecture Rules\n")

    sp = dna.service_patterns
    if sp.singleton_services:
        lines.append(f"- Services are singletons: `{', '.join(sp.singleton_services)}`")
    if sp.dependencies_file:
        lines.append(f"- Service wiring lives in `{sp.dependencies_file}`")
    if sp.injection_pattern:
        lines.append(f"- Use {sp.injection_pattern} for dependency injection")

    ap = dna.auth_patterns
    if ap.middleware_used:
        lines.append(f"- Auth middleware: `{', '.join(ap.middleware_used)}`")
    if ap.auth_decorators:
        lines.append(f"- Auth decorators: `{', '.join(ap.auth_decorators)}`")
    if ap.auth_context_type:
        lines.append(f"- Auth context type: `{ap.auth_context_type}`")

    # -- database rules --
    db = dna.database_patterns
    if db.orm_used:
        lines.append("\n## Database Conventions\n")
        lines.append(f"- ORM: {db.orm_used}")
        lines.append(f"- Primary key type: `{db.id_type}`")
        lines.append(f"- Timestamp type: `{db.timestamp_type}`")
        if db.has_rls:
            lines.append("- Row Level Security is enabled -- respect RLS policies")
        if db.cascade_deletes:
            lines.append("- Use cascade deletes for parent-child relationships")

    # -- error handling rules --
    ep = dna.error_patterns
    if ep.exception_classes or ep.http_exception_usage or ep.logging_on_error:
        lines.append("\n## Error Handling\n")
        if ep.exception_classes:
            lines.append(f"- Use existing exceptions: `{', '.join(ep.exception_classes)}`")
        if ep.http_exception_usage:
            lines.append("- Use HTTPException for API error responses")
        if ep.logging_on_error:
            lines.append("- Always log exceptions before re-raising")

    # -- testing rules --
    tp = dna.test_patterns
    if tp.framework:
        lines.append("\n## Testing\n")
        lines.append(f"- Framework: {tp.framework}")
        lines.append(f"- Test file pattern: `{tp.test_file_pattern}`")
        if tp.fixture_style:
            lines.append(f"- Fixture style: {tp.fixture_style}")
        if tp.mock_library:
            lines.append(f"- Mock with: {tp.mock_library}")
        if tp.has_conftest:
            lines.append("- Shared fixtures live in `conftest.py`")
        lines.append("- Run: `pytest tests/ -v`")

    # -- API patterns --
    if dna.api_versioning or dna.router_pattern:
        lines.append("\n## API Patterns\n")
        if dna.api_versioning:
            lines.append(f"- API versioning: `{dna.api_versioning}`")
        if dna.router_pattern:
            lines.append(f"- Router pattern: `{dna.router_pattern}`")

    # -- dependency warnings --
    if dna.circular_dependencies:
        lines.append("\n## Circular Dependencies (fix these)\n")
        for pair in dna.circular_dependencies[:5]:
            lines.append(f"- `{pair[0]}` <-> `{pair[1]}`")

    # -- tribal knowledge from guided interview (highest value content) --
    tribal = render_tribal_knowledge(dna.interview)
    if tribal:
        lines.append(tribal)

    # -- team rules (human-written sections only) --
    if dna.team_rules:
        cleaned = _clean_team_rules(dna.team_rules)
        if cleaned:
            lines.append("\n## Team Rules\n")
            if dna.team_rules_source:
                lines.append(f"*Imported from `{dna.team_rules_source}`*\n")
            lines.append(cleaned)

    return "\n".join(lines) + "\n"
