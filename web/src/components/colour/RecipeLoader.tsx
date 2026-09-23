import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { Button, ColorSwatch, Group, NativeSelect, Stack } from "@mantine/core";
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
  const snapshotUndo = useProjectStore((s) => s.snapshotUndo);
  const [recipes, setRecipes] = useState<Recipe[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [preview, setPreview] = useState<PaintColor[] | null>(null);

  useEffect(() => {
    listRecipes().then((res) => { setRecipes(res.recipes); if (res.recipes.length > 0) setSelected(res.recipes[0].name); });
  }, []);

  if (!book) return null;

  const doPreview = () => {
    const recipe = recipes.find((r) => r.name === selected);
    if (recipe) setPreview(toPalette(recipe, catalogPaints));
  };
  const doApply = () => {
    if (!preview) return;
    snapshotUndo();
    setPaletteAt(book.selected, preview);
    setPreview(null);
    onRecipeLoaded();
  };

  return (
    <Stack gap="xs">
      <Group gap="xs">
        <NativeSelect size="xs" value={selected} onChange={(e) => { setSelected(e.target.value); setPreview(null); }} style={{ flex: 1 }}>
          {recipes.length === 0 && <option value="">{t("colour.select_recipe")}</option>}
          {recipes.map((r) => <option key={r.name} value={r.name}>{r.name}</option>)}
        </NativeSelect>
        <Button size="xs" variant="default" onClick={doPreview} disabled={!selected}>{t("colour.preview_recipe")}</Button>
      </Group>
      {preview && (
        <Group gap="xs" align="center">
          <Group gap={2}>{preview.map((p, i) => <ColorSwatch key={i} color={p.hex} size={18} />)}</Group>
          <Button size="xs" onClick={doApply}>{t("colour.apply_recipe")}</Button>
          <Button size="xs" variant="subtle" onClick={() => setPreview(null)}>{t("colour.cancel")}</Button>
        </Group>
      )}
    </Stack>
  );
}
