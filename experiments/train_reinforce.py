"""Offline pre-training for REINFORCEAgent.

Usage:
    python experiments/train_reinforce.py
    # or via CLI:  saar rl train --agent reinforce
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from saar.rl.agents.reinforce import REINFORCEAgent
from saar.rl.policy_store import PolicyStore
from saar.rl.simulator import SaarSimulator

RESULTS_DIR = Path(__file__).parent / "results"


def main() -> None:
    n_episodes = 500
    sim = SaarSimulator()
    episodes = sim.generate_episodes(n=n_episodes)
    agent = REINFORCEAgent(seed=42)
    store = PolicyStore()

    rewards_per_episode: list[float] = []
    baseline_history: list[float] = []
    rolling_window = 50

    for i, ep in enumerate(episodes):
        # Compute log-prob for the simulator-assigned action, then update.
        # Oracle actions get positive advantage (reward > EMA baseline);
        # non-oracle actions receive a negative update signal.
        probs = agent.forward(ep.state)
        log_prob = float(np.log(probs[ep.action] + 1e-12))
        agent._last_action = ep.action
        agent.update(log_prob, ep.reward)
        rewards_per_episode.append(ep.reward)
        baseline_history.append(agent.baseline)

        if (i + 1) % 100 == 0:
            rolling = np.mean(rewards_per_episode[-rolling_window:])
            print(
                f"Episode {i + 1:4d}/{n_episodes}:"
                f"  rolling-{rolling_window} avg = {rolling:.3f}"
                f"  baseline = {agent.baseline:.3f}"
                f"  episodes = {agent.episode_count}"
            )

    final_mean = float(np.mean(rewards_per_episode))
    final_rolling = float(np.mean(rewards_per_episode[-rolling_window:]))
    print(f"\nFinal mean reward     : {final_mean:.3f}")
    print(f"Final rolling-{rolling_window} avg : {final_rolling:.3f}")
    print(f"Final baseline        : {agent.baseline:.3f}")

    saved_path = store.save(agent)
    print(f"Saved REINFORCE policy → {saved_path}")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = RESULTS_DIR / "reinforce_training.json"
    out.write_text(
        json.dumps(
            {
                "rewards": rewards_per_episode,
                "baseline_history": baseline_history,
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
        bl = np.array(baseline_history)

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4))

        ax1.plot(rolling, color="coral", linewidth=1.5, label=f"Rolling-{window} mean")
        ax1.axhline(final_mean, color="coral", linestyle="--", linewidth=0.8, label=f"Overall mean ({final_mean:.3f})")
        ax1.set_xlabel("Training episode")
        ax1.set_ylabel("Reward")
        ax1.set_ylim(0, 1)
        ax1.set_title("REINFORCE — Reward Learning Curve")
        ax1.legend()

        ax2.plot(bl, color="olive", linewidth=1.2, alpha=0.7, label="EMA Baseline")
        ax2.set_xlabel("Training episode")
        ax2.set_ylabel("Baseline value")
        ax2.set_title("REINFORCE — Baseline Convergence")
        ax2.set_ylim(0, 1)
        ax2.legend()

        plt.tight_layout()
        chart = RESULTS_DIR / "reinforce_learning_curve.png"
        fig.savefig(str(chart), dpi=150, bbox_inches="tight")
        print(f"Learning curve chart  → {chart}")
        plt.close(fig)
    except ImportError:
        print("(matplotlib not installed — skipping learning curve chart)")


if __name__ == "__main__":
    main()
