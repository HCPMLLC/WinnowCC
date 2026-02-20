import { View, Text, TouchableOpacity, StyleSheet } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import {
  JOB_STATUS_COLORS,
  type RecruiterJob,
  type JobStatus,
} from "../lib/recruiter-types";
import { colors, spacing, fontSize, borderRadius } from "../lib/theme";

interface RecruiterJobCardProps {
  job: RecruiterJob;
  onPress: () => void;
}

export default function RecruiterJobCard({ job, onPress }: RecruiterJobCardProps) {
  const statusColor = JOB_STATUS_COLORS[job.status as JobStatus] ?? colors.gray400;

  return (
    <TouchableOpacity style={styles.card} onPress={onPress} activeOpacity={0.7}>
      <View style={styles.header}>
        <Text style={styles.title} numberOfLines={1}>
          {job.title}
        </Text>
        <View style={[styles.statusBadge, { backgroundColor: statusColor }]}>
          <Text style={styles.statusText}>
            {job.status.charAt(0).toUpperCase() + job.status.slice(1)}
          </Text>
        </View>
      </View>

      {job.client_company_name && (
        <Text style={styles.client} numberOfLines={1}>
          {job.client_company_name}
        </Text>
      )}

      <View style={styles.metaRow}>
        {job.location && (
          <View style={styles.metaItem}>
            <Ionicons name="location-outline" size={14} color={colors.gray400} />
            <Text style={styles.metaText}>{job.location}</Text>
          </View>
        )}
        {job.remote_policy && (
          <View style={styles.metaItem}>
            <Ionicons name="globe-outline" size={14} color={colors.gray400} />
            <Text style={styles.metaText}>{job.remote_policy}</Text>
          </View>
        )}
      </View>

      <View style={styles.footer}>
        <View style={styles.footerItem}>
          <Ionicons name="people-outline" size={14} color={colors.gray500} />
          <Text style={styles.footerText}>
            {job.matched_candidates_count} candidates
          </Text>
        </View>
        {job.priority && (job.priority === "high" || job.priority === "urgent") && (
          <View
            style={[
              styles.priorityBadge,
              {
                backgroundColor:
                  job.priority === "urgent" ? colors.red500 : colors.amber500,
              },
            ]}
          >
            <Text style={styles.priorityText}>
              {job.priority.toUpperCase()}
            </Text>
          </View>
        )}
      </View>
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
  title: {
    fontSize: fontSize.md,
    fontWeight: "600",
    color: colors.gray900,
    flex: 1,
    marginRight: spacing.sm,
  },
  statusBadge: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: borderRadius.full,
  },
  statusText: {
    fontSize: fontSize.xs,
    fontWeight: "600",
    color: colors.white,
  },
  client: {
    fontSize: fontSize.sm,
    color: colors.gray600,
    marginBottom: spacing.xs,
  },
  metaRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.md,
    marginBottom: spacing.xs,
  },
  metaItem: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
  },
  metaText: {
    fontSize: fontSize.xs,
    color: colors.gray500,
  },
  footer: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginTop: spacing.xs,
  },
  footerItem: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
  },
  footerText: {
    fontSize: fontSize.xs,
    color: colors.gray500,
  },
  priorityBadge: {
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: borderRadius.full,
  },
  priorityText: {
    fontSize: 10,
    fontWeight: "700",
    color: colors.white,
  },
});
