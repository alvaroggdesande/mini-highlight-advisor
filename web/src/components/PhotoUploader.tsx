import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button, Group, Stack, Text } from "@mantine/core";
import { listSamplePhotos, samplePhotoBlob, uploadPhoto } from "../api/client";
import type { SamplePhoto } from "../api/types";
import { useProjectStore } from "../store/projectStore";
import { downscaleImage } from "../lib/downscale";
import { ErrorNotice } from "./ErrorNotice";

export function PhotoUploader() {
  const { t } = useTranslation();
  const initFromPhoto = useProjectStore((s) => s.initFromPhoto);
  const [samples, setSamples] = useState<SamplePhoto[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => { listSamplePhotos().then(setSamples).catch(() => setSamples([])); }, []);

  async function handleBlob(blob: Blob, name: string) {
    setBusy(true); setError(null);
    try { initFromPhoto(await uploadPhoto(await downscaleImage(blob), name)); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  }

  return (
    <Stack gap="sm" mt="md">
      <Button variant="default" loading={busy} onClick={() => fileRef.current?.click()}>
        {t("upload.button")}
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
          <Text size="sm" c="dimmed">{t("upload.or_sample")}</Text>
          <Group gap="xs">
            {samples.map((s) => (
              <Button key={s.id} variant="subtle" size="xs" disabled={busy}
                onClick={async () => {
                  try { await handleBlob(await samplePhotoBlob(s.id), `${s.id}.png`); }
                  catch (e) { setError(e instanceof Error ? e.message : String(e)); }
                }}>
                {s.name}
              </Button>
            ))}
          </Group>
        </>
      )}
      {error && <ErrorNotice message={t("errors.upload")} detail={error} />}
    </Stack>
  );
}
