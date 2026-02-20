import { useEffect, useState, useCallback } from "react";
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  RefreshControl,
  ScrollView,
} from "react-native";
import { useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { api } from "../../lib/api";
import LoadingSpinner from "../../components/LoadingSpinner";
import StatusBadge from "../../components/StatusBadge";
import { colors, spacing, fontSize, borderRadius } from "../../lib/theme";

interface EmployerJob {
  id: number;
  title: string;
  status: string;
  location: string | null;
  remote_policy: string | null;
  employment_type: string | null;
  view_count: number;
  application_count: number;
  created_at: string;
  posted_at: string | null;
}

const FILTERS = ["all", "draft", "active", "paused", "closed"];

export default function EmployerJobsScreen() {
  const router = useRouter();
  const [jobs, setJobs] = useState<EmployerJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [statusFilter, setStatusFilter] = useState("all");

  const loadJobs = useCallback(async () => {
    try {
      const query = statusFilter !== "all" ? `?status=${statusFilter}` : "";
      const res = await api.get(`/api/employer/jobs${query}`);
      if (res.ok) {
        setJobs(await res.json());
      }
    } catch {
      // Silently fail
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    setLoading(true);
    loadJobs();
  }, [loadJobs]);

  const onRefresh = () => {
    setRefreshing(true);
    loadJobs();
  };

  if (loading && !refreshing) return <LoadingSpinner />;

  return (
    <View style={styles.container}>
      {/* Filter chips */}
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        style={styles.filterBar}
        contentContainerStyle={styles.filterContent}
      >
        {FILTERS.map((f) => (
          <TouchableOpacity
            key={f}
            style={[
              styles.filterChip,
              statusFilter === f && styles.filterChipActive,
            ]}
            onPress={() => setStatusFilter(f)}
          >
            <Text
              style={[
                styles.filterText,
                statusFilter === f && styles.filterTextActive,
              ]}
            >
              {f.charAt(0).toUpperCase() + f.slice(1)}
            </Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      <FlatList
        data={jobs}
        keyExtractor={(item) => String(item.id)}
        renderItem={({ item }) => (
          <TouchableOpacity
            style={styles.jobCard}
            onPress={() => router.push(`/employer/job/${item.id}`)}
          >
            <View style={styles.jobHeader}>
              <Text style={styles.jobTitle} numberOfLines={1}>
                {item.title}
              </Text>
              <StatusBadge status={item.status} />
            </View>

            <View style={styles.jobMeta}>
              {item.location && (
                <View style={styles.metaItem}>
                  <Ionicons
                    name="location-outline"
                    size={14}
                    color={colors.gray500}
                  />
                  <Text style={styles.metaText}>{item.location}</Text>
                </View>
              )}
              {item.remote_policy && (
                <View style={styles.metaItem}>
                  <Ionicons
                    name="globe-outline"
                    size={14}
                    color={colors.gray500}
                  />
                  <Text style={styles.metaText}>{item.remote_policy}</Text>
                </View>
              )}
            </View>

            <View style={styles.jobStats}>
              <Text style={styles.statText}>
                {item.view_count} views
              </Text>
              <Text style={styles.statDot}>&middot;</Text>
              <Text style={styles.statText}>
                {item.application_count} applications
              </Text>
            </View>
          </TouchableOpacity>
        )}
        ListEmptyComponent={
          <View style={styles.empty}>
            <Ionicons
              name="briefcase-outline"
              size={48}
              color={colors.gray300}
            />
            <Text style={styles.emptyTitle}>No jobs yet</Text>
            <Text style={styles.emptyDesc}>
              Post your first job to start attracting candidates
            </Text>
            <TouchableOpacity
              style={styles.emptyCta}
              onPress={() => router.push("/employer/job/new")}
            >
              <Text style={styles.emptyCtaText}>Post a Job</Text>
            </TouchableOpacity>
          </View>
        }
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
        contentContainerStyle={
          jobs.length === 0 ? styles.emptyContainer : styles.listContent
        }
      />

      {/* FAB */}
      {jobs.length > 0 && (
        <TouchableOpacity
          style={styles.fab}
          onPress={() => router.push("/employer/job/new")}
        >
          <Ionicons name="add" size={28} color={colors.primary} />
        </TouchableOpacity>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.gray50 },
  filterBar: {
    maxHeight: 52,
    backgroundColor: colors.white,
    borderBottomWidth: 1,
    borderBottomColor: colors.gray200,
  },
  filterContent: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    gap: spacing.sm,
  },
  filterChip: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    borderRadius: borderRadius.full,
    backgroundColor: colors.gray100,
  },
  filterChipActive: {
    backgroundColor: colors.primary,
  },
  filterText: {
    fontSize: fontSize.sm,
    fontWeight: "500",
    color: colors.gray600,
  },
  filterTextActive: {
    color: colors.gold,
  },
  listContent: { padding: spacing.md },
  jobCard: {
    backgroundColor: colors.white,
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    marginBottom: spacing.sm,
    shadowColor: "#000",
    shadowOpacity: 0.05,
    shadowRadius: 8,
    elevation: 2,
  },
  jobHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: spacing.sm,
  },
  jobTitle: {
    flex: 1,
    fontSize: fontSize.md,
    fontWeight: "600",
    color: colors.gray900,
    marginRight: spacing.sm,
  },
  jobMeta: {
    flexDirection: "row",
    gap: spacing.md,
    marginBottom: spacing.sm,
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
  jobStats: {
    flexDirection: "row",
    alignItems: "center",
  },
  statText: {
    fontSize: fontSize.xs,
    color: colors.gray400,
  },
  statDot: {
    marginHorizontal: spacing.xs,
    color: colors.gray300,
  },
  emptyContainer: { flexGrow: 1 },
  empty: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: spacing.xl,
  },
  emptyTitle: {
    fontSize: fontSize.xl,
    fontWeight: "700",
    color: colors.gray900,
    marginTop: spacing.md,
  },
  emptyDesc: {
    fontSize: fontSize.sm,
    color: colors.gray500,
    textAlign: "center",
    marginTop: spacing.xs,
    marginBottom: spacing.lg,
  },
  emptyCta: {
    backgroundColor: colors.gold,
    borderRadius: borderRadius.md,
    paddingHorizontal: spacing.xl,
    paddingVertical: spacing.sm,
  },
  emptyCtaText: {
    fontSize: fontSize.md,
    fontWeight: "600",
    color: colors.primary,
  },
  fab: {
    position: "absolute",
    bottom: spacing.lg,
    right: spacing.lg,
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: colors.gold,
    alignItems: "center",
    justifyContent: "center",
    shadowColor: "#000",
    shadowOpacity: 0.15,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 4 },
    elevation: 6,
  },
});
