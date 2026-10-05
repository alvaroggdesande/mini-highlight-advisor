import { useEffect, useMemo, useState } from "react";
import { matchPaint } from "../api/client";
import type { MatchResult } from "../api/types";
import { useCatalogStore } from "../store/catalogStore";

/** Match `hex` against the owned collection (null hex = skip). Re-runs when the
 *  hex, finish or collection changes; `debounceMs` absorbs typing in a hex field. */
export function useMatch(hex: string | null, finish: string, debounceMs = 0) {
  const ownedCodes = useCatalogStore((s) => s.ownedCodes);
  const ownedList = useMemo(() => [...ownedCodes].sort(), [ownedCodes]);
  const ownedKey = ownedList.join(",");
  const [result, setResult] = useState<MatchResult | null>(null);

  useEffect(() => {
    if (!hex) { setResult(null); return; }
    let live = true;
    const timer = setTimeout(async () => {
      try {
        const r = await matchPaint({ hex, finish, owned_codes: ownedList });
        if (live) setResult(r);
      } catch { /* ignore */ }
    }, debounceMs);
    return () => { live = false; clearTimeout(timer); };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hex, finish, ownedKey, debounceMs]);

  return { result, hasOwned: ownedList.length > 0, ownedCodes };
}
