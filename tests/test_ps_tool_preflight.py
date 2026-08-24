"""Pre-flight checks fail loud on the two common setup mistakes (wrong env,
bad checkpoint) before any capture work — instead of an einops traceback deep in
the vendored inference or a broadcast crash. Regression for the real run that was
launched from the app's torch-free .venv with a placeholder checkpoint path."""
import pytest

from tools import ps_tool

PreflightError = ps_tool.PreflightError


def test_runtime_env_check_flags_torchless_venv():
    # This test runs in the app's .venv, which is deliberately torch-free, so the
    # env check must fire and point the user at tools/.ps-venv.
    with pytest.raises(PreflightError, match="tools/.ps-venv"):
        ps_tool._check_runtime_env()


def test_checkpoint_check_rejects_missing_dir(tmp_path):
    with pytest.raises(PreflightError, match="not a directory"):
        ps_tool._check_checkpoint(tmp_path / "path" / "to" / "checkpoint")


def test_checkpoint_check_rejects_dir_without_normal_subdir(tmp_path):
    ckpt = tmp_path / "checkpoint"
    ckpt.mkdir()
    with pytest.raises(PreflightError, match="normal"):
        ps_tool._check_checkpoint(ckpt)


def test_checkpoint_check_accepts_valid_dir(tmp_path):
    ckpt = tmp_path / "checkpoint"
    (ckpt / "normal").mkdir(parents=True)
    ps_tool._check_checkpoint(ckpt)   # no raise
