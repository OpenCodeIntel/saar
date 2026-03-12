"""Cursor .mdc rule formatter (OPE-143).

Generates .cursor/rules/*.mdc files with YAML frontmatter and glob-based
conditional loading. This is the Cursor v2 format, strictly better than
flat .cursorrules because rules load only when editing matching files.

Why this matters:
  .cursorrules loads ALL rules for every file.
  .mdc loads ONLY the rules relevant to the file being edited.
  A Python backend rule never loads when editing a React component.
  Shorter context = more precise AI behavior.

.mdc format:
  ---
  description: Short summary shown in Cursor UI
  globs: ["**/*.py"]    # only load for Python files
  alwaysApply: false    # true = load regardless of file
  ---
  # Rule content here (markdown)

Output: dict[filename, content] where filename is relative to .cursor/rules/
  e.g. {"backend.mdc": "---\\n...", "frontend.mdc": "---\\n..."}

The CLI writes each entry to .cursor/rules/<filename>.
"""
from __future__ import annotations

from saar.models import CodebaseDNA


def _frontmatter(description: str, globs: list[str], always: bool = False) -> str:
    """Build YAML frontmatter block for a .mdc file."""
    lines = ["---", f"description: {description}"]
    if globs:
        # Cursor expects a JSON array in the globs field
        glob_str = ", ".join(f'"{g}"' for g in globs)
        lines.append(f"globs: [{glob_str}]")
    lines.append(f"alwaysApply: {'true' if always else 'false'}")
    lines.append("---")
    return "\n".join(lines)


