import { SchemeGenerator } from "./SchemeGenerator";
import { RampEditor } from "./RampEditor";
import { BandEditor } from "./BandEditor";
import { SchemeManager } from "./SchemeManager";

export function ColourPanel() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <SchemeGenerator />
      <RampEditor />
      <BandEditor />
      <SchemeManager />
    </div>
  );
}
