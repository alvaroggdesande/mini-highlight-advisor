import { useState } from "react";
import { useProjectStore, activeBookOf } from "../store/projectStore";
import { RegionCanvas } from "./RegionCanvas";

export function ManagePanel() {
  const book = useProjectStore(activeBookOf);
  const addRegion = useProjectStore((s) => s.addRegion);
  const removeRegion = useProjectStore((s) => s.removeRegion);
  const renameRegion = useProjectStore((s) => s.renameRegion);
  const [drawing, setDrawing] = useState(false);
  const [draftRings, setDraftRings] = useState<number[][][]>([]);
  const [name, setName] = useState("");

  if (!book) return null;
  const sel = book.selected;
  const defaultName = `region ${book.drawn.length + 1}`;

  function commit() {
    if (draftRings.length === 0) return;
    addRegion(draftRings, name.trim() || defaultName);
    setDrawing(false); setDraftRings([]); setName("");
  }
  function cancel() { setDrawing(false); setDraftRings([]); setName(""); }

  return (
    <div>
      <RegionCanvas drawing={drawing} draftRings={draftRings} onDraftChange={setDraftRings} />
      {!drawing ? (
        <button onClick={() => setDrawing(true)}>Draw region</button>
      ) : (
        <div>
          <input placeholder={defaultName} value={name} onChange={(e) => setName(e.target.value)} />
          <button onClick={commit}>Add region</button>
          <button onClick={cancel}>Cancel</button>
          {draftRings.length > 0 && <span> {draftRings.length} stroke(s)</span>}
        </div>
      )}
      {!drawing && sel >= 1 && (
        <div>
          <input value={book.drawn[sel - 1].name}
                 onChange={(e) => renameRegion(sel, e.target.value)} />
          <button onClick={() => removeRegion(sel)}>Delete region</button>
        </div>
      )}
    </div>
  );
}
