import cv2
import numpy as np
from mini_highlight_advisor.input_check import (
    check_input, CheckResult, SHOOTING_GUIDE, PAINTED_CAPTURE_NOTE,
    FLAT_SPREAD_MAX, MIN_FOCUS_VAR,
)
from mini_highlight_advisor.masking import load_image, compute_mask

# primed_hand.png has a real alpha cutout (tight mask on the primed mini); primed.png
# is opaque black-on-black, so its mask is the whole frame and would pollute the checks.
PRIMED_FIXTURE = "fixtures/skaven-hero/primed_hand.png"


def _full_mask(h, w):
    return np.ones((h, w), dtype=bool)


def test_flat_image_fails_lighting_with_advice():
    # Uniform mid-grey -> no tonal spread -> lighting must fail.
    rgb = np.full((200, 200, 3), 128, dtype=np.uint8)
    results = check_input(rgb, _full_mask(200, 200))
    lighting = next(r for r in results if r.id == "lighting")
    assert lighting.ok is False
    assert "flat" in lighting.detail.lower()
    assert "raking" in lighting.detail.lower()  # actionable fix present


def test_high_contrast_gradient_passes_lighting():
    grad = np.tile(np.linspace(0, 255, 200, dtype=np.uint8), (200, 1))
    rgb = np.stack([grad, grad, grad], axis=-1)
    results = check_input(rgb, _full_mask(200, 200))
    lighting = next(r for r in results if r.id == "lighting")
    assert lighting.ok is True
    assert isinstance(lighting, CheckResult)
    assert lighting.value >= FLAT_SPREAD_MAX


def test_check_input_returns_lighting_first():
    rgb = np.full((50, 50, 3), 128, dtype=np.uint8)
    results = check_input(rgb, _full_mask(50, 50))
    assert results[0].id == "lighting"


def test_empty_mask_returns_non_crashing_advice():
    rgb = np.full((50, 50, 3), 128, dtype=np.uint8)
    mask = np.zeros((50, 50), dtype=bool)
    results = check_input(rgb, mask)  # must not raise
    assert len(results) >= 1
    assert results[0].ok is False
    assert "no mini detected" in results[0].detail.lower()


def test_mostly_black_fails_exposure_crushed():
    rgb = np.zeros((200, 200, 3), dtype=np.uint8)  # all crushed to black
    results = check_input(rgb, _full_mask(200, 200))
    exposure = next(r for r in results if r.id == "exposure")
    assert exposure.ok is False
    assert "crushed" in exposure.detail.lower()
    assert "raise exposure" in exposure.detail.lower()


def test_mostly_white_fails_exposure_blown():
    rgb = np.full((200, 200, 3), 255, dtype=np.uint8)  # all blown out
    results = check_input(rgb, _full_mask(200, 200))
    exposure = next(r for r in results if r.id == "exposure")
    assert exposure.ok is False
    assert "blown" in exposure.detail.lower()
    assert "lower exposure" in exposure.detail.lower()


def test_balanced_gradient_passes_exposure():
    grad = np.tile(np.linspace(20, 235, 200, dtype=np.uint8), (200, 1))
    rgb = np.stack([grad, grad, grad], axis=-1)
    results = check_input(rgb, _full_mask(200, 200))
    exposure = next(r for r in results if r.id == "exposure")
    assert exposure.ok is True


def test_sharp_checkerboard_passes_focus():
    tile = np.kron(np.array([[0, 1], [1, 0]]), np.ones((10, 10)))
    board = np.tile(tile, (10, 10)).astype(np.uint8) * 255
    rgb = np.stack([board, board, board], axis=-1)
    results = check_input(rgb, _full_mask(*board.shape))
    focus = next(r for r in results if r.id == "focus")
    assert focus.ok is True
    assert focus.value >= MIN_FOCUS_VAR


