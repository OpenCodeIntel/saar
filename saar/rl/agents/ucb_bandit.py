"""UCB Contextual Bandit agent for extractor priority learning.

Architecture:
  - C=6 contexts via online k-means on the 20-dim state space
  - K=8 arms (extraction profiles)
  - UCB1 selection with optimistic initialisation (q=0.5 on first pull)
  - Cosine-similarity context assignment with online centroid update

Cold-start: when total_pulls < C*K, fall back to random action to
            ensure every arm is tried before exploitation begins.
"""
from __future__ import annotations

import logging
import math
import random
from typing import Optional

import numpy as np

from saar.rl.action_space import N_ACTIONS

logger = logging.getLogger(__name__)

N_CONTEXTS: int = 6
_COLD_START_THRESHOLD: int = N_CONTEXTS * N_ACTIONS  # 48
_CENTROID_LR: float = 0.01
_UCB_CONST: float = 2.0
_OPTIMISTIC_Q: float = 0.5


class UCBContextualBandit:
    """UCB1 contextual bandit with online k-means context clustering."""

    def __init__(self, state_dim: int = 20, seed: Optional[int] = None) -> None:
        self._rng = np.random.default_rng(seed)
        self._state_dim = state_dim

        # Centroids: C × D, initialised uniformly in [0,1]
        self.centroids: np.ndarray = self._rng.uniform(
            0.0, 1.0, size=(N_CONTEXTS, state_dim)
        ).astype(np.float32)

        # Pull counts: n[c][k]
        self.n: np.ndarray = np.zeros((N_CONTEXTS, N_ACTIONS), dtype=np.int64)

        # Mean rewards: q[c][k]
        self.q: np.ndarray = np.zeros((N_CONTEXTS, N_ACTIONS), dtype=np.float64)

        self.total_pulls: int = 0

    # -- Context assignment ---------------------------------------------------

    def _assign_context(self, state: np.ndarray) -> int:
        """Return the index of the nearest centroid using cosine similarity."""
        s = state.astype(np.float64)
        s_norm = np.linalg.norm(s)
        if s_norm < 1e-10:
            # Zero vector: fall back to L2-nearest centroid
            dists = np.linalg.norm(self.centroids - s, axis=1)
            return int(np.argmin(dists))

        sims = np.zeros(N_CONTEXTS)
        for c in range(N_CONTEXTS):
            c_norm = np.linalg.norm(self.centroids[c])
            if c_norm < 1e-10:
                sims[c] = 0.0
            else:
                sims[c] = float(np.dot(self.centroids[c], s) / (c_norm * s_norm))
        return int(np.argmax(sims))

    def _update_centroid(self, context: int, state: np.ndarray) -> None:
        """Online centroid update: centroid ← centroid + lr * (state − centroid)."""
        self.centroids[context] += _CENTROID_LR * (state.astype(np.float32) - self.centroids[context])

    # -- Action selection -----------------------------------------------------

    def select_action(self, state: np.ndarray) -> int:
        """Select action using UCB1.  Falls back to random during cold-start."""
        if self.total_pulls < _COLD_START_THRESHOLD:
            return random.randrange(N_ACTIONS)

        ctx = self._assign_context(state)
        self._update_centroid(ctx, state)

        n_ctx = self.n[ctx]
        big_n = int(n_ctx.sum())

        ucb_values = np.full(N_ACTIONS, np.inf)
        for k in range(N_ACTIONS):
            if n_ctx[k] > 0 and big_n > 0:
                exploration = math.sqrt(_UCB_CONST * math.log(big_n) / n_ctx[k])
                ucb_values[k] = self.q[ctx][k] + exploration

        return int(np.argmax(ucb_values))

    def best_action(self, state: np.ndarray) -> int:
        """Return argmax q for the nearest context (no exploration)."""
        ctx = self._assign_context(state)
        # For any arm never pulled, use optimistic value
        q_ctx = self.q[ctx].copy()
        for k in range(N_ACTIONS):
            if self.n[ctx][k] == 0:
                q_ctx[k] = _OPTIMISTIC_Q
        return int(np.argmax(q_ctx))

    # -- Update ---------------------------------------------------------------

    def update(self, state: np.ndarray, action: int, reward: float) -> None:
        """Update pull counts, mean reward, and centroids for the given transition."""
        ctx = self._assign_context(state)
        self._update_centroid(ctx, state)

        self.n[ctx][action] += 1
        nk = int(self.n[ctx][action])

        # On first pull, initialise with optimistic q
        if nk == 1:
            self.q[ctx][action] = _OPTIMISTIC_Q + (1.0 / nk) * (reward - _OPTIMISTIC_Q)
        else:
            # Incremental mean: q ← q + (1/n) * (r - q)
            self.q[ctx][action] += (1.0 / nk) * (reward - self.q[ctx][action])

        self.total_pulls += 1

    # -- Serialisation helpers ------------------------------------------------

    def to_dict(self) -> dict:
        """Serialise parameters to a JSON-friendly dict."""
        return {
            "centroids": self.centroids.tolist(),
            "n": self.n.tolist(),
            "q": self.q.tolist(),
            "total_pulls": self.total_pulls,
            "state_dim": self._state_dim,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "UCBContextualBandit":
        """Restore agent from a serialised dict."""
        agent = cls(state_dim=data.get("state_dim", 20))
        agent.centroids = np.array(data["centroids"], dtype=np.float32)
        agent.n = np.array(data["n"], dtype=np.int64)
        agent.q = np.array(data["q"], dtype=np.float64)
        agent.total_pulls = int(data["total_pulls"])
        return agent

    # -- Diagnostics ----------------------------------------------------------

    def __repr__(self) -> str:
        lines = [f"UCBContextualBandit(pulls={self.total_pulls})"]
        for c in range(N_CONTEXTS):
            best_k = int(np.argmax(self.q[c]))
            lines.append(
                f"  ctx {c}: best_arm={best_k}  q={self.q[c][best_k]:.3f}"
                f"  n={self.n[c].sum()}"
            )
        return "\n".join(lines)
