import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button, Group, Stack, Text } from "@mantine/core";
import { exportRecipes, importRecipes } from "../../api/client";
import { ErrorNotice } from "../ErrorNotice";

function triggerDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a"); a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
}

export function RecipeManager() {
  const { t } = useTranslation();
  const recipeRef = useRef<HTMLInputElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);

  async function run(fn: () => Promise<void>) {
    setError(null); setOk(null);
    try { await fn(); } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  }
  async function onRecipes(f: File) { await run(async () => { await importRecipes(f); setOk(t("recipes.import_success")); }); }

  return (
    <Stack gap={4}>
      <Group gap="xs" wrap="wrap">
        <Button size="xs" variant="subtle" onClick={() => run(async () => triggerDownload(await exportRecipes(), "recipes.json"))}>
          {t("recipes.export")}
        </Button>
        <Button size="xs" variant="subtle" onClick={() => recipeRef.current?.click()}>
          {t("recipes.import")}
        </Button>
        <input ref={recipeRef} type="file" accept=".json" style={{ display: "none" }} data-kind="recipes"
          onChange={(e) => { const f = e.target.files?.[0]; if (f) { onRecipes(f); e.target.value = ""; } }} />
      </Group>
      {ok && <Text size="xs" c="green">{ok}</Text>}
      {error && <ErrorNotice message={t("errors.import")} detail={error} />}
    </Stack>
  );
}
