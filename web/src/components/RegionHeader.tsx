import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Button, Collapse, Group, NativeSelect, Paper, Stack, Text, TextInput } from "@mantine/core";
import { useProjectStore, activeBookOf } from "../store/projectStore";
import { SURFACES } from "../api/types";
import { ManagePanel } from "./ManagePanel";

export function RegionHeader() {
  const { t } = useTranslation();
  const book = useProjectStore((s) => activeBookOf(s));
  const setSelected = useProjectStore((s) => s.setSelected);
  const setSurface = useProjectStore((s) => s.setSurface);
  const setTone = useProjectStore((s) => s.setTone);
  const setMaterial = useProjectStore((s) => s.setMaterial);
  const [manageOpen, setManageOpen] = useState(false);

  if (!book) return null;
  const g = book.selected;
  const region = g === 0 ? book.whole : book.drawn[g - 1];
  const names = ["Whole mini", ...book.drawn.map((r) => r.name)];

  return (
    <Paper withBorder p="xs">
      <Stack gap="xs">
        <Group gap="xs" align="flex-end">
          <Text size="sm" fw={600}>{t("region.editing")}</Text>
          <NativeSelect aria-label="region" size="xs" value={g}
            onChange={(e) => setSelected(Number(e.target.value))}>
            {names.map((name, i) => <option key={i} value={i}>{name}</option>)}
          </NativeSelect>
          <Button size="xs" variant="subtle" onClick={() => setManageOpen((o) => !o)}>
            {t("region.manage")}
          </Button>
        </Group>
        <Group gap="xs" align="flex-end" wrap="wrap">
          <NativeSelect label={t("colour.surface")} size="xs" value={region.surface ?? "skin"}
            onChange={(e) => setSurface(g, e.target.value)}
            data={SURFACES.map((s) => ({ value: s, label: t(`surfaces.${s}`) }))} />
          <TextInput label={t("colour.tone")} size="xs" value={region.tone ?? ""}
            onChange={(e) => setTone(g, e.target.value)} style={{ maxWidth: 120 }} />
          <NativeSelect label={t("technique.material")} size="xs" value={region.material}
            onChange={(e) => setMaterial(g, e.target.value)}
            data={[{ value: "matte", label: t("technique.matte") },
                   { value: "metallic", label: t("technique.metallic") }]} />
        </Group>
        <Collapse in={manageOpen}><ManagePanel /></Collapse>
      </Stack>
    </Paper>
  );
}
