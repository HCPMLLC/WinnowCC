import { useEffect, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
  Alert,
} from "react-native";
import { useLocalSearchParams, useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { api } from "../../../lib/api";
import LoadingSpinner from "../../../components/LoadingSpinner";
import StatusBadge from "../../../components/StatusBadge";
import { colors, spacing, fontSize, borderRadius } from "../../../lib/theme";

interface JobDetail {
  id: number;
  title: string;
  description: string;
  requirements: string | null;
  nice_to_haves: string | null;
  location: string | null;
  remote_policy: string | null;
  employment_type: string | null;
  salary_min: number | null;
  salary_max: number | null;
  salary_currency: string;
  equity_offered: boolean;
  application_url: string | null;
  application_email: string | null;
  status: string;
  view_count: number;
  application_count: number;
  posted_at: string | null;
  created_at: string | null;
}

const STATUS_OPTIONS = ["draft", "active", "paused", "closed"];

export default function JobDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const [job, setJob] = useState<JobDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [updating, setUpdating] = useState(false);

  const loadJob = async () => {
    try {
      const res = await api.get(`/api/employer/jobs/${id}`);
      if (res.ok) {
        setJob(await res.json());
      }
    } catch {
      // Silently fail
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadJob();
  }, [id]);

  const onRefresh = () => {
    setRefreshing(true);
    loadJob();
  };

  const handleStatusChange = async (newStatus: string) => {
    if (!job || job.status === newStatus) return;
    setUpdating(true);
    try {
      const res = await api.patch(`/api/employer/jobs/${id}`, {
        status: newStatus,
      });
      if (res.ok) {
        const updated = await res.json();
        setJob(updated);
      } else {
        const err = await res.json().catch(() => null);
        Alert.alert("Error", err?.detail || "Failed to update status");
      }
    } catch {
      Alert.alert("Error", "Something went wrong.");
    } finally {
      setUpdating(false);
    }
  };

  const handleDelete = () => {
    Alert.alert(
      "Delete Job",
      "Are you sure you want to permanently delete this job posting?",
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Delete",
          style: "destructive",
          onPress: async () => {
            try {
              const res = await api.delete(`/api/employer/jobs/${id}`);
              if (res.ok || res.status === 204) {
                router.back();
              } else {
                Alert.alert("Error", "Failed to delete job.");
              }
            } catch {
              Alert.alert("Error", "Something went wrong.");
            }
          },
        },
      ],
    );
  };

  if (loading) return <LoadingSpinner />;
  if (!job) {
    return (
      <View style={styles.center}>
        <Text style={styles.errorText}>Job not found.</Text>
      </View>
    );
  }

  const salary =
    job.salary_min || job.salary_max
      ? [
          job.salary_min ? `$${job.salary_min.toLocaleString()}` : null,
          job.salary_max ? `$${job.salary_max.toLocaleString()}` : null,
        ]
          .filter(Boolean)
          .join(" - ") + ` ${job.salary_currency}`
      : null;

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
      }
    >
      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.title}>{job.title}</Text>
        <StatusBadge status={job.status} />
      </View>

      {/* Meta */}
      <View style={styles.metaRow}>
        {job.location && (
          <View style={styles.metaItem}>
            <Ionicons name="location-outline" size={16} color={colors.gray500} />
            <Text style={styles.metaText}>{job.location}</Text>
          </View>
        )}
        {job.remote_policy && (
          <View style={styles.metaItem}>
            <Ionicons name="globe-outline" size={16} color={colors.gray500} />
            <Text style={styles.metaText}>{job.remote_policy}</Text>
          </View>
        )}
        {job.employment_type && (
          <View style={styles.metaItem}>
            <Ionicons name="time-outline" size={16} color={colors.gray500} />
            <Text style={styles.metaText}>{job.employment_type}</Text>
          </View>
        )}
      </View>

      {salary && (
        <Text style={styles.salary}>{salary}</Text>
      )}

      {/* Stats */}
      <View style={styles.statsRow}>
        <View style={styles.statBox}>
          <Text style={styles.statValue}>{job.view_count}</Text>
          <Text style={styles.statLabel}>Views</Text>
        </View>
        <View style={styles.statBox}>
          <Text style={styles.statValue}>{job.application_count}</Text>
          <Text style={styles.statLabel}>Applications</Text>
        </View>
        <View style={styles.statBox}>
          <Text style={styles.statValue}>
            {job.posted_at
              ? new Date(job.posted_at).toLocaleDateString()
              : "Not posted"}
          </Text>
          <Text style={styles.statLabel}>Posted</Text>
        </View>
      </View>

      {/* Status actions */}
      <Text style={styles.sectionTitle}>Status</Text>
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        style={styles.statusBar}
      >
        {STATUS_OPTIONS.map((s) => (
          <TouchableOpacity
            key={s}
            style={[
              styles.statusChip,
              job.status === s && styles.statusChipActive,
            ]}
            onPress={() => handleStatusChange(s)}
            disabled={updating || job.status === s}
          >
            <Text
              style={[
                styles.statusChipText,
                job.status === s && styles.statusChipTextActive,
              ]}
            >
              {s.charAt(0).toUpperCase() + s.slice(1)}
            </Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      {/* Description */}
      <Text style={styles.sectionTitle}>Description</Text>
      <Text style={styles.bodyText}>{job.description}</Text>

      {job.requirements && (
        <>
          <Text style={styles.sectionTitle}>Requirements</Text>
          <Text style={styles.bodyText}>{job.requirements}</Text>
        </>
      )}

      {job.nice_to_haves && (
        <>
          <Text style={styles.sectionTitle}>Nice to Haves</Text>
          <Text style={styles.bodyText}>{job.nice_to_haves}</Text>
        </>
      )}

      {(job.application_email || job.application_url) && (
        <>
          <Text style={styles.sectionTitle}>Application Info</Text>
          {job.application_email && (
            <Text style={styles.bodyText}>Email: {job.application_email}</Text>
          )}
          {job.application_url && (
            <Text style={styles.bodyText}>URL: {job.application_url}</Text>
          )}
        </>
      )}

      {job.equity_offered && (
        <View style={styles.equityBadge}>
          <Text style={styles.equityText}>Equity Offered</Text>
        </View>
      )}

      {/* Delete */}
      <TouchableOpacity style={styles.deleteBtn} onPress={handleDelete}>
        <Ionicons name="trash-outline" size={18} color={colors.red500} />
        <Text style={styles.deleteText}>Delete Job</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.gray50 },
  content: { padding: spacing.md, paddingBottom: spacing.xxl },
  center: { flex: 1, alignItems: "center", justifyContent: "center" },
  errorText: { fontSize: fontSize.md, color: colors.gray500 },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    marginBottom: spacing.sm,
  },
  title: {
    flex: 1,
    fontSize: fontSize.xxl,
    fontWeight: "700",
    color: colors.gray900,
    marginRight: spacing.sm,
  },
  metaRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.md,
    marginBottom: spacing.sm,
  },
  metaItem: { flexDirection: "row", alignItems: "center", gap: 4 },
  metaText: { fontSize: fontSize.sm, color: colors.gray500 },
  salary: {
    fontSize: fontSize.lg,
    fontWeight: "600",
    color: colors.green500,
    marginBottom: spacing.md,
  },
  statsRow: {
    flexDirection: "row",
    gap: spacing.sm,
    marginBottom: spacing.lg,
  },
  statBox: {
    flex: 1,
    backgroundColor: colors.white,
    borderRadius: borderRadius.md,
    padding: spacing.sm,
    alignItems: "center",
    shadowColor: "#000",
    shadowOpacity: 0.05,
    shadowRadius: 4,
    elevation: 1,
  },
  statValue: {
    fontSize: fontSize.lg,
    fontWeight: "700",
    color: colors.gray900,
  },
  statLabel: {
    fontSize: fontSize.xs,
    color: colors.gray500,
    marginTop: 2,
  },
  sectionTitle: {
    fontSize: fontSize.lg,
    fontWeight: "700",
    color: colors.gray900,
    marginBottom: spacing.sm,
    marginTop: spacing.md,
  },
  statusBar: { marginBottom: spacing.md },
  statusChip: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    borderRadius: borderRadius.full,
    backgroundColor: colors.gray100,
    marginRight: spacing.sm,
  },
  statusChipActive: { backgroundColor: colors.primary },
  statusChipText: {
    fontSize: fontSize.sm,
    fontWeight: "500",
    color: colors.gray600,
  },
  statusChipTextActive: { color: colors.gold },
  bodyText: {
    fontSize: fontSize.md,
    color: colors.gray700,
    lineHeight: 24,
    marginBottom: spacing.sm,
  },
  equityBadge: {
    alignSelf: "flex-start",
    backgroundColor: colors.sage,
    borderRadius: borderRadius.full,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    marginTop: spacing.md,
  },
  equityText: {
    fontSize: fontSize.sm,
    fontWeight: "600",
    color: colors.primary,
  },
  deleteBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.xs,
    borderRadius: borderRadius.md,
    paddingVertical: spacing.md,
    marginTop: spacing.xl,
    borderWidth: 1,
    borderColor: colors.red500,
  },
  deleteText: {
    fontSize: fontSize.md,
    fontWeight: "600",
    color: colors.red500,
  },
});
