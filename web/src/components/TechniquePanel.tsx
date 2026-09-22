import { useTranslation } from "react-i18next";
import { useProjectStore, activeBookOf } from "../store/projectStore";

export function TechniquePanel() {
  const { t } = useTranslation();
  const selected = useProjectStore((s) => activeBookOf(s)?.selected ?? 0);
  const material = useProjectStore((s) => {
    const b = activeBookOf(s);
    if (!b) return "matte";
    return selected === 0 ? b.whole.material : (b.drawn[selected - 1]?.material ?? "matte");
  });
  const setMaterial = useProjectStore((s) => s.setMaterial);

  return (
    <div style={{ padding: 8 }}>
      <label>
        {t("technique.material")}
        {" "}
        <select value={material} onChange={(e) => setMaterial(selected, e.target.value)}>
          <option value="matte">{t("technique.matte")}</option>
          <option value="metallic">{t("technique.metallic")}</option>
        </select>
      </label>
    </div>
  );
}
