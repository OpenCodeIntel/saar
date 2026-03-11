"""saar init -- bootstrap a new project's AGENTS.md from scratch.

For developers starting a brand new project who don't have code yet.
Also useful for onboarding: "I just cloned this, tell me about it."

The interview is project-setup focused, not convention-focused.
We ask about intent and stack, not about existing patterns.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


STACK_PRESETS: dict[str, dict] = {
    "fastapi": {
        "label": "FastAPI + Python",
        "backend": "FastAPI",
        "language": "Python",
        "test_cmd": "pytest tests/ -v",
        "never_do": "Never use sync functions in async endpoints; never use print() -- use logging",
        "verify": "pytest tests/ -v && uvicorn main:app",
        "conventions": "Type hints on all functions; snake_case for functions; PascalCase for classes",
    },
    "nextjs": {
        "label": "Next.js + TypeScript",
        "backend": "Next.js",
        "language": "TypeScript",
        "test_cmd": "bun run test",
        "never_do": "Never use npm/yarn -- use bun; never use class components -- use hooks",
        "verify": "bun run test && bun run build",
        "conventions": "Functional components only; TanStack Query for data fetching; cn() for classes",
    },
    "django": {
        "label": "Django + Python",
        "backend": "Django",
        "language": "Python",
        "test_cmd": "python manage.py test",
        "never_do": "Never bypass the ORM for writes; never put business logic in views",
        "verify": "python manage.py test && python manage.py check",
        "conventions": "snake_case; models in models.py; fat models, thin views",
    },
    "express": {
        "label": "Express + Node.js",
        "backend": "Express",
        "language": "JavaScript/TypeScript",
        "test_cmd": "npm test",
        "never_do": "Never forget to call next() in middleware; never store secrets in code",
        "verify": "npm test && npm run lint",
        "conventions": "Async/await over callbacks; error-first middleware; REST conventions",
    },
    "flask": {
        "label": "Flask + Python",
        "backend": "Flask",
        "language": "Python",
        "test_cmd": "pytest",
        "never_do": "Never use global state outside app context; never use debug=True in production",
        "verify": "pytest && flask --debug run",
        "conventions": "Blueprints for routes; snake_case; app factory pattern",
    },
    "react": {
        "label": "React + TypeScript (frontend only)",
        "backend": "React",
        "language": "TypeScript",
        "test_cmd": "bun run test",
        "never_do": "Never use class components; never fetch in useEffect -- use TanStack Query",
        "verify": "bun run test && bun run build",
        "conventions": "Functional components; custom hooks for logic; Tailwind for styling",
    },
    "custom": {
        "label": "Custom / Other",
        "backend": "",
        "language": "",
        "test_cmd": "",
        "never_do": "",
        "verify": "",
        "conventions": "",
    },
}


@dataclass
class InitAnswers:
    project_purpose: str
    stack_key: str
    package_manager: Optional[str]
    verify_workflow: str
    never_do: str
    team_size: str   # "solo" | "small" (2-5) | "team" (5+)


def run_init_interview(console) -> Optional[InitAnswers]:
    """Run the new-project interview. Returns None if user skips."""
    try:
        import questionary
        from questionary import Style
    except ImportError:
        console.print("[yellow]questionary not installed -- run: pip install saar[interview][/yellow]")
        return None

    saar_style = Style([
        ("qmark", "fg:#00d7ff bold"),
        ("question", "bold"),
        ("answer", "fg:#00d7ff"),
        ("pointer", "fg:#00d7ff bold"),
        ("highlighted", "fg:#00d7ff bold"),
        ("instruction", "fg:#888888"),
    ])

    console.print()

    # Q1 — project purpose
    purpose = questionary.text(
        "What are you building?",
        instruction="(one sentence -- this becomes Claude's role context)",
        style=saar_style,
    ).ask()
    if not purpose:
        return None

    # Q2 — stack
    stack_choices = [
        questionary.Choice(v["label"], value=k)
        for k, v in STACK_PRESETS.items()
    ]
    stack_key = questionary.select(
        "What's your stack?",
        choices=stack_choices,
        style=saar_style,
    ).ask()
    if not stack_key:
        return None

    preset = STACK_PRESETS[stack_key]

    # Q3 — verify workflow (pre-filled from preset)
    verify = questionary.text(
        "How do you verify changes work?",
        default=preset["test_cmd"],
        instruction="(the exact command you run -- Claude will use this verbatim)",
        style=saar_style,
    ).ask()

    # Q4 — never-do (pre-filled from preset)
    never_do = questionary.text(
        "Any absolute never-do rules?",
        default=preset["never_do"],
        instruction="(separate multiple rules with semicolons)",
        style=saar_style,
    ).ask()

    # Q5 — team size (affects whether we add team conventions section)
    team_size = questionary.select(
        "Who's working on this?",
        choices=[
            questionary.Choice("Just me", value="solo"),
            questionary.Choice("Small team (2-5)", value="small"),
            questionary.Choice("Larger team (5+)", value="team"),
        ],
        style=saar_style,
    ).ask()
    if not team_size:
        team_size = "solo"

    return InitAnswers(
        project_purpose=purpose or "",
        stack_key=stack_key,
        package_manager=None,
        verify_workflow=verify or preset["test_cmd"],
        never_do=never_do or preset["never_do"],
        team_size=team_size,
    )


def render_init_agents_md(answers: InitAnswers, project_name: str) -> str:
    """Generate a starter AGENTS.md from init answers."""
    preset = STACK_PRESETS.get(answers.stack_key, STACK_PRESETS["custom"])
    lines = []

    lines.append(f"# AGENTS.md -- {project_name}")
    lines.append("")
    lines.append(f"**Project:** {answers.project_purpose}")
    lines.append("")

    if preset["backend"] or preset["language"]:
        lines.append("## Stack")
        lines.append("")
        if preset["backend"]:
            lines.append(f"- Backend: {preset['backend']}")
        if preset["language"]:
            lines.append(f"- Language: {preset['language']}")
        lines.append("")

    if preset["conventions"]:
        lines.append("## Coding Conventions")
        lines.append("")
        for conv in preset["conventions"].split(";"):
            c = conv.strip()
            if c:
                lines.append(f"- {c}")
        lines.append("")

    if answers.never_do:
        lines.append("## Never Do")
        lines.append("")
        for rule in answers.never_do.split(";"):
            r = rule.strip()
            if r:
                lines.append(f"- {r}")
        lines.append("")

    if answers.verify_workflow:
        lines.append("## How to Verify Changes Work")
        lines.append("")
        lines.append("```bash")
        lines.append(answers.verify_workflow)
        lines.append("```")
        lines.append("")

    lines.append("## Tribal Knowledge")
    lines.append("")
    lines.append("<!-- Add domain vocabulary, gotchas, and off-limits files here.")
    lines.append("     Use: saar add 'your rule here'  -->")
    lines.append("")

    if answers.team_size in ("small", "team"):
        lines.append("## Team Conventions")
        lines.append("")
        lines.append("<!-- Add team-specific patterns here: PR process, code review rules, etc. -->")
        lines.append("")

    lines.append("---")
    lines.append("*Generated by [saar](https://getsaar.com). Re-run `saar extract .` once you have code.*")

    return "\n".join(lines)
