import { PhotoUploader } from "./components/PhotoUploader";
import { PreviewImage } from "./components/PreviewImage";
import { BandControl } from "./components/BandControl";
import { useAnalyze } from "./hooks/useAnalyze";
import { useProjectStore } from "./store/projectStore";

export default function App() {
  useAnalyze();
  const hasAngle = useProjectStore((s) => s.angles.length > 0);
  return (
    <main style={{ maxWidth: 900, margin: "0 auto", padding: 16 }}>
      <h1>Mini Highlight Advisor</h1>
      {!hasAngle ? <PhotoUploader /> : (<><BandControl /><PreviewImage /></>)}
    </main>
  );
}
