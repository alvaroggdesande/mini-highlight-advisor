import { useEffect, useRef, useState } from "react";
import { Button, Group, Stack, Text } from "@mantine/core";
import { listSamplePhotos, samplePhotoBlob, uploadPhoto } from "../api/client";
import type { SamplePhoto } from "../api/types";
import { useProjectStore } from "../store/projectStore";

export function PhotoUploader() {
  const initFromPhoto = useProjectStore((s) => s.initFromPhoto);
  const setError = useProjectStore((s) => s.setError);
  const [samples, setSamples] = useState<SamplePhoto[]>([]);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => { listSamplePhotos().then(setSamples).catch(() => setSamples([])); }, []);

  async function handleBlob(blob: Blob, name: string) {
    try { initFromPhoto(await uploadPhoto(blob, name)); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  }

  return (
    <Stack gap="sm" mt="md">
      <Button variant="default" onClick={() => fileRef.current?.click()}>
        Upload photo
      </Button>
      <input
        ref={fileRef}
        type="file"
        accept="image/png,image/jpeg"
        style={{ display: "none" }}
        onChange={(e) => { const f = e.target.files?.[0]; if (f) handleBlob(f, f.name); }}
      />
      {samples.length > 0 && (
        <>
          <Text size="sm" c="dimmed">Or start from a sample:</Text>
          <Group gap="xs">
            {samples.map((s) => (
              <Button key={s.id} variant="subtle" size="xs"
                onClick={async () => {
                  try { handleBlob(await samplePhotoBlob(s.id), `${s.id}.png`); }
                  catch (e) { setError(e instanceof Error ? e.message : String(e)); }
                }}>
                {s.name}
              </Button>
            ))}
          </Group>
        </>
      )}
    </Stack>
  );
}
