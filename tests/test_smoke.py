import mini_highlight_advisor as mha


def test_package_imports_with_version():
    assert isinstance(mha.__version__, str)
    assert mha.__version__
