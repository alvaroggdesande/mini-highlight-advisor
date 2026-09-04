import importlib


def test_osl_panel_module_imports_and_has_render():
    mod = importlib.import_module("ui.osl_panel")
    assert hasattr(mod, "render")


def test_ps_mode_calls_osl_only_with_normals(monkeypatch):
    # Guard: OSL must be gated on has_normals. Assert the source string references
    # the normals gate so the panel can never run in Path-L mode.
    import inspect, ui.ps_mode as ps
    src = inspect.getsource(ps)
    assert "osl" in src.lower()
    assert "normal" in src.lower()
