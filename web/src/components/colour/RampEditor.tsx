import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Button, ColorInput, Group, Stack, Text } from "@mantine/core";
import { useProjectStore, activeBookOf } from "../../store/projectStore";
import { generateRamp } from "../../api/client";
import { RAMP_VARIANTS } from "../../api/types";
import { validHex } from "../../lib/color";

export function RampEditor() {
  const { t } = useTranslation();
  const book = useProjectStore((s) => activeBookOf(s));
  const setHexSlot = useProjectStore((s) => s.setHexSlot);
  const setRampState = useProjectStore((s) => s.setRampState);

  const activeRegion = book
    ? book.selected === 0 ? book.whole : book.drawn[book.selected - 1]
    : null;

  const seedHex = activeRegion?.ramp_midtone
    ?? activeRegion?.palette[Math.floor((activeRegion.palette.length) / 2)]?.hex
    ?? "#808080";

  const [midtoneHex, setMidtoneHex] = useState(seedHex);
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
      setRampState(g, normalizedMidtoneHex, variant);
    } finally { setLoading(null); }
  };

  return (
    <Stack gap="xs">
      <Text size="sm" fw={500}>{t("colour.ramp_editor")}</Text>
      <Group gap="xs" align="flex-end">
        <ColorInput label={t("colour.midtone")} value={midtoneHex} onChange={setMidtoneHex}
          format="hex" size="xs" withEyeDropper={false} style={{ flex: 1 }} />
        {book.hero_hex && (
          <Button size="xs" variant="subtle" onClick={() => setMidtoneHex(book.hero_hex!)}>
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
