import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Button, ColorInput, Group, Stack } from "@mantine/core";
import { useProjectStore, activeBookOf } from "../../store/projectStore";
import { useCatalogStore } from "../../store/catalogStore";
import { generateRamp } from "../../api/client";
import { RAMP_VARIANTS } from "../../api/types";
import type { PaintColor } from "../../api/types";
import { validHex } from "../../lib/color";
import { PaintSearch } from "./PaintSearch";

export function RampEditor() {
  const { t } = useTranslation();
  const book = useProjectStore((s) => activeBookOf(s));
  const setHexSlot = useProjectStore((s) => s.setHexSlot);
  const setRampState = useProjectStore((s) => s.setRampState);
  const setPaletteSlot = useProjectStore((s) => s.setPaletteSlot);
  const paints = useCatalogStore((s) => s.paints);

  const activeRegion = book
    ? book.selected === 0 ? book.whole : book.drawn[book.selected - 1]
    : null;

  const seedHex = activeRegion?.ramp_midtone
    ?? activeRegion?.palette[Math.floor((activeRegion.palette.length) / 2)]?.hex
    ?? "#808080";

  const [midtoneHex, setMidtoneHex] = useState(seedHex);
  // The catalogue paint behind the midtone, if it came from one (picked, or a stored midtone
  // that is exactly a catalogue colour). Typing a different hex drops it.
  const [picked, setPicked] = useState<PaintColor | null>(
    () => paints.find((p) => p.code && p.hex.toLowerCase() === seedHex.toLowerCase()) ?? null);
  const setHex = (hex: string) => {
    setMidtoneHex(hex);
    if (picked && picked.hex.toLowerCase() !== hex.toLowerCase()) setPicked(null);
  };
  const pick = (p: PaintColor) => { setPicked(p); setMidtoneHex(p.hex); };
  const [loading, setLoading] = useState<string | null>(null);

  if (!book || !activeRegion) return null;

  const g = book.selected;
  const n = activeRegion.palette.length;
  const normalizedMidtoneHex = validHex(midtoneHex);

  const handleVariant = async (variant: string) => {
    if (!normalizedMidtoneHex) return;
    setLoading(variant);
    try {
      const res = await generateRamp({ midtone_hex: normalizedMidtoneHex, n, variant });
      res.hexes.forEach((hex, i) => setHexSlot(g, i, hex));
      // A plain ramp keeps the midtone unrotated, so its middle layer IS the picked paint.
      if (picked && variant === "ramp") setPaletteSlot(g, Math.floor(n / 2), picked);
      setRampState(g, normalizedMidtoneHex, variant);
    } finally { setLoading(null); }
  };

  return (
    <Stack gap="xs">
      <Group gap="xs" align="flex-end">
        <ColorInput label={t("colour.midtone")} value={midtoneHex} onChange={setHex}
          format="hex" size="xs" withEyeDropper={false} style={{ flex: 1 }} />
        <PaintSearch label={t("colour.or_pick_paint")} value={picked?.code ?? null} onPick={pick} style={{ flex: 1 }} />
        {book.hero_hex && (
          <Button size="xs" variant="subtle" onClick={() => setHex(book.hero_hex!)}>
            {t("colour.use_scheme_colour")}
          </Button>
        )}
      </Group>
      <Button.Group>
        {RAMP_VARIANTS.map((variant) => (
          <Button key={variant} size="xs" variant="default"
            onClick={() => handleVariant(variant)}
            loading={loading === variant} disabled={loading !== null || !normalizedMidtoneHex}>
            {t(`colour.${variant}`)}
          </Button>
        ))}
      </Button.Group>
    </Stack>
  );
}
