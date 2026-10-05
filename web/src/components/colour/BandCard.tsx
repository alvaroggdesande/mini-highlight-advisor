import { useState, useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import { ActionIcon, Box, Button, ColorInput, ColorSwatch, Group, Slider, Text, Tooltip } from "@mantine/core";
import { useProjectStore } from "../../store/projectStore";
import { matchPaint, generateRamp } from "../../api/client";
import type { TFunction } from "i18next";
import type { PaintColor, MatchResult } from "../../api/types";
import { validHex } from "../../lib/color";
import { PaintSearch } from "./PaintSearch";

interface Props {
  g: number; i: number; paint: PaintColor; finish: string; n: number; palette: PaintColor[];
  role: string; coverageValue: number; isAuto: boolean;
  onCoverage: (i: number, val: number) => void;
}

function matchPhrase(r: MatchResult, t: TFunction): string {
  if (r.tier === "exact") return `✓ ${r.name ?? ""}`;
  if (r.tier === "close") return `≈ ${r.name ?? ""}`;
  if (r.tier === "mix") return r.phrase;
  return t("colour.buy", { name: r.name ?? "" });
}

export function BandCard({ g, i, paint, finish, n, palette, role, coverageValue, isAuto, onCoverage }: Props) {
  const { t } = useTranslation();
  const setPaletteSlot = useProjectStore((s) => s.setPaletteSlot);
  const setHexSlot = useProjectStore((s) => s.setHexSlot);
  const removeBand = useProjectStore((s) => s.removeBand);
  const snapshotUndo = useProjectStore((s) => s.snapshotUndo);
  const isCustom = !paint.code;
  const [matchResult, setMatchResult] = useState<MatchResult | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pct = Math.round(coverageValue * 100);

  useEffect(() => {
    if (!isCustom) { setMatchResult(null); return; }
    const normalizedHex = validHex(paint.hex);
    if (!normalizedHex) { setMatchResult(null); return; }
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      try { setMatchResult(await matchPaint({ hex: normalizedHex, finish, owned_codes: [] })); } catch { /* ignore */ }
    }, 400);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [paint.hex, isCustom, finish]);

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
          ? <Text size="xs" c="dimmed">{pct}% · {t("colour.auto")}</Text>
          : <ActionIcon size="sm" variant="subtle" color="red" disabled={n <= 3}
              onClick={() => { if (n > 3) { snapshotUndo(); removeBand(i); } }} aria-label={t("colour.delete_band")}>✕</ActionIcon>}
      </Group>
      <Group gap={4} align="center" wrap="nowrap">
        <ColorSwatch color={validHex(paint.hex) ?? "#808080"} size={22} style={{ flexShrink: 0 }} />
        {isCustom ? (
          <>
            <ColorInput value={paint.hex} onChange={(hex) => setHexSlot(g, i, hex)}
              format="hex" size="xs" style={{ flex: 1 }} withEyeDropper={false} />
            <PaintSearch onPick={(p) => setPaletteSlot(g, i, p)} style={{ flex: 1 }} />
          </>
        ) : (
          <>
            <PaintSearch value={paint.code} onPick={(p) => setPaletteSlot(g, i, p)} style={{ flex: 1 }} />
            <Button size="compact-xs" variant="subtle" onClick={() => setHexSlot(g, i, paint.hex)}
              title={t("colour.custom_hint")}>{t("colour.custom_short")}</Button>
          </>
        )}
        {i > 0 && i < n - 1 && (
          <ActionIcon size="sm" variant="subtle" onClick={handleBlend} title={t("colour.blend")}>↕</ActionIcon>
        )}
      </Group>
      {isCustom && matchResult && <Text size="xs" c="dimmed" ml={28}>{matchPhrase(matchResult, t)}</Text>}
      {!isAuto && (
        <Group gap="xs" align="center" wrap="nowrap" mt={6}>
          <Tooltip label={t("colour.coverage_hint")} withArrow>
            <Text size="xs" miw={70} style={{ cursor: "help" }}>{t("colour.coverage")} ⓘ</Text>
          </Tooltip>
          <Slider thumbLabel={t("colour.coverage")} value={pct} onChange={(v) => onCoverage(i, v)} min={0} max={100} step={1} size="sm" style={{ flex: 1 }} />
          <Text size="xs" miw={32} ta="right">{pct}%</Text>
        </Group>
      )}
    </Box>
  );
}
