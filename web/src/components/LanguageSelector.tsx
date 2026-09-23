import { useTranslation } from "react-i18next";
import { SegmentedControl } from "@mantine/core";

export function LanguageSelector() {
  const { i18n } = useTranslation();
  return (
    <SegmentedControl
      size="xs"
      data={[{ value: "en", label: "EN" }, { value: "es", label: "ES" }]}
      value={i18n.language}
      onChange={(v) => i18n.changeLanguage(v)}
    />
  );
}
