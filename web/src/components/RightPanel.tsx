import { useState } from "react";
import { useTranslation } from "react-i18next";
import { ManagePanel } from "./ManagePanel";
import { ColourPanel } from "./colour/ColourPanel";
import { TechniquePanel } from "./TechniquePanel";

type Tab = "manage" | "colour" | "technique";
const TABS: Tab[] = ["manage", "colour", "technique"];

export function RightPanel() {
  const { t } = useTranslation();
  const [active, setActive] = useState<Tab>("manage");

  return (
    <div>
      <div role="tablist" style={{ display: "flex", gap: 4, marginBottom: 8 }}>
        {TABS.map((tab) => (
          <button
            key={tab}
            role="tab"
            aria-selected={active === tab}
            onClick={() => setActive(tab)}
            style={{ fontWeight: active === tab ? "bold" : "normal" }}
          >
            {t(`tabs.${tab}`)}
          </button>
        ))}
      </div>
      <div role="tabpanel">
        {active === "manage" && <ManagePanel />}
        {active === "colour" && <ColourPanel />}
        {active === "technique" && <TechniquePanel />}
      </div>
    </div>
  );
}
