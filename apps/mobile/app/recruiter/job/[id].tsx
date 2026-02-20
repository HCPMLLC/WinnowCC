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
import { Picker } from "@react-native-picker/picker";
import { useLocalSearchParams } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { api } from "../../../lib/api";
import LoadingSpinner from "../../../components/LoadingSpinner";
import PipelineStageChip from "../../../components/PipelineStageChip";
import {
  JOB_STATUSES,
  JOB_STATUS_COLORS,
  type RecruiterJob,
  type JobStatus,
} from "../../../lib/recruiter-types";
import { colors, spacing, fontSize, borderRadius } from "../../../lib/theme";

interface MatchedCandidate {
  id: number;
  candidate_name: string | null;
  headline: string | null;
  match_score: number | null;
  stage: string | null;
}

export default function RecruiterJobDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const [job, setJob] = useState<RecruiterJob | null>(null);
  const [candidates, setCandidates] = useState<MatchedCandidate[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [editStatus, setEditStatus] = useState<string>("");
  const [saving, setSaving] = useState(false);

  const loadData = async () => {
    try {
      const [jobRes, candRes] = await Promise.all([
        api.get(`/api/recruiter/jobs/${id}`),
        api.get(`/api/recruiter/jobs/${id}/candidates?limit=50`).catch(() => null),
      ]);

      if (jobRes.ok) {
        const data = await jobRes.json();
        setJob(data);
        setEditStatus(data.status);
      }
      if (candRes && candRes.ok) {
        const data = await candRes.json();
        setCandidates(Array.isArray(data) ? data : data.items ?? []);
      }
    } catch {
      // Silently fail
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [id]);

  const onRefresh = () => {
    setRefreshing(true);
    loadData();
  };

  const handleStatusChange = async (newStatus: string) => {
    setEditStatus(newStatus);
    setSaving(true);
    try {
      const res = await api.patch(`/api/recruiter/jobs/${id}`, {
        status: newStatus,
      });
      if (res.ok) {
        setJob((prev) => (prev ? { ...prev, status: newStatus as JobStatus } : prev));
      } else {
        Alert.alert("Error", "Failed to update status.");
        setEditStatus(job?.status ?? "");
      }
    } catch {
      Alert.alert("Error", "Something went wrong.");
      setEditStatus(job?.status ?? "");
    } finally {
      setSaving(false);
    }
  };

  if (loading) return <LoadingSpinner />;

  if (!job) {
    return (
      <View style={styles.emptyContainer}>
        <Text style={styles.emptyText}>Job not found</Text>
      </View>
    );
  }

  const statusColor = JOB_STATUS_COLORS[job.status as JobStatus] ?? colors.gray400;

  const salaryRange =
    job.salary_min || job.salary_max
      ? `$${(job.salary_min ?? 0).toLocaleString()} - $${(job.salary_max ?? 0).toLocaleString()}`
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
      <View style={styles.headerCard}>
        <View style={styles.titleRow}>
          <Text style={styles.title}>{job.title}</Text>
          <View style={[styles.statusBadge, { backgroundColor: statusColor }]}>
            <Text style={styles.statusText}>
              {job.status.charAt(0).toUpperCase() + job.status.slice(1)}
            </Text>
          </View>
        </View>
        {job.client_company_name && (
          <Text style={styles.client}>{job.client_company_name}</Text>
        )}
      </View>

      {/* Details */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Details</Text>
        {job.location && <DetailRow label="Location" value={job.location} />}
        {job.remote_policy && (
          <DetailRow label="Remote" value={job.remote_policy} />
        )}
        {job.employment_type && (
          <DetailRow label="Type" value={job.employment_type} />
        )}
        {salaryRange && <DetailRow label="Salary" value={salaryRange} />}
        {job.priority && <DetailRow label="Priority" value={job.priority} />}
        <DetailRow
          label="Positions"
          value={`${job.positions_filled} / ${job.positions_to_fill} filled`}
        />
        {job.closes_at && (
          <DetailRow
            label="Closes"
            value={new Date(job.closes_at).toLocaleDateString()}
          />
        )}
      </View>

      {/* Status change */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Change Status</Text>
        <View style={styles.pickerWrapper}>
          <Picker
            selectedValue={editStatus}
            onValueChange={handleStatusChange}
            style={styles.picker}
            enabled={!saving}
          >
            {JOB_STATUSES.map((s) => (
              <Picker.Item
                key={s}
                label={s.charAt(0).toUpperCase() + s.slice(1)}
                value={s}
              />
            ))}
          </Picker>
        </View>
      </View>

      {/* Description */}
      {job.description && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Description</Text>
          <Text style={styles.bodyText}>{job.description}</Text>
        </View>
      )}

      {/* Requirements */}
      {job.requirements && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Requirements</Text>
          <Text style={styles.bodyText}>{job.requirements}</Text>
        </View>
      )}

      {/* Matched candidates */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>
          Matched Candidates ({candidates.length})
        </Text>
        {candidates.length === 0 ? (
          <Text style={styles.emptyHint}>No matched candidates yet</Text>
        ) : (
          candidates.map((c) => (
            <View key={c.id} style={styles.candidateRow}>
              <View style={styles.candidateInfo}>
                <Text style={styles.candidateName}>
                  {c.candidate_name ?? "Unknown"}
                </Text>
                {c.headline && (
                  <Text style={styles.candidateHeadline} numberOfLines={1}>
                    {c.headline}
                  </Text>
                )}
              </View>
              {c.match_score != null && (
                <View style={styles.matchBadge}>
                  <Text style={styles.matchText}>{c.match_score}%</Text>
                </View>
              )}
              {c.stage && <PipelineStageChip stage={c.stage} />}
            </View>
          ))
        )}
      </View>
    </ScrollView>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <View style={detailStyles.row}>
      <Text style={detailStyles.label}>{label}</Text>
      <Text style={detailStyles.value}>{value}</Text>
    </View>
  );
}

const detailStyles = StyleSheet.create({
  row: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingVertical: spacing.xs,
    borderBottomWidth: 1,
    borderBottomColor: colors.gray100,
  },
  label: { fontSize: fontSize.sm, color: colors.gray500 },
  value: { fontSize: fontSize.sm, fontWeight: "600", color: colors.gray900 },
});

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.gray50 },
  content: { padding: spacing.md, paddingBottom: spacing.xxl },
  emptyContainer: { flex: 1, justifyContent: "center", alignItems: "center" },
  emptyText: { fontSize: fontSize.md, color: colors.gray500 },
  headerCard: {
    backgroundColor: colors.white,
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    marginBottom: spacing.md,
    shadowColor: "#000",
    shadowOpacity: 0.05,
    shadowRadius: 8,
    elevation: 2,
  },
  titleRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  title: {
    fontSize: fontSize.xl,
    fontWeight: "700",
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
    fontSize: fontSize.md,
    color: colors.gray600,
    marginTop: spacing.xs,
  },
  section: {
    backgroundColor: colors.white,
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    marginBottom: spacing.md,
    shadowColor: "#000",
    shadowOpacity: 0.05,
    shadowRadius: 8,
    elevation: 2,
  },
  sectionTitle: {
    fontSize: fontSize.lg,
    fontWeight: "700",
    color: colors.gray900,
    marginBottom: spacing.sm,
  },
  pickerWrapper: {
    backgroundColor: colors.gray50,
    borderRadius: borderRadius.md,
    borderWidth: 1,
    borderColor: colors.gray200,
    overflow: "hidden",
  },
  picker: { color: colors.gray900 },
  bodyText: {
    fontSize: fontSize.sm,
    color: colors.gray700,
    lineHeight: 22,
  },
  emptyHint: {
    fontSize: fontSize.sm,
    color: colors.gray400,
    fontStyle: "italic",
  },
  candidateRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.gray100,
  },
  candidateInfo: { flex: 1 },
  candidateName: {
    fontSize: fontSize.sm,
    fontWeight: "600",
    color: colors.gray900,
  },
  candidateHeadline: {
    fontSize: fontSize.xs,
    color: colors.gray500,
    marginTop: 2,
  },
  matchBadge: {
    backgroundColor: colors.sage,
    borderRadius: borderRadius.full,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    marginRight: spacing.sm,
  },
  matchText: {
    fontSize: fontSize.xs,
    fontWeight: "600",
    color: colors.primary,
  },
});
