import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Button, Group, Stack, Text, TextInput } from "@mantine/core";
import { useProjectStore, activeBookOf } from "../store/projectStore";
import { RegionCanvas } from "./RegionCanvas";

// Mounted only while drawing: opening it starts the lasso; Add or Cancel closes it.
export function ManagePanel({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation();
  const book = useProjectStore(activeBookOf);
  const addRegion = useProjectStore((s) => s.addRegion);
  const [draftRings, setDraftRings] = useState<number[][][]>([]);
  const [name, setName] = useState("");

  if (!book) return null;
  const defaultName = t("region.default_name", { n: book.drawn.length + 1 });

  function commit() {
    if (draftRings.length === 0) return;
    addRegion(draftRings, name.trim() || defaultName);
    onClose();
  }

  return (
    <Stack gap="xs">
      <Text size="xs" c="dimmed">{t("region.draw_hint")}</Text>
      <RegionCanvas drawing draftRings={draftRings} onDraftChange={setDraftRings} />
      <Group gap="xs" align="center">
        <TextInput size="xs" placeholder={defaultName} value={name}
          onChange={(e) => setName(e.target.value)} style={{ flex: 1 }} />
        <Button size="xs" onClick={commit} disabled={draftRings.length === 0}>{t("region.add")}</Button>
        <Button size="xs" variant="subtle" onClick={onClose}>{t("region.cancel")}</Button>
        {draftRings.length > 0 && (
          <Text size="xs" c="dimmed">{t("region.strokes", { count: draftRings.length })}</Text>
        )}
      </Group>
    </Stack>
  );
}
