import { useTranslation } from "react-i18next";
import { useProjectStore } from "../../store/projectStore";

const _ROLES: Record<number, string[]> = {
  3: ["Shadow", "Base", "Highlight"],
  4: ["Shadow", "Base", "Midtone", "Highlight"],
  5: ["Shadow", "Base", "Midtone", "Highlight", "Bright Highlight"],
  6: ["Shadow", "Deep Base", "Base", "Midtone", "Highlight", "Bright Highlight"],
  7: ["Shadow", "Deep Base", "Base", "Midtone", "Upper Midtone", "Highlight", "Bright Highlight"],
};
function roleNames(n: number): string[] {
  return _ROLES[n] ?? Array.from({ length: n }, (_, i) => `Layer ${i + 1}`);
}
function defaultCoverage(n: number): number[] {
  const weights = Array.from({ length: n }, (_, i) => n - i);
  const total = weights.reduce((a, b) => a + b, 0);
  return weights.map((w) => w / total);
}

interface Props { g: number; n: number; coverage: number[]; }

export function CoverageEditor({ g, n, coverage }: Props) {
  const { t } = useTranslation();
  const setCoverage = useProjectStore((s) => s.setCoverage);
  const names = roleNames(n);

  const handleSlider = (i: number, raw: string) => {
    const val = Number(raw) / 100;
    const others = coverage.reduce((sum, v, j) => (j !== i && j !== n - 1 ? sum + v : sum), 0);
    const max = Math.max(0, 1 - others - 0.03);
    const clamped = Math.min(val, max);
    const newCov = coverage.slice();
    newCov[i] = clamped;
    const remainder = 1 - newCov.slice(0, n - 1).reduce((a, b) => a + b, 0);
    newCov[n - 1] = Math.max(0, remainder);
    setCoverage(newCov);
  };

  return (
    <div>
      {Array.from({ length: n - 1 }, (_, i) => (
        <div key={i} style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ minWidth: 120, fontSize: 12 }}>{names[i]}</span>
          <input
            type="range" min={0} max={100}
            value={Math.round((coverage[i] ?? 0) * 100)}
            onChange={(e) => handleSlider(i, e.target.value)}
            onMouseUp={() => { /* setCoverage is called on every change; mouseUp is a no-op */ }}
          />
          <span style={{ fontSize: 12, minWidth: 32 }}>
            {Math.round((coverage[i] ?? 0) * 100)}%
          </span>
        </div>
      ))}
      <div style={{ fontSize: 12, color: "#888" }}>
        {names[n - 1]}: {Math.round((coverage[n - 1] ?? 0) * 100)}% (auto)
      </div>
      <button onClick={() => setCoverage(defaultCoverage(n))} style={{ marginTop: 4 }}>
        {t("colour.reset_coverage")}
      </button>
    </div>
  );
}
