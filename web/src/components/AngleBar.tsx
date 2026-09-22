import { useProjectStore } from "../store/projectStore";
import { uploadPhoto } from "../api/client";

export function AngleBar() {
  const angles = useProjectStore((s) => s.angles);
  const active = useProjectStore((s) => s.activeAngle);
  const addAngle = useProjectStore((s) => s.addAngle);
  const switchAngle = useProjectStore((s) => s.switchAngle);
  const renameAngle = useProjectStore((s) => s.renameAngle);
  const removeAngle = useProjectStore((s) => s.removeAngle);
  const setError = useProjectStore((s) => s.setError);
  if (angles.length === 0) return null;

  async function onAdd(file: File) {
    try { addAngle(await uploadPhoto(file, file.name)); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  }

  return (
    <div>
      <strong>Angles</strong>
      <div style={{ display: "flex", gap: 8 }}>
        {angles.map((a, i) => (
          <button key={a.id} onClick={() => switchAngle(i)}
                  style={{ fontWeight: i === active ? "bold" : "normal" }}>{a.label}</button>
        ))}
      </div>
      <input value={angles[active].label} onChange={(e) => renameAngle(active, e.target.value)} />
      <button disabled={angles.length === 1} onClick={() => removeAngle(active)}>Remove angle</button>
      <label> Add angle:
        <input type="file" accept="image/png,image/jpeg" onChange={(e) => {
          const f = e.target.files?.[0]; if (f) onAdd(f);
        }} />
      </label>
    </div>
  );
}
