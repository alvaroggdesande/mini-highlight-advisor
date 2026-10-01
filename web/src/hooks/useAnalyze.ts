import { useEffect, useRef } from "react";
import { analyze } from "../api/client";
import { useProjectStore, activeAngleOf } from "../store/projectStore";
import type { RegionPayload } from "../api/types";
import { paletteHasValidHexes } from "../lib/color";

export function useAnalyze(delay = 150) {
  const angle = useProjectStore(activeAngleOf);
  const setPreview = useProjectStore((s) => s.setPreview);
  const setError = useProjectStore((s) => s.setError);
  const setAnalyzing = useProjectStore((s) => s.setAnalyzing);
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);
  // Latest request number per angle id: only the newest response for an angle may
  // update it, and it is dropped if the user has switched to another angle meanwhile.
  const seq = useRef(0);
  const latest = useRef<Record<string, number>>({});

  const angleId = angle?.id;
  const photoId = angle?.photoId;
  const book = angle?.book;
  const settings = angle?.settings;
  const nonce = angle?.analyzeNonce ?? 0;

  useEffect(() => {
    if (!angleId || !photoId || !book || !settings) return;
    clearTimeout(timer.current);
    timer.current = setTimeout(async () => {
      const regions: RegionPayload[] = book.drawn
        .filter((r) => !r.blank && r.rings.length > 0)
        .map((r) => ({ name: r.name, rings: r.rings, palette: r.palette,
                       coverage: r.coverage, material: r.material }));
      if (!paletteHasValidHexes(book.whole.palette)
          || regions.some((r) => !paletteHasValidHexes(r.palette))) {
        return;
      }
      const mine = ++seq.current;
      latest.current[angleId] = mine;
      const isLatest = () => latest.current[angleId] === mine;
      const isActive = () => activeAngleOf(useProjectStore.getState())?.id === angleId;
      setAnalyzing(true, angleId);
      try {
        const res = await analyze({ photo_id: photoId, whole: book.whole, regions, settings });
        if (isLatest() && isActive()) setPreview(res.preview_png, res.result_token);
      } catch (e) {
        if (isLatest() && isActive()) setError(e instanceof Error ? e.message : String(e));
      } finally {
        if (isLatest()) setAnalyzing(false, angleId);
      }
    }, delay);
    return () => clearTimeout(timer.current);
  }, [angleId, photoId, book, settings, nonce, delay, setPreview, setError, setAnalyzing]);
}
