import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Button, Group, Stack, Text } from "@mantine/core";
import { useProjectStore, activeBookOf } from "../../store/projectStore";
import { defaultCoverage } from "../../lib/roles";
import type { PaintColor } from "../../api/types";
import { RampEditor } from "./RampEditor";
import { RecipeLoader } from "./RecipeLoader";

interface Props { g: number; n: number; onRecipeChanged: () => void; }
type Fill = "ramp" | "recipe";

export function LayerTools({ g, n, onRecipeChanged }: Props) {
  const { t } = useTranslation();
  const setBandCount = useProjectStore((s) => s.setBandCount);
  const setHexSlot = useProjectStore((s) => s.setHexSlot);
  const setCoverage = useProjectStore((s) => s.setCoverage);
  const snapshotUndo = useProjectStore((s) => s.snapshotUndo);
  const undo = useProjectStore((s) => s.undo);
  const canUndo = useProjectStore((s) => s.undoSnapshot !== null);
  const palette = useProjectStore((s) => {
    const book = activeBookOf(s);
    if (!book) return [] as PaintColor[];
    return g === 0 ? book.whole.palette : book.drawn[g - 1]?.palette ?? [];
  });
  const [fill, setFill] = useState<Fill | null>(null);
  const toggle = (f: Fill) => setFill((cur) => (cur === f ? null : f));

  const addBand = () => {
    if (n < 7) {
      setBandCount(n + 1);
      setHexSlot(g, n, palette[n - 1]?.hex ?? "#808080");
    }
  };
  const resetCoverage = () => { snapshotUndo(); setCoverage(defaultCoverage(n)); };

  return (
    <Stack gap="xs">
      <Group gap="xs" wrap="wrap">
        <Button size="xs" variant="light" onClick={addBand} disabled={n >= 7}>{t("colour.add_band")}</Button>
        <Button size="xs" variant="subtle" onClick={resetCoverage}>{t("colour.reset_coverage")}</Button>
        <Button size="xs" variant="subtle" onClick={undo} disabled={!canUndo}
          aria-label={t("colour.undo")}>↺ {t("colour.undo")}</Button>
      </Group>
      <Group gap="xs" align="center" wrap="wrap">
        <Text size="xs">{t("studio.fill_from")}</Text>
        <Button size="xs" variant={fill === "ramp" ? "filled" : "default"} aria-pressed={fill === "ramp"}
          onClick={() => toggle("ramp")}>{t("studio.fill_one_colour")}</Button>
        <Button size="xs" variant={fill === "recipe" ? "filled" : "default"} aria-pressed={fill === "recipe"}
          onClick={() => toggle("recipe")}>{t("studio.fill_recipe")}</Button>
      </Group>
      {fill === "ramp" && <RampEditor />}
      {fill === "recipe" && <RecipeLoader onRecipeLoaded={onRecipeChanged} />}
    </Stack>
  );
}
