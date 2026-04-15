"""Evaluation: UCB vs REINFORCE vs Ensemble vs random baseline.

Includes:
  - Bootstrap 95% confidence intervals
  - Welch's t-test vs random baseline
  - Bar chart with CI error bars
  - Learning curve (rolling reward) plots from training history

Usage:
    python experiments/eval_comparison.py
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from saar.rl.action_space import N_ACTIONS
from saar.rl.agents.ensemble import EnsembleAgent
from saar.rl.agents.reinforce import REINFORCEAgent
from saar.rl.agents.ucb_bandit import UCBContextualBandit
from saar.rl.policy_store import PolicyStore
from saar.rl.simulator import SaarSimulator

RESULTS_DIR = Path(__file__).parent / "results"
N_TEST_EPISODES = 200
N_BOOTSTRAP = 2000
CONFIDENCE = 0.95

_ORACLE_REWARD = 0.70
_NON_ORACLE_REWARD = 0.30


# ── Evaluation ────────────────────────────────────────────────────────────────

def _eval_agent(name: str, agent, episodes: list) -> dict:
    """Evaluate agent on held-out episodes.

    Reward depends on whether the agent selects the oracle action:
      action == oracle → reward drawn from N(0.70, 0.05)
      action != oracle → reward drawn from N(0.30, 0.05)
    """
    rewards: list[float] = []
    optimal_count = 0
    rng = np.random.default_rng(99)

    for ep in episodes:
        if isinstance(agent, EnsembleAgent):
            action, _ = agent.select_action(ep.state)
        elif isinstance(agent, UCBContextualBandit):
            action = agent.best_action(ep.state)
        elif isinstance(agent, REINFORCEAgent):
            probs = agent.action_probs(ep.state)
            action = int(np.argmax(probs))
        else:
            action = random.randrange(N_ACTIONS)

        oracle = ep.info.get("oracle_action", -1)
        is_optimal = action == oracle
        if is_optimal:
            optimal_count += 1
            reward = float(np.clip(rng.normal(_ORACLE_REWARD, 0.05), -1.0, 1.0))
        else:
            reward = float(np.clip(rng.normal(_NON_ORACLE_REWARD, 0.05), -1.0, 1.0))
        rewards.append(reward)

    return {
        "agent": name,
        "mean_reward": float(np.mean(rewards)),
        "std_reward": float(np.std(rewards)),
        "pct_optimal": float(optimal_count / len(episodes) * 100),
        "n_episodes": len(episodes),
        "rewards": rewards,
    }


# ── Statistical validation ────────────────────────────────────────────────────

def _bootstrap_ci(
    rewards: list[float],
    n_bootstrap: int = N_BOOTSTRAP,
    confidence: float = CONFIDENCE,
    seed: int = 0,
) -> tuple[float, float]:
    """Non-parametric bootstrap confidence interval for the mean reward.

    Returns (lower, upper) bounds for the given confidence level.
    """
    rng = np.random.default_rng(seed)
    arr = np.array(rewards)
    boot_means = np.array([
        rng.choice(arr, size=len(arr), replace=True).mean()
        for _ in range(n_bootstrap)
    ])
    alpha = 1.0 - confidence
    lower = float(np.percentile(boot_means, 100 * alpha / 2))
    upper = float(np.percentile(boot_means, 100 * (1 - alpha / 2)))
    return lower, upper


def _welch_t_test(
    rewards_a: list[float],
    rewards_b: list[float],
) -> tuple[float, float]:
    """Welch's two-sample t-test (unequal variances).

    Returns (t_statistic, p_value).
    """
    a = np.array(rewards_a, dtype=np.float64)
    b = np.array(rewards_b, dtype=np.float64)
    na, nb = len(a), len(b)
    mean_a, mean_b = a.mean(), b.mean()
    var_a, var_b = a.var(ddof=1), b.var(ddof=1)

    se = np.sqrt(var_a / na + var_b / nb)
    if se < 1e-12:
        return 0.0, 1.0

    t = float((mean_a - mean_b) / se)

    # Welch–Satterthwaite degrees of freedom
    df_num = (var_a / na + var_b / nb) ** 2
    df_den = (var_a / na) ** 2 / (na - 1) + (var_b / nb) ** 2 / (nb - 1)
    df = float(df_num / df_den) if df_den > 0 else float(na + nb - 2)

    # Two-tailed p-value using incomplete beta function approximation
    # P(T > |t|) ≈ 2 * (1 - CDF_t(|t|, df)) — use scipy if available
    try:
        from scipy.stats import t as t_dist  # type: ignore[import]
        p = float(2 * t_dist.sf(abs(t), df))
    except ImportError:
        # Fallback: approximate via normal for large df
        p = float(2 * _normal_sf(abs(t)))

    return t, p


def _normal_sf(z: float) -> float:
    """Survival function of standard normal (upper tail).  No scipy required."""
    import math
    return 0.5 * math.erfc(z / math.sqrt(2))


# ── Printing ──────────────────────────────────────────────────────────────────

def _print_table(results: list[dict]) -> None:
    header = (
        f"{'Agent':<18}  {'Mean ± CI':>18}  {'Std':>6}  {'% Optimal':>10}"
    )
    print()
    print(header)
    print("-" * len(header))
    for r in results:
        ci = r.get("ci_95", (float("nan"), float("nan")))
        ci_str = f"{r['mean_reward']:.3f} [{ci[0]:.3f},{ci[1]:.3f}]"
        print(
            f"{r['agent']:<18}  {ci_str:>18}  {r['std_reward']:>6.3f}"
            f"  {r['pct_optimal']:>9.1f}%"
        )
    print()


def _ascii_bar(label: str, value: float, max_val: float, width: int = 40) -> str:
    filled = int(width * value / max(max_val, 1e-6))
    bar = "#" * filled + "-" * (width - filled)
    return f"{label:<18}  [{bar}] {value:.3f}"


# ── Main ─────────────────────────────────────────────────────────────────────

def _quick_train_ucb(n: int = 300) -> UCBContextualBandit:
    sim = SaarSimulator()
    agent = UCBContextualBandit(seed=0)
    for ep in sim.generate_episodes(n):
        a = agent.select_action(ep.state)
        agent.update(ep.state, a, ep.reward)
    return agent


def _quick_train_rf(n: int = 300) -> REINFORCEAgent:
    sim = SaarSimulator()
    agent = REINFORCEAgent(seed=0)
    for ep in sim.generate_episodes(n):
        a, lp = agent.select_action(ep.state)
        agent.update(lp, ep.reward)
    return agent


def main() -> None:
    store = PolicyStore()
    ucb = store.load_ucb()
    rf = store.load_reinforce()
    ensemble = store.load_ensemble()

    if ucb is None:
        print("No UCB policy — running quick training (300 episodes)...")
        ucb = _quick_train_ucb()
        store.save(ucb)

    if rf is None:
        print("No REINFORCE policy — running quick training (300 episodes)...")
        rf = _quick_train_rf()
        store.save(rf)

    if ensemble is None:
        print("No ensemble policy — building from sub-agents...")
        ensemble = EnsembleAgent(ucb=ucb, reinforce=rf, seed=0)
        sim = SaarSimulator()
        for ep in sim.generate_episodes(300):
            a, idx = ensemble.select_action(ep.state)
            ensemble.update(ep.state, a, ep.reward, idx)
        store.save(ensemble)

    # Held-out test episodes (fixed seed for reproducibility)
    sim = SaarSimulator(seed=42)
    test_episodes = sim.generate_episodes(n=N_TEST_EPISODES)

    raw_results = [
        _eval_agent("UCB Bandit", ucb, test_episodes),
        _eval_agent("REINFORCE", rf, test_episodes),
        _eval_agent("Ensemble", ensemble, test_episodes),
        _eval_agent("Random", None, test_episodes),
    ]

    # Bootstrap CI + t-test vs random
    random_rewards = raw_results[-1]["rewards"]
    results = []
    for r in raw_results:
        ci = _bootstrap_ci(r["rewards"])
        t_stat, p_val = _welch_t_test(r["rewards"], random_rewards)
        results.append({
            **{k: v for k, v in r.items() if k != "rewards"},
            "ci_95": ci,
            "t_vs_random": t_stat,
            "p_vs_random": p_val,
            "significant": p_val < 0.05 and r["agent"] != "Random",
        })

    print("\n=== Evaluation Results (N=200 held-out episodes) ===")
    _print_table(results)

    print("Statistical significance vs random baseline (Welch t-test):")
    for r in results:
        if r["agent"] == "Random":
            continue
        sig = "**p<0.05**" if r["significant"] else "n.s."
        print(
            f"  {r['agent']:<18}  t={r['t_vs_random']:+.3f}  "
            f"p={r['p_vs_random']:.4f}  {sig}"
        )
    print()

    # ASCII bar chart
    max_reward = max(r["mean_reward"] for r in results)
    print("Mean reward comparison:")
    for r in results:
        print(_ascii_bar(r["agent"], r["mean_reward"], max_reward))
    print()

    # Save JSON (drop CI tuples → lists for JSON serialisation)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = RESULTS_DIR / "comparison.json"
    serialisable = [
        {**r, "ci_95": list(r["ci_95"])} for r in results
    ]
    out.write_text(json.dumps(serialisable, indent=2), encoding="utf-8")
    print(f"Results saved to {out}")

    # Matplotlib charts
    try:
        import matplotlib.pyplot as plt
        import matplotlib.gridspec as gridspec

        fig = plt.figure(figsize=(14, 5))
        gs = gridspec.GridSpec(1, 2, figure=fig)

        # -- Left: bar chart with 95% CI error bars ---------------------------
        ax1 = fig.add_subplot(gs[0, 0])
        names = [r["agent"] for r in results]
        means = [r["mean_reward"] for r in results]
        ci_errs = [
            [r["mean_reward"] - r["ci_95"][0] for r in results],
            [r["ci_95"][1] - r["mean_reward"] for r in results],
        ]
        colors = ["steelblue", "coral", "mediumpurple", "grey"]
        bars = ax1.bar(
            range(len(names)), means,
            yerr=ci_errs, capsize=6,
            color=colors, alpha=0.85, edgecolor="black", linewidth=0.7,
        )
        ax1.set_xticks(range(len(names)))
        ax1.set_xticklabels(names, rotation=15, ha="right")
        ax1.set_ylabel("Mean Reward")
        ax1.set_title("Agent Comparison (95% Bootstrap CI)")
        ax1.set_ylim(0, 1.05)
        ax1.axhline(means[-1], color="grey", linestyle="--", linewidth=0.8, label="Random")

        for bar, r in zip(bars, results):
            sig = "*" if r.get("significant") else ""
            ax1.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + ci_errs[1][results.index(r)] + 0.02,
                sig, ha="center", va="bottom", fontsize=14, color="red",
            )

        # -- Right: learning curves from training history ---------------------
        ax2 = fig.add_subplot(gs[0, 1])
        curve_files = {
            "UCB": RESULTS_DIR / "ucb_training.json",
            "REINFORCE": RESULTS_DIR / "reinforce_training.json",
        }
        window = 25
        plotted_any = False
        for label, path in curve_files.items():
            if not path.exists():
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
            raw = np.array(data.get("rewards", []), dtype=np.float64)
            if len(raw) < window:
                continue
            rolling = np.convolve(raw, np.ones(window) / window, mode="valid")
            ax2.plot(rolling, label=f"{label} (rolling {window})")
            plotted_any = True

        if plotted_any:
            ax2.set_xlabel("Training episode")
            ax2.set_ylabel("Rolling mean reward")
            ax2.set_title("Learning Curves")
            ax2.legend(loc="lower right")
            ax2.set_ylim(0, 1)
        else:
            ax2.text(
                0.5, 0.5,
                "Run experiments/train_ucb.py\nand train_reinforce.py\nto generate curves",
                ha="center", va="center", transform=ax2.transAxes, fontsize=10,
            )
            ax2.set_title("Learning Curves (not yet generated)")

        plt.tight_layout()
        chart_path = RESULTS_DIR / "comparison_chart.png"
        fig.savefig(str(chart_path), dpi=150, bbox_inches="tight")
        print(f"Chart saved to {chart_path}")
        plt.close(fig)

    except ImportError:
        print("(matplotlib not installed — skipping charts)")


if __name__ == "__main__":
    main()
