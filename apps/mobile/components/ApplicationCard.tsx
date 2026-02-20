import { View, Text, TouchableOpacity, StyleSheet } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { colors, spacing, fontSize, borderRadius } from "../lib/theme";

const STATUS_COLORS: Record<string, string> = {
  saved: colors.gray500,
  applied: colors.blue500,
  interviewing: colors.amber500,
  offer: colors.green500,
  rejected: "#EF4444",
};

const STATUS_LABELS: Record<string, string> = {
  saved: "Saved",
  applied: "Applied",
  interviewing: "Interviewing",
  offer: "Offer",
  rejected: "Rejected",
};

interface ApplicationCardProps {
  id: number;
  title: string;
  company: string;
  matchScore: number;
  status: string;
  onPress: () => void;
  onStatusChange: (newStatus: string) => void;
}

export default function ApplicationCard({
  title,
  company,
  matchScore,
  status,
  onPress,
  onStatusChange,
}: ApplicationCardProps) {
  const statusColor = STATUS_COLORS[status] || colors.gray500;
  const statusLabel = STATUS_LABELS[status] || status;

  const nextStatuses = Object.keys(STATUS_LABELS).filter((s) => s !== status);

  return (
    <TouchableOpacity style={styles.card} onPress={onPress} activeOpacity={0.7}>
      <View style={styles.header}>
        <View style={{ flex: 1 }}>
          <Text style={styles.title} numberOfLines={2}>
            {title}
          </Text>
          <Text style={styles.company}>{company}</Text>
        </View>
        <View style={styles.scoreBadge}>
          <Text style={styles.scoreText}>{matchScore}%</Text>
        </View>
      </View>

      <View style={styles.statusRow}>
        <View style={[styles.statusChip, { backgroundColor: statusColor }]}>
          <Text style={styles.statusText}>{statusLabel}</Text>
        </View>
      </View>

      <View style={styles.actionsRow}>
        {nextStatuses.slice(0, 3).map((s) => (
          <TouchableOpacity
            key={s}
            style={styles.actionBtn}
            onPress={() => onStatusChange(s)}
          >
            <Text style={styles.actionBtnText}>
              {STATUS_LABELS[s]}
            </Text>
          </TouchableOpacity>
        ))}
      </View>
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
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
  },
  title: {
    fontSize: fontSize.md,
    fontWeight: "600",
    color: colors.gray900,
  },
  company: {
    fontSize: fontSize.sm,
    color: colors.gray500,
    marginTop: 2,
  },
  scoreBadge: {
    backgroundColor: colors.sage,
    borderRadius: borderRadius.full,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    marginLeft: spacing.sm,
  },
  scoreText: {
    fontSize: fontSize.sm,
    fontWeight: "700",
    color: colors.primary,
  },
  statusRow: {
    flexDirection: "row",
    marginTop: spacing.sm,
  },
  statusChip: {
    paddingHorizontal: spacing.sm,
    paddingVertical: 3,
    borderRadius: borderRadius.full,
  },
  statusText: {
    fontSize: fontSize.xs,
    fontWeight: "600",
    color: colors.white,
  },
  actionsRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.xs,
    marginTop: spacing.sm,
    paddingTop: spacing.sm,
    borderTopWidth: 1,
    borderTopColor: colors.gray100,
  },
  actionBtn: {
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
    borderRadius: borderRadius.full,
    borderWidth: 1,
    borderColor: colors.gray300,
  },
  actionBtnText: {
    fontSize: fontSize.xs,
    color: colors.gray600,
    fontWeight: "500",
  },
});
