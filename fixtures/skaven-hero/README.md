# Fixture: skaven-hero

A **paired** real-mini fixture for region/segmentation spikes and future tests.

| File | What | Use |
|------|------|-----|
| `primed.png` | The clean, standalone **primed** photo you uploaded to the app (grey primer, background-removed). **Not** the app's output panel. | Input for the SAM segmentation spike — the thing we test "can SAM find regions on a monochrome primer". |
| `painted-reference.png` | The official **painted** studio photo of the same sculpt. | The reference that a (future) labeling step reads to name regions + suggest per-region palettes. Also the canonical colored-mini test case. |

## Why paired

Priming removes the colour/texture cues that distinguish armour from cloth, so the
painted reference is what restores them. The two images are **different pose / crop /
scale / instance** — so the reference can only *label* regions, never transfer masks
pixel-for-pixel. See `docs/superpowers/specs/2026-08-09-roadmap-and-idea-assessment.md`.

## Provenance / licensing

`painted-reference.png` is a Games Workshop studio product image (copyright GW). Kept
here only as a private-repo test fixture — **do not redistribute publicly.**
