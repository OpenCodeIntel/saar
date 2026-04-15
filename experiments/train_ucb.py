"""Offline pre-training for UCBContextualBandit.

Usage:
    python experiments/train_ucb.py
    # or via CLI:  saar rl train --agent ucb
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

# Make sure saar is importable when run directly
sys.path.insert(0, str(Path(__file__).parent.parent))

from saar.rl.agents.ucb_bandit import UCBContextualBandit
from saar.rl.policy_store import PolicyStore
from saar.rl.simulator import SaarSimulator

RESULTS_DIR = Path(__file__).parent / "results"


def main() -> None:
    n_episodes = 500
    sim = SaarSimulator()
    episodes = sim.generate_episodes(n=n_episodes)
    agent = UCBContextualBandit(seed=42)
    store = PolicyStore()

    rewards_per_episode: list[float] = []
    rolling_window = 50

    for i, ep in enumerate(episodes):
        # UCB online update: agent learns from each (state, action, reward) tuple
        agent.update(ep.state, ep.action, ep.reward)
        rewards_per_episode.append(ep.reward)
        if (i + 1) % 100 == 0:
            rolling = np.mean(rewards_per_episode[-rolling_window:])
            print(
                f"Episode {i + 1:4d}/{n_episodes}:"
                f"  rolling-{rolling_window} avg = {rolling:.3f}"
                f"  total_pulls = {agent.total_pulls}"
            )

    final_mean = float(np.mean(rewards_per_episode))
    final_rolling = float(np.mean(rewards_per_episode[-rolling_window:]))
    print(f"\nFinal mean reward     : {final_mean:.3f}")
    print(f"Final rolling-{rolling_window} avg : {final_rolling:.3f}")

    saved_path = store.save(agent)
    print(f"Saved UCB policy      → {saved_path}")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = RESULTS_DIR / "ucb_training.json"
    out.write_text(
        json.dumps(
            {
                "rewards": rewards_per_episode,
                "final_mean": final_mean,
                "n_episodes": n_episodes,
                "rolling_window": rolling_window,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Training rewards      → {out}")

    # Optional learning curve plot
    try:
        import matplotlib.pyplot as plt

        window = 25
        rolling = np.convolve(
            rewards_per_episode, np.ones(window) / window, mode="valid"
        )
        fig, ax = plt.subplots(figsize=(9, 4))
        ax.plot(rolling, color="steelblue", linewidth=1.5, label=f"Rolling-{window} mean")
        ax.axhline(final_mean, color="steelblue", linestyle="--", linewidth=0.8, label=f"Overall mean ({final_mean:.3f})")
        ax.set_xlabel("Training episode")
        ax.set_ylabel("Reward")
        ax.set_ylim(0, 1)
        ax.set_title("UCB Bandit — Learning Curve")
        ax.legend()
        chart = RESULTS_DIR / "ucb_learning_curve.png"
        fig.savefig(str(chart), dpi=150, bbox_inches="tight")
        print(f"Learning curve chart  → {chart}")
        plt.close(fig)
    except ImportError:
        print("(matplotlib not installed — skipping learning curve chart)")


if __name__ == "__main__":
    main()
