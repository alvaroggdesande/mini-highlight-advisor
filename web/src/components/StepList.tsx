import { useTranslation } from "react-i18next";
import type { RegionPlanDto, StepImageDto } from "../api/types";

function StepCard({ step }: { step: StepImageDto }) {
  const { t } = useTranslation();
  const imgStyle: React.CSSProperties = { width: "100%", display: "block" };
  const captionStyle: React.CSSProperties = {
    fontSize: 12, color: "#aaa", textAlign: "center", marginTop: 4,
  };
  const colStyle: React.CSSProperties = { display: "flex", flexDirection: "column" };

  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ fontWeight: 600, marginBottom: 8 }}>{step.label}</div>
      {step.is_last ? (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
          <div style={colStyle}>
            <img src={step.zone_png} alt={t("paint.step_zone")} style={imgStyle} />
            <span style={captionStyle}>{t("paint.step_zone")}</span>
          </div>
          <div style={colStyle}>
            <img src={step.cumulative_png} alt={t("paint.step_cumulative")} style={imgStyle} />
            <span style={captionStyle}>{t("paint.step_cumulative")}</span>
          </div>
        </div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 8 }}>
          <div style={colStyle}>
            <img src={step.zone_png} alt={t("paint.step_zone")} style={imgStyle} />
            <span style={captionStyle}>{t("paint.step_zone")}</span>
          </div>
          <div style={colStyle}>
            <img src={step.cumulative_png} alt={t("paint.step_cumulative")} style={imgStyle} />
            <span style={captionStyle}>{t("paint.step_cumulative")}</span>
          </div>
          <div style={colStyle}>
            <img src={step.exact_png!} alt={t("paint.step_exact")} style={imgStyle} />
            <span style={captionStyle}>{t("paint.step_exact")}</span>
          </div>
        </div>
      )}
    </div>
  );
}

export interface StepListProps { plans: RegionPlanDto[]; }

export function StepList({ plans }: StepListProps) {
  return (
    <div>
      {plans.map((plan) => (
        <section key={plan.name} style={{ marginBottom: 32 }}>
          <h3 style={{ borderBottom: "1px solid #333", paddingBottom: 8, marginBottom: 16 }}>
            {plan.name}
          </h3>
          {plan.steps.map((step) => (
            <StepCard key={`${step.kind}-${step.index}`} step={step} />
          ))}
        </section>
      ))}
    </div>
  );
}
