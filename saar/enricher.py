"""AI enrichment engine for tribal knowledge.

Takes raw developer answers from the guided interview and passes them
through Claude to produce tight, precise, actionable rules.

Why this exists:
    Developers write naturally: "don't touch billing it's messy"
    AI assistants need precision: "NEVER modify `billing/` -- legacy Stripe
    integration, no test coverage, frozen until Q3 migration"

    Same information. 5x more useful. Zero extra developer effort.

This module is optional -- requires ANTHROPIC_API_KEY env var and
the 'anthropic' package (pip install saar[enrich]).
The rest of saar works fine without it.
"""
import json
import logging
import os
from typing import Optional

from saar.models import CodebaseDNA, InterviewAnswers

logger = logging.getLogger(__name__)

# Optional import -- only required for enrichment, not for offline saar usage
try:
    import anthropic as _anthropic_module
except ImportError:
    _anthropic_module = None  # type: ignore[assignment]

# Use Haiku for speed and cost -- this is a transformation task, not reasoning
_MODEL = "claude-haiku-4-5-20251001"

_SYSTEM_PROMPT = """You are an expert technical writer who specializes in writing
AI coding assistant instructions. You transform raw developer notes into precise,
actionable rules that AI coding tools like Claude Code, Cursor, and Copilot can
follow perfectly.

Your job: take messy, informal developer notes and rewrite them as tight,
imperative rules that are:
- Specific and unambiguous (never vague)
- Actionable ("NEVER do X" or "ALWAYS do Y because Z")
- Concise (under 40 words per rule)  
- Use backticks for file paths, function names, and code references
- Include WHY when the reason is non-obvious
- Preserve all technical details -- never omit specifics

You return ONLY valid JSON. No markdown, no explanation, no preamble."""

_USER_PROMPT_TEMPLATE = """Here are raw notes from a developer about their codebase.
Rewrite each section as tight, precise rules an AI coding assistant should follow.

PROJECT: {project_name}
DETECTED STACK: {detected_stack}

RAW NOTES:
{raw_notes}

Return a JSON object with these exact keys (use null for sections with no content):
{{
  "project_purpose": "one crisp sentence describing what this project does and for whom",
  "never_do": "bullet list of NEVER DO rules, one per line, each starting with '- NEVER'",
  "domain_terms": "bullet list of domain definitions, one per line, format: '- `Term` = precise definition'",
  "verify_workflow": "exact command sequence to verify changes work, with actual commands in backticks",
  "auth_gotchas": "bullet list of auth/security rules, or null",
  "off_limits": "bullet list of files/modules AI must not touch, format: '- `path/` -- reason', or null",
  "extra_context": "any other critical rules, or null"
}}

Rules for rewriting:
1. NEVER invent information that wasn't in the raw notes
2. DO expand abbreviations and add precision where the intent is clear
3. DO add backticks around file paths, function names, package names
4. DO convert vague statements to specific imperatives
5. DO merge duplicate or overlapping rules
6. NEVER lose any information -- if in doubt, keep it"""


def _build_raw_notes(answers: InterviewAnswers) -> str:
    """Format interview answers as readable raw notes for the prompt."""
    sections = []

    if answers.project_purpose:
        sections.append(f"PROJECT PURPOSE:\n{answers.project_purpose}")

    if answers.never_do:
        sections.append(f"NEVER DO / GOTCHAS:\n{answers.never_do}")

    if answers.domain_terms:
        sections.append(f"DOMAIN TERMS:\n{answers.domain_terms}")

    if answers.verify_workflow:
        sections.append(f"VERIFICATION WORKFLOW:\n{answers.verify_workflow}")

    if answers.auth_gotchas:
        sections.append(f"AUTH / SECURITY:\n{answers.auth_gotchas}")

    if answers.off_limits:
        sections.append(f"OFF-LIMITS FILES:\n{answers.off_limits}")

    if answers.extra_context:
        sections.append(f"EXTRA CONTEXT:\n{answers.extra_context}")

    return "\n\n".join(sections) if sections else "(no notes provided)"


def _build_detected_stack(dna: Optional[CodebaseDNA]) -> str:
    """Summarize detected stack for the enrichment prompt."""
    if not dna:
        return "unknown"
    parts = []
    if dna.detected_framework:
        parts.append(dna.detected_framework)
    if dna.language_distribution:
        langs = ", ".join(
            f"{lang}" for lang, _ in
            sorted(dna.language_distribution.items(), key=lambda x: -x[1])
        )
        parts.append(langs)
    if dna.database_patterns.orm_used:
        parts.append(dna.database_patterns.orm_used)
    if dna.test_patterns.framework:
        parts.append(dna.test_patterns.framework)
    return " + ".join(parts) if parts else "unknown"


def enrich_answers(
    answers: InterviewAnswers,
    dna: Optional[CodebaseDNA] = None,
    api_key: Optional[str] = None,
) -> tuple[InterviewAnswers, bool]:
    """Pass raw interview answers through Claude to produce tighter rules.

    Returns (enriched_answers, was_enriched).
    was_enriched is False if enrichment was skipped (no API key, import error, etc.).
    Original answers are never modified -- returns a new InterviewAnswers object.
    """
    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        logger.warning(
            "ANTHROPIC_API_KEY not set -- skipping enrichment. "
            "Set the env var or pass api_key to enable AI enrichment."
        )
        return answers, False

    if _anthropic_module is None:
        logger.warning(
            "anthropic package not installed. "
            "Run: pip install saar[enrich]"
        )
        return answers, False

    # check if there's anything to enrich
    raw_notes = _build_raw_notes(answers)
    if raw_notes == "(no notes provided)":
        logger.debug("No interview answers to enrich")
        return answers, False

    project_name = dna.repo_name if dna else "unknown"
    detected_stack = _build_detected_stack(dna)

    user_prompt = _USER_PROMPT_TEMPLATE.format(
        project_name=project_name,
        detected_stack=detected_stack,
        raw_notes=raw_notes,
    )

    try:
        client = _anthropic_module.Anthropic(api_key=key)
        response = client.messages.create(
            model=_MODEL,
            max_tokens=1500,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )

        raw_json = response.content[0].text.strip()

        # strip markdown code fences if Claude added them despite instructions
        if raw_json.startswith("```"):
            raw_json = raw_json.split("```")[1]
            if raw_json.startswith("json"):
                raw_json = raw_json[4:]
            raw_json = raw_json.strip()

        enriched_data = json.loads(raw_json)

        enriched = InterviewAnswers(
            project_purpose=enriched_data.get("project_purpose") or answers.project_purpose,
            never_do=enriched_data.get("never_do") or answers.never_do,
            domain_terms=enriched_data.get("domain_terms") or answers.domain_terms,
            verify_workflow=enriched_data.get("verify_workflow") or answers.verify_workflow,
            auth_gotchas=enriched_data.get("auth_gotchas") or answers.auth_gotchas,
            off_limits=enriched_data.get("off_limits") or answers.off_limits,
            extra_context=enriched_data.get("extra_context") or answers.extra_context,
        )

        logger.debug("Enrichment complete via %s", _MODEL)
        return enriched, True

    except json.JSONDecodeError as e:
        logger.warning("Enrichment returned invalid JSON: %s -- using original answers", e)
        return answers, False
    except Exception as e:
        logger.warning("Enrichment failed: %s -- using original answers", e)
        return answers, False
