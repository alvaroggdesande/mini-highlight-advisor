import { useState } from "react";
import { useTranslation } from "react-i18next";
import { NativeSelect, Stack } from "@mantine/core";
import { useProjectStore, activeBookOf } from "../../store/projectStore";
import { roleNames, ROLE_KEY } from "../../lib/roles";
import { StepSection } from "../StepSection";
import { BandCard } from "./BandCard";
import { LayerTools } from "./LayerTools";

export function BandEditor() {
  const { t } = useTranslation();
  const book = useProjectStore((s) => activeBookOf(s));
  const setCoverage = useProjectStore((s) => s.setCoverage);
  const setSelected = useProjectStore((s) => s.setSelected);
  const [recipeKey, setRecipeKey] = useState(0);

  if (!book) return null;
  const g = book.selected;
  const region = g === 0 ? book.whole : book.drawn[g - 1];
  if (!region) return null;
  const names = [t("region.whole_mini"), ...book.drawn.map((r) => r.name)];
  const { palette, coverage, material } = region;
  const n = palette.length;
  const roles = roleNames(n).map((r) => t(ROLE_KEY[r] ?? r));

  // Same math as the retired CoverageEditor.handleSlider: adjust band i, keep last band auto.
  const handleCoverage = (i: number, val: number) => {
    const valFraction = val / 100;
    const others = coverage.reduce((sum, v, j) => (j !== i && j !== n - 1 ? sum + v : sum), 0);
    const clamped = Math.min(valFraction, Math.max(0, 1 - others - 0.03));
    const newCov = coverage.slice();
    newCov[i] = clamped;
    const remainder = 1 - newCov.slice(0, n - 1).reduce((a, b) => a + b, 0);
    newCov[n - 1] = Math.max(0, remainder);
    setCoverage(newCov);
  };

  return (
    <StepSection n={3} title={t("studio.step_layers")} testId="step-layers"
      right={
        <NativeSelect aria-label={t("region.select")} size="xs" value={g}
          onChange={(e) => setSelected(Number(e.target.value))}>
          {names.map((name, i) => <option key={i} value={i}>{name}</option>)}
        </NativeSelect>
      }>
      {/* Re-keyed after a recipe is applied: remounts cards and closes the fill panel. */}
      <Stack gap="xs" key={recipeKey}>
        {palette.map((paint, i) => (
          <BandCard key={i} g={g} i={i} paint={paint} finish={material} n={n} palette={palette}
            role={roles[i]} coverageValue={coverage[i] ?? 0} isAuto={i === n - 1} onCoverage={handleCoverage} />
        ))}
        <LayerTools g={g} n={n} onRecipeChanged={() => setRecipeKey((k) => k + 1)} />
      </Stack>
    </StepSection>
  );
}
