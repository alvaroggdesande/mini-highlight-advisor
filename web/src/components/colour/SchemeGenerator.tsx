import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { Button, Checkbox, ColorInput, Group, NativeSelect, Stack, Table, Text } from "@mantine/core";
import { useProjectStore, activeBookOf } from "../../store/projectStore";
import { useCatalogStore } from "../../store/catalogStore";
import { generateScheme } from "../../api/client";
import { MOODS, VARIANTS, SURFACES } from "../../api/types";
import type { RegionColorSpec } from "../../api/types";

export function SchemeGenerator() {
  const { t } = useTranslation();
  const book = useProjectStore((s) => activeBookOf(s));
  const catalogPaints = useCatalogStore((s) => s.paints);
  const setPaletteAt = useProjectStore((s) => s.setPaletteAt);
  const setHeroHex = useProjectStore((s) => s.setHeroHex);
  const setMood = useProjectStore((s) => s.setMood);
  const setVariant = useProjectStore((s) => s.setVariant);
  const setSurface = useProjectStore((s) => s.setSurface);
  const setTone = useProjectStore((s) => s.setTone);

  const regionCount = book ? 1 + book.drawn.length : 1;
  const [anchorIndex, setAnchorIndex] = useState(0);
  const [heroHex, setHeroHexLocal] = useState(() => book?.hero_hex ?? "#c0392b");
  const [mood, setMoodLocal] = useState(() => book?.mood ?? "neutral");
  const [variant, setVariantLocal] = useState(() => book?.variant ?? "complementary");
  const [perRegion, setPerRegion] = useState<{ surface: string; tone: string }[]>(() =>
    Array.from({ length: regionCount }, (_, i) => ({
      surface: i === 0 ? (book?.whole.surface ?? "skin") : (book?.drawn[i - 1]?.surface ?? "skin"),
      tone: i === 0 ? (book?.whole.tone ?? "") : (book?.drawn[i - 1]?.tone ?? ""),
    }))
  );
  const [ownedOnly, setOwnedOnly] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!book) return;
    const needed = 1 + book.drawn.length;
    if (perRegion.length < needed) {
      setPerRegion((prev) => [...prev, ...Array.from({ length: needed - prev.length }, (_, i) => {
        const di = prev.length - 1 + i;
        return { surface: book.drawn[di]?.surface ?? "skin", tone: book.drawn[di]?.tone ?? "" };
      })]);
    }
  }, [book?.drawn.length]);

  if (!book) return null;

  const regionNames = ["Whole Mini", ...book.drawn.map((r) => r.name)];
  const ownedCodes = ownedOnly ? catalogPaints.map((p) => p.code ?? "").filter(Boolean) : [];

  const handleGenerate = async () => {
    setLoading(true);
    try {
      const anchorName = regionNames[anchorIndex] ?? "Whole Mini";
      const specs: RegionColorSpec[] = regionNames.map((name, i) => ({
        region_name: name,
        surface: perRegion[i]?.surface ?? "skin",
        tone: perRegion[i]?.tone || undefined,
        n_bands: i === 0 ? book.whole.palette.length : book.drawn[i - 1].palette.length,
        is_anchor: i === anchorIndex,
      }));
      const res = await generateScheme({ specs, anchor_name: anchorName, anchor_hex: heroHex, mood, variant, owned_codes: ownedCodes });
      regionNames.forEach((name, i) => { const pal = res.palettes[name]; if (pal) setPaletteAt(i, pal); });
      setHeroHex(heroHex); setMood(mood); setVariant(variant);
      regionNames.forEach((_, i) => { setSurface(i, perRegion[i]?.surface ?? "skin"); if (perRegion[i]?.tone) setTone(i, perRegion[i].tone); });
    } finally { setLoading(false); }
  };

  const updatePerRegion = (i: number, field: "surface" | "tone", value: string) =>
    setPerRegion((prev) => prev.map((r, j) => j === i ? { ...r, [field]: value } : r));

  return (
    <Stack gap="xs">
      <Text size="sm" fw={500}>{t("colour.scheme_generator")}</Text>
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
      <Table>
        <Table.Thead>
          <Table.Tr><Table.Th>Region</Table.Th><Table.Th>Surface</Table.Th><Table.Th>Tone</Table.Th></Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {regionNames.map((name, i) => (
            <Table.Tr key={i}>
              <Table.Td><Text size="xs">{name}</Text></Table.Td>
              <Table.Td>
                <NativeSelect size="xs" value={perRegion[i]?.surface ?? "skin"}
                  onChange={(e) => updatePerRegion(i, "surface", e.target.value)}
                  data={SURFACES.map((s) => ({ value: s, label: t(`surfaces.${s}`) }))} />
              </Table.Td>
              <Table.Td>
                <input type="text" placeholder={t("colour.tone")} value={perRegion[i]?.tone ?? ""}
                  onChange={(e) => updatePerRegion(i, "tone", e.target.value)}
                  style={{ width: 80, fontSize: 12, background: "transparent",
                    border: "1px solid var(--mantine-color-dark-4)", color: "inherit",
                    borderRadius: 4, padding: "2px 4px" }} />
              </Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
      <Group gap="sm">
        <Checkbox size="xs" label={t("colour.owned_only")} checked={ownedOnly}
          onChange={(e) => setOwnedOnly(e.currentTarget.checked)} />
        <Button size="xs" onClick={handleGenerate} loading={loading}>
          {t("colour.generate")}
        </Button>
      </Group>
    </Stack>
  );
}
