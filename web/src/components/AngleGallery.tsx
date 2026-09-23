import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { ActionIcon, Badge, Card, Center, Group, Image, SimpleGrid, Stack, Text, TextInput } from "@mantine/core";
import { analyze } from "../api/client";
import { useProjectStore } from "../store/projectStore";
import type { AnalyzeRequest } from "../api/types";
import type { Angle } from "../store/projectStore";

function buildRequest(angle: Angle): AnalyzeRequest {
  return {
    photo_id: angle.photoId!,
    whole: angle.book.whole,
    regions: angle.book.drawn
      .filter((r) => !r.blank)
      .map((r) => ({ name: r.name, rings: r.rings, palette: r.palette, coverage: r.coverage, material: r.material })),
    settings: angle.settings,
  };
}

type PreviewState = string | null | "error";

export function AngleGallery() {
  const { t } = useTranslation();
  const angles = useProjectStore((s) => s.angles);
  const activeAngle = useProjectStore((s) => s.activeAngle);
  const switchAngle = useProjectStore((s) => s.switchAngle);
  const renameAngle = useProjectStore((s) => s.renameAngle);
  const removeAngle = useProjectStore((s) => s.removeAngle);

  const [previews, setPreviews] = useState<Record<string, PreviewState>>(() => {
    const init: Record<string, PreviewState> = {};
    for (const a of angles) { init[a.id] = a.preview ?? null; }
    return init;
  });

  useEffect(() => {
    let cancelled = false;
    setPreviews((prev) => {
      const next: Record<string, PreviewState> = {};
      for (const a of angles) { next[a.id] = a.preview ?? prev[a.id] ?? null; }
      return next;
    });
    for (const angle of angles) {
      if (angle.preview || !angle.photoId) continue;
      analyze(buildRequest(angle))
        .then((res) => { if (!cancelled) setPreviews((prev) => { const e = prev[angle.id]; if (e && e !== "error") return prev; return { ...prev, [angle.id]: res.preview_png }; }); })
        .catch(() => { if (!cancelled) setPreviews((p) => ({ ...p, [angle.id]: "error" })); });
    }
    return () => { cancelled = true; };
  }, [angles]);

  if (angles.length === 0) return <Text c="dimmed" size="sm">{t("gallery.no_angles")}</Text>;

  return (
    <Stack gap="xs">
      <Text fw={500}>{t("gallery.heading")}</Text>
      <Text size="xs" c="dimmed" mb="xs">{t("gallery.caption")}</Text>
      <SimpleGrid cols={3} spacing="md">
        {angles.map((angle, idx) => {
          const preview = previews[angle.id];
          const isActive = idx === activeAngle;
          return (
            <Card key={angle.id} withBorder padding="xs"
              data-testid={`angle-card-${idx}`}
              onClick={() => switchAngle(idx)}
              style={{ borderColor: isActive ? "var(--mantine-color-violet-5)" : undefined, cursor: "pointer" }}>
              {!angle.photoId ? (
                <Center h={160}><Text size="sm" c="dimmed">{t("gallery.no_photo")}</Text></Center>
              ) : preview === null ? (
                <Center h={160}><Text size="sm" c="dimmed">{t("gallery.loading")}</Text></Center>
              ) : preview === "error" ? (
                <Center h={160}><Text size="sm" c="red">{t("gallery.preview_error")}</Text></Center>
              ) : (
                <Image src={preview} alt={angle.label} w="100%" style={{ display: "block", objectFit: "contain" }} />
              )}
              <Group gap="xs" mt="xs" onClick={(e) => e.stopPropagation()}>
                <TextInput size="xs" aria-label="Rename angle" value={angle.label}
                  onChange={(e) => renameAngle(idx, e.target.value)} style={{ flex: 1 }} />
                {isActive && <Badge size="xs" variant="light">{t("gallery.active_badge")}</Badge>}
                <ActionIcon size="sm" variant="subtle" color="red" aria-label="Remove angle"
                  disabled={angles.length === 1} onClick={() => removeAngle(idx)}>✕</ActionIcon>
              </Group>
            </Card>
          );
        })}
      </SimpleGrid>
    </Stack>
  );
}
