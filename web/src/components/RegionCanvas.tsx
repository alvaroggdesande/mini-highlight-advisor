import { useState } from "react";
import { Stage, Layer, Line, Image as KonvaImage } from "react-konva";
import useImage from "use-image";
import { useProjectStore, activeAngleOf, activeBookOf } from "../store/projectStore";
import { displaySize, toImageSpace, toDisplaySpace, decimate, REGION_COLORS, type Pt } from "../lib/geometry";

const DECIMATE_EPS = 1.5;

export function appendPoint(stroke: number[][], p: number[]): number[][] {
  return stroke.concat([p]);
}

interface Props {
  drawing: boolean;
  draftRings: number[][][];
  onDraftChange: (rings: number[][][]) => void;
}

export function RegionCanvas({ drawing, draftRings, onDraftChange }: Props) {
  const angle = useProjectStore(activeAngleOf);
  const book = useProjectStore(activeBookOf);
  const [live, setLive] = useState<Pt[]>([]);
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
    const p = pointerPt(e); if (p) setLive([p]);
  }
  function onMove(e: any) {
    if (!drawing || live.length === 0) return;
    const p = pointerPt(e); if (p) setLive((s) => appendPoint(s, p) as Pt[]);
  }
  function onUp() {
    if (!drawing || live.length < 3) { setLive([]); return; }
    const ring = decimate(live, DECIMATE_EPS).map((p) => toImageSpace(p, srcW, srcH, dispW, dispH));
    onDraftChange(draftRings.concat([ring]));
    setLive([]);
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
        {live.length > 1 && (
          <Line points={live.flatMap((p) => p)} stroke="#ff28c8" strokeWidth={2} dash={[6, 4]} />
        )}
      </Layer>
    </Stage>
  );
}
