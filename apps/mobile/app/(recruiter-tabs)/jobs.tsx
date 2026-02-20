import { useEffect, useState, useCallback } from "react";
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  RefreshControl,
} from "react-native";
import { useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { api } from "../../lib/api";
import LoadingSpinner from "../../components/LoadingSpinner";
import RecruiterJobCard from "../../components/RecruiterJobCard";
import {
  JOB_STATUSES,
  JOB_STATUS_COLORS,
  type RecruiterJob,
  type JobStatus,
} from "../../lib/recruiter-types";
import { colors, spacing, fontSize, borderRadius } from "../../lib/theme";

export default function RecruiterJobsScreen() {
  const router = useRouter();
  const [jobs, setJobs] = useState<RecruiterJob[]>([]);
  const [filter, setFilter] = useState<string>("all");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const loadData = useCallback(async () => {
    try {
      const query = filter === "all" ? "" : `?status=${filter}`;
      const res = await api.get(`/api/recruiter/jobs${query}`);
      if (res.ok) {
        const data = await res.json();
        setJobs(Array.isArray(data) ? data : data.items ?? []);
      }
    } catch {
      // Silently fail
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [filter]);

  useEffect(() => {
    setLoading(true);
    loadData();
  }, [loadData]);

  const onRefresh = () => {
    setRefreshing(true);
    loadData();
  };

  if (loading) return <LoadingSpinner />;

  const STATUS_LABELS: Record<string, string> = {
    all: "All",
    draft: "Draft",
    active: "Active",
    paused: "Paused",
    closed: "Closed",
  };

  return (
    <View style={styles.container}>
      {/* Filter chips */}
      <FlatList
        horizontal
        showsHorizontalScrollIndicator={false}
        style={styles.filtersContainer}
        contentContainerStyle={styles.filters}
        data={["all", ...JOB_STATUSES]}
        keyExtractor={(item) => item}
        renderItem={({ item: status }) => {
          const isActive = filter === status;
          const chipColor =
            status === "all"
              ? colors.primary
              : JOB_STATUS_COLORS[status as JobStatus];

          return (
            <TouchableOpacity
              style={[
                styles.chip,
                isActive && { backgroundColor: chipColor },
              ]}
              onPress={() => setFilter(status)}
            >
              <Text
                style={[styles.chipText, isActive && styles.chipTextActive]}
              >
                {STATUS_LABELS[status]}
              </Text>
            </TouchableOpacity>
          );
        }}
      />

      {/* Jobs list */}
      <FlatList
        data={jobs}
        keyExtractor={(item) => String(item.id)}
        renderItem={({ item }) => (
          <RecruiterJobCard
            job={item}
            onPress={() => router.push(`/recruiter/job/${item.id}`)}
          />
        )}
        contentContainerStyle={styles.list}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
        ListEmptyComponent={
          <View style={styles.empty}>
            <Ionicons
              name="briefcase-outline"
              size={48}
              color={colors.gray300}
            />
            <Text style={styles.emptyText}>No job orders yet</Text>
            <Text style={styles.emptyHint}>
              Create jobs on winnow.app for the full editor
            </Text>
          </View>
        }
        ListFooterComponent={
          jobs.length > 0 ? (
            <View style={styles.notice}>
              <Text style={styles.noticeText}>
                Create jobs on winnow.app for the full editor
              </Text>
            </View>
          ) : null
        }
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.gray50 },
  filtersContainer: { maxHeight: 52, flexGrow: 0 },
  filters: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    gap: spacing.xs,
  },
  chip: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    borderRadius: borderRadius.full,
    backgroundColor: colors.gray200,
    marginRight: spacing.xs,
  },
  chipText: {
    fontSize: fontSize.xs,
    fontWeight: "600",
    color: colors.gray600,
  },
  chipTextActive: {
    color: colors.white,
  },
  list: {
    padding: spacing.md,
    paddingBottom: spacing.xxl,
  },
  empty: {
    alignItems: "center",
    paddingTop: spacing.xxl,
  },
  emptyText: {
    fontSize: fontSize.lg,
    fontWeight: "600",
    color: colors.gray500,
    marginTop: spacing.md,
  },
  emptyHint: {
    fontSize: fontSize.sm,
    color: colors.gray400,
    marginTop: spacing.xs,
  },
  notice: {
    backgroundColor: colors.sage,
    borderRadius: borderRadius.md,
    padding: spacing.md,
    marginTop: spacing.md,
  },
  noticeText: {
    fontSize: fontSize.sm,
    color: colors.primary,
    textAlign: "center",
  },
});
