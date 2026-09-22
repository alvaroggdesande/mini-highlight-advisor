import { PhotoUploader } from "./components/PhotoUploader";
import { PreviewImage } from "./components/PreviewImage";
import { BandControl } from "./components/BandControl";
import { useAnalyze } from "./hooks/useAnalyze";

export default function App() {
  useAnalyze();
  return (
    <main style={{ maxWidth: 900, margin: "0 auto", padding: 16 }}>
      <h1>Mini Highlight Advisor</h1>
      <PhotoUploader />
      <BandControl />
      <PreviewImage />
    </main>
  );
}
