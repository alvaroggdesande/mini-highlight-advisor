import { useRef } from "react";
import { useTranslation } from "react-i18next";
import { exportRecipes, importRecipes, exportCollection, importCollection } from "../../api/client";

function triggerDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url; a.download = filename; a.click();
  URL.revokeObjectURL(url);
}

export function RecipeManager() {
  const { t } = useTranslation();
  const recipeImportRef = useRef<HTMLInputElement>(null);
  const collectionImportRef = useRef<HTMLInputElement>(null);

  const handleExportRecipes = async () => {
    const blob = await exportRecipes();
    triggerDownload(blob, "recipes.json");
  };

  const handleImportRecipes = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    await importRecipes(file);
    e.target.value = "";
  };

  const handleExportCollection = async () => {
    const blob = await exportCollection();
    triggerDownload(blob, "collection.json");
  };

  const handleImportCollection = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    await importCollection(file);
    e.target.value = "";
  };

  return (
    <section>
      <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
        <button onClick={handleExportRecipes}>{t("recipes.export")}</button>
        <button onClick={() => recipeImportRef.current?.click()}>{t("recipes.import")}</button>
        <input ref={recipeImportRef} type="file" accept=".json" style={{ display: "none" }}
          onChange={handleImportRecipes} />
        <button onClick={handleExportCollection}>{t("recipes.collection_export")}</button>
        <button onClick={() => collectionImportRef.current?.click()}>{t("recipes.collection_import")}</button>
        <input ref={collectionImportRef} type="file" accept=".json" style={{ display: "none" }}
          onChange={handleImportCollection} />
      </div>
    </section>
  );
}
