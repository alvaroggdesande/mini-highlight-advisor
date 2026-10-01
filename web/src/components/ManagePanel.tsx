import { useState } from "react";
import { useTranslation } from "react-i18next";
import { ActionIcon, Button, Checkbox, Group, Stack, Text, TextInput } from "@mantine/core";
import { useProjectStore, activeBookOf } from "../store/projectStore";
import { RegionCanvas } from "./RegionCanvas";

export function ManagePanel() {
  const { t } = useTranslation();
  const book = useProjectStore(activeBookOf);
  const addRegion = useProjectStore((s) => s.addRegion);
  const removeRegion = useProjectStore((s) => s.removeRegion);
  const renameRegion = useProjectStore((s) => s.renameRegion);
  const toggleBlank = useProjectStore((s) => s.toggleBlank);
  const [drawing, setDrawing] = useState(false);
  const [draftRings, setDraftRings] = useState<number[][][]>([]);
  const [name, setName] = useState("");

  if (!book) return null;
  const sel = book.selected;
  const defaultName = t("region.default_name", { n: book.drawn.length + 1 });

  function commit() {
    if (draftRings.length === 0) return;
    addRegion(draftRings, name.trim() || defaultName);
    setDrawing(false); setDraftRings([]); setName("");
  }
  function cancel() { setDrawing(false); setDraftRings([]); setName(""); }

  return (
    <Stack gap="xs">
      <RegionCanvas drawing={drawing} draftRings={draftRings} onDraftChange={setDraftRings} />
      {!drawing ? (
        <Button size="xs" variant="default" onClick={() => setDrawing(true)}>{t("region.draw")}</Button>
      ) : (
        <Group gap="xs" align="center">
          <TextInput size="xs" placeholder={defaultName} value={name}
            onChange={(e) => setName(e.target.value)} style={{ flex: 1 }} />
          <Button size="xs" onClick={commit}>{t("region.add")}</Button>
          <Button size="xs" variant="subtle" onClick={cancel}>{t("region.cancel")}</Button>
          {draftRings.length > 0 && (
            <Text size="xs" c="dimmed">{t("region.strokes", { count: draftRings.length })}</Text>
          )}
        </Group>
      )}
      {!drawing && sel >= 1 && (
        <Group gap="xs" align="center">
          <TextInput size="xs" value={book.drawn[sel - 1].name}
            onChange={(e) => renameRegion(sel, e.target.value)} style={{ flex: 1 }} />
          <Checkbox size="xs" aria-label={t("region.visible")} label={t("region.visible")}
            checked={!book.drawn[sel - 1].blank} onChange={() => toggleBlank(sel)} />
          <ActionIcon size="sm" variant="subtle" color="red"
            onClick={() => removeRegion(sel)} aria-label={t("region.delete")}>✕</ActionIcon>
        </Group>
      )}
    </Stack>
  );
}
