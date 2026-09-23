import { Box, Group, Stack } from "@mantine/core";
import { PreviewImage } from "./PreviewImage";
import { RegionHeader } from "./RegionHeader";
import { GeneratePanel } from "./colour/GeneratePanel";
import { BandEditor } from "./colour/BandEditor";
import { SchemeManager } from "./colour/SchemeManager";
import { RecipeManager } from "./colour/RecipeManager";

export function StudioPanel() {
  return (
    <Group align="flex-start" gap="xl" wrap="nowrap">
      <Box data-testid="studio-preview"
        style={{ position: "sticky", top: 16, alignSelf: "flex-start", maxWidth: 360, flexShrink: 0 }}>
        <PreviewImage />
      </Box>
      <Stack data-testid="studio-editor" style={{ flex: 1 }} gap="md">
        <GeneratePanel />
        <RegionHeader />
        <BandEditor />
        <SchemeManager />
        <RecipeManager />
      </Stack>
    </Group>
  );
}
