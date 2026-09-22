import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { useProjectStore, activeBookOf } from "../../store/projectStore";
import { useCatalogStore } from "../../store/catalogStore";
import { generateScheme } from "../../api/client";
import { MOODS, VARIANTS, SURFACES } from "../../api/types";
import type { RegionColorSpec } from "../../api/types";

export function SchemeGenerator() {
  const { t } = useTranslation();
  const book = useProjectStore((s) => activeBookOf(s));
  const catalogPaints = useCatalogStore((s) => s.paints);
  const setPaletteAt = useProjectStore((s) => s.setPaletteAt);
  const setHeroHex = useProjectStore((s) => s.setHeroHex);
  const setMood = useProjectStore((s) => s.setMood);
  const setVariant = useProjectStore((s) => s.setVariant);
  const setSurface = useProjectStore((s) => s.setSurface);
  const setTone = useProjectStore((s) => s.setTone);

  const regionCount = book ? 1 + book.drawn.length : 1;

  const [anchorIndex, setAnchorIndex] = useState(0);
  const [heroHex, setHeroHexLocal] = useState(() => book?.hero_hex ?? "#c0392b");
  const [mood, setMoodLocal] = useState(() => book?.mood ?? "neutral");
  const [variant, setVariantLocal] = useState(() => book?.variant ?? "complementary");
  const [perRegion, setPerRegion] = useState<{ surface: string; tone: string }[]>(() =>
    Array.from({ length: regionCount }, (_, i) => ({
      surface: i === 0 ? (book?.whole.surface ?? "skin") : (book?.drawn[i - 1]?.surface ?? "skin"),
      tone: i === 0 ? (book?.whole.tone ?? "") : (book?.drawn[i - 1]?.tone ?? ""),
    }))
  );
  const [ownedOnly, setOwnedOnly] = useState(false);
  const [loading, setLoading] = useState(false);

  // Grow perRegion if drawn regions were added after mount
  useEffect(() => {
    if (!book) return;
    const needed = 1 + book.drawn.length;
    if (perRegion.length < needed) {
      setPerRegion((prev) => [
        ...prev,
        ...Array.from({ length: needed - prev.length }, (_, i) => {
          const di = prev.length - 1 + i;
          return { surface: book.drawn[di]?.surface ?? "skin", tone: book.drawn[di]?.tone ?? "" };
        }),
      ]);
    }
  }, [book?.drawn.length]);

  if (!book) return null;

  const regionNames = ["Whole Mini", ...book.drawn.map((r) => r.name)];
  const ownedCodes = ownedOnly ? catalogPaints.map((p) => p.code ?? "").filter(Boolean) : [];

  const handleGenerate = async () => {
    setLoading(true);
    try {
      const anchorName = regionNames[anchorIndex] ?? "Whole Mini";
      const specs: RegionColorSpec[] = regionNames.map((name, i) => ({
        region_name: name,
        surface: perRegion[i]?.surface ?? "skin",
        tone: perRegion[i]?.tone || undefined,
        n_bands: i === 0 ? book.whole.palette.length : book.drawn[i - 1].palette.length,
        is_anchor: i === anchorIndex,
      }));
      const res = await generateScheme({
        specs,
        anchor_name: anchorName,
        anchor_hex: heroHex,
        mood,
        variant,
        owned_codes: ownedCodes,
      });
      regionNames.forEach((name, i) => {
        const pal = res.palettes[name];
        if (pal) setPaletteAt(i, pal);
      });
      setHeroHex(heroHex);
      setMood(mood);
      setVariant(variant);
      regionNames.forEach((_, i) => {
        setSurface(i, perRegion[i]?.surface ?? "skin");
        if (perRegion[i]?.tone) setTone(i, perRegion[i].tone);
      });
    } finally {
      setLoading(false);
    }
  };

  const updatePerRegion = (i: number, field: "surface" | "tone", value: string) =>
    setPerRegion((prev) => prev.map((r, j) => j === i ? { ...r, [field]: value } : r));

  return (
    <section>
      <h4 style={{ margin: "0 0 8px" }}>{t("colour.scheme_generator")}</h4>

      <label>
        {t("colour.anchor_region")}:{" "}
        <select value={anchorIndex} onChange={(e) => setAnchorIndex(Number(e.target.value))}>
          {regionNames.map((name, i) => <option key={i} value={i}>{name}</option>)}
        </select>
      </label>

      <br />
      <label>
        {t("colour.hero_colour")}:{" "}
        <input type="color" value={heroHex} onChange={(e) => setHeroHexLocal(e.target.value)} />
        <input type="text" value={heroHex} style={{ width: 80, marginLeft: 4 }}
          onChange={(e) => setHeroHexLocal(e.target.value)} />
      </label>

      <br />
      <label>
        {t("colour.mood")}:{" "}
        <select value={mood} onChange={(e) => setMoodLocal(e.target.value)}>
          {MOODS.map((m) => <option key={m} value={m}>{t(`moods.${m}`)}</option>)}
        </select>
      </label>

      <br />
      <label>
        {t("colour.harmony")}:{" "}
        <select value={variant} onChange={(e) => setVariantLocal(e.target.value)}>
          {VARIANTS.map((v) => <option key={v} value={v}>{t(`variants.${v}`)}</option>)}
        </select>
      </label>

      <div style={{ marginTop: 8 }}>
        {regionNames.map((name, i) => (
          <div key={i} style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 4 }}>
            <span style={{ minWidth: 80 }}>{name}</span>
            <select value={perRegion[i]?.surface ?? "skin"}
              onChange={(e) => updatePerRegion(i, "surface", e.target.value)}>
              {SURFACES.map((s) => <option key={s} value={s}>{t(`surfaces.${s}`)}</option>)}
            </select>
            <input type="text" placeholder={t("colour.tone")} value={perRegion[i]?.tone ?? ""}
              style={{ width: 100 }}
              onChange={(e) => updatePerRegion(i, "tone", e.target.value)} />
          </div>
        ))}
      </div>

      <label>
        <input type="checkbox" checked={ownedOnly} onChange={(e) => setOwnedOnly(e.target.checked)} />
        {" "}{t("colour.owned_only")}
      </label>

      <br />
      <button onClick={handleGenerate} disabled={loading} style={{ marginTop: 8 }}>
        {loading ? t("colour.generating") : t("colour.generate")}
      </button>
    </section>
  );
}
