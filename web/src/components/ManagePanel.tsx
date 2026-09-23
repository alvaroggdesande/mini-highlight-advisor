import { useState } from "react";
import { ActionIcon, Button, Group, Stack, Text, TextInput } from "@mantine/core";
import { useProjectStore, activeBookOf } from "../store/projectStore";
import { RegionCanvas } from "./RegionCanvas";

export function ManagePanel() {
  const book = useProjectStore(activeBookOf);
  const addRegion = useProjectStore((s) => s.addRegion);
  const removeRegion = useProjectStore((s) => s.removeRegion);
  const renameRegion = useProjectStore((s) => s.renameRegion);
  const [drawing, setDrawing] = useState(false);
  const [draftRings, setDraftRings] = useState<number[][][]>([]);
  const [name, setName] = useState("");

  if (!book) return null;
  const sel = book.selected;
  const defaultName = `region ${book.drawn.length + 1}`;

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
        <Button size="xs" variant="default" onClick={() => setDrawing(true)}>Draw region</Button>
      ) : (
        <Group gap="xs" align="center">
          <TextInput size="xs" placeholder={defaultName} value={name}
            onChange={(e) => setName(e.target.value)} style={{ flex: 1 }} />
          <Button size="xs" onClick={commit}>Add region</Button>
          <Button size="xs" variant="subtle" onClick={cancel}>Cancel</Button>
          {draftRings.length > 0 && (
            <Text size="xs" c="dimmed">{draftRings.length} stroke(s)</Text>
          )}
        </Group>
      )}
      {!drawing && sel >= 1 && (
        <Group gap="xs">
          <TextInput size="xs" value={book.drawn[sel - 1].name}
            onChange={(e) => renameRegion(sel, e.target.value)} style={{ flex: 1 }} />
          <ActionIcon size="sm" variant="subtle" color="red"
            onClick={() => removeRegion(sel)} aria-label="Delete region">✕</ActionIcon>
        </Group>
      )}
    </Stack>
  );
}
