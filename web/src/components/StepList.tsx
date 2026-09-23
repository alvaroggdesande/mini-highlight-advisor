import { useTranslation } from "react-i18next";
import { Image, Paper, SimpleGrid, Stack, Text, Title } from "@mantine/core";
import type { RegionPlanDto, StepImageDto } from "../api/types";

function StepCard({ step }: { step: StepImageDto }) {
  const { t } = useTranslation();
  return (
    <Paper p="sm" withBorder mb="sm">
      <Text fw={600} mb="xs">{step.label}</Text>
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

export interface StepListProps { plans: RegionPlanDto[]; }

export function StepList({ plans }: StepListProps) {
  return (
    <Stack gap="xl">
      {plans.map((plan) => (
        <div key={plan.name}>
          <Title order={4} mb="sm">{plan.name}</Title>
          {plan.steps.map((step) => (
            <StepCard key={`${step.kind}-${step.index}`} step={step} />
          ))}
        </div>
      ))}
    </Stack>
  );
}
