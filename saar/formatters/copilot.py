"""GitHub Copilot custom instructions formatter.

Outputs DNA as a copilot-instructions.md file. GitHub expects this
at .github/copilot-instructions.md. Format is plain markdown with
imperative instructions -- similar to CLAUDE.md but Copilot parses
it differently (no hierarchy, single file).
"""
from saar.models import CodebaseDNA


def render_copilot(dna: CodebaseDNA) -> str:
    """Render DNA as a copilot-instructions.md file."""
    lines = [f"# Copilot Instructions -- {dna.repo_name}\n"]

    if dna.detected_framework:
        lines.append(f"This project uses {dna.detected_framework}.\n")

    # -- conventions --
    lines.append("## Conventions\n")
    nc = dna.naming_conventions
    rules = []
    if nc.function_style != "unknown":
        rules.append(f"Functions use `{nc.function_style}`")
    if nc.class_style != "unknown":
        rules.append(f"Classes use `{nc.class_style}`")
    if nc.file_style != "unknown":
        rules.append(f"Files use `{nc.file_style}`")
    for r in rules:
        lines.append(f"- {r}")

    # -- architecture --
    sp = dna.service_patterns
    ap = dna.auth_patterns
    if sp.singleton_services or ap.middleware_used:
        lines.append("\n## Architecture\n")
        if sp.singleton_services:
            lines.append(f"Services are singletons: {', '.join(sp.singleton_services)}.")
        if sp.dependencies_file:
            lines.append(f"Service wiring is in `{sp.dependencies_file}`.")
        if ap.middleware_used:
            lines.append(f"Authentication uses {', '.join(ap.middleware_used)}.")
        if ap.auth_context_type:
            lines.append(f"Auth context type is `{ap.auth_context_type}`.")

    # -- database --
    db = dna.database_patterns
    if db.orm_used:
        lines.append("\n## Database\n")
        lines.append(f"ORM: {db.orm_used}. IDs are `{db.id_type}`. "
                      f"Timestamps are `{db.timestamp_type}`.")
        if db.has_rls:
            lines.append("Row Level Security is enabled.")

    # -- error handling --
    ep = dna.error_patterns
    if ep.exception_classes or ep.http_exception_usage:
        lines.append("\n## Error Handling\n")
        if ep.exception_classes:
            lines.append(f"Use existing exceptions: {', '.join(ep.exception_classes)}.")
        if ep.http_exception_usage:
            lines.append("Use HTTPException for API errors.")
        if ep.logging_on_error:
            lines.append("Always log exceptions before re-raising.")

    # -- testing --
    tp = dna.test_patterns
    if tp.framework:
        lines.append("\n## Testing\n")
        lines.append(f"Use {tp.framework}. Test files match `{tp.test_file_pattern}`.")
        if tp.mock_library:
            lines.append(f"Use {tp.mock_library} for mocking.")

    # -- team rules --
    if dna.team_rules:
        lines.append("\n## Team Rules\n")
        lines.append(dna.team_rules)

    return "\n".join(lines) + "\n"
