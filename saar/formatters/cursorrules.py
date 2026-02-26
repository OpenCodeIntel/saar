"""Cursor rules formatter.

Outputs DNA as a .cursorrules file. Cursor expects plain text
instructions -- no YAML frontmatter in the legacy format.
Modern .cursor/rules/ uses .mdc but we target the simpler
root .cursorrules for maximum compatibility.
"""
from saar.models import CodebaseDNA


def render_cursorrules(dna: CodebaseDNA) -> str:
    """Render DNA as a .cursorrules file."""
    lines = [f"# Project: {dna.repo_name}\n"]

    if dna.detected_framework:
        lines.append(f"This is a {dna.detected_framework} project.\n")

    # -- style rules --
    lines.append("## Style Rules\n")
    nc = dna.naming_conventions
    if nc.function_style != "unknown":
        lines.append(f"- Name functions in {nc.function_style}")
    if nc.class_style != "unknown":
        lines.append(f"- Name classes in {nc.class_style}")
    if nc.file_style != "unknown":
        lines.append(f"- Name files in {nc.file_style}")

    # -- architecture --
    sp = dna.service_patterns
    ap = dna.auth_patterns
    db = dna.database_patterns
    has_arch = sp.singleton_services or ap.middleware_used or db.orm_used

    if has_arch:
        lines.append("\n## Architecture\n")
        if sp.singleton_services:
            lines.append(f"- Services are singletons: {', '.join(sp.singleton_services)}")
        if sp.dependencies_file:
            lines.append(f"- Wire services in {sp.dependencies_file}")
        if ap.middleware_used:
            lines.append(f"- Auth uses: {', '.join(ap.middleware_used)}")
        if ap.auth_decorators:
            lines.append(f"- Auth decorators: {', '.join(ap.auth_decorators)}")
        if db.orm_used:
            lines.append(f"- Database: {db.orm_used}, IDs are {db.id_type}")
        if db.has_rls:
            lines.append("- RLS is enabled, respect row-level policies")

    # -- error handling --
    ep = dna.error_patterns
    if ep.exception_classes or ep.http_exception_usage:
        lines.append("\n## Error Handling\n")
        if ep.exception_classes:
            lines.append(f"- Use: {', '.join(ep.exception_classes)}")
        if ep.http_exception_usage:
            lines.append("- Raise HTTPException for API errors")
        if ep.logging_on_error:
            lines.append("- Log before re-raising")

    # -- testing --
    tp = dna.test_patterns
    if tp.framework:
        lines.append("\n## Testing\n")
        lines.append(f"- Framework: {tp.framework}")
        lines.append(f"- Pattern: {tp.test_file_pattern}")
        if tp.mock_library:
            lines.append(f"- Mocking: {tp.mock_library}")

    # -- imports --
    if dna.common_imports:
        lines.append("\n## Common Imports\n")
        for imp in dna.common_imports[:10]:
            lines.append(f"- {imp}")

    # -- team rules --
    if dna.team_rules:
        lines.append("\n## Team Rules\n")
        lines.append(dna.team_rules)

    return "\n".join(lines) + "\n"
