import { useState, useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import { fetchSteps, analyze, TokenExpiredError } from "../api/client";
import { useProjectStore, activeAngleOf } from "../store/projectStore";
import { StepList } from "./StepList";
import type { RegionPlanDto, RegionPayload } from "../api/types";

export function PaintTab() {
  const { t } = useTranslation();
  const token = useProjectStore((s) => activeAngleOf(s)?.resultToken);
  const setPreview = useProjectStore((s) => s.setPreview);
  const [plans, setPlans] = useState<RegionPlanDto[] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Track the last token for which plans were successfully loaded, to avoid
  // re-fetching after a retry that already updated the store token via setPreview.
  const lastLoadedToken = useRef<string | undefined>(undefined);

  useEffect(() => {
    if (!token) return;
    if (lastLoadedToken.current === token) return;
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const data = await fetchSteps(token!);
        if (!cancelled) {
          lastLoadedToken.current = token;
          setPlans(data.plans);
        }
      } catch (e) {
        if (cancelled) return;
        if (e instanceof TokenExpiredError) {
          // Cache evicted: re-analyze with current store state, then retry
          try {
            const { angles, activeAngle } = useProjectStore.getState();
            const a = angles[activeAngle];
            if (!a?.photoId) throw new Error("no photo");
            const regions: RegionPayload[] = a.book.drawn
              .filter((r) => !r.blank && r.rings.length > 0)
              .map((r) => ({
                name: r.name, rings: r.rings, palette: r.palette,
                coverage: r.coverage, material: r.material,
              }));
            const res = await analyze({
              photo_id: a.photoId,
              whole: a.book.whole,
              regions,
              settings: a.settings,
            });
            if (!cancelled) {
              const retry = await fetchSteps(res.result_token);
              if (!cancelled) {
                // Mark the new token as loaded before updating the store,
                // so the effect that fires for the new token bails out early.
                lastLoadedToken.current = res.result_token;
                setPlans(retry.plans);
                setPreview(res.preview_png, res.result_token);
              }
            }
          } catch (retryErr) {
            if (!cancelled) setError(String(retryErr));
          }
        } else {
          setError(String(e));
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => { cancelled = true; };
  }, [token]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!token) {
    return <p style={{ color: "#aaa" }}>{t("paint.no_preview")}</p>;
  }
  if (loading) {
    return <p style={{ color: "#aaa" }}>{t("paint.loading")}</p>;
  }
  if (error) {
    return <p style={{ color: "#e55" }}>{error}</p>;
  }
  if (!plans) return null;

  return <StepList plans={plans} />;
}
