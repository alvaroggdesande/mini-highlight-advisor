import { useEffect } from "react";
import { PhotoUploader } from "./components/PhotoUploader";
import { PreviewImage } from "./components/PreviewImage";
import { RegionSelector } from "./components/RegionSelector";
import { AngleBar } from "./components/AngleBar";
import { RightPanel } from "./components/RightPanel";
import { useAnalyze } from "./hooks/useAnalyze";
import { useProjectStore } from "./store/projectStore";
import { useCatalogStore } from "./store/catalogStore";

export default function App() {
  useAnalyze();
  const hasAngle = useProjectStore((s) => s.angles.length > 0);
  const fetchCatalog = useCatalogStore((s) => s.fetch);

  useEffect(() => {
    if (hasAngle) fetchCatalog();
  }, [hasAngle, fetchCatalog]);

  return (
    <main style={{ maxWidth: 1100, margin: "0 auto", padding: 16 }}>
      <h1>Mini Highlight Advisor</h1>
      {!hasAngle ? (
        <PhotoUploader />
      ) : (
        <>
          <AngleBar />
          <div style={{ display: "flex", gap: 24, alignItems: "flex-start" }}>
            <div style={{ flex: "0 0 auto" }}>
              <PreviewImage />
            </div>
            <div style={{ flex: 1 }}>
              <RegionSelector />
              <RightPanel />
            </div>
          </div>
        </>
      )}
    </main>
  );
}
