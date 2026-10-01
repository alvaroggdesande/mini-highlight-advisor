import { useTranslation } from "react-i18next";
import { List, Stack, Text } from "@mantine/core";

const TIP_KEYS = ["raking", "no_flash", "fill", "background", "focus", "primed"] as const;

/** How-to-photograph guidance (mirrors the core SHOOTING_GUIDE), shared by the
 *  first screen and the photo-quality alert. */
export function PhotoTips() {
  const { t } = useTranslation();
  return (
    <Stack gap={6}>
      <List size="sm" spacing={4}>
        {TIP_KEYS.map((k) => <List.Item key={k}>{t(`tips.${k}`)}</List.Item>)}
      </List>
      <Text size="xs" c="dimmed">{t("tips.painted")}</Text>
    </Stack>
  );
}
