import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Checkbox, Divider, Group, Slider, Stack, Text } from "@mantine/core";
import { useProjectStore, activeAngleOf } from "../store/projectStore";

/** Per-angle edge-highlight settings; changes re-run the preview via useAnalyze. */
export function EdgeSettings() {
  const { t } = useTranslation();
  const settings = useProjectStore((s) => activeAngleOf(s)?.settings);
  const setSettings = useProjectStore((s) => s.setSettings);
  // Local value while dragging; committed on release so a drag is one analysis, not dozens.
  const [dragSens, setDragSens] = useState<number | null>(null);

  if (!settings) return null;
  const off = !settings.edge_hl;

  return (
    <Stack gap={4}>
      <Divider label={t("edges.title")} labelPosition="left" />
      <Group gap="md" wrap="wrap">
        <Checkbox size="xs" label={t("edges.enabled")} checked={settings.edge_hl}
          onChange={(e) => setSettings({ edge_hl: e.currentTarget.checked })} />
        <Checkbox size="xs" label={t("edges.extreme")} checked={settings.edge_extreme} disabled={off}
          onChange={(e) => setSettings({ edge_extreme: e.currentTarget.checked })} />
      </Group>
      <Group gap="xs" align="center" wrap="nowrap">
        <Text size="xs" miw={90}>{t("edges.sens")}</Text>
        <Text size="xs" c="dimmed">{t("edges.fewer")}</Text>
        <Slider thumbLabel={t("edges.sens")} min={0} max={1} step={0.05} size="sm" style={{ flex: 1 }}
          label={null} disabled={off} value={dragSens ?? settings.edge_sens} onChange={setDragSens}
          onChangeEnd={(v) => { setDragSens(null); setSettings({ edge_sens: v }); }} />
        <Text size="xs" c="dimmed">{t("edges.more")}</Text>
      </Group>
    </Stack>
  );
}
