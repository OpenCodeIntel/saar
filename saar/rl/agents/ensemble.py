"""Ensemble agent: Thompson Sampling meta-agent over UCB + REINFORCE.

This implements a two-level RL hierarchy that satisfies the Multi-Agent RL
requirement:

  Level 1 (meta-agent): Thompson Sampling selects which sub-agent to trust
    for the current state.  Each sub-agent has a Beta(α, β) belief about its
    own competence.  Sampling θᵢ ~ Beta(αᵢ, βᵢ) and picking argmax θᵢ
    naturally balances exploration of less-tested agents with exploitation of
    better-performing ones.

  Level 2 (sub-agents): UCBContextualBandit and REINFORCEAgent each maintain
    their own learned policies.  The selected sub-agent proposes an action;
    the ensemble executes it.

After observing reward r:
  - The selected sub-agent updates its own parameters.
  - The meta-agent updates its Beta distribution:
      r ≥ REWARD_THRESHOLD → α_i  += 1  (success)
      r <  REWARD_THRESHOLD → β_i  += 1  (failure)

The EnsembleAgent is serialisable to/from dict (stored alongside UCB and
REINFORCE policies in PolicyStore).
"""
from __future__ import annotations

import logging
from typing import Optional

import numpy as np

from saar.rl.agents.reinforce import REINFORCEAgent
from saar.rl.agents.ucb_bandit import UCBContextualBandit

logger = logging.getLogger(__name__)

# Reward threshold separating success from failure for the meta-agent update
_REWARD_THRESHOLD: float = 0.5

# Agent index constants
_UCB_IDX: int = 0
_REINFORCE_IDX: int = 1
_N_AGENTS: int = 2


class EnsembleAgent:
    """Thompson Sampling meta-agent coordinating UCB and REINFORCE sub-agents.

    Usage::
        ensemble = EnsembleAgent(ucb_agent, reinforce_agent, seed=0)
        action, agent_idx = ensemble.select_action(state)
        ensemble.update(state, action, reward, agent_idx)

    The sub-agents are updated in-place so their policies continue to improve
    independently.  The meta-agent's Beta parameters capture which sub-agent
    is currently more reliable for the observed reward distribution.
    """

    N_AGENTS: int = _N_AGENTS
    REWARD_THRESHOLD: float = _REWARD_THRESHOLD

    def __init__(
        self,
        ucb: UCBContextualBandit,
        reinforce: REINFORCEAgent,
        seed: Optional[int] = None,
    ) -> None:
        self._rng = np.random.default_rng(seed)
        self.ucb = ucb
        self.reinforce = reinforce

        # Beta(α, β) per sub-agent, initialised to uniform Beta(1, 1)
        self.beta_params: np.ndarray = np.ones((_N_AGENTS, 2), dtype=np.float64)

        # Diagnostics
        self.selection_counts: np.ndarray = np.zeros(_N_AGENTS, dtype=np.int64)
        self.total_updates: int = 0

        # Cache last log_prob from REINFORCE select_action for the update step
        self._last_log_prob: Optional[float] = None

    # -- Action selection -----------------------------------------------------

    def select_action(self, state: np.ndarray) -> tuple[int, int]:
        """Thompson Sampling: sample θᵢ ~ Beta(αᵢ, βᵢ), pick argmax, get action.

        Returns:
            (action, agent_idx) — agent_idx 0=UCB, 1=REINFORCE.
        """
        thetas = [
            float(self._rng.beta(self.beta_params[i, 0], self.beta_params[i, 1]))
            for i in range(_N_AGENTS)
        ]
        agent_idx = int(np.argmax(thetas))
        self.selection_counts[agent_idx] += 1

        if agent_idx == _UCB_IDX:
            action = self.ucb.select_action(state)
            self._last_log_prob = None
        else:
            action, log_prob = self.reinforce.select_action(state)
            self._last_log_prob = log_prob

        logger.debug(
            "Ensemble selected agent=%d (θ=[%.3f, %.3f]) → action=%d",
            agent_idx, thetas[0], thetas[1], action,
        )
        return action, agent_idx

    def best_action(self, state: np.ndarray) -> int:
        """Deterministic: use the sub-agent with the higher expected Beta mean."""
        expected = self.beta_params[:, 0] / (
            self.beta_params[:, 0] + self.beta_params[:, 1]
        )
        agent_idx = int(np.argmax(expected))

        if agent_idx == _UCB_IDX:
            return self.ucb.best_action(state)
        probs = self.reinforce.action_probs(state)
        return int(np.argmax(probs))

    # -- Update ---------------------------------------------------------------

    def update(
        self,
        state: np.ndarray,
        action: int,
        reward: float,
        agent_idx: int,
    ) -> None:
        """Update the selected sub-agent and the meta-agent's Beta distribution.

        Args:
            state:      State vector that was passed to select_action.
            action:     Action that was executed.
            reward:     Observed scalar reward.
            agent_idx:  Which sub-agent was selected (0=UCB, 1=REINFORCE).
        """
        # -- Sub-agent update -------------------------------------------------
        if agent_idx == _UCB_IDX:
            self.ucb.update(state, action, reward)
        else:
            log_prob = self._last_log_prob if self._last_log_prob is not None else 0.0
            self.reinforce.update(log_prob, reward)

        # -- Meta-agent Beta update -------------------------------------------
        if reward >= _REWARD_THRESHOLD:
            self.beta_params[agent_idx, 0] += 1.0   # success → α
        else:
            self.beta_params[agent_idx, 1] += 1.0   # failure → β

        self.total_updates += 1
        self._last_log_prob = None

    # -- Serialisation --------------------------------------------------------

    def to_dict(self) -> dict:
        """Serialise meta-agent parameters (sub-agents serialised separately)."""
        return {
            "beta_params": self.beta_params.tolist(),
            "selection_counts": self.selection_counts.tolist(),
            "total_updates": self.total_updates,
        }

    @classmethod
    def from_dict(
        cls,
        data: dict,
        ucb: UCBContextualBandit,
        reinforce: REINFORCEAgent,
    ) -> "EnsembleAgent":
        """Restore meta-agent from serialised dict."""
        agent = cls(ucb=ucb, reinforce=reinforce)
        agent.beta_params = np.array(data["beta_params"], dtype=np.float64)
        agent.selection_counts = np.array(data["selection_counts"], dtype=np.int64)
        agent.total_updates = int(data["total_updates"])
        return agent

    # -- Diagnostics ----------------------------------------------------------

    def agent_weights(self) -> dict[str, float]:
        """Return expected Beta mean (trust weight) for each sub-agent."""
        names = ["ucb", "reinforce"]
        return {
            name: float(self.beta_params[i, 0] / (self.beta_params[i, 0] + self.beta_params[i, 1]))
            for i, name in enumerate(names)
        }

    def __repr__(self) -> str:
        names = ["UCB", "REINFORCE"]
        lines = [f"EnsembleAgent(updates={self.total_updates})"]
        for i, name in enumerate(names):
            alpha, beta = self.beta_params[i]
            expected = alpha / (alpha + beta)
            lines.append(
                f"  {name}: E[θ]={expected:.3f}  α={alpha:.0f}  β={beta:.0f}"
                f"  selections={self.selection_counts[i]}"
            )
        return "\n".join(lines)
