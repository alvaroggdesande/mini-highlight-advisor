from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .palette import PaintColor

BUILTIN_PATH = Path(__file__).parent / "data" / "recipes_builtin.json"
USER_PATH = Path(__file__).resolve().parents[2] / "user_data" / "recipes.json"


@dataclass(frozen=True)
class RecipeStep:
    label: str
    hex: str
    paint_ref: str | None = None


@dataclass(frozen=True)
class Recipe:
    name: str
    steps: list[RecipeStep]


def _parse(data: dict) -> list[Recipe]:
    return [
        Recipe(r["name"], [RecipeStep(s["label"], s["hex"], s.get("paint_ref")) for s in r["steps"]])
        for r in data.get("recipes", [])
    ]


def load_builtin(path: Path = BUILTIN_PATH) -> list[Recipe]:
    return _parse(json.loads(Path(path).read_text(encoding="utf-8")))


def load_user(path: Path = USER_PATH) -> list[Recipe]:
    path = Path(path)
    if not path.exists():
        return []
    return _parse(json.loads(path.read_text(encoding="utf-8")))


def save_user(recipe: Recipe, path: Path = USER_PATH) -> None:
    path = Path(path)
    existing = [r for r in load_user(path) if r.name != recipe.name]
    existing.append(recipe)
    payload = {"recipes": [
        {"name": r.name, "steps": [
            {"label": s.label, "hex": s.hex, "paint_ref": s.paint_ref} for s in r.steps
        ]} for r in existing
    ]}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_all(builtin_path: Path = BUILTIN_PATH, user_path: Path = USER_PATH) -> list[Recipe]:
    return load_builtin(builtin_path) + load_user(user_path)


def to_palette(recipe: Recipe) -> list[PaintColor]:
    return [PaintColor(name=s.paint_ref or s.label, hex=s.hex) for s in recipe.steps]
