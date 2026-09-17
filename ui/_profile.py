"""Opt-in per-rerun timing, printed to the terminal running Streamlit.

Enable with the env var MHA_PROFILE=1, e.g. (PowerShell):
    $env:MHA_PROFILE=1; streamlit run app.py

Everything here is a no-op when disabled, so it's safe to leave wired in. Each
rerun prints a "── RERUN #n ──" banner followed by one line per timed phase, so
you can see exactly which phase dominates a slow interaction (drawing, saving…).
"""
import os
import sys
import time
import contextlib

ENABLED = os.environ.get("MHA_PROFILE") == "1"

_n = 0
_t0 = None


def rerun_start() -> None:
    global _n, _t0
    if not ENABLED:
        return
    _n += 1
    _t0 = time.perf_counter()
    print(f"\n[MHA] ──────── RERUN #{_n} ────────", file=sys.stderr, flush=True)


def rerun_end() -> None:
    if not ENABLED or _t0 is None:
        return
    ms = (time.perf_counter() - _t0) * 1000
    print(f"[MHA] ── total rerun {ms:8.1f} ms", file=sys.stderr, flush=True)


def mark(msg: str) -> None:
    if ENABLED:
        print(f"[MHA]    · {msg}", file=sys.stderr, flush=True)


@contextlib.contextmanager
def prof(label: str):
    if not ENABLED:
        yield
        return
    s = time.perf_counter()
    try:
        yield
    finally:
        ms = (time.perf_counter() - s) * 1000
        print(f"[MHA]    {label:34s} {ms:8.1f} ms", file=sys.stderr, flush=True)
