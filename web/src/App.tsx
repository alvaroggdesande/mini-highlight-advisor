import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { PhotoUploader } from "./components/PhotoUploader";
import { PreviewImage } from "./components/PreviewImage";
import { RegionSelector } from "./components/RegionSelector";
import { AngleBar } from "./components/AngleBar";
import { RightPanel } from "./components/RightPanel";
import { PaintTab } from "./components/PaintTab";
import { PaintsTab } from "./components/PaintsTab";
import { AnglesTab } from "./components/AnglesTab";
import { useAnalyze } from "./hooks/useAnalyze";
import { useProjectStore, activeAngleOf } from "./store/projectStore";
import { useCatalogStore } from "./store/catalogStore";
import { ProjectLibrary } from "./components/ProjectLibrary";

type MainTab = "studio" | "paint" | "paints" | "angles";

export default function App() {
  const { t } = useTranslation();
  useAnalyze();
  const hasAngle = useProjectStore((s) => s.angles.length > 0);
  const resultToken = useProjectStore((s) => activeAngleOf(s)?.resultToken);
  const fetchCatalog = useCatalogStore((s) => s.fetch);
  const [tab, setTab] = useState<MainTab>("studio");

  useEffect(() => {
    if (hasAngle) fetchCatalog();
  }, [hasAngle, fetchCatalog]);

  const loadCollection = useCatalogStore((s) => s.loadCollection);
  const catalogStatus = useCatalogStore((s) => s.status);
  useEffect(() => {
    if (catalogStatus === "ready") loadCollection();
  }, [catalogStatus, loadCollection]);

  const tabBtn = (id: MainTab, disabled = false): React.CSSProperties => ({
    padding: "6px 18px", marginRight: 4,
    background: "none", border: "none",
    borderBottom: tab === id ? "2px solid #eee" : "2px solid transparent",
    color: disabled ? "#555" : tab === id ? "#eee" : "#888",
    fontSize: 14, fontWeight: tab === id ? 600 : 400,
    cursor: disabled ? "default" : "pointer",
  });

  return (
    <main style={{ maxWidth: 1100, margin: "0 auto", padding: 16 }}>
      <h1>Mini Highlight Advisor</h1>
      <ProjectLibrary />
      {!hasAngle ? (
        <PhotoUploader />
      ) : (
        <>
          <AngleBar />
          <nav style={{ borderBottom: "1px solid #333", marginBottom: 16 }}>
            <button style={tabBtn("studio")} onClick={() => setTab("studio")}>
              {t("tabs.studio")}
            </button>
            <button
              style={tabBtn("paint", !resultToken)}
              onClick={() => { if (resultToken) setTab("paint"); }}
              disabled={!resultToken}
            >
              {t("tabs.paint")}
            </button>
            <button
              style={tabBtn("paints")}
              onClick={() => setTab("paints")}
            >
              {t("tabs.paints")}
            </button>
            <button
              style={tabBtn("angles")}
              onClick={() => setTab("angles")}
            >
              {t("tabs.angles")}
            </button>
          </nav>
          {tab === "studio" && (
            <div style={{ display: "flex", gap: 24, alignItems: "flex-start" }}>
              <div style={{ flex: "0 0 auto" }}>
                <PreviewImage />
              </div>
              <div style={{ flex: 1 }}>
                <RegionSelector />
                <RightPanel />
              </div>
            </div>
          )}
          {tab === "paint" && <PaintTab />}
          {tab === "paints" && <PaintsTab />}
          {tab === "angles" && <AnglesTab />}
        </>
      )}
    </main>
  );
}
