import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  deleteProjectApi,
  downloadProjectBlob,
  listProjects,
  loadProjectApi,
  saveProjectApi,
  uploadProjectBlob,
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

  useEffect(() => {
    if (projectName && !inputName) setInputName(projectName);
  }, [projectName]);

  useEffect(() => {
    if (!open) return;
    listProjects().then(setProjects).catch(() => setProjects([]));
  }, [open]);

  async function handleSave() {
    const name = inputName.trim();
    if (!name || !hasAngles) return;
    setBusy("save");
    setError(null);
    try {
      const res = await saveProjectApi(name, activeAngle, angles);
      setProjectMeta(res.name, res.slug);
      setProjects(await listProjects());
    } catch (e) {
      setError(e instanceof Error ? e.message : "save failed");
    } finally {
      setBusy(null);
    }
  }

  async function handleLoad(projectSlug: string) {
    setBusy(`load:${projectSlug}`);
    setError(null);
    try {
      const manifest = await loadProjectApi(projectSlug);
      initFromProject(manifest);
    } catch (e) {
      setError(e instanceof Error ? e.message : "load failed");
    } finally {
      setBusy(null);
    }
  }

  async function handleDelete(projectSlug: string, name: string) {
    if (!window.confirm(t("projects.react_confirm_delete", { name }))) return;
    setBusy(`delete:${projectSlug}`);
    setError(null);
    try {
      await deleteProjectApi(projectSlug);
      setProjects((prev) => prev.filter((p) => p.slug !== projectSlug));
    } catch (e) {
      setError(e instanceof Error ? e.message : "delete failed");
    } finally {
      setBusy(null);
    }
  }

  async function handleDownload(projectSlug: string) {
    setBusy(`download:${projectSlug}`);
    setError(null);
    try {
      await downloadProjectBlob(projectSlug);
    } catch (e) {
      setError(e instanceof Error ? e.message : "download failed");
    } finally {
      setBusy(null);
    }
  }

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setBusy("upload");
    setError(null);
    try {
      const manifest = await uploadProjectBlob(file);
      initFromProject(manifest);
      setProjects(await listProjects());
    } catch (e) {
      setError(e instanceof Error ? e.message : "upload failed");
    } finally {
      setBusy(null);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  const label = `${open ? "▼" : "▶"} ${t("projects.react_toggle")}${projectName ? ` — ${projectName}` : ""}`;

  return (
    <div style={{ marginBottom: 16, paddingBottom: open ? 12 : 0, borderBottom: "1px solid #2a2a2a" }}>
      <button
        onClick={() => setOpen((v) => !v)}
        style={{ background: "none", border: "none", color: "#888", cursor: "pointer", padding: "4px 0", fontSize: 13 }}
      >
        {label}
      </button>

      {open && (
        <div style={{ marginTop: 10 }}>
          {error && (
            <div style={{ color: "#f66", marginBottom: 8, fontSize: 13 }}>{error}</div>
          )}

          <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 10, flexWrap: "wrap" }}>
            <input
              value={inputName}
              onChange={(e) => setInputName(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") handleSave(); }}
              placeholder={t("projects.react_name_placeholder")}
              style={{
                flex: "1 1 160px", padding: "4px 8px",
                background: "#1a1a1a", color: "#ddd",
                border: "1px solid #444", borderRadius: 4, fontSize: 13,
              }}
            />
            <button
              onClick={handleSave}
              disabled={!inputName.trim() || !hasAngles || busy === "save"}
              style={{ padding: "4px 12px", fontSize: 13, cursor: "pointer" }}
            >
              {busy === "save" ? t("projects.react_saving") : t("projects.react_save")}
            </button>
            <button
              onClick={() => fileRef.current?.click()}
              disabled={busy === "upload"}
              style={{ padding: "4px 12px", fontSize: 13, cursor: "pointer" }}
            >
              {busy === "upload" ? t("projects.react_importing") : t("projects.react_import")}
            </button>
            <input
              ref={fileRef}
              type="file"
              accept=".json"
              onChange={handleUpload}
              style={{ display: "none" }}
            />
          </div>

          {projects.length === 0 ? (
            <div style={{ color: "#555", fontSize: 13 }}>{t("projects.react_empty")}</div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
              {projects.map((p) => (
                <div
                  key={p.slug}
                  style={{ display: "flex", alignItems: "center", gap: 8, padding: "3px 0" }}
                >
                  <span style={{ flex: 1, fontSize: 13, color: p.slug === slug ? "#eee" : "#999" }}>
                    {p.name}
                  </span>
                  <span style={{ color: "#444", fontSize: 11, whiteSpace: "nowrap" }}>
                    {new Date(p.updated_at).toLocaleDateString()}
                  </span>
                  <button
                    onClick={() => handleLoad(p.slug)}
                    disabled={busy === `load:${p.slug}`}
                    style={{ padding: "2px 8px", fontSize: 12, cursor: "pointer" }}
                  >
                    {busy === `load:${p.slug}` ? "…" : t("projects.react_load")}
                  </button>
                  <button
                    onClick={() => handleDownload(p.slug)}
                    disabled={busy === `download:${p.slug}`}
                    title="Export JSON"
                    style={{ padding: "2px 6px", fontSize: 12, cursor: "pointer" }}
                  >
                    {t("projects.react_export")}
                  </button>
                  <button
                    onClick={() => handleDelete(p.slug, p.name)}
                    disabled={busy?.startsWith("delete:") ?? false}
                    title="Delete"
                    style={{ padding: "2px 6px", fontSize: 12, cursor: "pointer", color: "#c44" }}
                  >
                    {t("projects.react_delete")}
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
