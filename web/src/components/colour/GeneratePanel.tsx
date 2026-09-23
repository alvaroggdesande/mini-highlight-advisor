import { useState } from "react";
import { useTranslation } from "react-i18next";
import { ActionIcon, Button, Checkbox, ColorInput, Group, NativeSelect, Stack, Text } from "@mantine/core";
import { useProjectStore, activeBookOf } from "../../store/projectStore";
import { useCatalogStore } from "../../store/catalogStore";
import { generateScheme } from "../../api/client";
import { MOODS, VARIANTS } from "../../api/types";
import type { RegionColorSpec } from "../../api/types";

export function GeneratePanel() {
  const { t } = useTranslation();
  const book = useProjectStore((s) => activeBookOf(s));
  const catalogPaints = useCatalogStore((s) => s.paints);
  const setPaletteAt = useProjectStore((s) => s.setPaletteAt);
  const setHeroHex = useProjectStore((s) => s.setHeroHex);
  const setMood = useProjectStore((s) => s.setMood);
  const setVariant = useProjectStore((s) => s.setVariant);
  const snapshotUndo = useProjectStore((s) => s.snapshotUndo);

  const [anchorIndex, setAnchorIndex] = useState(0);
  const [heroHex, setHeroHexLocal] = useState(() => book?.hero_hex ?? "#c0392b");
  const [mood, setMoodLocal] = useState(() => book?.mood ?? "neutral");
  const [variant, setVariantLocal] = useState(() => book?.variant ?? "complementary");
  const [ownedOnly, setOwnedOnly] = useState(false);
  const [loading, setLoading] = useState(false);
  // Collapsed once a scheme exists (hero_hex set); user can override with toggle.
  const [open, setOpen] = useState<boolean | null>(null);

  if (!book) return null;
  const expanded = open ?? !book.hero_hex;
  const regionNames = ["Whole Mini", ...book.drawn.map((r) => r.name)];
  const ownedCodes = ownedOnly ? catalogPaints.map((p) => p.code ?? "").filter(Boolean) : [];
  const surfaceOf = (i: number) => (i === 0 ? book.whole.surface : book.drawn[i - 1]?.surface) ?? "skin";
  const toneOf = (i: number) => (i === 0 ? book.whole.tone : book.drawn[i - 1]?.tone) || undefined;

  const handleGenerate = async () => {
    setLoading(true);
    try {
      snapshotUndo();
      const anchorName = regionNames[anchorIndex] ?? "Whole Mini";
      const specs: RegionColorSpec[] = regionNames.map((name, i) => ({
        region_name: name, surface: surfaceOf(i), tone: toneOf(i),
        n_bands: i === 0 ? book.whole.palette.length : book.drawn[i - 1].palette.length,
        is_anchor: i === anchorIndex,
      }));
      const res = await generateScheme({ specs, anchor_name: anchorName, anchor_hex: heroHex, mood, variant, owned_codes: ownedCodes });
      regionNames.forEach((name, i) => { const pal = res.palettes[name]; if (pal) setPaletteAt(i, pal); });
      setHeroHex(heroHex); setMood(mood); setVariant(variant);
    } finally { setLoading(false); }
  };

  return (
    <Stack gap="xs">
      <Group justify="space-between">
        <Text size="sm" fw={500}>{t("colour.generate_whole_mini")}</Text>
        <ActionIcon size="sm" variant="subtle" data-testid="generate-toggle"
          onClick={() => setOpen(!expanded)} aria-label="toggle generate">
          {expanded ? "▾" : "▸"}
        </ActionIcon>
      </Group>
      {expanded && (
        <>
          <Group gap="xs" align="flex-end" wrap="wrap">
            <NativeSelect label={t("colour.anchor_region")} size="xs"
              value={anchorIndex} onChange={(e) => setAnchorIndex(Number(e.target.value))}>
              {regionNames.map((name, i) => <option key={i} value={i}>{name}</option>)}
            </NativeSelect>
            <ColorInput label={t("colour.hero_colour")} value={heroHex} onChange={setHeroHexLocal}
              format="hex" size="xs" withEyeDropper={false} />
            <NativeSelect label={t("colour.mood")} size="xs" value={mood}
              onChange={(e) => setMoodLocal(e.target.value)}
              data={MOODS.map((m) => ({ value: m, label: t(`moods.${m}`) }))} />
            <NativeSelect label={t("colour.harmony")} size="xs" value={variant}
              onChange={(e) => setVariantLocal(e.target.value)}
              data={VARIANTS.map((v) => ({ value: v, label: t(`variants.${v}`) }))} />
          </Group>
          <Group gap="sm">
            <Checkbox size="xs" label={t("colour.owned_only")} checked={ownedOnly}
              onChange={(e) => setOwnedOnly(e.currentTarget.checked)} />
            <Button size="xs" onClick={handleGenerate} loading={loading}>{t("colour.generate")}</Button>
          </Group>
        </>
      )}
    </Stack>
  );
}
