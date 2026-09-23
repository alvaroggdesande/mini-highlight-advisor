import { Checkbox, Paper, Radio, Stack, Text } from "@mantine/core";
import { useProjectStore, activeBookOf } from "../store/projectStore";
import { regionLabel } from "../lib/geometry";

export function RegionSelector() {
  const book = useProjectStore(activeBookOf);
  const setSelected = useProjectStore((s) => s.setSelected);
  const toggleBlank = useProjectStore((s) => s.toggleBlank);
  if (!book) return null;
  const names = ["Whole mini", ...book.drawn.map((r) => r.name)];

  return (
    <Paper withBorder p="xs" mb="xs">
      <Text size="xs" fw={500} mb={4}>Region</Text>
      <Radio.Group value={String(book.selected)} onChange={(v) => setSelected(Number(v))}>
        <Stack gap={4}>
          {names.map((name, g) => (
            <Stack key={g} gap={2}>
              <Radio value={String(g)} label={regionLabel(g, name)} size="xs" />
              {g >= 1 && (
                <Checkbox size="xs" label="visible" ml="md"
                  checked={!book.drawn[g - 1].blank}
                  onChange={() => toggleBlank(g)} />
              )}
            </Stack>
          ))}
        </Stack>
      </Radio.Group>
    </Paper>
  );
}
