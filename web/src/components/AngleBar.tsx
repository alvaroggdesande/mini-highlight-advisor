import { useRef } from "react";
import { ActionIcon, Button, Group, Stack, TextInput } from "@mantine/core";
import { useProjectStore } from "../store/projectStore";
import { uploadPhoto } from "../api/client";

export function AngleBar() {
  const angles = useProjectStore((s) => s.angles);
  const active = useProjectStore((s) => s.activeAngle);
  const addAngle = useProjectStore((s) => s.addAngle);
  const switchAngle = useProjectStore((s) => s.switchAngle);
  const renameAngle = useProjectStore((s) => s.renameAngle);
  const removeAngle = useProjectStore((s) => s.removeAngle);
  const setError = useProjectStore((s) => s.setError);
  const fileRef = useRef<HTMLInputElement>(null);

  if (angles.length === 0) return null;

  async function onAdd(file: File) {
    try { addAngle(await uploadPhoto(file, file.name)); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  }

  return (
    <Stack gap="xs" mb="sm">
      <Group gap="xs" wrap="wrap">
        {angles.map((a, i) => (
          <Button key={a.id} size="xs"
            variant={i === active ? "filled" : "default"}
            onClick={() => switchAngle(i)}>
            {a.label}
          </Button>
        ))}
        <Button size="xs" variant="subtle" onClick={() => fileRef.current?.click()}>+ angle</Button>
        <input ref={fileRef} type="file" accept="image/png,image/jpeg" style={{ display: "none" }}
          onChange={(e) => { const f = e.target.files?.[0]; if (f) onAdd(f); }} />
      </Group>
      <Group gap="xs">
        <TextInput
          size="xs"
          value={angles[active].label}
          onChange={(e) => renameAngle(active, e.target.value)}
          aria-label="Rename angle"
          style={{ maxWidth: 200 }}
        />
        <ActionIcon size="sm" variant="subtle" color="red"
          disabled={angles.length === 1}
          onClick={() => removeAngle(active)}
          aria-label="Remove angle">
          ✕
        </ActionIcon>
      </Group>
    </Stack>
  );
}
