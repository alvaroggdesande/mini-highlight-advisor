import { useRef } from "react";
import { useTranslation } from "react-i18next";
import { Button, Group } from "@mantine/core";
import { exportRecipes, importRecipes, exportCollection, importCollection } from "../../api/client";

function triggerDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a"); a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
}

export function RecipeManager() {
  const { t } = useTranslation();
  const recipeRef = useRef<HTMLInputElement>(null);
  const collectionRef = useRef<HTMLInputElement>(null);

  return (
    <Group gap="xs" wrap="wrap">
      <Button size="xs" variant="subtle" onClick={async () => triggerDownload(await exportRecipes(), "recipes.json")}>
        {t("recipes.export")}
      </Button>
      <Button size="xs" variant="subtle" onClick={() => recipeRef.current?.click()}>
        {t("recipes.import")}
      </Button>
      <input ref={recipeRef} type="file" accept=".json" style={{ display: "none" }}
        onChange={async (e) => { const f = e.target.files?.[0]; if (f) { await importRecipes(f); e.target.value = ""; } }} />
      <Button size="xs" variant="subtle" onClick={async () => triggerDownload(await exportCollection(), "collection.json")}>
        {t("recipes.collection_export")}
      </Button>
      <Button size="xs" variant="subtle" onClick={() => collectionRef.current?.click()}>
        {t("recipes.collection_import")}
      </Button>
      <input ref={collectionRef} type="file" accept=".json" style={{ display: "none" }}
        onChange={async (e) => { const f = e.target.files?.[0]; if (f) { await importCollection(f); e.target.value = ""; } }} />
    </Group>
  );
}
