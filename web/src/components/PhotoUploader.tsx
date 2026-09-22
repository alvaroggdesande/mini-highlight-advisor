import { useEffect, useState } from "react";
import { listSamplePhotos, samplePhotoBlob, uploadPhoto } from "../api/client";
import type { SamplePhoto } from "../api/types";
import { useProjectStore } from "../store/projectStore";

export function PhotoUploader() {
  const initFromPhoto = useProjectStore((s) => s.initFromPhoto);
  const setError = useProjectStore((s) => s.setError);
  const [samples, setSamples] = useState<SamplePhoto[]>([]);

  useEffect(() => { listSamplePhotos().then(setSamples).catch(() => setSamples([])); }, []);

  async function handleBlob(blob: Blob, name: string) {
    try { initFromPhoto(await uploadPhoto(blob, name)); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
  }

  return (
    <div>
      <input type="file" accept="image/png,image/jpeg" onChange={(e) => {
        const f = e.target.files?.[0]; if (f) handleBlob(f, f.name);
      }} />
      {samples.length > 0 && (
        <div>
          <p>Or start from a sample:</p>
          {samples.map((s) => (
            <button key={s.id} onClick={async () => {
              try {
                handleBlob(await samplePhotoBlob(s.id), `${s.id}.png`);
              } catch (e) {
                setError(e instanceof Error ? e.message : String(e));
              }
            }}>
              {s.name}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
