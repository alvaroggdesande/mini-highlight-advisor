# Technique System — Design Spec

**Date:** 2026-09-02
**Status:** Draft — awaiting user review
**Classification:** Architectural (new module, extends Region, touches pipeline + UI + guide text)

## Background

The core promise of the tool is: *"this is fur — how do I paint it step by step?"* Today the
answer is always the same regardless of what the material is: band the luminance, label the
bands Shadow/Base/Midtone/Highlight/Bright Highlight, and say "apply across the highlighted
zone." That answer is correct for smooth layering. It is wrong — or at least incomplete — for
drybrushing, glazing, NMM, and OSL.

`Region.material` already carries a technique hint (`"matte"` | `"nmm"`), but it only switches
the shading math (nothing else). There is no per-technique guide text, no per-technique role
names, no per-technique step captions. This spec builds that spine, with **drybrushing on fur**
as the worked first entry — zero new rendering math, maximum guide-text payoff, simple-image
compatible.

## Goals

1. A **`TechniqueSpec`** data model that carries: display name, role names for up to 7 bands,
   coverage notes per role, step-caption overrides, and an application hint.
2. A **registry** of techniques (`"smooth"`, `"drybrush"`) with room for `"nmm"` and `"osl"` to
   slot in later without restructuring anything.
3. **`RegionPlan`** carries the technique; the written guide (role names, notes, step captions)
   respects it.
4. The **technique picker** is visible in both simple-image mode and PS mode (currently the
   material selector is PS-only). NMM remains PS-only within the picker.
5. **Path L byte-identical** — drybrush changes only text; the rendered images are unchanged.
6. **Back-compat** — `"matte"` and `"nmm"` in saved projects load cleanly; `"drybrush"` is a
   new valid value, no migration needed.

## Non-goals (this slice)

- NMM redesign — the NMM model stays as-is; it gains a registry entry but no new math.
- OSL — future entry, the registry shape supports it; not built here.
- Per-technique step *images* that look different — the zone/cumulative/exact renders are
  correct for drybrush already (luminance bands land on raised peaks = where drybrush catches).
  Only the text around the images changes.
- UX reorganisation — the technique picker stays in `results.py` for now. Moving it into the
  region editor panel is the planned UX-pass follow-up.
- Material presets (fur / robe / skin / wood) — those bundle a technique + palette suggestions.
  They come after the technique spine is proven.
- Roughness-driven auto-detection — using `roughness.png` from PS to suggest drybrush is a
  PS-only nicety. Not built here; slots in naturally once the technique field exists.

## Architecture

```
techniques.py          ← new; pure, torch-free, Streamlit-free
  TechniqueSpec
  TECHNIQUES: dict[str, TechniqueSpec]   {"smooth", "drybrush"}
  role_names_for(technique, n) -> list[str]
  coverage_note_for(technique, role) -> str
  step_captions_for(technique) -> StepCaptions  (across/stays strings)

regions.py             ← Region.material valid values: + "drybrush"
pipeline.py            ← RegionPlan.technique field; plan_region passes it through
overlay.py             ← render_legend receives roles already (no change); _COVERAGE_NOTES stays
                          for smooth fallback (rename notes become technique-aware via helpers)
ui/helpers.py          ← render_region_steps accepts technique, adjusts captions
ui/results.py          ← technique picker replaces PS-only material selector; always visible;
                          NMM option guarded by normal_field is not None
projects.py            ← no change; "drybrush" is just another valid material string
```

No change to banding math, step image rendering, palette, or matching.

## Data model — `techniques.py`

```python
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass(frozen=True)
class StepCaptions:
    """Text for the across/stays columns in render_region_steps."""
    across: str   # e.g. "Apply across — whole area (~{pct}%)"
    stays: str    # e.g. "Stays this colour — final (~{pct}%)"


@dataclass(frozen=True)
class TechniqueSpec:
    name: str                          # internal key, e.g. "drybrush"
    display: str                       # UI label, e.g. "Drybrush"
    description: str                   # one-liner shown as tooltip
    _role_names: tuple[str, ...]       # up to 7, ordered dark→light
    _coverage_notes: dict[str, str]    # role → application note
    captions: StepCaptions

    def role_names(self, n: int) -> list[str]:
        """Return n role names for this technique, clamping to available."""
        roles = self._role_names
        if n <= len(roles):
            return list(roles[-n:])          # always ends at the lightest role
        # n > available: pad from the left with indexed names
        pad = [f"Layer {i+1}" for i in range(n - len(roles))]
        return pad + list(roles)

    def coverage_note(self, role: str) -> str:
        return self._coverage_notes.get(role, "")
```

### Smooth (the existing behaviour, named)

