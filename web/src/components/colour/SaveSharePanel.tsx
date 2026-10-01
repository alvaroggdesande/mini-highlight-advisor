import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Button, Stack } from "@mantine/core";
import { RecipeSaver } from "./RecipeSaver";
import { SchemeManager } from "./SchemeManager";
import { RecipeManager } from "./RecipeManager";

export function SaveSharePanel() {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  return (
    <Stack gap="xs" data-testid="save-share">
      <Button size="xs" variant="subtle" justify="flex-start" style={{ alignSelf: "flex-start" }}
        aria-expanded={open} onClick={() => setOpen((o) => !o)}>
        {open ? "▾" : "▸"} {t("studio.save_share")}
      </Button>
      {open && (
        <Stack gap="sm" pl="sm">
          <RecipeSaver />
          <SchemeManager />
          <RecipeManager />
        </Stack>
      )}
    </Stack>
  );
}
