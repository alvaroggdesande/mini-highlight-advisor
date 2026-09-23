import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { exportCollection, importCollection } from "../api/client";
import { useCatalogStore } from "../store/catalogStore";
import { PaintInventory } from "./PaintInventory";

export function PaintsTab() {
  const { t } = useTranslation();
  const setOwnedFromImport = useCatalogStore((s) => s.setOwnedFromImport);
  const ownedCodes = useCatalogStore((s) => s.ownedCodes);
  const [importing, setImporting] = useState(false);
  const [message, setMessage] = useState<{ kind: "ok" | "err"; text: string } | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  async function handleExport() {
    const blob = await exportCollection();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "my_paints.json";
    a.click();
    URL.revokeObjectURL(url);
  }

  async function handleImport(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setImporting(true);
    setMessage(null);
    try {
      const res = await importCollection(file);
      setOwnedFromImport(res.owned);
      setMessage({ kind: "ok", text: t("paints.import_success", { count: res.owned.length }) });
    } catch (err) {
      setMessage({ kind: "err", text: t("paints.import_error", { err: String(err) }) });
    } finally {
      setImporting(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  return (
    <div style={{ padding: "0 4px" }}>
      <PaintInventory />

      <div style={{ marginTop: 16, paddingTop: 12, borderTop: "1px solid #2a2a2a" }}>
        <div style={{ color: "#888", fontSize: 12, marginBottom: 6 }}>
          {t("paints.manage_section")}
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {ownedCodes.size > 0 && (
            <button
              onClick={handleExport}
              style={{ padding: "4px 12px", fontSize: 13, cursor: "pointer" }}
            >
              {t("paints.export_btn")}
            </button>
          )}
          <button
            onClick={() => fileRef.current?.click()}
            disabled={importing}
            style={{ padding: "4px 12px", fontSize: 13, cursor: "pointer" }}
          >
            {importing ? t("paints.importing") : t("paints.import_btn")}
          </button>
          <input
            ref={fileRef}
            type="file"
            accept=".json"
            onChange={handleImport}
            style={{ display: "none" }}
          />
        </div>
        {message && (
          <div
            style={{
              marginTop: 8, fontSize: 13,
              color: message.kind === "ok" ? "#6c6" : "#f66",
            }}
          >
            {message.text}
          </div>
        )}
      </div>
    </div>
  );
}
