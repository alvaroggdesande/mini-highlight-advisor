import { Box, Group, Stack } from "@mantine/core";
import { PreviewImage } from "./PreviewImage";
import { RegionSelector } from "./RegionSelector";
import { RightPanel } from "./RightPanel";

export function StudioPanel() {
  return (
    <Group align="flex-start" gap="xl" wrap="nowrap">
      <Box data-testid="studio-preview"
        style={{ position: "sticky", top: 16, alignSelf: "flex-start", maxWidth: 360, flexShrink: 0 }}>
        <PreviewImage />
      </Box>
      <Stack data-testid="studio-editor" style={{ flex: 1 }}>
        <RegionSelector />
        <RightPanel />
      </Stack>
    </Group>
  );
}
