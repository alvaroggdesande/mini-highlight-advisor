import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Box, Button, Collapse, Group, Stack, Text, TextInput, UnstyledButton } from "@mantine/core";
import {
  deleteProjectApi, downloadProjectBlob, listProjects,
  loadProjectApi, saveProjectApi, uploadProjectBlob,
} from "../api/client";
import { useProjectStore } from "../store/projectStore";
import type { ProjectMeta } from "../api/types";

export function ProjectLibrary() {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [projects, setProjects] = useState<ProjectMeta[]>([]);
  const [inputName, setInputName] = useState("");
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const projectName = useProjectStore((s) => s.projectName);
  const slug = useProjectStore((s) => s.slug);
  const activeAngle = useProjectStore((s) => s.activeAngle);
  const angles = useProjectStore((s) => s.angles);
  const initFromProject = useProjectStore((s) => s.initFromProject);
  const setProjectMeta = useProjectStore((s) => s.setProjectMeta);
  const hasAngles = angles.length > 0;

  useEffect(() => { if (projectName && !inputName) setInputName(projectName); }, [projectName]);
  useEffect(() => { if (!open) return; listProjects().then(setProjects).catch(() => setProjects([])); }, [open]);

  async function handleSave() {
    const name = inputName.trim();
    if (!name || !hasAngles) return;
    setBusy("save"); setError(null);
    try {
      const res = await saveProjectApi(name, activeAngle, angles);
      setProjectMeta(res.name, res.slug);
      setProjects(await listProjects());
    } catch (e) { setError(e instanceof Error ? e.message : "save failed"); }
    finally { setBusy(null); }
  }

  async function handleLoad(projectSlug: string) {
    setBusy(`load:${projectSlug}`); setError(null);
    try { initFromProject(await loadProjectApi(projectSlug)); }
    catch (e) { setError(e instanceof Error ? e.message : "load failed"); }
    finally { setBusy(null); }
  }

  async function handleDelete(projectSlug: string, name: string) {
    if (!window.confirm(t("projects.react_confirm_delete", { name }))) return;
    setBusy(`delete:${projectSlug}`); setError(null);
    try { await deleteProjectApi(projectSlug); setProjects((prev) => prev.filter((p) => p.slug !== projectSlug)); }
    catch (e) { setError(e instanceof Error ? e.message : "delete failed"); }
    finally { setBusy(null); }
  }

  async function handleDownload(projectSlug: string) {
    setBusy(`download:${projectSlug}`); setError(null);
    try { await downloadProjectBlob(projectSlug); }
    catch (e) { setError(e instanceof Error ? e.message : "download failed"); }
    finally { setBusy(null); }
  }

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]; if (!file) return;
    setBusy("upload"); setError(null);
    try { initFromProject(await uploadProjectBlob(file)); setProjects(await listProjects()); }
    catch (e) { setError(e instanceof Error ? e.message : "upload failed"); }
    finally { setBusy(null); if (fileRef.current) fileRef.current.value = ""; }
  }

  const toggleLabel = `${open ? "▼" : "▶"} ${t("projects.react_toggle")}${projectName ? ` — ${projectName}` : ""}`;

  return (
    <Box mb="md" pb={open ? "sm" : 0} style={{ borderBottom: "1px solid var(--mantine-color-dark-4)" }}>
      <UnstyledButton onClick={() => setOpen((v) => !v)} c="dimmed" fz="sm">
        {toggleLabel}
      </UnstyledButton>

      <Collapse in={open}>
        <Stack gap="xs" mt="sm">
          {error && <Text c="red" size="sm">{error}</Text>}
          <Group gap="xs" wrap="wrap">
            <TextInput
              value={inputName}
              onChange={(e) => setInputName(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") handleSave(); }}
              placeholder={t("projects.react_name_placeholder")}
              size="xs"
              style={{ flex: "1 1 160px" }}
            />
            <Button size="xs" onClick={handleSave}
              disabled={!inputName.trim() || !hasAngles} loading={busy === "save"}>
              {t("projects.react_save")}
            </Button>
            <Button size="xs" variant="default" onClick={() => fileRef.current?.click()}
              loading={busy === "upload"}>
              {t("projects.react_import")}
            </Button>
            <input ref={fileRef} type="file" accept=".json" style={{ display: "none" }} onChange={handleUpload} />
          </Group>
          {projects.length === 0 ? (
            <Text c="dimmed" size="sm">{t("projects.react_empty")}</Text>
          ) : (
            <Stack gap={4}>
              {projects.map((p) => (
                <Group key={p.slug} gap="xs" wrap="nowrap">
                  <Text size="sm" c={p.slug === slug ? undefined : "dimmed"} style={{ flex: 1 }}>{p.name}</Text>
                  <Text size="xs" c="dimmed">{new Date(p.updated_at).toLocaleDateString()}</Text>
                  <Button size="xs" variant="subtle" loading={busy === `load:${p.slug}`} onClick={() => handleLoad(p.slug)}>
                    {t("projects.react_load")}
                  </Button>
                  <Button size="xs" variant="subtle" loading={busy === `download:${p.slug}`} onClick={() => handleDownload(p.slug)}>
                    {t("projects.react_export")}
                  </Button>
                  <Button size="xs" variant="subtle" color="red"
                    disabled={busy?.startsWith("delete:") ?? false}
                    onClick={() => handleDelete(p.slug, p.name)}>
                    {t("projects.react_delete")}
                  </Button>
                </Group>
              ))}
            </Stack>
          )}
        </Stack>
      </Collapse>
    </Box>
  );
}
