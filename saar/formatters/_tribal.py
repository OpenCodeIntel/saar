"""Shared renderer for tribal knowledge section.

Used by all formatters that support interview answers.
Tribal knowledge is the highest-value content in any context file --
it captures what static analysis cannot: gotchas, domain terms,
verification workflows, and accumulated corrections.
"""
from saar.models import InterviewAnswers
from typing import Optional


def render_tribal_knowledge(interview: Optional[InterviewAnswers]) -> str:
    """Render interview answers as a Tribal Knowledge section.

    Returns empty string if no answers were provided -- formatters
    should only include this section when there's actual content.
    """
    if not interview:
        return ""

    # check if there's anything meaningful to render
    fields = [
        interview.project_purpose,
        interview.never_do,
        interview.domain_terms,
        interview.verify_workflow,
        interview.auth_gotchas,
        interview.off_limits,
        interview.extra_context,
    ]
    if not any(fields):
        return ""

    lines = ["\n## Tribal Knowledge\n"]
    lines.append("*Captured via `saar` interview -- human knowledge static analysis cannot detect.*\n")

    if interview.project_purpose:
        lines.append(f"**This project:** {interview.project_purpose}\n")

    if interview.never_do:
        lines.append("### Never Do\n")
        # normalize: if it looks like a list already, preserve it
        # otherwise render as a block
        content = interview.never_do.strip()
        if not content.startswith("-") and not content.startswith("*"):
            # wrap plain text as a blockquote so it's visually distinct
            for line in content.splitlines():
                if line.strip():
                    lines.append(f"- {line.strip()}")
        else:
            lines.append(content)
        lines.append("")

    if interview.domain_terms:
        lines.append("### Domain Vocabulary\n")
        content = interview.domain_terms.strip()
        if not content.startswith("-") and not content.startswith("*"):
            for line in content.splitlines():
                if line.strip():
                    lines.append(f"- {line.strip()}")
        else:
            lines.append(content)
        lines.append("")

    if interview.verify_workflow:
        lines.append("### Verification Workflow\n")
        lines.append(interview.verify_workflow.strip())
        lines.append("")

    if interview.auth_gotchas:
        lines.append("### Auth / Security Gotchas\n")
        content = interview.auth_gotchas.strip()
        if not content.startswith("-") and not content.startswith("*"):
            for line in content.splitlines():
                if line.strip():
                    lines.append(f"- {line.strip()}")
        else:
            lines.append(content)
        lines.append("")

    if interview.off_limits:
        lines.append("### Off-Limits Files\n")
        lines.append("> AI must never modify these:\n")
        content = interview.off_limits.strip()
        if not content.startswith("-") and not content.startswith("*"):
            for line in content.splitlines():
                if line.strip():
                    lines.append(f"- `{line.strip()}`")
        else:
            lines.append(content)
        lines.append("")

    if interview.extra_context:
        lines.append("### Additional Context\n")
        lines.append(interview.extra_context.strip())
        lines.append("")

    return "\n".join(lines)
