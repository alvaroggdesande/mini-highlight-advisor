import { useTranslation } from "react-i18next";
import { Tabs, Tooltip } from "@mantine/core";

/** Paint-steps tab trigger; while disabled, a tooltip says why. Disabled buttons
 *  swallow mouse events, so the tooltip anchors on a wrapper span and the button
 *  itself ignores the pointer. */
export function PaintTabTrigger({ disabled }: { disabled: boolean }) {
  const { t } = useTranslation();
  return (
    <Tooltip label={t("tabs.paint_disabled")} disabled={!disabled} withArrow>
      <span data-testid="paint-tab-wrap" style={{ display: "inline-flex" }}>
        <Tabs.Tab value="paint" disabled={disabled}
          style={disabled ? { pointerEvents: "none" } : undefined}>
          {t("tabs.paint")}
        </Tabs.Tab>
      </span>
    </Tooltip>
  );
}
