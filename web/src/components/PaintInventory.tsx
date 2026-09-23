import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Checkbox, ColorSwatch, Group, Loader, ScrollArea, Stack, Text, TextInput } from "@mantine/core";
import { useCatalogStore } from "../store/catalogStore";

export function PaintInventory() {
  const { t } = useTranslation();
  const paints = useCatalogStore((s) => s.paints);
  const ownedCodes = useCatalogStore((s) => s.ownedCodes);
  const status = useCatalogStore((s) => s.status);
  const toggleOwned = useCatalogStore((s) => s.toggleOwned);
  const [search, setSearch] = useState("");

  if (status !== "ready") {
    return (
      <Group gap="sm">
        <Loader size="xs" />
        <Text size="sm" c="dimmed">{t("paints.loading")}</Text>
      </Group>
    );
  }

  const q = search.trim().toLowerCase();
  const filtered = q
    ? paints.filter((p) =>
        p.name.toLowerCase().includes(q) ||
        (p.code ?? "").toLowerCase().includes(q) ||
        (p.paint_range ?? "").toLowerCase().includes(q))
    : paints;

  const ownedCount = paints.filter((p) => ownedCodes.has(p.code ?? "")).length;

  return (
    <Stack gap="xs">
      <TextInput
        type="search"
        placeholder={t("paints.search_placeholder")}
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        size="xs"
      />
      <Text size="xs" c="dimmed">
        {t("paints.owned_count", { owned: ownedCount, total: paints.length })}
        {q && ` · ${filtered.length} ${t("paints.filtered_suffix")}`}
      </Text>
      <ScrollArea h={420}>
        <Stack gap={0}>
          {filtered.map((p) => {
            const code = p.code ?? "";
            const owned = ownedCodes.has(code);
            return (
              <Group key={code || p.name} gap="xs" py={4}
                style={{ borderBottom: "1px solid var(--mantine-color-dark-5)", opacity: owned ? 1 : 0.7, cursor: "pointer" }}
                onClick={() => toggleOwned(code)}>
                <Checkbox size="xs" checked={owned}
                  onChange={() => toggleOwned(code)}
                  onClick={(e) => e.stopPropagation()}
                  style={{ flexShrink: 0 }} />
                <ColorSwatch color={p.hex} size={14} style={{ flexShrink: 0 }} />
                <Text size="xs" c={owned ? undefined : "dimmed"} style={{ flex: 1 }}>{p.name}</Text>
                {p.paint_range && <Text size="xs" c="dimmed">{p.paint_range}</Text>}
                <Text size="xs" c="dimmed" ff="monospace">{code}</Text>
              </Group>
            );
          })}
          {filtered.length === 0 && q && (
            <Text size="sm" c="dimmed" p="xs">{t("paints.no_results")}</Text>
          )}
        </Stack>
      </ScrollArea>
    </Stack>
  );
}
