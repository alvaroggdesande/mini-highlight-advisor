import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { useProjectStore, activeBookOf } from "../../store/projectStore";
import { useCatalogStore } from "../../store/catalogStore";
import { listRecipes } from "../../api/client";
import type { Recipe, PaintColor } from "../../api/types";

function toPalette(recipe: Recipe, catalog: PaintColor[]): PaintColor[] {
  return recipe.steps.map((step) => {
    const found = step.paint_ref ? catalog.find((p) => p.name === step.paint_ref) : undefined;
    return found ?? { name: "custom", hex: step.hex, code: "", finish: "matte" };
  });
}

interface Props { onRecipeLoaded(): void; }

export function RecipeLoader({ onRecipeLoaded }: Props) {
  const { t } = useTranslation();
  const book = useProjectStore((s) => activeBookOf(s));
  const catalogPaints = useCatalogStore((s) => s.paints);
  const setPaletteAt = useProjectStore((s) => s.setPaletteAt);

  const [recipes, setRecipes] = useState<Recipe[]>([]);
  const [selected, setSelected] = useState<string>("");

  useEffect(() => {
    listRecipes().then((res) => {
      setRecipes(res.recipes);
      if (res.recipes.length > 0) setSelected(res.recipes[0].name);
    });
  }, []);

  if (!book) return null;

  const handleLoad = () => {
    const recipe = recipes.find((r) => r.name === selected);
    if (!recipe) return;
    const palette = toPalette(recipe, catalogPaints);
    setPaletteAt(book.selected, palette);
    onRecipeLoaded();
  };

  return (
    <div style={{ display: "flex", gap: 4, alignItems: "center" }}>
      <select value={selected} onChange={(e) => setSelected(e.target.value)}
        style={{ flex: 1 }}>
        {recipes.length === 0 && <option value="">{t("colour.select_recipe")}</option>}
        {recipes.map((r) => <option key={r.name} value={r.name}>{r.name}</option>)}
      </select>
      <button onClick={handleLoad} disabled={!selected}>{t("colour.load_recipe")}</button>
    </div>
  );
}
