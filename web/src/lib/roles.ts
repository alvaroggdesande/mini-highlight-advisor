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

export function defaultCoverage(n: number): number[] {
  const weights = Array.from({ length: n }, (_, i) => n - i);
  const total = weights.reduce((a, b) => a + b, 0);
  return weights.map((w) => w / total);
}
