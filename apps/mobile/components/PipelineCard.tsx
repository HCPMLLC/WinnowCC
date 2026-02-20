import { View, Text, TouchableOpacity, StyleSheet } from "react-native";
import PipelineStageChip from "./PipelineStageChip";
import SkillTag from "./SkillTag";
import type { PipelineCandidate } from "../lib/recruiter-types";
import { colors, spacing, fontSize, borderRadius } from "../lib/theme";

interface PipelineCardProps {
  candidate: PipelineCandidate;
  onPress: () => void;
}

export default function PipelineCard({ candidate, onPress }: PipelineCardProps) {
  const name =
    candidate.candidate_name || candidate.external_name || "Unknown";
  const skills = (candidate.skills ?? []).slice(0, 4);

  return (
    <TouchableOpacity style={styles.card} onPress={onPress} activeOpacity={0.7}>
      <View style={styles.header}>
        <View style={styles.nameRow}>
          <Text style={styles.name} numberOfLines={1}>
            {name}
          </Text>
          {candidate.match_score != null && (
            <View style={styles.scoreBadge}>
              <Text style={styles.scoreText}>{candidate.match_score}%</Text>
            </View>
          )}
        </View>
        <PipelineStageChip stage={candidate.stage} />
      </View>

      {candidate.headline && (
        <Text style={styles.headline} numberOfLines={1}>
          {candidate.headline}
        </Text>
      )}

      {candidate.location && (
        <Text style={styles.meta} numberOfLines={1}>
          {candidate.location}
          {candidate.current_company ? ` · ${candidate.current_company}` : ""}
        </Text>
      )}

      {skills.length > 0 && (
        <View style={styles.skillsRow}>
          {skills.map((s) => (
            <SkillTag key={s} name={s} />
          ))}
        </View>
      )}

      {candidate.notes && (
        <Text style={styles.notes} numberOfLines={1}>
          {candidate.notes}
        </Text>
      )}
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.white,
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    marginBottom: spacing.sm,
    shadowColor: "#000",
    shadowOpacity: 0.05,
    shadowRadius: 8,
    elevation: 2,
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: spacing.xs,
  },
  nameRow: {
    flexDirection: "row",
    alignItems: "center",
    flex: 1,
    marginRight: spacing.sm,
  },
  name: {
    fontSize: fontSize.md,
    fontWeight: "600",
    color: colors.gray900,
    flex: 1,
  },
  scoreBadge: {
    backgroundColor: colors.sage,
    borderRadius: borderRadius.full,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    marginLeft: spacing.xs,
  },
  scoreText: {
    fontSize: fontSize.xs,
    fontWeight: "600",
    color: colors.primary,
  },
  headline: {
    fontSize: fontSize.sm,
    color: colors.gray600,
    marginBottom: spacing.xs,
  },
  meta: {
    fontSize: fontSize.xs,
    color: colors.gray400,
    marginBottom: spacing.xs,
  },
  skillsRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.xs,
    marginTop: spacing.xs,
  },
  notes: {
    fontSize: fontSize.xs,
    color: colors.gray500,
    fontStyle: "italic",
    marginTop: spacing.xs,
  },
});
