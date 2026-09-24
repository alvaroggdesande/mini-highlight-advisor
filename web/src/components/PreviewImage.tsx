import { useProjectStore, activeAngleOf } from "../store/projectStore";

export function PreviewImage() {
  const angle = useProjectStore(activeAngleOf);
  if (!angle?.preview) return <p>Upload a photo or pick a sample to see the preview.</p>;
  return (
    <>
      {angle.error && <p role="alert" style={{ color: "crimson" }}>Analyze failed: {angle.error}</p>}
      <img src={angle.preview} alt="painted preview" style={{ maxWidth: "100%" }} />
    </>
  );
}
