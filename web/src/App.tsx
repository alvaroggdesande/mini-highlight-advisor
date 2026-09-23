import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { Container, Group, Tabs, Title } from "@mantine/core";
import { PhotoUploader } from "./components/PhotoUploader";
import { StudioPanel } from "./components/StudioPanel";
import { AngleBar } from "./components/AngleBar";
import { PaintTab } from "./components/PaintTab";
import { PaintsTab } from "./components/PaintsTab";
import { AnglesTab } from "./components/AnglesTab";
import { useAnalyze } from "./hooks/useAnalyze";
import { useProjectStore, activeAngleOf } from "./store/projectStore";
import { useCatalogStore } from "./store/catalogStore";
import { ProjectLibrary } from "./components/ProjectLibrary";
import { LanguageSelector } from "./components/LanguageSelector";

type MainTab = "studio" | "paint" | "paints" | "angles";

export default function App() {
  const { t } = useTranslation();
  useAnalyze();
  const hasAngle = useProjectStore((s) => s.angles.length > 0);
  const resultToken = useProjectStore((s) => activeAngleOf(s)?.resultToken);
  const fetchCatalog = useCatalogStore((s) => s.fetch);
  const [tab, setTab] = useState<MainTab>("studio");

  useEffect(() => { if (hasAngle) fetchCatalog(); }, [hasAngle, fetchCatalog]);

  const loadCollection = useCatalogStore((s) => s.loadCollection);
  const catalogStatus = useCatalogStore((s) => s.status);
  useEffect(() => { if (catalogStatus === "ready") loadCollection(); }, [catalogStatus, loadCollection]);

  return (
    <Container size="xl" p="md">
      <Group justify="space-between" mb="xs">
        <Title order={3}>Mini Highlight Advisor</Title>
        <LanguageSelector />
      </Group>

      <ProjectLibrary />

      {!hasAngle ? (
        <PhotoUploader />
      ) : (
        <Tabs value={tab} onChange={(v) => setTab((v as MainTab) ?? "studio")}>
          <AngleBar />
          <Tabs.List mb="md">
            <Tabs.Tab value="studio">{t("tabs.studio")}</Tabs.Tab>
            <Tabs.Tab value="paint" disabled={!resultToken}>{t("tabs.paint")}</Tabs.Tab>
            <Tabs.Tab value="paints">{t("tabs.paints")}</Tabs.Tab>
            <Tabs.Tab value="angles">{t("tabs.angles")}</Tabs.Tab>
          </Tabs.List>

          <Tabs.Panel value="studio">
            <StudioPanel />
          </Tabs.Panel>
          <Tabs.Panel value="paint"><PaintTab /></Tabs.Panel>
          <Tabs.Panel value="paints"><PaintsTab /></Tabs.Panel>
          <Tabs.Panel value="angles"><AnglesTab /></Tabs.Panel>
        </Tabs>
      )}
    </Container>
  );
}
