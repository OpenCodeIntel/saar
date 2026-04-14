"""RL subcommand implementations.

Registered in saar/cli.py under the `rl` typer group.
Never add logic directly to cli.py — only in this file.

Commands:
  saar rl train --agent [ucb|reinforce|both]
  saar rl status
  saar rate [good|bad]
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

logger = logging.getLogger(__name__)
console = Console()

rl_app = typer.Typer(
    name="rl",
    help="RL policy training and status.",
    no_args_is_help=True,
)

_FEEDBACK_FILE: Path = Path.home() / ".saar" / "rl" / "feedback.json"


# ── Train ─────────────────────────────────────────────────────────────────────

@rl_app.command(name="train")
def cmd_rl_train(
    agent: Annotated[
        str,
        typer.Option("--agent", "-a", help="Agent to train: ucb | reinforce | both"),
    ] = "both",
    episodes: Annotated[
        int,
        typer.Option("--episodes", "-n", help="Number of training episodes"),
    ] = 500,
) -> None:
    """Train RL policy via offline simulation."""
    import numpy as np
    from saar.rl.agents.ucb_bandit import UCBContextualBandit
    from saar.rl.agents.reinforce import REINFORCEAgent
    from saar.rl.policy_store import PolicyStore
    from saar.rl.simulator import SaarSimulator

    valid = {"ucb", "reinforce", "both"}
    if agent not in valid:
        console.print(f"  [red]Unknown agent '{agent}'. Choose: ucb | reinforce | both[/red]")
        raise typer.Exit(code=1)

    sim = SaarSimulator()
    store = PolicyStore()

    def _train_ucb(eps_list: list) -> None:
        ucb = UCBContextualBandit(seed=42)
        rewards: list[float] = []
        console.print(f"  Training UCB bandit ({len(eps_list)} episodes)...")
        for i, ep in enumerate(eps_list):
            ucb.update(ep.state, ep.action, ep.reward)
            rewards.append(ep.reward)
            if (i + 1) % 100 == 0:
                console.print(
                    f"  [dim]  episode {i + 1}/{len(eps_list)}"
                    f"  rolling avg = {np.mean(rewards[-50:]):.3f}[/dim]"
                )
        path = store.save(ucb)
        console.print(f"  [green]Saved[/green] UCB policy → {path}")

    def _train_reinforce(eps_list: list) -> None:
        import numpy as _np
        rf = REINFORCEAgent(seed=42)
        rewards: list[float] = []
        console.print(f"  Training REINFORCE ({len(eps_list)} episodes)...")
        for i, ep in enumerate(eps_list):
            probs = rf.forward(ep.state)
            lp = float(_np.log(probs[ep.action] + 1e-12))
            rf._last_action = ep.action
            rf.update(lp, ep.reward)
            rewards.append(ep.reward)
            if (i + 1) % 100 == 0:
                console.print(
                    f"  [dim]  episode {i + 1}/{len(eps_list)}"
                    f"  rolling avg = {np.mean(rewards[-50:]):.3f}[/dim]"
                )
        path = store.save(rf)
        console.print(f"  [green]Saved[/green] REINFORCE policy → {path}")

    console.print()
    eps = sim.generate_episodes(n=episodes)
    if agent in ("ucb", "both"):
        _train_ucb(eps)
    if agent in ("reinforce", "both"):
        _train_reinforce(eps)

    # After training both sub-agents, build and save the ensemble
    if agent == "both":
        from saar.rl.agents.ensemble import EnsembleAgent
        ucb_agent = store.load_ucb()
        rf_agent = store.load_reinforce()
        if ucb_agent is not None and rf_agent is not None:
            ensemble = EnsembleAgent(ucb=ucb_agent, reinforce=rf_agent, seed=42)
            # Warm-start ensemble: run it through the same episodes
            console.print("  Building ensemble (Thompson Sampling meta-agent)...")
            for ep in eps:
                action, agent_idx = ensemble.select_action(ep.state)
                ensemble.update(ep.state, action, ep.reward, agent_idx)
            epath = store.save(ensemble)
            console.print(f"  [green]Saved[/green] Ensemble policy → {epath}")

    console.print()
    console.print("  [dim]Training complete.[/dim]")


# ── Status ────────────────────────────────────────────────────────────────────

@rl_app.command(name="status")
def cmd_rl_status() -> None:
    """Show saved policy stats."""
    from saar.rl.policy_store import PolicyStore

    store = PolicyStore()
    stats = store.stats()

    console.print()
    if not stats:
        console.print("  [dim]No trained policies found. Run:[/dim]  saar rl train")
        console.print()
        return

    table = Table(show_header=True, box=None, padding=(0, 2))
    table.add_column("Agent", style="bold")
    table.add_column("Version")
    table.add_column("Episodes")
    table.add_column("Saved at")

    for alg_name, info in stats.items():
        if "error" in info:
            table.add_row(alg_name, "—", "—", f"[red]{info['error']}[/red]")
        else:
            table.add_row(
                alg_name,
                str(info.get("version", "—")),
                str(info.get("episode_count", "—")),
                str(info.get("created_at", "—")),
            )

    console.print(table)
    console.print()

    # If UCB is loaded, show top arm per context
    ucb = store.load_ucb()
    if ucb is not None:
        console.print("  [dim]UCB top arms per context:[/dim]")
        console.print(f"  [dim]{ucb!r}[/dim]")
        console.print()

    # If ensemble is loaded, show trust weights
    ensemble = store.load_ensemble()
    if ensemble is not None:
        console.print("  [dim]Ensemble sub-agent trust weights:[/dim]")
        console.print(f"  [dim]{ensemble!r}[/dim]")
        console.print()


# ── Rate ──────────────────────────────────────────────────────────────────────

def cmd_rate(
    rating: Annotated[str, typer.Argument(help="Feedback: good | bad")],
) -> None:
    """Record explicit feedback for the last extraction."""
    rating = rating.strip().lower()
    if rating not in ("good", "bad"):
        console.print(f"  [red]Unknown rating '{rating}'. Use: good | bad[/red]")
        raise typer.Exit(code=1)

    feedback_value = 1.0 if rating == "good" else -1.0
    _save_feedback(feedback_value)
    console.print()
    icon = "[green]+1.0[/green]" if feedback_value > 0 else "[red]-1.0[/red]"
    console.print(f"  Feedback recorded: {icon}")
    console.print()


def _save_feedback(value: float) -> None:
    """Append feedback value to the feedback JSON file."""
    _FEEDBACK_FILE.parent.mkdir(parents=True, exist_ok=True)
    records: list = []
    if _FEEDBACK_FILE.exists():
        try:
            records = json.loads(_FEEDBACK_FILE.read_text(encoding="utf-8"))
        except Exception:
            records = []
    from datetime import datetime, timezone
    records.append({"value": value, "ts": datetime.now(tz=timezone.utc).isoformat()})
    _FEEDBACK_FILE.write_text(json.dumps(records, indent=2), encoding="utf-8")


def load_last_feedback() -> float:
    """Return the most recent explicit feedback value, or 0.0 if none."""
    if not _FEEDBACK_FILE.exists():
        return 0.0
    try:
        records = json.loads(_FEEDBACK_FILE.read_text(encoding="utf-8"))
        if records:
            return float(records[-1].get("value", 0.0))
    except Exception:
        pass
    return 0.0
