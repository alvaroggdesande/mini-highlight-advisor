import { PhotoUploader } from "./components/PhotoUploader";
import { PreviewImage } from "./components/PreviewImage";
import { BandControl } from "./components/BandControl";
import { RegionSelector } from "./components/RegionSelector";
import { ManagePanel } from "./components/ManagePanel";
import { AngleBar } from "./components/AngleBar";
import { useAnalyze } from "./hooks/useAnalyze";
import { useProjectStore } from "./store/projectStore";

export default function App() {
  useAnalyze();
  const hasAngle = useProjectStore((s) => s.angles.length > 0);
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
              <ManagePanel />
              <BandControl />
            </div>
          </div>
        </>
      )}
    </main>
  );
}
