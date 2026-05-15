import pytest

from locomotion import FakePolicyRunner


def test_action_length_matches_metadata():
    r = FakePolicyRunner(action_dim=10, obs_dim=48)
    obs = [0.0] * 48
    cmd = [0.3, 0.0, 0.1]
    act = r.act(obs, cmd)
    assert len(act) == r.get_metadata()["action_dim"] == 10


def test_command_echoed_into_first_slots():
    r = FakePolicyRunner(action_dim=10, obs_dim=48)
    act = r.act([0.0] * 48, [0.4, -0.2, 0.1])
    assert act[0] == pytest.approx(0.4)
    assert act[1] == pytest.approx(-0.2)
    assert act[2] == pytest.approx(0.1)
    assert all(a == 0.0 for a in act[3:])


def test_step_count_increments():
    r = FakePolicyRunner()
    assert r.get_metadata()["step_count"] == 0
    r.act([0.0] * 48, [0.1, 0.0, 0.0])
    r.act([0.0] * 48, [0.1, 0.0, 0.0])
    assert r.get_metadata()["step_count"] == 2


def test_reset_clears_step_count():
    r = FakePolicyRunner()
    r.act([0.0] * 48, [0.1, 0.0, 0.0])
    r.reset()
    assert r.get_metadata()["step_count"] == 0


def test_metadata_fields_present():
    md = FakePolicyRunner().get_metadata()
    for k in ("name", "obs_dim", "action_dim", "command_dim",
              "action_semantic", "trained_on"):
        assert k in md, f"missing metadata field: {k}"
    assert md["trained_on"] == "fake"


def test_short_command_padded():
    r = FakePolicyRunner(command_dim=3)
    act = r.act([0.0] * 48, [0.4])  # only vx given
    assert act[0] == pytest.approx(0.4)
    assert act[1] == 0.0
    assert act[2] == 0.0


def test_obs_length_mismatch_doesnt_crash():
    r = FakePolicyRunner(obs_dim=48)
    # Too-short observation — the fake runner should still return a valid
    # action (the kinematic backend doesn't consume it anyway).
    act = r.act([0.0] * 10, [0.1, 0.0, 0.0])
    assert len(act) == r.get_metadata()["action_dim"]
