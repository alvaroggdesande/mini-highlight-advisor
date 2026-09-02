# src/mini_highlight_advisor/techniques.py
"""Technique registry: maps technique names to role names, coverage notes, and
step captions. Torch-free, Streamlit-free.

Each technique describes HOW paint is applied in a region:
  smooth   — classic glazed layers, dark-to-light (the original behaviour)
  drybrush — nearly-dry brush dragged across raised surfaces (fur, chainmail, cloth)

NMM and OSL are future entries; the registry shape accommodates them without
restructuring. Add an entry to TECHNIQUES and a get_technique() call picks it up.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class StepCaptions:
    """Per-technique caption strings for the two step-image columns.

    Both strings are Python format strings containing ``{pct:.0f}``
    (the band's percentage coverage) and nothing else.
    """
    across: str   # caption for the "apply across" column
    stays: str    # caption for the "stays this colour" column


@dataclass
class TechniqueSpec:
    """A technique: how paint is applied, and what to call each layer."""
    name: str
    display: str          # shown in the UI picker
    description: str      # tooltip text
    _roles: dict[int, list[str]]      # n -> role names, dark to light
    _coverage_notes: dict[str, str]   # role name -> application note
    captions: StepCaptions

    def role_names(self, n: int) -> list[str]:
        """Return n role names for this technique.

        Uses the per-n table when available; falls back to generic
        "Layer 1 … Layer n" for n values not in the table.
        """
        if n in self._roles:
            return list(self._roles[n])
        return [f"Layer {i + 1}" for i in range(n)]

    def coverage_note(self, role: str) -> str:
        """Short application note for a role name; empty string if unknown."""
        return self._coverage_notes.get(role, "")


_SMOOTH = TechniqueSpec(
    name="smooth",
    display="Smooth layering",
    description="Classic glazed layers, working dark to light.",
    _roles={
        3: ["Shadow", "Base", "Highlight"],
        4: ["Shadow", "Base", "Midtone", "Highlight"],
        5: ["Shadow", "Base", "Midtone", "Highlight", "Bright Highlight"],
        6: ["Shadow", "Deep Base", "Base", "Midtone", "Highlight", "Bright Highlight"],
        7: ["Shadow", "Deep Base", "Base", "Midtone", "Upper Midtone",
            "Highlight", "Bright Highlight"],
    },
    _coverage_notes={
        "Shadow":                  "deepest recesses",
        "Base":                    "the main body of the surface",
        "Deep Base":               "deep base tone, below midtone",
        "Midtone":                 "flat, gently-lit panels",
        "Upper Midtone":           "upper midtone transitional zone",
        "Highlight":               "raised areas facing the light",
        "Bright Highlight":        "the brightest broad zones",
        "Edge Highlight":          "the crisp lit rim of every plate",
        "Extreme Edge Highlight":  "sharpest edges only, the final pop",
    },
    captions=StepCaptions(
        across="Apply across — whole area (~{pct:.0f}%)",
        stays="Stays this colour — final (~{pct:.0f}%)",
    ),
)

_DRYBRUSH = TechniqueSpec(
    name="drybrush",
    display="Drybrush",
    description=(
        "Drag a nearly-dry brush across raised surfaces — "
        "fur, chainmail, cloth, textured bases."
    ),
    _roles={
        1: ["Base coat"],
        2: ["Base coat", "Drybrush"],
        3: ["Base coat", "Drybrush", "Highlight drybrush"],
        4: ["Base coat", "First drybrush", "Second drybrush", "Highlight drybrush"],
        5: ["Base coat", "First drybrush", "Second drybrush",
            "Highlight drybrush", "Fine highlight"],
        6: ["Base coat", "First drybrush", "Second drybrush",
            "Highlight drybrush", "Fine highlight", "Tip highlight"],
        7: ["Base coat", "First drybrush", "Second drybrush",
            "Highlight drybrush", "Fine highlight", "Tip highlight", "Specular tip"],
    },
    _coverage_notes={
        "Base coat":          "basecoat or wash into every recess — your darkest colour",
        "Drybrush":           "drybrush across the whole textured surface",
        "First drybrush":     "heavy drybrush across the whole textured surface",
        "Second drybrush":    "medium drybrush, slightly less pressure",
        "Highlight drybrush": "light drybrush, raised peaks and strands only",
        "Fine highlight":     "barely-dry brush on the sharpest raised tips",
        "Tip highlight":      "almost no paint — crisp topmost fibres only",
        "Specular tip":       "near-white on the very sharpest peaks",
    },
    captions=StepCaptions(
        across="Drybrush across raised areas (~{pct:.0f}%)",
        stays="Peak colour — this zone only (~{pct:.0f}%)",
    ),
)

TECHNIQUES: dict[str, TechniqueSpec] = {
    "smooth":   _SMOOTH,
    "matte":    _SMOOTH,    # back-compat alias for projects saved before this feature
    "drybrush": _DRYBRUSH,
}


def get_technique(name: str) -> TechniqueSpec:
    """Return the TechniqueSpec for name; falls back to smooth for unknown values."""
    return TECHNIQUES.get(name, _SMOOTH)
