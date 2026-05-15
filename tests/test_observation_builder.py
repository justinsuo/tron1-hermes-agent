import math

import pytest

from locomotion import ObservationBuilder, ObservationSpec
from locomotion.observation_builder import (
    JOINT_ORDER, DEFAULT_JOINT_POS, domain_randomize_defaults,
)


def _zeros_args(n_joints: int) -> dict:
    return dict(
        base_ang_vel=(0.0, 0.0, 0.0),
        base_quat=(1.0, 0.0, 0.0, 0.0),
        joint_pos=[0.0] * n_joints,
        joint_vel=[0.0] * n_joints,
        last_action=[0.0] * n_joints,
        command=(0.0, 0.0, 0.0),
    )


def test_default_total_dim_matches_spec():
    spec = ObservationSpec()
    builder = ObservationBuilder(spec=spec)
    obs = builder.build(**_zeros_args(spec.num_joints))
    assert len(obs) == spec.total_dim


def test_total_dim_includes_gait_clock_when_enabled():
    spec = ObservationSpec(include_gait_clock=True)
    builder = ObservationBuilder(spec=spec)
    obs = builder.build(**_zeros_args(spec.num_joints), gait_phase=0.25)
    assert len(obs) == spec.total_dim
    # The last two slots should be sin/cos of (2π · 0.25) = (1, 0)
    assert obs[-2] == pytest.approx(1.0, abs=1e-6)
    assert obs[-1] == pytest.approx(0.0, abs=1e-6)


def test_command_lives_in_correct_slot():
    spec = ObservationSpec()
    builder = ObservationBuilder(spec=spec)
    obs = builder.build(
        base_ang_vel=(0.0, 0.0, 0.0),
        base_quat=(1.0, 0.0, 0.0, 0.0),
        joint_pos=[0.0] * spec.num_joints,
        joint_vel=[0.0] * spec.num_joints,
        last_action=[0.0] * spec.num_joints,
        command=(0.5, -0.1, 0.2),
    )
    # last command_dim slots are the command
    assert obs[-3:] == [0.5, -0.1, 0.2]


def test_projected_gravity_identity_quaternion():
    spec = ObservationSpec()
    builder = ObservationBuilder(spec=spec)
    obs = builder.build(**_zeros_args(spec.num_joints))
    # base_ang_vel(3) then projected_gravity(3). Identity quaternion =>
    # gravity = (0, 0, -1)
    assert obs[3:6] == pytest.approx([0.0, 0.0, -1.0], abs=1e-6)


def test_joint_pos_subtracted_against_default():
    spec = ObservationSpec()
    defaults = [0.1] * spec.num_joints
    builder = ObservationBuilder(spec=spec, default_joint_pos=defaults)
    args = _zeros_args(spec.num_joints)
    args["joint_pos"] = [0.5] * spec.num_joints
    obs = builder.build(**args)
    # joint_pos_rel slots = 0.5 - 0.1 = 0.4 each
    j_slice = obs[6:6 + spec.num_joints]
    assert j_slice == pytest.approx([0.4] * spec.num_joints)


def test_noise_changes_output_when_nonzero():
    import random
    spec = ObservationSpec()
    a = ObservationBuilder(spec=spec, noise_std=0.0, rng=random.Random(1)).build(
        **_zeros_args(spec.num_joints)
    )
    b = ObservationBuilder(spec=spec, noise_std=0.1, rng=random.Random(1)).build(
        **_zeros_args(spec.num_joints)
    )
    assert a != b


def test_default_joint_pos_constants_match_joint_order():
    assert len(JOINT_ORDER) == len(DEFAULT_JOINT_POS)


def test_domain_randomize_defaults_perturbs():
    import random
    spec = ObservationSpec()
    builder = ObservationBuilder(spec=spec, rng=random.Random(0))
    before = list(builder.default_joint_pos)
    domain_randomize_defaults(builder, joint_pos_std=0.1)
    after = list(builder.default_joint_pos)
    assert before != after
