import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Button, Divider, Group, Stack, Text } from "@mantine/core";
import { exportCollection, importCollection } from "../api/client";
import { useCatalogStore } from "../store/catalogStore";
import { PaintInventory } from "./PaintInventory";

export function PaintsTab() {
  const { t } = useTranslation();
  const setOwnedFromImport = useCatalogStore((s) => s.setOwnedFromImport);
  const ownedCodes = useCatalogStore((s) => s.ownedCodes);
  const [importing, setImporting] = useState(false);
  const [message, setMessage] = useState<{ kind: "ok" | "err"; text: string } | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  async function handleExport() {
    const blob = await exportCollection();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a"); a.href = url; a.download = "my_paints.json"; a.click();
    URL.revokeObjectURL(url);
  }

  async function handleImport(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]; if (!file) return;
    setImporting(true); setMessage(null);
    try {
      const res = await importCollection(file);
      setOwnedFromImport(res.owned);
      setMessage({ kind: "ok", text: t("paints.import_success", { count: res.owned.length }) });
    } catch (err) {
      setMessage({ kind: "err", text: t("paints.import_error", { err: String(err) }) });
    } finally { setImporting(false); if (fileRef.current) fileRef.current.value = ""; }
  }

  return (
    <Stack gap="sm" p="xs">
      <PaintInventory />
      <Divider />
      <Stack gap="xs">
        <Text size="xs" c="dimmed">{t("paints.manage_section")}</Text>
        <Group gap="xs" wrap="wrap">
          {ownedCodes.size > 0 && (
            <Button size="xs" variant="default" onClick={handleExport}>{t("paints.export_btn")}</Button>
          )}
          <Button size="xs" variant="default" loading={importing} onClick={() => fileRef.current?.click()}>
            {t("paints.import_btn")}
          </Button>
          <input ref={fileRef} type="file" accept=".json" style={{ display: "none" }} onChange={handleImport} />
        </Group>
        {message && <Text size="sm" c={message.kind === "ok" ? "green" : "red"}>{message.text}</Text>}
      </Stack>
    </Stack>
  );
}
