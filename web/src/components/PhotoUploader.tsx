import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Badge, Button, Group, Paper, Stack, Text, Title } from "@mantine/core";
import { listSamplePhotos, samplePhotoBlob, uploadPhoto } from "../api/client";
import type { SamplePhoto } from "../api/types";
import { useProjectStore } from "../store/projectStore";
import { downscaleImage } from "../lib/downscale";
import { ErrorNotice } from "./ErrorNotice";
import { PhotoTips } from "./PhotoTips";

export function PhotoUploader() {
  const { t } = useTranslation();
  const initFromPhoto = useProjectStore((s) => s.initFromPhoto);
  const [samples, setSamples] = useState<SamplePhoto[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tipsOpen, setTipsOpen] = useState(false);
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
      <Stack gap={4}>
        <Title order={4}>{t("intro.headline")}</Title>
        <Text size="sm" c="dimmed">{t("intro.sub")}</Text>
      </Stack>
      <Group gap="md" wrap="wrap">
        {(["step1", "step2", "step3"] as const).map((k, i) => (
          <Group key={k} gap={6} wrap="nowrap">
            <Badge circle variant="light">{i + 1}</Badge>
            <Text size="sm">{t(`intro.${k}`)}</Text>
          </Group>
        ))}
      </Group>
      <Button variant="default" loading={busy} onClick={() => fileRef.current?.click()}>
        {t("upload.button")}
      </Button>
      <input
        ref={fileRef}
        type="file"
        accept="image/png,image/jpeg"
        style={{ display: "none" }}
        onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ""; if (f) handleBlob(f, f.name); }}
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
      <Button variant="subtle" size="xs" style={{ alignSelf: "flex-start" }}
        onClick={() => setTipsOpen((o) => !o)}>
        {tipsOpen ? "▾" : "▸"} {t("tips.title")}
      </Button>
      {tipsOpen && <Paper withBorder p="sm"><PhotoTips /></Paper>}
    </Stack>
  );
}
