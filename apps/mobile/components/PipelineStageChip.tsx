import { View, Text, StyleSheet } from "react-native";
import {
  STAGE_COLORS,
  STAGE_LABELS,
  type PipelineStage,
} from "../lib/recruiter-types";
import { fontSize, borderRadius } from "../lib/theme";

interface PipelineStageChipProps {
  stage: string;
}

export default function PipelineStageChip({ stage }: PipelineStageChipProps) {
  const bg = STAGE_COLORS[stage as PipelineStage] ?? "#6B7280";
  const label = STAGE_LABELS[stage as PipelineStage] ?? stage;

  return (
    <View style={[styles.chip, { backgroundColor: bg }]}>
      <Text style={styles.text}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  chip: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: borderRadius.full,
  },
  text: {
    fontSize: fontSize.xs,
    fontWeight: "600",
    color: "#FFFFFF",
  },
});
