import { useTranslation } from "react-i18next";
import { Badge, Box, Center, Group, Loader, Text } from "@mantine/core";
import { useProjectStore, activeAngleOf } from "../store/projectStore";
import { ErrorNotice } from "./ErrorNotice";

export function PreviewImage() {
  const { t } = useTranslation();
  const angle = useProjectStore(activeAngleOf);
  const retry = useProjectStore((s) => s.retryAnalyze);
  if (!angle) return <Text c="dimmed">{t("preview.placeholder")}</Text>;
  const err = angle.error && <ErrorNotice message={t("errors.analyze")} detail={angle.error} onRetry={retry} />;
  if (!angle.preview) {
    return err || (
      <Center mih={200}><Group gap="xs"><Loader size="sm" /><Text size="sm" c="dimmed">{t("preview.rendering")}</Text></Group></Center>
    );
  }
  return (
    <>
      {err}
      <Box pos="relative">
        <img src={angle.preview} alt={t("preview.alt")} style={{ maxWidth: "100%", display: "block" }} />
        {angle.analyzing && (
          <Badge pos="absolute" top={8} left={8} variant="filled" color="dark"
            leftSection={<Loader size={10} color="white" />}>{t("preview.updating")}</Badge>
        )}
      </Box>
    </>
  );
}
