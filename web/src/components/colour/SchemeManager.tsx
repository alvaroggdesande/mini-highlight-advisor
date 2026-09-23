import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Button, Group, Stack, Text, TextInput } from "@mantine/core";
import { useProjectStore, activeBookOf } from "../../store/projectStore";

export function SchemeManager() {
  const { t } = useTranslation();
  const schemes = useProjectStore((s) => activeBookOf(s)?.schemes ?? []);
  const saveScheme = useProjectStore((s) => s.saveScheme);
  const applyScheme = useProjectStore((s) => s.applyScheme);
  const deleteScheme = useProjectStore((s) => s.deleteScheme);
  const [name, setName] = useState("");

  return (
    <Stack gap="xs">
      <Text size="sm" fw={500}>{t("schemes.title")}</Text>
      <Group gap="xs">
        <TextInput size="xs" value={name} placeholder={t("schemes.name_placeholder")}
          onChange={(e) => setName(e.target.value)} style={{ flex: 1 }} />
        <Button size="xs" disabled={!name.trim()}
          onClick={() => { if (name.trim()) { saveScheme(name.trim()); setName(""); } }}>
          {t("schemes.save")}
        </Button>
      </Group>
      <Stack gap={4}>
        {schemes.map((sc) => (
          <Group key={sc.id} gap="xs">
            <Text size="xs" style={{ flex: 1 }}>{sc.name}</Text>
            <Button size="xs" variant="subtle" onClick={() => applyScheme(sc.id)}>{t("schemes.apply")}</Button>
            <Button size="xs" variant="subtle" color="red" onClick={() => deleteScheme(sc.id)}>{t("schemes.delete")}</Button>
          </Group>
        ))}
      </Stack>
    </Stack>
  );
}
