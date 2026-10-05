import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { ColorSwatch, Group, Select, Text } from "@mantine/core";
import type { ComboboxItem, ComboboxLikeRenderOptionInput, OptionsFilter } from "@mantine/core";
import { useCatalogStore } from "../../store/catalogStore";
import type { PaintColor } from "../../api/types";

interface Props {
  /** Selected catalog code, or null when the slot holds a custom hex. */
  value?: string | null;
  onPick: (paint: PaintColor) => void;
  label?: string;
  placeholder?: string;
  style?: React.CSSProperties;
}

/** Every whitespace-separated word must appear in name, code, brand or range ("vallejo red"). */
export const paintFilter: OptionsFilter = ({ options, search }) => {
  const words = search.toLowerCase().split(/\s+/).filter(Boolean);
  if (words.length === 0) return options;
  return (options as ComboboxItem[]).filter((o) => {
    const hay = o.label.toLowerCase();
    return words.every((w) => hay.includes(w));
  });
};

export function PaintSearch({ value = null, onPick, label, placeholder, style }: Props) {
  const { t } = useTranslation();
  const paints = useCatalogStore((s) => s.paints);
  const byCode = useMemo(() => new Map(paints.map((p) => [p.code!, p])), [paints]);
  const data = useMemo(() => paints.filter((p) => p.code).map((p) => ({
    value: p.code!,
    label: [p.name, p.code, p.brand, p.paint_range].filter(Boolean).join(" · "),
  })), [paints]);

  const renderOption = ({ option }: ComboboxLikeRenderOptionInput<ComboboxItem>) => {
    const p = byCode.get(option.value);
    return (
      <Group gap={6} wrap="nowrap">
        <ColorSwatch color={p?.hex ?? "#808080"} size={14} style={{ flexShrink: 0 }} />
        <div>
          <Text size="xs">{p?.name}</Text>
          <Text size="xs" c="dimmed">{p?.brand} · {p?.code}</Text>
        </div>
      </Group>
    );
  };

  const selected = value ? byCode.get(value) : undefined;

  return (
    <Select searchable size="xs" label={label} style={style}
      placeholder={placeholder ?? t("colour.search_paint")}
      nothingFoundMessage={t("colour.no_paint_found")}
      data={data} value={selected ? value : null} filter={paintFilter} limit={50}
      renderOption={renderOption}
      leftSection={selected ? <ColorSwatch color={selected.hex} size={14} /> : undefined}
      comboboxProps={{ width: 300, position: "bottom-start" }}
      onChange={(code) => { const p = code ? byCode.get(code) : undefined; if (p) onPick(p); }} />
  );
}
