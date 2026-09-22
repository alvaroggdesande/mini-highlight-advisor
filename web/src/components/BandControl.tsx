import { useProjectStore, activeBookOf } from "../store/projectStore";

export function BandControl() {
  const book = useProjectStore(activeBookOf);
  const setBandCount = useProjectStore((s) => s.setBandCount);
  if (!book) return null;
  const cur = book.selected === 0 ? book.whole : book.drawn[book.selected - 1];
  return (
    <label>
      Bands: {cur.palette.length}
      <input type="range" min={1} max={8} value={cur.palette.length}
        onChange={(e) => setBandCount(Number(e.target.value))} />
    </label>
  );
}
