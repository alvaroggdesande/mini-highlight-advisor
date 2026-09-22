import { useState, useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import { useProjectStore } from "../../store/projectStore";
import { useCatalogStore } from "../../store/catalogStore";
import { matchPaint, generateRamp } from "../../api/client";
import type { PaintColor, MatchResult } from "../../api/types";

interface BandSlotProps {
  g: number;
  i: number;
  paint: PaintColor;
  finish: string;
  n: number;
  palette: PaintColor[];
}

function matchPhrase(result: MatchResult): string {
  if (result.tier === "exact") return `✓ ${result.name ?? ""}`;
  if (result.tier === "close") return `≈ ${result.name ?? ""}`;
  if (result.tier === "mix") return result.phrase;
  return `Buy: ${result.name ?? ""}`;
}

export function BandSlot({ g, i, paint, finish, n, palette }: BandSlotProps) {
  const { t } = useTranslation();
  const catalogPaints = useCatalogStore((s) => s.paints);
  const setPaletteSlot = useProjectStore((s) => s.setPaletteSlot);
  const setHexSlot = useProjectStore((s) => s.setHexSlot);
  const setBandCount = useProjectStore((s) => s.setBandCount);

  const isCustom = !paint.code;
  const [matchResult, setMatchResult] = useState<MatchResult | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Debounced match on hex change (custom mode only)
  useEffect(() => {
    if (!isCustom) { setMatchResult(null); return; }
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      try {
        const res = await matchPaint({ hex: paint.hex, finish, owned_codes: [] });
        setMatchResult(res);
      } catch { /* ignore */ }
    }, 400);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [paint.hex, isCustom, finish]);

  const handleCatalogChange = (code: string) => {
    if (code === "__custom__") {
      setHexSlot(g, i, paint.hex);
    } else {
      const found = catalogPaints.find((p) => p.code === code);
      if (found) setPaletteSlot(g, i, found);
    }
  };

  const handleBlend = async () => {
    const left = palette[i - 1];
    const right = palette[i + 1];
    if (!left || !right) return;
    try {
      const res = await generateRamp({
        n: 1, variant: "ramp",
        blend_hexes: [left.hex, right.hex],
      });
      if (res.hexes[0]) setHexSlot(g, i, res.hexes[0]);
    } catch { /* ignore */ }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4, padding: "4px 0", borderBottom: "1px solid #ccc" }}>
      <div style={{ display: "flex", gap: 4, alignItems: "center" }}>
        <div style={{ width: 24, height: 24, background: paint.hex, border: "1px solid #888", flexShrink: 0 }} />

        {isCustom ? (
          <>
            <input type="color" value={paint.hex} onChange={(e) => setHexSlot(g, i, e.target.value)} />
            <input type="text" value={paint.hex} style={{ width: 72 }}
              onChange={(e) => setHexSlot(g, i, e.target.value)} />
          </>
        ) : (
          <select value={paint.code} onChange={(e) => handleCatalogChange(e.target.value)} style={{ flex: 1 }}>
            {catalogPaints.map((p) => (
              <option key={p.code} value={p.code}>{p.code} — {p.name}</option>
            ))}
            <option value="__custom__">{t("colour.custom")}</option>
          </select>
        )}

        {i > 0 && i < n - 1 && (
          <button onClick={handleBlend} title={t("colour.blend")}>↕</button>
        )}
        <button
          onClick={() => { if (n > 3) setBandCount(n - 1); }}
          disabled={n <= 3}
          title={t("colour.delete_band")}
        >
          ✕
        </button>
        <button
          onClick={() => {
            if (n < 7) {
              setBandCount(n + 1);
              setHexSlot(g, n, palette[n - 1]?.hex ?? "#808080");
            }
          }}
          disabled={n >= 7}
          title={t("colour.add_band")}
        >
          ＋
        </button>
      </div>

      {isCustom && matchResult && (
        <div style={{ fontSize: 12, color: "#888", paddingLeft: 28 }}>
          {matchPhrase(matchResult)}
        </div>
      )}
    </div>
  );
}
