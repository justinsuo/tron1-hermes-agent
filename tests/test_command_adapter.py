import math

import pytest

from locomotion import CommandAdapter, LocomotionCommand, SafetyLimits


def test_default_limits_clip_high_vx():
    adapter = CommandAdapter()
    cmd = adapter.build(vx=5.0, duration=0.5)
    assert cmd.vx == pytest.approx(0.8)
    assert any("vx clipped" in n for n in cmd.clip_notes)


def test_default_limits_clip_negative_vx():
    cmd = CommandAdapter().build(vx=-5.0, duration=0.5)
    assert cmd.vx == pytest.approx(-0.8)


def test_duration_clipped_to_max():
    cmd = CommandAdapter().build(duration=10.0)
    assert cmd.duration == pytest.approx(2.0)


def test_negative_duration_clipped_to_zero():
    cmd = CommandAdapter().build(duration=-3.0)
    assert cmd.duration == 0.0


def test_custom_limits_respected():
    adapter = CommandAdapter(limits=SafetyLimits(max_vx=0.3))
    cmd = adapter.build(vx=0.5)
    assert cmd.vx == pytest.approx(0.3)


def test_within_limits_passthrough():
    cmd = CommandAdapter().build(vx=0.4, vy=0.1, yaw_rate=0.2, duration=1.0)
    assert (cmd.vx, cmd.vy, cmd.yaw_rate, cmd.duration) == (0.4, 0.1, 0.2, 1.0)
    assert cmd.clip_notes == ()


def test_as_policy_command_is_3_vector():
    cmd = CommandAdapter().build(vx=0.4, vy=0.1, yaw_rate=0.2)
    vec = cmd.as_policy_command()
    assert len(vec) == 3
    assert vec == [0.4, 0.1, 0.2]


def test_as_velocity_setpoint_drops_lateral():
    cmd = CommandAdapter().build(vx=0.4, vy=0.3, yaw_rate=0.1, duration=1.0)
    sp = cmd.as_velocity_setpoint()
    assert sp == {"linear": 0.4, "angular": 0.1, "duration": 1.0}


def test_non_numeric_raises():
    with pytest.raises(ValueError):
        CommandAdapter().build(vx="fast")  # type: ignore[arg-type]


def test_nan_raises():
    with pytest.raises(ValueError):
        CommandAdapter().build(vx=float("nan"))


def test_to_dict_roundtrip_keys():
    cmd = CommandAdapter().build(vx=0.2, yaw_rate=0.1, duration=0.5)
    d = cmd.to_dict()
    assert set(d) >= {"vx", "vy", "yaw_rate", "duration", "clip_notes"}
