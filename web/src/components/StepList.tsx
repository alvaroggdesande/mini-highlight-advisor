import { useTranslation } from "react-i18next";
import { ColorSwatch, Group, Image, Paper, SimpleGrid, Stack, Text } from "@mantine/core";
import type { RegionPlanDto, StepImageDto } from "../api/types";
import { ROLE_KEY } from "../lib/roles";
import { useMatch } from "../hooks/useMatch";
import { matchPhrase, withBrand } from "../lib/matchPhrase";
import { validHex } from "../lib/color";

/** Under a step's header: owned / not owned for a catalogue paint, or the mix
 *  guide from your collection for a custom hex (as the Streamlit Paint tab did). */
function StepPaintGuide({ step }: { step: StepImageDto }) {
  const { t } = useTranslation();
  const isCustom = !step.paint_code;
  const { result, hasOwned, ownedCodes } = useMatch(
    isCustom ? validHex(step.paint_hex) : null, step.paint_finish ?? "matte");
  if (!isCustom) {
    return <Text size="xs" c="dimmed" mt={-6} mb="xs" data-testid="step-guide">
      {step.paint_hex} · {ownedCodes.has(step.paint_code!) ? t("colour.owned") : t("colour.not_owned")}
    </Text>;
  }
  if (!result) return null;
  return <Text size="xs" c="dimmed" mt={-6} mb="xs" data-testid="step-guide">
    {matchPhrase(result, hasOwned, t)}
  </Text>;
}

function StepHeader({ step }: { step: StepImageDto }) {
  const { t } = useTranslation();
  const role = t(ROLE_KEY[step.label] ?? step.label);
  if (!step.paint_name) return <Text fw={600} mb="xs">{role}</Text>;
  return (
    <Group gap="xs" mb="xs" wrap="nowrap">
      {step.paint_hex && <ColorSwatch data-testid="step-swatch" color={step.paint_hex} size={20} />}
      <Text fw={600}>
        {role} — {withBrand(step.paint_name, step.paint_brand)}
        {step.paint_code && <Text span c="dimmed" fw={400}> · {step.paint_code}</Text>}
      </Text>
    </Group>
  );
}

function StepCard({ step }: { step: StepImageDto }) {
  const { t } = useTranslation();
  return (
    <Paper p="sm" withBorder mb="sm">
      <StepHeader step={step} />
      {step.paint_hex && <StepPaintGuide step={step} />}
      <SimpleGrid cols={step.is_last ? 2 : 3} spacing="xs">
        <Stack gap={4}>
          <Image src={step.zone_png} alt={t("paint.step_zone")} />
          <Text size="xs" c="dimmed" ta="center">{t("paint.step_zone")}</Text>
        </Stack>
        <Stack gap={4}>
          <Image src={step.cumulative_png} alt={t("paint.step_cumulative")} />
          <Text size="xs" c="dimmed" ta="center">{t("paint.step_cumulative")}</Text>
        </Stack>
        {!step.is_last && step.exact_png && (
          <Stack gap={4}>
            <Image src={step.exact_png} alt={t("paint.step_exact")} />
            <Text size="xs" c="dimmed" ta="center">{t("paint.step_exact")}</Text>
          </Stack>
        )}
      </SimpleGrid>
    </Paper>
  );
}

export interface StepListProps { plan: RegionPlanDto; }

/** Steps for a single region. The region name is shown by the selecting tab, so
 *  it is not repeated here. */
export function StepList({ plan }: StepListProps) {
  const { t } = useTranslation();
  return (
    <Stack gap="xs">
      <Text size="sm" c="dimmed">{t("paint.steps_hint")}</Text>
      {plan.steps.map((step) => (
        <StepCard key={`${step.kind}-${step.index}`} step={step} />
      ))}
    </Stack>
  );
}
