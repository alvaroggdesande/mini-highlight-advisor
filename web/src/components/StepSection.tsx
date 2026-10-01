import type { ReactNode } from "react";
import { Badge, Group, Stack, Text } from "@mantine/core";

interface Props {
  n?: number; title: ReactNode; caption?: string; right?: ReactNode; testId?: string; children: ReactNode;
}

/** Numbered step header (circle + title + optional right slot + caption) above its content. */
export function StepSection({ n, title, caption, right, testId, children }: Props) {
  return (
    <Stack gap="xs" data-testid={testId}>
      <Group gap="xs" align="center" wrap="wrap">
        {n !== undefined && <Badge circle size="lg" variant="filled">{n}</Badge>}
        <Text fw={600}>{title}</Text>
        {right}
        {caption && <Text size="xs" c="dimmed">{caption}</Text>}
      </Group>
      {children}
    </Stack>
  );
}
