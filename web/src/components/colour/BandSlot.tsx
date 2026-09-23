import { useState, useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import { ActionIcon, Box, ColorInput, ColorSwatch, Group, NativeSelect, Text } from "@mantine/core";
import { useProjectStore } from "../../store/projectStore";
import { useCatalogStore } from "../../store/catalogStore";
import { matchPaint, generateRamp } from "../../api/client";
import type { PaintColor, MatchResult } from "../../api/types";

interface BandSlotProps { g: number; i: number; paint: PaintColor; finish: string; n: number; palette: PaintColor[]; }

function matchPhrase(result: MatchResult): string {
  if (result.tier === "exact") return `✓ ${result.name ?? ""}`;
  if (result.tier === "close") return `≈ ${result.name ?? ""}`;
  if (result.tier === "mix") return result.phrase;
  return `Buy: ${result.name ?? ""}`;
}

export function BandSlot({ g, i, paint, finish, n, palette }: BandSlotProps) {
  const { t } = useTranslation();
  const catalogPaints = useCatalogStore((s) => s.paints);
  const setPaletteSlot = useProjectStore((s) => s.setPaletteSlot);
  const setHexSlot = useProjectStore((s) => s.setHexSlot);
  const setBandCount = useProjectStore((s) => s.setBandCount);
  const isCustom = !paint.code;
  const [matchResult, setMatchResult] = useState<MatchResult | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (!isCustom) { setMatchResult(null); return; }
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      try { setMatchResult(await matchPaint({ hex: paint.hex, finish, owned_codes: [] })); }
      catch { /* ignore */ }
    }, 400);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [paint.hex, isCustom, finish]);

  const handleCatalogChange = (code: string) => {
    if (code === "__custom__") { setHexSlot(g, i, paint.hex); }
    else { const found = catalogPaints.find((p) => p.code === code); if (found) setPaletteSlot(g, i, found); }
  };

  const handleBlend = async () => {
    const left = palette[i - 1]; const right = palette[i + 1];
    if (!left || !right) return;
    try {
      const res = await generateRamp({ n: 1, variant: "ramp", blend_hexes: [left.hex, right.hex] });
      if (res.hexes[0]) setHexSlot(g, i, res.hexes[0]);
    } catch { /* ignore */ }
  };

  return (
    <Box py={4} style={{ borderBottom: "1px solid var(--mantine-color-dark-4)" }}>
      <Group gap={4} align="center" wrap="nowrap">
        <ColorSwatch color={paint.hex} size={22} style={{ flexShrink: 0 }} />
        {isCustom ? (
          <ColorInput value={paint.hex} onChange={(hex) => setHexSlot(g, i, hex)}
            format="hex" size="xs" style={{ flex: 1 }} withEyeDropper={false} />
        ) : (
          <NativeSelect value={paint.code} onChange={(e) => handleCatalogChange(e.target.value)}
            size="xs" style={{ flex: 1 }}>
            {catalogPaints.map((p) => (
              <option key={p.code} value={p.code}>{p.code} — {p.name}</option>
            ))}
            <option value="__custom__">{t("colour.custom")}</option>
          </NativeSelect>
        )}
        {i > 0 && i < n - 1 && (
          <ActionIcon size="sm" variant="subtle" onClick={handleBlend} title={t("colour.blend")}>↕</ActionIcon>
        )}
        <ActionIcon size="sm" variant="subtle" color="red" disabled={n <= 3}
          onClick={() => { if (n > 3) setBandCount(n - 1); }} title={t("colour.delete_band")}>✕</ActionIcon>
        <ActionIcon size="sm" variant="subtle" disabled={n >= 7}
          onClick={() => { if (n < 7) { setBandCount(n + 1); setHexSlot(g, n, palette[n - 1]?.hex ?? "#808080"); } }}
          title={t("colour.add_band")}>＋</ActionIcon>
      </Group>
      {isCustom && matchResult && (
        <Text size="xs" c="dimmed" ml={28}>{matchPhrase(matchResult)}</Text>
      )}
    </Box>
  );
}
