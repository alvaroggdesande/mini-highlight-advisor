import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { analyze } from "../api/client";
import { useProjectStore } from "../store/projectStore";
import type { AnalyzeRequest } from "../api/types";
import type { Angle } from "../store/projectStore";

const COLS = 3;

function buildRequest(angle: Angle): AnalyzeRequest {
  return {
    photo_id: angle.photoId,
    whole: angle.book.whole,
    regions: angle.book.drawn
      .filter((r) => !r.blank)
      .map((r) => ({
        name: r.name,
        rings: r.rings,
        palette: r.palette,
        coverage: r.coverage,
        material: r.material,
      })),
    settings: angle.settings,
  };
}

type PreviewState = string | null | "error";  // data URI | loading | error

export function AngleGallery() {
  const { t } = useTranslation();
  const angles = useProjectStore((s) => s.angles);
  const activeAngle = useProjectStore((s) => s.activeAngle);

  // Seed initial previews from store (active angle already has one from useAnalyze)
  const [previews, setPreviews] = useState<Record<string, PreviewState>>(() => {
    const init: Record<string, PreviewState> = {};
    for (const a of angles) {
      init[a.id] = a.preview ?? null;
    }
    return init;
  });

  useEffect(() => {
    let cancelled = false;

    // Merge: preserve existing local previews; only seed null for new/missing IDs
    setPreviews((prev) => {
      const next: Record<string, PreviewState> = {};
      for (const a of angles) {
        next[a.id] = a.preview ?? prev[a.id] ?? null;
      }
      return next;
    });

    for (const angle of angles) {
      if (angle.preview) continue;
      if (!angle.photoId) continue;

      analyze(buildRequest(angle))
        .then((res) => {
          if (!cancelled) {
            setPreviews((prev) => {
              const existing = prev[angle.id];
              if (existing && existing !== "error") return prev; // don't overwrite a good preview
              return { ...prev, [angle.id]: res.preview_png };
            });
          }
        })
        .catch(() => {
          if (!cancelled) {
            setPreviews((p) => ({ ...p, [angle.id]: "error" }));
          }
        });
    }

    return () => { cancelled = true; };
  }, [angles]);

  if (angles.length === 0) {
    return (
      <p style={{ color: "#888", fontSize: 14 }}>{t("gallery.no_angles")}</p>
    );
  }

  const rows: Angle[][] = [];
  for (let i = 0; i < angles.length; i += COLS) {
    rows.push(angles.slice(i, i + COLS));
  }

  return (
    <div>
      <h3 style={{ color: "#ccc", fontWeight: 500, marginBottom: 4 }}>{t("gallery.heading")}</h3>
      <p style={{ color: "#777", fontSize: 12, marginBottom: 16 }}>{t("gallery.caption")}</p>
      {rows.map((row, ri) => (
        <div
          key={ri}
          style={{ display: "grid", gridTemplateColumns: `repeat(${COLS}, 1fr)`, gap: 16, marginBottom: 16 }}
        >
          {row.map((angle, ci) => {
            const idx = ri * COLS + ci;
            const preview = previews[angle.id];
            const isActive = angle.id === angles[activeAngle]?.id;

            return (
              <div
                key={angle.id}
                style={{
                  background: "#111", borderRadius: 6, overflow: "hidden",
                  border: isActive ? "2px solid #888" : "2px solid #222",
                }}
              >
                <div>
                  {!angle.photoId ? (
                    <div
                      style={{
                        height: 160, display: "flex", alignItems: "center",
                        justifyContent: "center", color: "#555", fontSize: 13,
                      }}
                    >
                      {t("gallery.no_photo")}
                    </div>
                  ) : preview === null ? (
                    <div
                      style={{
                        height: 160, display: "flex", alignItems: "center",
                        justifyContent: "center", color: "#555", fontSize: 13,
                      }}
                    >
                      {t("gallery.loading")}
                    </div>
                  ) : preview === "error" ? (
                    <div
                      style={{
                        height: 160, display: "flex", alignItems: "center",
                        justifyContent: "center", color: "#844", fontSize: 13,
                      }}
                    >
                      {t("gallery.preview_error")}
                    </div>
                  ) : (
                    <img
                      src={preview}
                      alt={angle.label}
                      style={{ width: "100%", display: "block", objectFit: "contain" }}
                    />
                  )}
                </div>
                <div style={{ padding: "6px 8px", display: "flex", alignItems: "center", gap: 6 }}>
                  <span style={{ flex: 1, fontSize: 13, color: "#ccc", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {angle.label}
                  </span>
                  {isActive && (
                    <span style={{ fontSize: 11, color: "#888", whiteSpace: "nowrap" }}>
                      {t("gallery.active_badge")}
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      ))}
    </div>
  );
}
