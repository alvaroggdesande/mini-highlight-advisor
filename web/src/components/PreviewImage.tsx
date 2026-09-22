import { useProjectStore, activeAngleOf } from "../store/projectStore";

export function PreviewImage() {
  const angle = useProjectStore(activeAngleOf);
  if (angle?.error) return <p role="alert" style={{ color: "crimson" }}>Analyze failed: {angle.error}</p>;
  if (!angle?.preview) return <p>Upload a photo or pick a sample to see the preview.</p>;
  return <img src={angle.preview} alt="painted preview" style={{ maxWidth: "100%" }} />;
}