def render_cursor_mdc(dna: CodebaseDNA) -> dict[str, str]:
    """Render DNA as a set of .mdc rule files for .cursor/rules/.

    Returns a dict mapping filename -> file content.
    Each .mdc file targets a specific part of the codebase via globs.
    """
    files: dict[str, str] = {}

    fp = dna.frontend_patterns
    has_python = dna.language_distribution.get("python", 0) > 0
    has_ts = dna.language_distribution.get("typescript", 0) > 0
    has_js = dna.language_distribution.get("javascript", 0) > 0

    # ── core.mdc -- always loaded, project-level rules ────────────────────
    core_lines: list[str] = []

    if dna.detected_framework:
        core_lines.append(f"This is a **{dna.detected_framework}** project.\n")

    # verify workflow -- always relevant
    if dna.verify_workflow:
        core_lines.append("## How to Verify Changes\n")
        core_lines.append(dna.verify_workflow)
        core_lines.append("\nRun these before considering any change done.\n")

    # package manager
    if fp and fp.package_manager:
        core_lines.append("## Package Manager\n")
        core_lines.append(
            f"- Always use `{fp.package_manager}` — never npm or yarn"
        )

    # deep rules that are always relevant (never_do, auth)
    deep_rules = getattr(dna, "deep_rules", [])
    never_do = [r for r in deep_rules if r.get("category") == "never_do"]
    if never_do:
        core_lines.append("\n## Never Do\n")
        for r in never_do[:5]:
            core_lines.append(f"- {r['text']}")

    # team rules
    if dna.team_rules:
        core_lines.append("\n## Project-Specific Rules\n")
        core_lines.append(dna.team_rules.strip())

    if core_lines:
        content = _frontmatter(
            f"{dna.repo_name} project rules",
            globs=[],
            always=True,
        )
        content += "\n\n" + "\n".join(core_lines).strip() + "\n"
        files["core.mdc"] = content

    # ── backend.mdc -- Python files only ─────────────────────────────────
    if has_python:
        backend_lines: list[str] = []
        backend_globs = ["**/*.py"]

        # auth deep rules
        auth_deep = [r for r in deep_rules if r.get("category") == "auth"]
        if auth_deep:
            backend_lines.append("## Auth\n")
            for r in auth_deep[:3]:
                backend_lines.append(f"- {r['text']}")

        # exception rules
        exc_deep = [r for r in deep_rules if r.get("category") == "exceptions"]
        ep = dna.error_patterns
        if exc_deep or ep.exception_classes:
            backend_lines.append("\n## Error Handling\n")
            for r in exc_deep[:2]:
                backend_lines.append(f"- {r['text']}")
            if ep.exception_classes and not exc_deep:
                all_exc = ep.exception_classes
                if len(all_exc) <= 10:
                    backend_lines.append(
                        f"- Use domain exceptions: `{', '.join(all_exc)}`"
                    )
                else:
                    top = all_exc[:8]
                    backend_lines.append(
                        f"- Use domain exceptions ({len(all_exc)} total). "
                        f"Top: `{', '.join(top)}`"
                    )
            if ep.http_exception_usage:
                backend_lines.append("- Raise `HTTPException` for API errors")
            if ep.logging_on_error:
                backend_lines.append("- Log before re-raising")

        # database
        db = dna.database_patterns
        if db.orm_used:
            backend_lines.append("\n## Database\n")
            backend_lines.append(f"- ORM: {db.orm_used}")
            if db.id_type != "unknown":
                backend_lines.append(f"- ID type: `{db.id_type}`")
            if db.has_rls:
                backend_lines.append("- RLS enabled — always respect row-level policies")

        # naming
        nc = dna.naming_conventions
        if nc.function_style != "unknown":
            backend_lines.append("\n## Naming\n")
            backend_lines.append(f"- Functions: `{nc.function_style}`")
            if nc.class_style != "unknown":
                backend_lines.append(f"- Classes: `{nc.class_style}`")

        # testing deep rules
        test_deep = [r for r in deep_rules if r.get("category") == "testing"]
        tp = dna.test_patterns
        if tp.framework or test_deep:
            backend_lines.append("\n## Testing\n")
            if tp.framework:
                backend_lines.append(f"- Framework: `{tp.framework}` — pattern `{tp.test_file_pattern}`")
            for r in test_deep[:2]:
                backend_lines.append(f"- {r['text']}")

        # logging
        lp = dna.logging_patterns
        if lp.logger_import:
            backend_lines.append("\n## Logging\n")
            backend_lines.append(f"- Use `{lp.logger_import}` — never bare `print()`")

        if backend_lines:
            content = _frontmatter(
                "Python backend rules",
                globs=backend_globs,
            )
            content += "\n\n" + "\n".join(backend_lines).strip() + "\n"
            files["backend.mdc"] = content

    # ── frontend.mdc -- TypeScript/JavaScript files ───────────────────────
    if (has_ts or has_js) and fp:
        fe_lines: list[str] = []
        fe_globs = []
        if has_ts:
            fe_globs += ["**/*.ts", "**/*.tsx"]
        if has_js:
            fe_globs += ["**/*.js", "**/*.jsx"]

        if fp.framework:
            fe_lines.append("## Framework\n")
            fe_lines.append(f"- {fp.framework}")
            if fp.component_library:
                fe_lines.append(
                    f"- Use `{fp.component_library}` components over custom ones"
                )
            if fp.state_management:
                fe_lines.append(f"- State: {fp.state_management}")
            if fp.uses_react_query:
                fe_lines.append(
                    "- Data fetching: use `useQuery`/`useMutation` — never raw `fetch` in useEffect"
                )

        # naming deep rules for frontend
        naming_deep = [r for r in deep_rules if r.get("category") == "naming"]
        if naming_deep:
            fe_lines.append("\n## Naming\n")
            for r in naming_deep[:3]:
                fe_lines.append(f"- {r['text']}")

        # frontend testing
        if fp.test_framework:
            fe_lines.append("\n## Testing\n")
            fe_lines.append(f"- Framework: `{fp.test_framework}`")

        if fe_lines:
            content = _frontmatter(
                "Frontend TypeScript/React rules",
                globs=fe_globs,
            )
            content += "\n\n" + "\n".join(fe_lines).strip() + "\n"
            files["frontend.mdc"] = content

    # ── tests.mdc -- test files only ──────────────────────────────────────
    test_globs: list[str] = []
    if has_python:
        test_globs.append("**/test_*.py")
        test_globs.append("**/*_test.py")
    if has_ts or has_js:
        test_globs.append("**/*.test.ts")
        test_globs.append("**/*.test.tsx")
        test_globs.append("**/*.spec.ts")

    test_deep = [r for r in deep_rules if r.get("category") == "testing"]
    tp = dna.test_patterns

    if test_globs and (test_deep or tp.framework):
        test_lines: list[str] = ["## Testing Rules\n"]
        if tp.framework:
            test_lines.append(f"- Framework: `{tp.framework}`")
        if tp.has_conftest:
            test_lines.append("- Shared fixtures in `conftest.py` — use pytest fixtures, not setUp/tearDown")
        for r in test_deep[:4]:
            if "conftest" not in r["text"].lower() or not tp.has_conftest:
                test_lines.append(f"- {r['text']}")
        if tp.mock_library:
            test_lines.append(f"- Mocking: `{tp.mock_library}`")

        content = _frontmatter(
            "Test file rules",
            globs=test_globs,
        )
        content += "\n\n" + "\n".join(test_lines).strip() + "\n"
        files["tests.mdc"] = content

    return files
