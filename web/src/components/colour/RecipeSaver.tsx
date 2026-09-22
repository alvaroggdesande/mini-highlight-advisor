import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useProjectStore, activeBookOf } from "../../store/projectStore";
import { saveRecipe } from "../../api/client";

interface Props { onSaved(): void; }

export function RecipeSaver({ onSaved }: Props) {
  const { t } = useTranslation();
  const book = useProjectStore((s) => activeBookOf(s));
  const [name, setName] = useState("");
  const [toast, setToast] = useState(false);

  if (!book) return null;

  const activeRegion = book.selected === 0 ? book.whole : book.drawn[book.selected - 1];
  const palette = activeRegion?.palette ?? [];

  const handleSave = async () => {
    if (!name.trim()) return;
    const steps = palette.map((p, i) => ({ label: `step ${i + 1}`, hex: p.hex, paint_ref: p.name !== "custom" ? p.name : null }));
    await saveRecipe({ name: name.trim(), steps });
    setToast(true);
    setName("");
    onSaved();
    setTimeout(() => setToast(false), 2000);
  };

  return (
    <div style={{ display: "flex", gap: 4, alignItems: "center", marginTop: 8 }}>
      <input type="text" value={name} placeholder={t("colour.recipe_name")}
        onChange={(e) => setName(e.target.value)} style={{ flex: 1 }} />
      <button onClick={handleSave} disabled={!name.trim()}>{t("colour.save_recipe")}</button>
      {toast && <span style={{ color: "green", fontSize: 12 }}>{t("colour.recipe_saved")}</span>}
    </div>
  );
}
