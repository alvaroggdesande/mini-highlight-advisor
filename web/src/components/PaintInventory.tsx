import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useCatalogStore } from "../store/catalogStore";

export function PaintInventory() {
  const { t } = useTranslation();
  const paints = useCatalogStore((s) => s.paints);
  const ownedCodes = useCatalogStore((s) => s.ownedCodes);
  const status = useCatalogStore((s) => s.status);
  const toggleOwned = useCatalogStore((s) => s.toggleOwned);
  const [search, setSearch] = useState("");

  if (status !== "ready") {
    return <p style={{ color: "#888", fontSize: 13 }}>{t("paints.loading")}</p>;
  }

  const q = search.trim().toLowerCase();
  const filtered = q
    ? paints.filter(
        (p) =>
          p.name.toLowerCase().includes(q) ||
          (p.code ?? "").toLowerCase().includes(q) ||
          (p.paint_range ?? "").toLowerCase().includes(q),
      )
    : paints;

  const ownedCount = paints.filter((p) => ownedCodes.has(p.code ?? "")).length;

  return (
    <div>
      <input
        role="searchbox"
        type="search"
        placeholder={t("paints.search_placeholder")}
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        style={{
          width: "100%", padding: "6px 10px", marginBottom: 8, boxSizing: "border-box",
          background: "#1a1a1a", color: "#ddd", border: "1px solid #444",
          borderRadius: 4, fontSize: 13,
        }}
      />

      <div style={{ color: "#666", fontSize: 12, marginBottom: 8 }}>
        {t("paints.owned_count", { owned: ownedCount, total: paints.length })}
        {q && ` · ${filtered.length} ${t("paints.filtered_suffix")}`}
      </div>

      <div style={{ maxHeight: 420, overflowY: "auto" }}>
        {filtered.map((p) => {
          const code = p.code ?? "";
          const owned = ownedCodes.has(code);
          return (
            <label
              key={code || p.name}
              style={{
                display: "flex", alignItems: "center", gap: 8, padding: "4px 2px",
                cursor: "pointer", borderBottom: "1px solid #1e1e1e",
                opacity: owned ? 1 : 0.7,
              }}
            >
              <input
                type="checkbox"
                checked={owned}
                onChange={() => toggleOwned(code)}
                style={{ flexShrink: 0, cursor: "pointer" }}
              />
              <span
                style={{
                  display: "inline-block", width: 14, height: 14,
                  borderRadius: 3, background: p.hex, flexShrink: 0,
                  border: "1px solid #555",
                }}
              />
              <span style={{ flex: 1, fontSize: 13, color: owned ? "#ddd" : "#999" }}>
                {p.name}
              </span>
              {p.paint_range && (
                <span style={{ fontSize: 11, color: "#555", whiteSpace: "nowrap" }}>
                  {p.paint_range}
                </span>
              )}
              <span style={{ fontSize: 11, color: "#444", whiteSpace: "nowrap", fontFamily: "monospace" }}>
                {code}
              </span>
            </label>
          );
        })}
        {filtered.length === 0 && q && (
          <p style={{ color: "#555", fontSize: 13, padding: "8px 0" }}>
            {t("paints.no_results")}
          </p>
        )}
      </div>
    </div>
  );
}
