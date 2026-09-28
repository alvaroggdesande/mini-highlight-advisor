const _ROLES: Record<number, string[]> = {
  3: ["Shadow", "Base", "Highlight"],
  4: ["Shadow", "Base", "Midtone", "Highlight"],
  5: ["Shadow", "Base", "Midtone", "Highlight", "Bright Highlight"],
  6: ["Shadow", "Deep Base", "Base", "Midtone", "Highlight", "Bright Highlight"],
  7: ["Shadow", "Deep Base", "Base", "Midtone", "Upper Midtone", "Highlight", "Bright Highlight"],
};

export function roleNames(n: number): string[] {
  return _ROLES[n] ?? Array.from({ length: n }, (_, i) => `Layer ${i + 1}`);
}

// Maps English canonical role/step names (from backend) to their i18n keys.
export const ROLE_KEY: Record<string, string> = {
  "Shadow": "roles.shadow",
  "Deep Base": "roles.deep_base",
  "Base": "roles.base",
  "Midtone": "roles.midtone",
  "Upper Midtone": "roles.upper_midtone",
  "Highlight": "roles.highlight",
  "Bright Highlight": "roles.bright_highlight",
  "Edge Highlight": "roles.edge_highlight",
  "Extreme Edge Highlight": "roles.extreme_edge_highlight",
  "Recess Shade": "roles.recess_shade",
};

export function defaultCoverage(n: number): number[] {
  const weights = Array.from({ length: n }, (_, i) => n - i);
  const total = weights.reduce((a, b) => a + b, 0);
  return weights.map((w) => w / total);
}
