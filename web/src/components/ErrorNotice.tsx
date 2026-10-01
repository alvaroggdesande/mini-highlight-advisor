import { useTranslation } from "react-i18next";
import { Alert, Button, Stack, Text } from "@mantine/core";

export interface ErrorNoticeProps { message: string; detail?: string; onRetry?: () => void; }

/** Friendly error box: translated message, optional raw detail (for bug reports), optional Retry. */
export function ErrorNotice({ message, detail, onRetry }: ErrorNoticeProps) {
  const { t } = useTranslation();
  return (
    <Alert color="red" variant="light" role="alert">
      <Stack gap={6} align="flex-start">
        <Text size="sm">{message}</Text>
        {detail && <Text size="xs" c="dimmed" style={{ wordBreak: "break-word" }}>{detail}</Text>}
        {onRetry && <Button size="xs" variant="light" color="red" onClick={onRetry}>{t("errors.retry")}</Button>}
      </Stack>
    </Alert>
  );
}
