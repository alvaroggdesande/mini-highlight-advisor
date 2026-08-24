"""SDM-UniPS runs as a subprocess with cwd=vendor/sdm_unips, so relative
--checkpoint / --test_dir would resolve against the vendor dir, not the user's
cwd. Regression for the real run that passed relative paths and got
'Pretrained model not Found' + 'Found 0 objects!'."""
from pathlib import Path

from tools import ps_tool


def _arg(cmd, flag):
    return cmd[cmd.index(flag) + 1]


def test_checkpoint_is_absolutized_from_relative_input():
    cmd = ps_tool._build_sdm_cmd(
        Path("some/rel/out/prepared.data"), Path("rel/checkpoint"),
        "/abs/session", "/abs/main.py")
    assert Path(_arg(cmd, "--checkpoint")).is_absolute()


def test_test_dir_is_absolutized_and_is_prepared_parent():
    cmd = ps_tool._build_sdm_cmd(
        Path("some/rel/out/prepared.data"), Path("rel/checkpoint"),
        "/abs/session", "/abs/main.py")
    test_dir = _arg(cmd, "--test_dir")
    assert Path(test_dir).is_absolute()
    # test_dir is the parent of the prepared .data dir (SDM scans it for *.data)
    assert Path(test_dir).name == "out"


def test_scan_extension_and_prefix_match_prepared_layout():
    cmd = ps_tool._build_sdm_cmd(
        Path("out/prepared.data"), Path("ckpt"), "/abs/session", "/abs/main.py")
    assert _arg(cmd, "--test_ext") == ".data"     # prepared dir is *.data
    assert _arg(cmd, "--test_prefix") == "L*"     # frames are L_*.png
