import { View, Text, TouchableOpacity, StyleSheet } from "react-native";
import { useRouter } from "expo-router";
import { colors, spacing, fontSize, borderRadius } from "../lib/theme";
import ScoreBadge from "./ScoreBadge";
import SkillTag from "./SkillTag";

interface MatchCardProps {
  match: {
    id: number;
    job_title: string;
    company: string;
    location: string;
    remote_flag: boolean;
    match_score: number;
    interview_readiness_score: number;
    reasons?: { matched_skills?: string[] };
    application_status?: string;
    match_explanation?: string;
  };
}

export default function MatchCard({ match }: MatchCardProps) {
  const router = useRouter();
  const skills = match.reasons?.matched_skills?.slice(0, 3) || [];

  return (
    <TouchableOpacity
      style={styles.card}
      onPress={() => router.push(`/match/${match.id}`)}
      activeOpacity={0.7}
    >
      <View style={styles.header}>
        <View style={styles.info}>
          <Text style={styles.title} numberOfLines={2}>
            {match.job_title}
          </Text>
          <Text style={styles.company}>{match.company}</Text>
          <Text style={styles.location}>
            {match.location}
            {match.remote_flag && "  Remote"}
          </Text>
          {match.match_explanation && (
            <Text style={styles.explanation}>{match.match_explanation}</Text>
          )}
        </View>
        <ScoreBadge score={match.match_score} label="Match" />
      </View>

      {skills.length > 0 && (
        <View style={styles.skills}>
          {skills.map((s) => (
            <SkillTag key={s} name={s} />
          ))}
        </View>
      )}

      {match.application_status && (
        <View style={styles.statusRow}>
          <Text style={styles.statusText}>
            Status: {match.application_status}
          </Text>
        </View>
      )}
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.white,
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    marginBottom: spacing.md,
    shadowColor: "#000",
    shadowOpacity: 0.05,
    shadowRadius: 8,
    elevation: 2,
  },
  header: { flexDirection: "row", justifyContent: "space-between" },
  info: { flex: 1, marginRight: spacing.sm },
  title: {
    fontSize: fontSize.lg,
    fontWeight: "600",
    color: colors.gray900,
  },
  company: {
    fontSize: fontSize.sm,
    color: colors.gray600,
    marginTop: 2,
  },
  location: {
    fontSize: fontSize.xs,
    color: colors.gray400,
    marginTop: 2,
  },
  explanation: {
    fontSize: fontSize.xs,
    fontStyle: "italic",
    color: colors.green500,
    marginTop: 4,
  },
  skills: {
    flexDirection: "row",
    flexWrap: "wrap",
    marginTop: spacing.sm,
    gap: spacing.xs,
  },
  statusRow: {
    marginTop: spacing.sm,
    paddingTop: spacing.sm,
    borderTopWidth: 1,
    borderTopColor: colors.gray100,
  },
  statusText: {
    fontSize: fontSize.xs,
    color: colors.gray500,
    textTransform: "capitalize",
  },
});
