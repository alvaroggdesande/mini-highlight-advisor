import { useTranslation } from "react-i18next";

const LANGS = [
  { code: "en", label: "EN" },
  { code: "es", label: "ES" },
];

export function LanguageSelector() {
  const { i18n } = useTranslation();
  const current = i18n.language;

  return (
    <div style={{ display: "flex", gap: 4 }}>
      {LANGS.map(({ code, label }) => (
        <button
          key={code}
          onClick={() => i18n.changeLanguage(code)}
          style={{
            padding: "2px 8px",
            background: "none",
            border: current === code ? "1px solid #888" : "1px solid #444",
            color: current === code ? "#eee" : "#666",
            borderRadius: 3,
            fontSize: 12,
            cursor: current === code ? "default" : "pointer",
          }}
          disabled={current === code}
        >
          {label}
        </button>
      ))}
    </div>
  );
}
