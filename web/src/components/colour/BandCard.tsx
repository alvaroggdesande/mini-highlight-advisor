import { useState, useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import { ActionIcon, Box, ColorInput, ColorSwatch, Group, NativeSelect, Slider, Text } from "@mantine/core";
import { useProjectStore } from "../../store/projectStore";
import { useCatalogStore } from "../../store/catalogStore";
import { matchPaint, generateRamp } from "../../api/client";
import type { PaintColor, MatchResult } from "../../api/types";

interface Props {
  g: number; i: number; paint: PaintColor; finish: string; n: number; palette: PaintColor[];
  role: string; coverageValue: number; isAuto: boolean;
  onCoverage: (i: number, val: number) => void;
}

function matchPhrase(r: MatchResult): string {
  if (r.tier === "exact") return `✓ ${r.name ?? ""}`;
  if (r.tier === "close") return `≈ ${r.name ?? ""}`;
  if (r.tier === "mix") return r.phrase;
  return `Buy: ${r.name ?? ""}`;
}

export function BandCard({ g, i, paint, finish, n, palette, role, coverageValue, isAuto, onCoverage }: Props) {
  const { t } = useTranslation();
  const catalogPaints = useCatalogStore((s) => s.paints);
  const setPaletteSlot = useProjectStore((s) => s.setPaletteSlot);
  const setHexSlot = useProjectStore((s) => s.setHexSlot);
  const setBandCount = useProjectStore((s) => s.setBandCount);
  const isCustom = !paint.code;
  const [matchResult, setMatchResult] = useState<MatchResult | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pct = Math.round(coverageValue * 100);

  useEffect(() => {
    if (!isCustom) { setMatchResult(null); return; }
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      try { setMatchResult(await matchPaint({ hex: paint.hex, finish, owned_codes: [] })); } catch { /* ignore */ }
    }, 400);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [paint.hex, isCustom, finish]);

  const handleCatalogChange = (code: string) => {
    if (code === "__custom__") setHexSlot(g, i, paint.hex);
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
    <Box p="xs" style={{ border: "1px solid var(--mantine-color-dark-4)", borderRadius: 6 }}>
      <Group justify="space-between" mb={4}>
        <Text size="xs" fw={600}>{role}</Text>
        {isAuto
          ? <Text size="xs" c="dimmed">{pct}% ({t("colour.auto")})</Text>
          : <ActionIcon size="sm" variant="subtle" color="red" disabled={n <= 3}
              onClick={() => { if (n > 3) setBandCount(n - 1); }} aria-label={t("colour.delete_band")}>✕</ActionIcon>}
      </Group>
      <Group gap={4} align="center" wrap="nowrap">
        <ColorSwatch color={paint.hex} size={22} style={{ flexShrink: 0 }} />
        {isCustom ? (
          <ColorInput value={paint.hex} onChange={(hex) => setHexSlot(g, i, hex)}
            format="hex" size="xs" style={{ flex: 1 }} withEyeDropper={false} />
        ) : (
          <NativeSelect value={paint.code} onChange={(e) => handleCatalogChange(e.target.value)}
            size="xs" style={{ flex: 1 }}>
            {catalogPaints.map((p) => <option key={p.code} value={p.code}>{p.code} — {p.name}</option>)}
            <option value="__custom__">{t("colour.custom")}</option>
          </NativeSelect>
        )}
        {i > 0 && i < n - 1 && (
          <ActionIcon size="sm" variant="subtle" onClick={handleBlend} title={t("colour.blend")}>↕</ActionIcon>
        )}
      </Group>
      {isCustom && matchResult && <Text size="xs" c="dimmed" ml={28}>{matchPhrase(matchResult)}</Text>}
      {!isAuto && (
        <Group gap="xs" align="center" wrap="nowrap" mt={6}>
          <Text size="xs" miw={70}>{t("colour.coverage")}</Text>
          <Slider value={pct} onChange={(v) => onCoverage(i, v)} min={0} max={100} step={1} size="sm" style={{ flex: 1 }} />
          <Text size="xs" miw={32} ta="right">{pct}%</Text>
        </Group>
      )}
    </Box>
  );
}
