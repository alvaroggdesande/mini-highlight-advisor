import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Alert, Button, Group, List, Stack } from "@mantine/core";
import { useProjectStore, activeAngleOf } from "../store/projectStore";
import { PhotoTips } from "./PhotoTips";

const KNOWN_IDS = new Set(["lighting", "exposure", "focus", "resolution", "input"]);

/** Warns about failed photo-quality checks for the active angle. Advice is
 *  translated by check id; unknown/missing ids fall back to the server's text.
 *  Dismissal is per photo and lasts for the session. */
export function QualityAlert() {
  const { t } = useTranslation();
  const angle = useProjectStore(activeAngleOf);
  const [dismissed, setDismissed] = useState<Set<string>>(new Set());
  const [tipsOpen, setTipsOpen] = useState(false);

  const failing = angle?.qualityChecks.filter((c) => !c.ok) ?? [];
  const photoId = angle?.photoId;
  if (!photoId || failing.length === 0 || dismissed.has(photoId)) return null;

  return (
    <Alert color="yellow" variant="light" title={t("quality.title")} mb="sm">
      <Stack gap="xs">
        <List size="sm" spacing={4}>
          {failing.map((c, i) => (
            <List.Item key={c.id ?? i}>
              {c.id && KNOWN_IDS.has(c.id) ? t(`quality.${c.id}`) : c.detail}
            </List.Item>
          ))}
        </List>
        <Group gap="xs">
          <Button size="xs" variant="light" color="yellow" onClick={() => setTipsOpen((o) => !o)}>
            {t("quality.tips")}
          </Button>
          <Button size="xs" variant="subtle" color="gray"
            onClick={() => setDismissed((d) => new Set(d).add(photoId))}>
            {t("quality.dismiss")}
          </Button>
        </Group>
        {tipsOpen && <PhotoTips />}
      </Stack>
    </Alert>
  );
}
