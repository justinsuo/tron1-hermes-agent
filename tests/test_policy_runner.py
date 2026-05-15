import pytest

from locomotion import PolicyLoadError, PolicyRunner


def test_missing_checkpoint_raises_clear_error(tmp_path):
    nonexistent = tmp_path / "no-such.pt"
    with pytest.raises(PolicyLoadError) as exc:
        PolicyRunner(str(nonexistent))
    assert "checkpoint not found" in str(exc.value)
    assert str(nonexistent) in str(exc.value)


def test_garbage_file_raises_clear_error(tmp_path):
    p = tmp_path / "garbage.pt"
    p.write_text("definitely not a torch checkpoint")
    pytest.importorskip("torch")
    with pytest.raises(PolicyLoadError) as exc:
        PolicyRunner(str(p))
    # We don't care which torch-internal error surfaces — only that we
    # wrap it in PolicyLoadError so Hermes can fall back gracefully.
    assert "torch.load" in str(exc.value) or "could not" in str(exc.value)
