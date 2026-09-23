import { useTranslation } from "react-i18next";
import { NativeSelect, Stack } from "@mantine/core";
import { useProjectStore, activeBookOf } from "../store/projectStore";

export function TechniquePanel() {
  const { t } = useTranslation();
  const selected = useProjectStore((s) => activeBookOf(s)?.selected ?? 0);
  const material = useProjectStore((s) => {
    const b = activeBookOf(s);
    if (!b) return "matte";
    return selected === 0 ? b.whole.material : (b.drawn[selected - 1]?.material ?? "matte");
  });
  const setMaterial = useProjectStore((s) => s.setMaterial);

  return (
    <Stack p="xs" gap="sm">
      <NativeSelect
        label={t("technique.material")}
        size="xs"
        value={material}
        onChange={(e) => setMaterial(selected, e.target.value)}
        data={[
          { value: "matte", label: t("technique.matte") },
          { value: "metallic", label: t("technique.metallic") },
        ]}
      />
    </Stack>
  );
}
