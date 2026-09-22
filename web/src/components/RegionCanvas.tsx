import { useRef } from "react";
import { Stage, Layer, Line, Image as KonvaImage } from "react-konva";
import useImage from "use-image";
import { useProjectStore, activeAngleOf, activeBookOf } from "../store/projectStore";
import { displaySize, toImageSpace, toDisplaySpace, decimate, REGION_COLORS, type Pt } from "../lib/geometry";

const DECIMATE_EPS = 1.5;

interface Props {
  drawing: boolean;
  draftRings: number[][][];
  onDraftChange: (rings: number[][][]) => void;
}

export function RegionCanvas({ drawing, draftRings, onDraftChange }: Props) {
  const angle = useProjectStore(activeAngleOf);
  const book = useProjectStore(activeBookOf);
  const stroke = useRef<Pt[]>([]);
  const [image] = useImage(angle?.photoId ? `/api/photo/${angle.photoId}/image` : "");

  if (!angle || !book || !angle.width || !angle.height) return null;
  const srcW = angle.width, srcH = angle.height;
  const { dispW, dispH } = displaySize(srcW, srcH);
  const toDisp = (p: number[]): number[] => toDisplaySpace(p as Pt, srcW, srcH, dispW, dispH);
  const flat = (ring: number[][]): number[] => ring.flatMap((p) => toDisp(p));

  function pointerPt(e: any): Pt | null {
    const pos = e.target.getStage().getPointerPosition();
    return pos ? [pos.x, pos.y] : null;
  }
  function onDown(e: any) {
    if (!drawing) return;
    const p = pointerPt(e); if (p) stroke.current = [p];
  }
  function onMove(e: any) {
    if (!drawing || stroke.current.length === 0) return;
    const p = pointerPt(e); if (p) stroke.current = stroke.current.concat([p]);
  }
  function onUp() {
    if (!drawing || stroke.current.length < 3) { stroke.current = []; return; }
    const ring = decimate(stroke.current, DECIMATE_EPS).map((p) => toImageSpace(p, srcW, srcH, dispW, dispH));
    onDraftChange(draftRings.concat([ring]));
    stroke.current = [];
  }

  return (
    <Stage width={dispW} height={dispH} onMouseDown={onDown} onMouseMove={onMove} onMouseUp={onUp}
           onTouchStart={onDown} onTouchMove={onMove} onTouchEnd={onUp}>
      <Layer listening={false}>
        {image && <KonvaImage image={image} width={dispW} height={dispH} />}
      </Layer>
      <Layer>
        {book.drawn.map((r, i) =>
          r.rings.map((ring, j) => (
            <Line key={`${r.id}-${j}`} points={flat(ring)} closed
                  stroke={REGION_COLORS[i % REGION_COLORS.length]}
                  strokeWidth={i + 1 === book.selected ? 3 : 1.5}
                  opacity={r.blank ? 0.3 : 1} />
          )))}
        {draftRings.map((ring, j) => (
          <Line key={`draft-${j}`} points={flat(ring)} closed stroke="#ff28c8" strokeWidth={2}
                dash={[6, 4]} fill="rgba(255,40,200,0.15)" />
        ))}
      </Layer>
    </Stage>
  );
}
