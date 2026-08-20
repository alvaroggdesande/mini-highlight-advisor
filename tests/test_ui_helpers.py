from ui import helpers


def test_swatch_is_inline_span_with_colour():
    html = helpers.swatch("# abc123".replace(" ", ""), size="2em")
    assert "background-color:#abc123" in html
    assert "width:2em" in html and "height:2em" in html
    assert html.startswith("<span")


def test_current_cov_seed_length_and_sums_to_100():
    seed = helpers.current_cov_seed(5)
    assert len(seed) == 5
    assert abs(sum(seed) - 100.0) < 1.0  # default_coverage fractions * 100