def test_blurred_image_fails_focus_with_advice():
    tile = np.kron(np.array([[0, 1], [1, 0]]), np.ones((10, 10)))
    board = np.tile(tile, (10, 10)).astype(np.uint8) * 255
    blurred = cv2.GaussianBlur(board, (0, 0), sigmaX=8)
    rgb = np.stack([blurred, blurred, blurred], axis=-1)
    results = check_input(rgb, _full_mask(*blurred.shape))
    focus = next(r for r in results if r.id == "focus")
    assert focus.ok is False
    assert "focus" in focus.detail.lower()
    assert "steady" in focus.detail.lower()  # actionable fix present


def test_tiny_mask_fails_framing_low_coverage():
    rgb = np.full((400, 400, 3), 128, dtype=np.uint8)
    mask = np.zeros((400, 400), dtype=bool)
    mask[0:20, 0:20] = True  # ~0.25% coverage, tiny area
    results = check_input(rgb, mask)
    framing = next(r for r in results if r.id == "resolution")
    assert framing.ok is False
    assert framing.label == "Framing"
    assert "frame" in framing.detail.lower()


def test_well_framed_mask_passes_framing():
    rgb = np.full((400, 400, 3), 128, dtype=np.uint8)
    mask = np.zeros((400, 400), dtype=bool)
    mask[50:350, 100:300] = True  # 60_000 px, 37.5% coverage
    results = check_input(rgb, mask)
    framing = next(r for r in results if r.id == "resolution")
    assert framing.ok is True


def test_small_image_fails_framing_low_resolution():
    rgb = np.full((400, 400, 3), 128, dtype=np.uint8)
    mask = np.zeros((400, 400), dtype=bool)
    mask[50:150, 50:350] = True  # 100x300 = 30_000 px area (< 40_000) but 18.75% coverage (>= 0.15)
    results = check_input(rgb, mask)
    framing = next(r for r in results if r.id == "resolution")
    assert framing.ok is False
    assert "resolution" in framing.detail.lower() or "larger image" in framing.detail.lower()


def test_check_input_order_is_stable():
    rgb = np.full((400, 400, 3), 128, dtype=np.uint8)
    mask = np.zeros((400, 400), dtype=bool)
    mask[50:350, 100:300] = True
    ids = [r.id for r in check_input(rgb, mask)]
    assert ids == ["lighting", "exposure", "focus", "resolution"]


def test_known_good_primed_photo_passes_all_checks():
    rgb, alpha = load_image(PRIMED_FIXTURE)
    mask = compute_mask(rgb, alpha)
    results = check_input(rgb, mask)
    failed = [r.id for r in results if not r.ok]
    assert failed == [], f"known-good photo failed checks: {failed}"
    assert all(isinstance(r.detail, str) and r.detail.strip() for r in results)


def test_shooting_guide_covers_the_key_points():
    text = SHOOTING_GUIDE.lower()
    for keyword in ["raking", "flash", "frame", "background", "focus"]:
        assert keyword in text, f"shooting guide missing '{keyword}'"


def test_shooting_guide_names_why_on_axis_flash_fails():
    # The flash line must explain the mechanism (fills recesses / erases shadows),
    # not just say "no flash" — that mechanism is the whole reason capture matters.
    text = SHOOTING_GUIDE.lower()
    assert "on-axis" in text or "frontal" in text
    assert "recess" in text or "erase" in text or "fills" in text


def test_painted_capture_note_flags_auto_check_is_primed_only():
    # On painted/colored minis the automatic lighting check can't tell flat-flash
    # from good raking light (single-image albedo/shading ambiguity), so the note
    # must put capture discipline on the user and say the auto-check is primed-only.
    text = PAINTED_CAPTURE_NOTE.lower()
    assert "paint" in text  # addresses painted/colored minis
    assert "primed" in text  # scopes the automatic check to primed
    assert "raking" in text or "side light" in text  # actionable capture fix


def test_bimodal_image_fails_exposure_both_crushed_and_blown():
    half = np.zeros((200, 200, 3), dtype=np.uint8)
    half[:, 100:] = 255  # left half black, right half white
    results = check_input(half, np.ones((200, 200), dtype=bool))
    exposure = next(r for r in results if r.id == "exposure")
    assert exposure.ok is False
    assert "crushed" in exposure.detail.lower()
    assert "blown" in exposure.detail.lower()
