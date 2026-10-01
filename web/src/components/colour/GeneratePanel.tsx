import { useState } from "react";
import { useTranslation } from "react-i18next";
import { ActionIcon, Button, Checkbox, ColorInput, Group, NativeSelect, Text } from "@mantine/core";
import { useProjectStore, activeBookOf, anchorIndexOf } from "../../store/projectStore";
import { useCatalogStore } from "../../store/catalogStore";
import { generateScheme } from "../../api/client";
import { MOODS, VARIANTS } from "../../api/types";
import type { RegionColorSpec } from "../../api/types";
import { ErrorNotice } from "../ErrorNotice";
import { StepSection } from "../StepSection";

const WHOLE_MINI_ID = "Whole Mini";   // API identifier — never translate

export function GeneratePanel() {
  const { t } = useTranslation();
  const book = useProjectStore((s) => activeBookOf(s));
  const owned = useCatalogStore((s) => s.ownedCodes);
  const setPaletteAt = useProjectStore((s) => s.setPaletteAt);
  const setHeroHex = useProjectStore((s) => s.setHeroHex);
  const setMood = useProjectStore((s) => s.setMood);
  const setVariant = useProjectStore((s) => s.setVariant);
  const snapshotUndo = useProjectStore((s) => s.snapshotUndo);

  const [heroHex, setHeroHexLocal] = useState(() => book?.hero_hex ?? "#c0392b");
  const [mood, setMoodLocal] = useState(() => book?.mood ?? "neutral");
  const [variant, setVariantLocal] = useState(() => book?.variant ?? "complementary");
  const [ownedOnly, setOwnedOnly] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Collapsed once a scheme exists (hero_hex set); user can override with toggle.
  const [open, setOpen] = useState<boolean | null>(null);

  if (!book) return null;
  const expanded = open ?? !book.hero_hex;
  const anchorIndex = anchorIndexOf(book);
  const regionNames = [WHOLE_MINI_ID, ...book.drawn.map((r) => r.name)];
  const ownedCodes = ownedOnly ? Array.from(owned) : [];
  const surfaceOf = (i: number) => (i === 0 ? book.whole.surface : book.drawn[i - 1]?.surface) ?? "skin";
  const toneOf = (i: number) => (i === 0 ? book.whole.tone : book.drawn[i - 1]?.tone) || undefined;

  const handleGenerate = async () => {
    setLoading(true); setError(null);
    try {
      snapshotUndo();
      const anchorName = regionNames[anchorIndex] ?? WHOLE_MINI_ID;
      const specs: RegionColorSpec[] = regionNames.map((name, i) => ({
        region_name: name, surface: surfaceOf(i), tone: toneOf(i),
        n_bands: i === 0 ? book.whole.palette.length : book.drawn[i - 1].palette.length,
        is_anchor: i === anchorIndex,
      }));
      const res = await generateScheme({ specs, anchor_name: anchorName, anchor_hex: heroHex, mood, variant, owned_codes: ownedCodes });
      regionNames.forEach((name, i) => { const pal = res.palettes[name]; if (pal) setPaletteAt(i, pal); });
      setHeroHex(heroHex); setMood(mood); setVariant(variant);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally { setLoading(false); }
  };

  return (
    <StepSection n={2} title={t("studio.step_scheme")} caption={t("studio.scheme_caption")} testId="step-scheme"
      right={
        <ActionIcon size="sm" variant="subtle" data-testid="generate-toggle"
          onClick={() => setOpen(!expanded)} aria-label={t("colour.toggle_generate")}>
          {expanded ? "▾" : "▸"}
        </ActionIcon>
      }>
      {expanded && (
        <>
          <Group gap="xs" align="flex-end" wrap="wrap">
            <ColorInput label={t("colour.hero_colour")} value={heroHex} onChange={setHeroHexLocal}
              format="hex" size="xs" withEyeDropper={false} />
            <NativeSelect label={t("colour.mood")} size="xs" value={mood}
              onChange={(e) => setMoodLocal(e.target.value)}
              data={MOODS.map((m) => ({ value: m, label: t(`moods.${m}`) }))} />
            <NativeSelect label={t("colour.harmony")} size="xs" value={variant}
              onChange={(e) => setVariantLocal(e.target.value)}
              data={VARIANTS.map((v) => ({ value: v, label: t(`variants.${v}`) }))} />
          </Group>
          <Text size="xs" c="dimmed">{t("studio.anchor_caption")}</Text>
          <Group gap="sm">
            <Checkbox size="xs" label={t("colour.owned_only")} checked={ownedOnly}
              onChange={(e) => setOwnedOnly(e.currentTarget.checked)} />
            <Button size="xs" onClick={handleGenerate} loading={loading}>{t("colour.generate")}</Button>
          </Group>
          {ownedOnly && owned.size === 0 && (
            <Text size="xs" c="dimmed">{t("colour.owned_only_none")}</Text>
          )}
          {error && <ErrorNotice message={t("errors.generate")} detail={error} />}
        </>
      )}
    </StepSection>
  );
}
