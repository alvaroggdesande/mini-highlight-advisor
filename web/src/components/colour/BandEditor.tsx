import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useProjectStore, activeBookOf } from "../../store/projectStore";
import { BandSlot } from "./BandSlot";
import { CoverageEditor } from "./CoverageEditor";
import { RecipeLoader } from "./RecipeLoader";
import { RecipeSaver } from "./RecipeSaver";

export function BandEditor() {
  const { t } = useTranslation();
  const book = useProjectStore((s) => activeBookOf(s));
  const [recipeKey, setRecipeKey] = useState(0);

  if (!book) return null;

  const g = book.selected;
  const region = g === 0 ? book.whole : book.drawn[g - 1];
  if (!region) return null;

  const { palette, coverage, material } = region;
  const n = palette.length;

  return (
    <section>
      <h4 style={{ margin: "0 0 8px" }}>{t("colour.band_editor")}</h4>
      <RecipeLoader key={recipeKey} onRecipeLoaded={() => setRecipeKey((k) => k + 1)} />

      {palette.map((paint, i) => (
        <BandSlot key={i} g={g} i={i} paint={paint} finish={material} n={n} palette={palette} />
      ))}

      <CoverageEditor g={g} n={n} coverage={coverage} />
      <RecipeSaver onSaved={() => setRecipeKey((k) => k + 1)} />
    </section>
  );
}
