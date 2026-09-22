import { useProjectStore, activeBookOf } from "../store/projectStore";
import { regionLabel } from "../lib/geometry";

export function RegionSelector() {
  const book = useProjectStore(activeBookOf);
  const setSelected = useProjectStore((s) => s.setSelected);
  const toggleBlank = useProjectStore((s) => s.toggleBlank);
  if (!book) return null;
  const names = ["Whole mini", ...book.drawn.map((r) => r.name)];
  return (
    <fieldset>
      <legend>Region</legend>
      {names.map((name, g) => (
        <div key={g}>
          <label>
            <input type="radio" name="region" checked={book.selected === g}
                   onChange={() => setSelected(g)} />
            {regionLabel(g, name)}
          </label>
          {g >= 1 && (
            <label style={{ marginLeft: 8, fontSize: "0.85em" }}>
              <input type="checkbox" checked={!book.drawn[g - 1].blank}
                     onChange={() => toggleBlank(g)} /> visible
            </label>
          )}
        </div>
      ))}
    </fieldset>
  );
}
