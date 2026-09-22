import { useEffect, useRef } from "react";
import { analyze } from "../api/client";
import { useProjectStore } from "../store/projectStore";

export function useAnalyze(delay = 150) {
  const { photoId, whole, settings, setPreview, setError } = useProjectStore();
  const timer = useRef<ReturnType<typeof setTimeout>>();
  useEffect(() => {
    if (!photoId || !whole) return;
    clearTimeout(timer.current);
    timer.current = setTimeout(async () => {
      try {
        const res = await analyze({ photo_id: photoId, whole, settings });
        setPreview(res.preview_png, res.result_token);
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      }
    }, delay);
    return () => clearTimeout(timer.current);
  }, [photoId, whole, settings, delay, setPreview, setError]);
}
