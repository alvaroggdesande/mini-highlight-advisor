import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Tabs } from "@mantine/core";
import { ManagePanel } from "./ManagePanel";
import { ColourPanel } from "./colour/ColourPanel";
import { TechniquePanel } from "./TechniquePanel";

type Tab = "manage" | "colour" | "technique";

export function RightPanel() {
  const { t } = useTranslation();
  const [active, setActive] = useState<Tab>("manage");

  return (
    <Tabs value={active} onChange={(v) => setActive((v as Tab) ?? "manage")}>
      <Tabs.List mb="sm">
        <Tabs.Tab value="manage">{t("tabs.manage")}</Tabs.Tab>
        <Tabs.Tab value="colour">{t("tabs.colour")}</Tabs.Tab>
        <Tabs.Tab value="technique">{t("tabs.technique")}</Tabs.Tab>
      </Tabs.List>
      <Tabs.Panel value="manage"><ManagePanel /></Tabs.Panel>
      <Tabs.Panel value="colour"><ColourPanel /></Tabs.Panel>
      <Tabs.Panel value="technique"><TechniquePanel /></Tabs.Panel>
    </Tabs>
  );
}
