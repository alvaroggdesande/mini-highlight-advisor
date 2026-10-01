import { useState } from "react";
import type { MouseEvent } from "react";
import { useTranslation } from "react-i18next";
import { ActionIcon, Button, Checkbox, NativeSelect, Table, Text, TextInput } from "@mantine/core";
import { useProjectStore, activeBookOf, anchorIndexOf } from "../store/projectStore";
import { SURFACES } from "../api/types";
import { ManagePanel } from "./ManagePanel";
import { StepSection } from "./StepSection";

// Inputs inside a row must not also select the row.
const stop = (e: MouseEvent) => e.stopPropagation();

export function RegionTable() {
  const { t } = useTranslation();
  const book = useProjectStore(activeBookOf);
  const setSelected = useProjectStore((s) => s.setSelected);
  const setSurface = useProjectStore((s) => s.setSurface);
  const setTone = useProjectStore((s) => s.setTone);
  const setMaterial = useProjectStore((s) => s.setMaterial);
  const setAnchor = useProjectStore((s) => s.setAnchor);
  const renameRegion = useProjectStore((s) => s.renameRegion);
  const toggleBlank = useProjectStore((s) => s.toggleBlank);
  const removeRegion = useProjectStore((s) => s.removeRegion);
  const [drawOpen, setDrawOpen] = useState(false);

  if (!book) return null;
  const anchor = anchorIndexOf(book);
  const rows = [
    { id: undefined as string | undefined, name: t("region.whole_mini"), r: book.whole },
    ...book.drawn.map((d) => ({ id: d.id as string | undefined, name: d.name, r: d })),
  ];

  return (
    <StepSection n={1} title={t("studio.step_regions")} testId="step-regions">
      <Table verticalSpacing={4} highlightOnHover>
        <Table.Thead>
          <Table.Tr>
            <Table.Th />
            <Table.Th>{t("region.select")}</Table.Th>
            <Table.Th>{t("colour.surface")}</Table.Th>
            <Table.Th>{t("colour.tone")}</Table.Th>
            <Table.Th>{t("technique.material")}</Table.Th>
            <Table.Th>{t("region.visible")}</Table.Th>
            <Table.Th />
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {rows.map(({ id, name, r }, g) => {
            const selected = g === book.selected;
            return (
              <Table.Tr key={id ?? "__whole__"} data-testid={`region-row-${g}`}
                aria-selected={selected} onClick={() => setSelected(g)} style={{ cursor: "pointer" }}
                bg={selected ? "var(--mantine-primary-color-light)" : undefined}>
                <Table.Td onClick={stop}>
                  <ActionIcon size="sm" variant="subtle" aria-pressed={g === anchor}
                    aria-label={t("studio.anchor_aria", { name })} onClick={() => setAnchor(id)}>
                    {g === anchor ? "★" : "☆"}
                  </ActionIcon>
                </Table.Td>
                <Table.Td>
                  {g === 0 ? name : (
                    <TextInput size="xs" aria-label={t("region.name_aria", { name })} value={name}
                      onChange={(e) => renameRegion(g, e.target.value)} />
                  )}
                </Table.Td>
                <Table.Td onClick={stop}>
                  <NativeSelect size="xs" aria-label={`${t("colour.surface")} ${name}`}
                    value={r.surface ?? "skin"} onChange={(e) => setSurface(g, e.target.value)}
                    data={SURFACES.map((s) => ({ value: s, label: t(`surfaces.${s}`) }))} />
                </Table.Td>
                <Table.Td onClick={stop}>
                  <TextInput size="xs" aria-label={`${t("colour.tone")} ${name}`} style={{ maxWidth: 120 }}
                    placeholder={t("colour.tone_placeholder")} value={r.tone ?? ""}
                    onChange={(e) => setTone(g, e.target.value)} />
                </Table.Td>
                <Table.Td onClick={stop}>
                  <NativeSelect size="xs" aria-label={`${t("technique.material")} ${name}`}
                    value={r.material} onChange={(e) => setMaterial(g, e.target.value)}
                    data={[{ value: "matte", label: t("technique.matte") },
                           { value: "metallic", label: t("technique.metallic") }]} />
                </Table.Td>
                <Table.Td onClick={stop}>
                  {g > 0 && (
                    <Checkbox size="xs" aria-label={`${t("region.visible")} ${name}`}
                      checked={!book.drawn[g - 1].blank} onChange={() => toggleBlank(g)} />
                  )}
                </Table.Td>
                <Table.Td onClick={stop}>
                  {g > 0 && (
                    <ActionIcon size="sm" variant="subtle" color="red"
                      aria-label={`${t("region.delete")} ${name}`} onClick={() => removeRegion(g)}>✕</ActionIcon>
                  )}
                </Table.Td>
              </Table.Tr>
            );
          })}
        </Table.Tbody>
      </Table>
      {book.drawn.length === 0 && !drawOpen && (
        <Text size="xs" c="dimmed">{t("region.intro")}</Text>
      )}
      <Button size="xs" variant="subtle" style={{ alignSelf: "flex-start" }}
        aria-expanded={drawOpen} onClick={() => setDrawOpen((o) => !o)}
        rightSection={drawOpen ? "▴" : "▾"}>
        {t(drawOpen ? "studio.hide_drawing" : "studio.draw_region")}
      </Button>
      {drawOpen && <ManagePanel onClose={() => setDrawOpen(false)} />}
    </StepSection>
  );
}
