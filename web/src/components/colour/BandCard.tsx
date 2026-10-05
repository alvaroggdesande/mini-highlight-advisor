import { useTranslation } from "react-i18next";
import { ActionIcon, Box, Button, ColorInput, ColorSwatch, Group, Popover, Slider, Stack, Text, Tooltip, UnstyledButton } from "@mantine/core";
import { useProjectStore } from "../../store/projectStore";
import { generateRamp } from "../../api/client";
import { useMatch } from "../../hooks/useMatch";
import { matchPhrase } from "../../lib/matchPhrase";
import type { PaintColor, MatchResult, NearestPaint } from "../../api/types";
import { validHex } from "../../lib/color";
import { PaintSearch } from "./PaintSearch";

interface Props {
  g: number; i: number; paint: PaintColor; finish: string; n: number; palette: PaintColor[];
  role: string; coverageValue: number; isAuto: boolean;
  onCoverage: (i: number, val: number) => void;
}

function toPaint({ delta_e: _d, owned: _o, ...paint }: NearestPaint): PaintColor { return paint; }

export function BandCard({ g, i, paint, finish, n, palette, role, coverageValue, isAuto, onCoverage }: Props) {
  const { t } = useTranslation();
  const setPaletteSlot = useProjectStore((s) => s.setPaletteSlot);
  const setHexSlot = useProjectStore((s) => s.setHexSlot);
  const removeBand = useProjectStore((s) => s.removeBand);
  const snapshotUndo = useProjectStore((s) => s.snapshotUndo);
  const isCustom = !paint.code;
  const { result: matchResult, hasOwned, ownedCodes } = useMatch(isCustom ? validHex(paint.hex) : null, finish, 400);
  const pct = Math.round(coverageValue * 100);

  const swatch = <ColorSwatch color={validHex(paint.hex) ?? "#808080"} size={22} />;

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
        <Popover width={280} position="bottom-start" withArrow shadow="md">
          <Popover.Target>
            <UnstyledButton aria-label={t("colour.which_paint")} title={t("colour.which_paint")}
              style={{ flexShrink: 0, lineHeight: 0 }}>{swatch}</UnstyledButton>
          </Popover.Target>
          <Popover.Dropdown>
            {isCustom
              ? <CustomInfo hex={paint.hex} result={matchResult} hasOwned={hasOwned}
                  onUse={(p) => setPaletteSlot(g, i, p)} />
              : <Stack gap={2}>
                  <Text size="sm" fw={600}>{paint.name}</Text>
                  <Text size="xs" c="dimmed">{[paint.brand, paint.paint_range, paint.code].filter(Boolean).join(" · ")}</Text>
                  <Text size="xs">{paint.hex} · {ownedCodes.has(paint.code!) ? t("colour.owned") : t("colour.not_owned")}</Text>
                </Stack>}
          </Popover.Dropdown>
        </Popover>
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
      {isCustom && matchResult && <Text size="xs" c="dimmed" ml={28}>{matchPhrase(matchResult, hasOwned, t)}</Text>}
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

function CustomInfo({ hex, result, hasOwned, onUse }: {
  hex: string; result: MatchResult | null; hasOwned: boolean; onUse: (p: PaintColor) => void;
}) {
  const { t } = useTranslation();
  if (!result) return <Text size="xs" c="dimmed">{hex}</Text>;
  return (
    <Stack gap={6}>
      <Text size="xs" fw={600}>{t("colour.from_your_paints")}</Text>
      <Text size="xs">{hasOwned ? matchPhrase(result, true, t) : t("colour.mark_owned_hint")}</Text>
      <Text size="xs" fw={600} mt={4}>{t("colour.closest_in_catalogue")}</Text>
      {result.nearest.map((p) => (
        <Group key={p.code} gap={6} wrap="nowrap" justify="space-between">
          <Group gap={6} wrap="nowrap" style={{ minWidth: 0 }}>
            <ColorSwatch color={p.hex} size={16} style={{ flexShrink: 0 }} />
            <div style={{ minWidth: 0 }}>
              <Text size="xs" truncate>{p.owned ? "✓ " : ""}{p.name}</Text>
              <Text size="xs" c="dimmed" truncate>{p.brand} · {p.code} · ΔE {p.delta_e}</Text>
            </div>
          </Group>
          <Button size="compact-xs" variant="light" onClick={() => onUse(toPaint(p))}>{t("colour.use_paint")}</Button>
        </Group>
      ))}
    </Stack>
  );
}