```python
TechniqueSpec(
    name="smooth",
    display="Smooth layering",
    description="Classic glazed layers, working dark to light.",
    _role_names=(
        "Shadow", "Base", "Midtone", "Highlight",
        "Bright Highlight", "Edge Highlight", "Extreme Edge Highlight",
    ),
    _coverage_notes={
        "Shadow":                "deepest recesses",
        "Base":                  "the main body of the surface",
        "Midtone":               "flat, gently-lit panels",
        "Highlight":             "raised areas facing the light",
        "Bright Highlight":      "the brightest broad zones",
        "Edge Highlight":        "the crisp lit rim of every plate",
        "Extreme Edge Highlight":"sharpest edges only, the final pop",
    },
    captions=StepCaptions(
        across="Apply across — whole area (~{pct:.0f}%)",
        stays="Stays this colour — final (~{pct:.0f}%)",
    ),
)
```

### Drybrush

Drybrush builds surface texture from dark-to-light with a nearly-dry brush, catching only the
raised peaks. The darkest colour (base coat / wash) goes everywhere and fills recesses; each
subsequent pass uses less paint and less pressure, landing only on the topmost raised areas.

```python
TechniqueSpec(
    name="drybrush",
    display="Drybrush",
    description="Drag a nearly-dry brush across raised surfaces — fur, chainmail, cloth, textured bases.",
    _role_names=(
        "Base coat",
        "First drybrush",
        "Second drybrush",
        "Highlight drybrush",
        "Fine highlight",
        "Tip highlight",
        "Specular tip",
    ),
    _coverage_notes={
        "Base coat":       "basecoat or wash into every recess — your darkest colour",
        "First drybrush":  "heavy drybrush across the whole textured surface",
        "Second drybrush": "medium drybrush, slightly less pressure",
        "Highlight drybrush": "light drybrush, raised peaks and strands only",
        "Fine highlight":  "barely-dry brush on the sharpest raised tips",
        "Tip highlight":   "almost no paint — crisp topmost fibres only",
        "Specular tip":    "near-white on the very sharpest peaks",
    },
    captions=StepCaptions(
        across="Drybrush across raised areas (~{pct:.0f}%)",
        stays="Peak colour — this zone only (~{pct:.0f}%)",
    ),
)
```

`TECHNIQUES = {"smooth": <smooth_spec>, "drybrush": <drybrush_spec>}` — a plain dict; NMM and
OSL will add entries here when their slices land.

Convenience: `"matte"` is an alias for `"smooth"` in the lookup so old project files load
cleanly.

## Pipeline changes — `pipeline.py`

`RegionPlan` gains one field:

```python
technique: str = "smooth"
```

`plan_region` signature gains `technique: str = "smooth"` (alongside existing `material`).
For now `material` and `technique` are the same value; when NMM and OSL are distinct they will
diverge. Inside `plan_region`:

```python
from .techniques import TECHNIQUES

spec = TECHNIQUES.get(technique) or TECHNIQUES["smooth"]
roles = spec.role_names(len(palette))
```

`roles` replaces the current call to `palette.role_names(len(palette))` for the `RegionPlan`
fields. The rest of `plan_region` is unchanged.

`analyze_regions` passes `material` as `technique` to `plan_region` (same value; the rename is
UI-facing only at this stage).

## `ui/helpers.py` — technique-aware captions

`render_region_steps(steps, roles, names, coverage, technique="smooth")` gains the `technique`
parameter. Inside the step loop, the "Apply across" and "Stays this colour" caption strings
come from `TECHNIQUES[technique].captions` (with `{pct}` formatted inline):

```python
from mini_highlight_advisor.techniques import TECHNIQUES

spec = TECHNIQUES.get(technique) or TECHNIQUES["smooth"]
# ...
c2.image(..., caption=spec.captions.across.format(pct=cum_cov))
c3.image(..., caption=spec.captions.stays.format(pct=cov))
```

`results.py` passes `plan.technique` when calling `render_region_steps`.

## `ui/results.py` — technique picker (replaces PS-only material selector)

The current PS-only material selectbox becomes an always-visible **technique picker** per region.
Options depend on mode:

- **Always:** "Smooth layering", "Drybrush"
- **PS mode only (normal_field is not None):** also "NMM"

