import { GeneratePanel } from "./GeneratePanel";
import { RampEditor } from "./RampEditor";
import { BandEditor } from "./BandEditor";
import { SchemeManager } from "./SchemeManager";
import { RecipeManager } from "./RecipeManager";

export function ColourPanel() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <GeneratePanel />
      <RampEditor />
      <BandEditor />
      <SchemeManager />
      <RecipeManager />
    </div>
  );
}
