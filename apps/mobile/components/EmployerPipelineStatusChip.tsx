import { View, Text, StyleSheet } from "react-native";
import { fontSize, borderRadius, spacing } from "../lib/theme";
import {
  PIPELINE_STATUS_LABELS,
  PIPELINE_STATUS_COLORS,
  type PipelineStatus,
} from "../lib/employer-types";

interface Props {
  status: string;
}

export default function EmployerPipelineStatusChip({ status }: Props) {
  const palette =
    PIPELINE_STATUS_COLORS[status as PipelineStatus] ??
    PIPELINE_STATUS_COLORS.nurturing;
  const label =
    PIPELINE_STATUS_LABELS[status as PipelineStatus] ?? status;

  return (
    <View style={[styles.chip, { backgroundColor: palette.bg }]}>
      <Text style={[styles.text, { color: palette.text }]}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  chip: {
    alignSelf: "flex-start",
    borderRadius: borderRadius.full,
    paddingHorizontal: spacing.sm,
    paddingVertical: 3,
  },
  text: {
    fontSize: fontSize.xs,
    fontWeight: "600",
  },
});
