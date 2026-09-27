import { useState, useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import { Center, Loader, Tabs, Text } from "@mantine/core";
import { fetchSteps, fetchPlanNames, analyze, TokenExpiredError } from "../api/client";
import { useProjectStore, activeAngleOf } from "../store/projectStore";
import { StepList } from "./StepList";
import type { RegionPlanDto, RegionPayload, PlansManifest, StepsResponse } from "../api/types";

/** Re-run analyze for the active angle to mint a fresh result token (used when a
 *  cached token has expired after a worker restart). Returns the new token. */
async function reanalyze(
  setPreview: (png: string, token: string) => void,
): Promise<string> {
  const { angles, activeAngle } = useProjectStore.getState();
  const a = angles[activeAngle];
  if (!a?.photoId) throw new Error("no photo");
  const regions: RegionPayload[] = a.book.drawn
    .filter((r) => !r.blank && r.rings.length > 0)
    .map((r) => ({ name: r.name, rings: r.rings, palette: r.palette, coverage: r.coverage, material: r.material }));
  const res = await analyze({ photo_id: a.photoId, whole: a.book.whole, regions, settings: a.settings });
  setPreview(res.preview_png, res.result_token);
  return res.result_token;
}

export function PaintTab() {
  const { t } = useTranslation();
  const token = useProjectStore((s) => activeAngleOf(s)?.resultToken);
  const setPreview = useProjectStore((s) => s.setPreview);

  const [names, setNames] = useState<string[] | null>(null);
  const [active, setActive] = useState<string | null>(null);
  const [cache, setCache] = useState<Record<string, RegionPlanDto>>({});
  const [namesLoading, setNamesLoading] = useState(false);
  const [stepLoading, setStepLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const loadedNamesToken = useRef<string | undefined>(undefined);

  // Load the region manifest (names only) whenever the result token changes.
  useEffect(() => {
    if (!token) return;
    if (loadedNamesToken.current === token) return;
    let cancelled = false;

    async function load() {
      setNamesLoading(true); setError(null);
      try {
        let manifest: PlansManifest;
        try {
          manifest = await fetchPlanNames(token!);
        } catch (e) {
          if (!(e instanceof TokenExpiredError)) throw e;
          // Mint a fresh token; the token change re-fires this effect, which
          // reloads the manifest cleanly (no inline refetch to race with it).
          await reanalyze(setPreview);
          return;
        }
        if (cancelled) return;
        loadedNamesToken.current = token!;
        const ns = manifest.plans.map((p) => p.name);
        setNames(ns);
        setActive(ns[0] ?? null);
        setCache({});
      } catch (e) {
        if (!cancelled) setError(String(e));
      } finally {
        if (!cancelled) setNamesLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, [token]); // eslint-disable-line react-hooks/exhaustive-deps

  // Fetch the active region's step images on demand; cache so re-selecting is instant.
  useEffect(() => {
    if (!token || !active) return;
    if (cache[active]) return;
    let cancelled = false;

    async function load() {
      setStepLoading(true); setError(null);
      try {
        let resp: StepsResponse;
        try {
          resp = await fetchSteps(token!, active!);
        } catch (e) {
          if (!(e instanceof TokenExpiredError)) throw e;
          // Refresh the token; the change re-fires the manifest + this effect.
          await reanalyze(setPreview);
          return;
        }
        if (cancelled) return;
        const plan = resp.plans[0];
        if (plan) setCache((c) => ({ ...c, [active!]: plan }));
      } catch (e) {
        if (!cancelled) setError(String(e));
      } finally {
        if (!cancelled) setStepLoading(false);
      }
    }
    load();
    return () => { cancelled = true; };
  }, [token, active, cache, setPreview]);

  if (!token) return <Text c="dimmed">{t("paint.no_preview")}</Text>;
  if (namesLoading) return <Center mt="xl"><Loader size="sm" /></Center>;
  if (error) return <Text c="red">{error}</Text>;
  if (!names || names.length === 0) return null;

  return (
    <Tabs value={active} onChange={setActive} keepMounted={false}>
      <Tabs.List mb="md">
        {names.map((n) => <Tabs.Tab key={n} value={n}>{n}</Tabs.Tab>)}
      </Tabs.List>
      {names.map((n) => (
        <Tabs.Panel key={n} value={n}>
          {cache[n]
            ? <StepList plan={cache[n]} />
            : stepLoading
              ? <Center mt="xl"><Loader size="sm" /></Center>
              : null}
        </Tabs.Panel>
      ))}
    </Tabs>
  );
}
