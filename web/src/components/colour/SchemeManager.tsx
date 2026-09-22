import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useProjectStore, activeBookOf } from "../../store/projectStore";

export function SchemeManager() {
  const { t } = useTranslation();
  const schemes = useProjectStore((s) => activeBookOf(s)?.schemes ?? []);
  const saveScheme = useProjectStore((s) => s.saveScheme);
  const applyScheme = useProjectStore((s) => s.applyScheme);
  const deleteScheme = useProjectStore((s) => s.deleteScheme);
  const [name, setName] = useState("");

  return (
    <section>
      <h4 style={{ margin: "0 0 8px" }}>{t("schemes.title")}</h4>
      <div style={{ display: "flex", gap: 4 }}>
        <input type="text" value={name} placeholder={t("schemes.name_placeholder")}
          onChange={(e) => setName(e.target.value)} style={{ flex: 1 }} />
        <button onClick={() => { if (name.trim()) { saveScheme(name.trim()); setName(""); } }}
          disabled={!name.trim()}>
          {t("schemes.save")}
        </button>
      </div>
      <ul style={{ listStyle: "none", padding: 0, margin: "8px 0 0" }}>
        {schemes.map((sc) => (
          <li key={sc.id} style={{ display: "flex", gap: 4, alignItems: "center", marginBottom: 4 }}>
            <span style={{ flex: 1 }}>{sc.name}</span>
            <button onClick={() => applyScheme(sc.id)}>{t("schemes.apply")}</button>
            <button onClick={() => deleteScheme(sc.id)}>{t("schemes.delete")}</button>
          </li>
        ))}
      </ul>
    </section>
  );
}
