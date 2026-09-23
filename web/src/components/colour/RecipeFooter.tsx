import { useTranslation } from "react-i18next";
import { Button, Group } from "@mantine/core";
import { useProjectStore, activeBookOf } from "../../store/projectStore";
import { defaultCoverage } from "../../lib/roles";
import { RampEditor } from "./RampEditor";
import { RecipeLoader } from "./RecipeLoader";
import { RecipeSaver } from "./RecipeSaver";

interface Props { g: number; n: number; onRecipeChanged: () => void; }

export function RecipeFooter({ g, n, onRecipeChanged }: Props) {
  const { t } = useTranslation();
  const setBandCount = useProjectStore((s) => s.setBandCount);
  const setHexSlot = useProjectStore((s) => s.setHexSlot);
  const setCoverage = useProjectStore((s) => s.setCoverage);
  const snapshotUndo = useProjectStore((s) => s.snapshotUndo);
  const undo = useProjectStore((s) => s.undo);
  const canUndo = useProjectStore((s) => s.undoSnapshot !== null);
  const palette = useProjectStore((s) => {
    const book = activeBookOf(s);
    if (!book) return [] as import("../../api/types").PaintColor[];
    return g === 0 ? book.whole.palette : book.drawn[g - 1]?.palette ?? [];
  });

  const addBand = () => {
    if (n < 7) {
      setBandCount(n + 1);
      setHexSlot(g, n, palette[n - 1]?.hex ?? "#808080");
    }
  };

  const resetCoverage = () => {
    snapshotUndo();
    setCoverage(defaultCoverage(n));
  };

  return (
    <Group gap="xs" wrap="wrap">
      <Button size="xs" variant="light" onClick={addBand} disabled={n >= 7}>{t("colour.add_band")}</Button>
      <RampEditor />
      <RecipeLoader onRecipeLoaded={onRecipeChanged} />
      <RecipeSaver onSaved={onRecipeChanged} />
      <Button size="xs" variant="subtle" onClick={resetCoverage}>{t("colour.reset_coverage")}</Button>
      <Button size="xs" variant="subtle" onClick={undo} disabled={!canUndo}
        aria-label="undo">↺ {t("colour.undo")}</Button>
    </Group>
  );
}
