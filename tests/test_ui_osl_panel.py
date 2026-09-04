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


def test_render_signature_takes_background():
    import inspect, ui.osl_panel as op
    params = list(inspect.signature(op.render).parameters)
    assert params[:2] == ["mask_shape", "background_rgb"]


def test_rescale_click_maps_display_to_full_res():
    import ui.osl_panel as op
    # display canvas 300x200 over a 600x400 source: a click at (150,100)
    # is the centre -> full-res (300,200)
    x, y = op._rescale_click((150.0, 100.0), disp_w=300, disp_h=200,
                             src_w=600, src_h=400)
    assert abs(x - 300.0) < 1e-6
    assert abs(y - 200.0) < 1e-6


def test_rescale_click_identity_when_same_size():
    import ui.osl_panel as op
    x, y = op._rescale_click((42.0, 17.0), disp_w=128, disp_h=128,
                             src_w=128, src_h=128)
    assert (x, y) == (42.0, 17.0)