```python
technique_options = ["Smooth layering", "Drybrush"]
technique_keys = ["smooth", "drybrush"]
if normal_field is not None:
    technique_options.append("NMM")
    technique_keys.append("nmm")

cur = book.material_at(sel)   # "matte" | "smooth" | "drybrush" | "nmm"
# normalise "matte" → "smooth" for the picker
cur_key = "smooth" if cur == "matte" else cur
cur_idx = technique_keys.index(cur_key) if cur_key in technique_keys else 0

choice_label = st.selectbox(
    f"Technique — {book.names()[sel]}",
    technique_options,
    index=cur_idx,
    key=keys.material(sel),
    help="How to apply paint in this region. Drybrush: drag nearly-dry brush across "
         "raised surfaces. NMM (PS only): non-metallic metal from surface normals.",
)
book.set_material_at(sel, technique_keys[technique_options.index(choice_label)])
```

The NMM horizon slider remains guarded by `normal_field is not None`. No other results.py
change.

## `overlay.py` — `render_legend`

`render_legend` already receives `roles` as a parameter (the caller computes them). Now the
caller passes `spec.role_names(n)` instead of `palette.role_names(n)`. The coverage notes
lookup (`_COVERAGE_NOTES.get(roles[i], "")`) needs updating: `_COVERAGE_NOTES` currently only
has smooth-technique role names. Two options:

**Chosen:** pass `coverage_notes: dict[str, str]` into `render_legend` (new param, default
`_COVERAGE_NOTES` for backward compat). The call site in `pipeline.py`'s `band_and_render`
passes `spec.coverage_notes` when a technique is known. The existing `_COVERAGE_NOTES` dict
stays as the smooth default so `analyze()` (the non-region path) remains unchanged.

Signature: `render_legend(colors, names, roles, coverage, height, coverage_notes=None)`.
Inside: `notes = coverage_notes or _COVERAGE_NOTES`.

## `regions.py`

`Region.material` field valid values: `"matte"` | `"nmm"` | `"drybrush"`. No structural change.
The `"drybrush"` value is saved and loaded as-is; old projects without it default to `"matte"`.

## Testing strategy

**`tests/test_techniques.py`** — pure, no Streamlit:
- `role_names_for("smooth", n)` returns exactly the same list as current `palette.role_names(n)`
  for n = 1..7 (regression lock on smooth).
- `role_names_for("drybrush", n)` — returns correct names, always `n` entries, darkest first.
- `coverage_note_for("smooth", "Shadow")` matches `_COVERAGE_NOTES["Shadow"]`.
- `coverage_note_for("drybrush", "Base coat")` returns non-empty string.
- `TECHNIQUES["matte"]` is the smooth spec (alias check).
- Unknown technique → falls back to smooth without raising.

**`tests/test_pipeline_technique.py`** — pure:
- `plan_region(..., technique="smooth")` produces `RegionPlan.technique == "smooth"` and the
  same role names as before (regression lock).
- `plan_region(..., technique="drybrush")` produces `RegionPlan.technique == "drybrush"` and
  drybrush role names; band placement (the actual pixel assignments) is **byte-identical** to
  `technique="smooth"` on the same inputs (no rendering math change).
- `analyze_regions` round-trip: a region with `material="drybrush"` produces a plan with
  `technique="drybrush"`.

**`tests/test_ui_technique_picker.py`** — AppTest:
- Technique picker renders in simple-image mode (no normal_field).
- Picking "Drybrush" writes `"drybrush"` to the book.
- NMM option absent when no normal_field; present when normal_field seeded.
- `"matte"` in book normalises to "Smooth layering" in the picker without error.

## Rollout / build order

1. **`techniques.py`** — TechniqueSpec + smooth + drybrush + tests. Pure. No other file touches.
2. **`pipeline.py`** — `RegionPlan.technique`; `plan_region(technique=)`; regression lock.
3. **`overlay.py`** — `render_legend(coverage_notes=)` param; caller passes spec notes.
4. **`ui/helpers.py`** — `render_region_steps(technique=)` caption override.
5. **`ui/results.py`** — technique picker (replaces PS-only material selector).

Steps 1–2 deliver the core; steps 3–5 are the visible payoff. Each step is independently
testable and committable.

## Self-review

**Placeholder scan:** no TBD; all role-name tables complete to 7 entries; caption format
strings use `{pct}` consistently.

**Consistency:** `Region.material` → `plan_region(technique=)` → `RegionPlan.technique` →
`render_region_steps(technique=)` — the value flows through without renaming mid-way.
`"matte"` alias is handled in exactly one place (TECHNIQUES lookup).

**Scope:** 5 files, zero new rendering math, zero persistence migration. Right-sized.

**Path L byte-identical:** confirmed — drybrush selects the same luminance shading as smooth;
only role names + captions differ.

**Back-compat:** `"matte"` in saved projects resolves to smooth spec. Old AppTest harnesses that
don't seed a technique get `"smooth"` by default. `render_region_steps` without `technique=`
defaults to `"smooth"`. `render_legend` without `coverage_notes=` defaults to `_COVERAGE_NOTES`.
