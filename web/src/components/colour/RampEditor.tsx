import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useProjectStore, activeBookOf } from "../../store/projectStore";
import { generateRamp } from "../../api/client";
import { RAMP_VARIANTS } from "../../api/types";

export function RampEditor() {
  const { t } = useTranslation();
  const book = useProjectStore((s) => activeBookOf(s));
  const setHexSlot = useProjectStore((s) => s.setHexSlot);
  const setRampState = useProjectStore((s) => s.setRampState);

  const activeRegion = book
    ? book.selected === 0 ? book.whole : book.drawn[book.selected - 1]
    : null;

  const seedHex = activeRegion?.ramp_midtone
    ?? activeRegion?.palette[Math.floor((activeRegion.palette.length) / 2)]?.hex
    ?? "#808080";

  const [midtoneHex, setMidtoneHex] = useState(seedHex);
  const [loading, setLoading] = useState<string | null>(null);

  if (!book || !activeRegion) return null;

  const g = book.selected;
  const n = activeRegion.palette.length;

  const handleVariant = async (variant: string) => {
    setLoading(variant);
    try {
      const res = await generateRamp({ midtone_hex: midtoneHex, n, variant });
      res.hexes.forEach((hex, i) => setHexSlot(g, i, hex));
      setRampState(g, midtoneHex, variant);
    } finally {
      setLoading(null);
    }
  };

  return (
    <section>
      <h4 style={{ margin: "0 0 8px" }}>{t("colour.ramp_editor")}</h4>
      <label>
        {t("colour.midtone")}:{" "}
        <input type="color" value={midtoneHex} onChange={(e) => setMidtoneHex(e.target.value)} />
        <input type="text" value={midtoneHex} style={{ width: 80, marginLeft: 4 }}
          onChange={(e) => setMidtoneHex(e.target.value)} />
      </label>

      {book.hero_hex && (
        <>
          {" "}
          <button onClick={() => setMidtoneHex(book.hero_hex!)}
            style={{ marginLeft: 8 }}>
            {t("colour.use_scheme_colour")}
          </button>
        </>
      )}

      <div style={{ display: "flex", gap: 4, marginTop: 8 }}>
        {RAMP_VARIANTS.map((variant) => (
          <button
            key={variant}
            onClick={() => handleVariant(variant)}
            disabled={loading !== null}
          >
            {loading === variant ? "…" : t(`colour.${variant}`)}
          </button>
        ))}
      </div>
    </section>
  );
}
