import { useEffect, useRef } from "react";
import { analyze } from "../api/client";
import { useProjectStore, activeAngleOf } from "../store/projectStore";
import type { RegionPayload } from "../api/types";
import { paletteHasValidHexes } from "../lib/color";

export function useAnalyze(delay = 150) {
  const angle = useProjectStore(activeAngleOf);
  const setPreview = useProjectStore((s) => s.setPreview);
  const setError = useProjectStore((s) => s.setError);
  const timer = useRef<ReturnType<typeof setTimeout>>(undefined);

  const photoId = angle?.photoId;
  const book = angle?.book;
  const settings = angle?.settings;

  useEffect(() => {
    if (!photoId || !book || !settings) return;
    clearTimeout(timer.current);
    timer.current = setTimeout(async () => {
      try {
        const regions: RegionPayload[] = book.drawn
          .filter((r) => !r.blank && r.rings.length > 0)
          .map((r) => ({ name: r.name, rings: r.rings, palette: r.palette,
                         coverage: r.coverage, material: r.material }));
        if (!paletteHasValidHexes(book.whole.palette)
            || regions.some((r) => !paletteHasValidHexes(r.palette))) {
          return;
        }
        const res = await analyze({ photo_id: photoId, whole: book.whole, regions, settings });
        setPreview(res.preview_png, res.result_token);
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      }
    }, delay);
    return () => clearTimeout(timer.current);
  }, [photoId, book, settings, delay, setPreview, setError]);
}
