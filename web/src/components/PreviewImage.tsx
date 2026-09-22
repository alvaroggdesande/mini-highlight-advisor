import { useProjectStore } from "../store/projectStore";

export function PreviewImage() {
  const preview = useProjectStore((s) => s.preview);
  const error = useProjectStore((s) => s.error);
  if (error) return <p role="alert" style={{ color: "crimson" }}>Analyze failed: {error}</p>;
  if (!preview) return <p>Upload a photo or pick a sample to see the preview.</p>;
  return <img src={preview} alt="painted preview" style={{ maxWidth: "100%" }} />;
}
