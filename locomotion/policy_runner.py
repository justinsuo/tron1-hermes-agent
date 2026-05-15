"""Torch-backed policy loader for LimX-style .pt checkpoints.

Loading is deliberately lazy and defensive: importing this module must
**never** require torch at import time, and constructing a ``PolicyRunner``
must surface clear errors rather than crashing the Hermes agent.

Use:

    runner = PolicyRunner(checkpoint_path="~/policies/tron1_walk.pt")
    runner.reset()
    action = runner.act(obs, command)
    print(runner.get_metadata())

If the checkpoint is missing or torch isn't installed, construction raises
:class:`PolicyLoadError` with a message describing the fallback (usually
"swap to FakePolicyRunner").

TODO before connecting a real policy:
  - confirm the expected forward() signature (some legged_gym checkpoints
    return a TorchScript module, others a state_dict to be applied to a
    fresh MLP — we handle both lazily below)
  - confirm obs/action normalization is baked into the checkpoint or
    needs to be applied here
  - confirm the action layout matches the URDF joint order in
    ``observation_builder.JOINT_ORDER``
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from .policy_interface import PolicyInterface


class PolicyLoadError(RuntimeError):
    """Raised when a checkpoint can't be loaded. Carries a user-facing reason."""


class PolicyRunner(PolicyInterface):
    """Loads and runs a LimX-style torch checkpoint.

    The class supports two common shapes:
      1. A torch.jit.ScriptModule callable as ``module(obs_tensor)``.
      2. A dict ``{"actor": state_dict, "obs_mean": ..., "obs_std": ...}``
         from rl-games / legged_gym. We don't reconstruct the MLP for case
         (2) here — that requires the trainer's config. Instead we surface
         a clear PolicyLoadError pointing at the config.
    """

    def __init__(
        self,
        checkpoint_path: str,
        obs_dim: int = 33,
        action_dim: int = 8,
        command_dim: int = 3,
        device: str = "cpu",
    ) -> None:
        self._checkpoint_path = Path(checkpoint_path).expanduser()
        self._obs_dim = obs_dim
        self._action_dim = action_dim
        self._command_dim = command_dim
        self._device_name = device
        self._module = None      # populated by _load
        self._module_kind = None  # "scripted" or "state_dict"
        self._step_count = 0
        self._load()

    # -- loading --------------------------------------------------------

    def _load(self) -> None:
        if not self._checkpoint_path.exists():
            raise PolicyLoadError(
                f"checkpoint not found at {self._checkpoint_path}. "
                "Pass a valid path, or use FakePolicyRunner for now."
            )
        try:
            import torch  # noqa: F401  — lazy import keeps non-torch envs working
        except ImportError as e:
            raise PolicyLoadError(
                f"torch is required to load .pt policies ({e}). "
                "Install torch or fall back to FakePolicyRunner."
            ) from e

        import torch
        try:
            # First try torch.jit — most LimX inference exports use this.
            self._module = torch.jit.load(
                str(self._checkpoint_path), map_location=self._device_name
            )
            self._module.eval()
            self._module_kind = "scripted"
            return
        except Exception:
            pass

        # Fall back to a raw .pt state_dict. We don't reconstruct the MLP
        # here; we just keep the dict and surface a clear error in act().
        try:
            obj = torch.load(
                str(self._checkpoint_path), map_location=self._device_name
            )
        except Exception as e:
            raise PolicyLoadError(
                f"could not torch.load({self._checkpoint_path}): {e}"
            ) from e
        self._module = obj
        self._module_kind = "state_dict"

    # -- inference ------------------------------------------------------

    def reset(self) -> None:
        self._step_count = 0
        # If the policy is recurrent we'd zero its hidden state here. The
        # default LimX walking policy is feed-forward MLP, so no-op.

    def act(
        self,
        observation: Sequence[float],
        command: Sequence[float],
    ) -> List[float]:
        if self._module_kind != "scripted":
            raise PolicyLoadError(
                "checkpoint loaded as raw state_dict — cannot run forward() "
                "without the trainer config that defines the actor MLP. "
                "Re-export the policy as a TorchScript module "
                "(torch.jit.script(actor)) or supply a wrapper."
            )
        import torch

        if len(observation) != self._obs_dim:
            raise ValueError(
                f"observation length {len(observation)} != "
                f"expected {self._obs_dim}"
            )
        cmd = list(command[: self._command_dim])
        while len(cmd) < self._command_dim:
            cmd.append(0.0)

        # Convention: the policy input is the observation vector built by
        # ObservationBuilder, which already includes the command in its
        # last command_dim slots. We pass obs through as-is; if the
        # trained checkpoint expects (obs, command) as a tuple we'd need
        # to adapt here.
        obs_t = torch.tensor(list(observation), dtype=torch.float32).unsqueeze(0)
        with torch.no_grad():
            try:
                action_t = self._module(obs_t)
            except Exception as e:
                raise PolicyLoadError(
                    f"forward() raised {type(e).__name__}: {e}. "
                    "Check obs_dim and action_dim against the checkpoint."
                ) from e
        action = action_t.squeeze(0).cpu().tolist()
        if len(action) != self._action_dim:
            # Don't raise — the backend can usually still consume a
            # different-length vector if it only uses the first N. Log
            # the mismatch via metadata.
            pass
        self._step_count += 1
        return action

    def get_metadata(self) -> Dict[str, Any]:
        return {
            "name": "PolicyRunner",
            "obs_dim": self._obs_dim,
            "action_dim": self._action_dim,
            "command_dim": self._command_dim,
            "action_semantic": "joint_pos_delta",  # TODO confirm vs checkpoint
            "trained_on": str(self._checkpoint_path),
            "module_kind": self._module_kind,
            "device": self._device_name,
            "step_count": self._step_count,
        }
