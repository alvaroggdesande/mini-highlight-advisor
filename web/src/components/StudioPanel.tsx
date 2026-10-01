import { useTranslation } from "react-i18next";
import { Box, Button, Group, Stack } from "@mantine/core";
import { PreviewImage } from "./PreviewImage";
import { QualityAlert } from "./QualityAlert";
import { RegionTable } from "./RegionTable";
import { GeneratePanel } from "./colour/GeneratePanel";
import { BandEditor } from "./colour/BandEditor";
import { SaveSharePanel } from "./colour/SaveSharePanel";
import { useProjectStore, activeAngleOf } from "../store/projectStore";

export function StudioPanel({ onGoToPaint }: { onGoToPaint: () => void }) {
  const { t } = useTranslation();
  const resultToken = useProjectStore((s) => activeAngleOf(s)?.resultToken);
  return (
    <Group align="flex-start" gap="xl" wrap="nowrap">
      <Box data-testid="studio-preview"
        style={{ position: "sticky", top: 16, alignSelf: "flex-start", maxWidth: 360, flexShrink: 0 }}>
        <QualityAlert />
        <PreviewImage />
        <Button mt="sm" fullWidth variant="light" disabled={!resultToken} onClick={onGoToPaint}>
          {t("studio.go_to_paint")}
        </Button>
      </Box>
      <Stack data-testid="studio-editor" style={{ flex: 1 }} gap="xl">
        <RegionTable />
        <GeneratePanel />
        <BandEditor />
        <SaveSharePanel />
      </Stack>
    </Group>
  );
}
