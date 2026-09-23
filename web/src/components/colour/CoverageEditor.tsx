import { useTranslation } from "react-i18next";
import { Button, Group, Slider, Stack, Text } from "@mantine/core";
import { useProjectStore } from "../../store/projectStore";
import { roleNames, defaultCoverage } from "../../lib/roles";

interface Props { g: number; n: number; coverage: number[]; }

export function CoverageEditor({ g: _g, n, coverage }: Props) {
  const { t } = useTranslation();
  const setCoverage = useProjectStore((s) => s.setCoverage);
  const names = roleNames(n);

  const handleSlider = (i: number, val: number) => {
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
    <Stack gap="xs" mt="xs">
      {Array.from({ length: n - 1 }, (_, i) => (
        <Group key={i} gap="xs" align="center" wrap="nowrap">
          <Text size="xs" miw={110}>{names[i]}</Text>
          <Slider value={Math.round((coverage[i] ?? 0) * 100)}
            onChange={(val) => handleSlider(i, val)}
            min={0} max={100} step={1} size="sm" style={{ flex: 1 }} />
          <Text size="xs" miw={32} ta="right">{Math.round((coverage[i] ?? 0) * 100)}%</Text>
        </Group>
      ))}
      <Text size="xs" c="dimmed">{names[n - 1]}: {Math.round((coverage[n - 1] ?? 0) * 100)}% (auto)</Text>
      <Button variant="subtle" size="xs" onClick={() => setCoverage(defaultCoverage(n))}>
        {t("colour.reset_coverage")}
      </Button>
    </Stack>
  );
}
