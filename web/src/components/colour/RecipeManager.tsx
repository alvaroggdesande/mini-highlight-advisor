import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button, Group, Stack, Text } from "@mantine/core";
import { exportRecipes, importRecipes, exportCollection, importCollection } from "../../api/client";
import { useCatalogStore } from "../../store/catalogStore";
import { ErrorNotice } from "../ErrorNotice";

function triggerDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a"); a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
}

export function RecipeManager() {
  const { t } = useTranslation();
  const recipeRef = useRef<HTMLInputElement>(null);
  const collectionRef = useRef<HTMLInputElement>(null);
  const setOwnedFromImport = useCatalogStore((s) => s.setOwnedFromImport);
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);

  async function run(fn: () => Promise<void>) {
    setError(null); setOk(null);
    try { await fn(); } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  }
  async function onRecipes(f: File) { await run(async () => { await importRecipes(f); setOk(t("recipes.import_success")); }); }
  async function onCollection(f: File) {
    await run(async () => {
      const res = await importCollection(f);
      setOwnedFromImport(res.owned);
      setOk(t("paints.import_success", { count: res.owned.length }));
    });
  }

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
        <Button size="xs" variant="subtle" onClick={() => run(async () => triggerDownload(await exportCollection(), "collection.json"))}>
          {t("recipes.collection_export")}
        </Button>
        <Button size="xs" variant="subtle" onClick={() => collectionRef.current?.click()}>
          {t("recipes.collection_import")}
        </Button>
        <input ref={collectionRef} type="file" accept=".json" style={{ display: "none" }} data-kind="collection"
          onChange={(e) => { const f = e.target.files?.[0]; if (f) { onCollection(f); e.target.value = ""; } }} />
      </Group>
      {ok && <Text size="xs" c="green">{ok}</Text>}
      {error && <ErrorNotice message={t("errors.import")} detail={error} />}
    </Stack>
  );
}
