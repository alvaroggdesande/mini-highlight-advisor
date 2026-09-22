import { useProjectStore } from "../store/projectStore";

export function BandControl() {
  const whole = useProjectStore((s) => s.whole);
  const setBandCount = useProjectStore((s) => s.setBandCount);
  if (!whole) return null;
  return (
    <label>
      Bands: {whole.palette.length}
      <input type="range" min={1} max={8} value={whole.palette.length}
        onChange={(e) => setBandCount(Number(e.target.value))} />
    </label>
  );
}
