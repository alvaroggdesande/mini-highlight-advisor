import mini_highlight_advisor as mha


def test_package_imports_with_version():
    assert isinstance(mha.__version__, str)
    assert mha.__version__


def test_input_check_panel_inputs_are_available():
    # The app renders one row per check + a guide; assert the contract it relies on.
    import numpy as np
    from mini_highlight_advisor.input_check import check_input, SHOOTING_GUIDE
    rgb = np.full((400, 400, 3), 128, dtype=np.uint8)
    mask = np.zeros((400, 400), dtype=bool)
    mask[50:350, 100:300] = True
    results = check_input(rgb, mask)
    assert [r.id for r in results] == ["lighting", "exposure", "focus", "resolution"]
    assert all(hasattr(r, "ok") and r.detail for r in results)
    assert SHOOTING_GUIDE.strip()
