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
import PipelineCard from "../../components/PipelineCard";
import {
  PIPELINE_STAGES,
  STAGE_LABELS,
  STAGE_COLORS,
  type PipelineCandidate,
  type PipelineStage,
} from "../../lib/recruiter-types";
import { colors, spacing, fontSize, borderRadius } from "../../lib/theme";

export default function PipelineScreen() {
  const router = useRouter();
  const [candidates, setCandidates] = useState<PipelineCandidate[]>([]);
  const [filter, setFilter] = useState<string>("all");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const loadData = useCallback(async () => {
    try {
      const query = filter === "all" ? "" : `?stage=${filter}`;
      const res = await api.get(`/api/recruiter/pipeline${query}`);
      if (res.ok) {
        const data = await res.json();
        setCandidates(Array.isArray(data) ? data : data.items ?? []);
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

  // Count by stage for filter chips
  const countByStage = (stage: string) =>
    filter === "all"
      ? candidates.filter((c) => c.stage === stage).length
      : stage === filter
        ? candidates.length
        : 0;

  if (loading) return <LoadingSpinner />;

  return (
    <View style={styles.container}>
      {/* Filter chips */}
      <FlatList
        horizontal
        showsHorizontalScrollIndicator={false}
        style={styles.filtersContainer}
        contentContainerStyle={styles.filters}
        data={["all", ...PIPELINE_STAGES]}
        keyExtractor={(item) => item}
        renderItem={({ item: stage }) => {
          const isActive = filter === stage;
          const label = stage === "all" ? "All" : STAGE_LABELS[stage as PipelineStage];
          const chipColor =
            stage === "all"
              ? colors.primary
              : STAGE_COLORS[stage as PipelineStage];

          return (
            <TouchableOpacity
              style={[
                styles.chip,
                isActive && { backgroundColor: chipColor },
              ]}
              onPress={() => setFilter(stage)}
            >
              <Text
                style={[
                  styles.chipText,
                  isActive && styles.chipTextActive,
                ]}
              >
                {label}
                {filter === "all" && stage !== "all"
                  ? ` (${countByStage(stage)})`
                  : ""}
              </Text>
            </TouchableOpacity>
          );
        }}
      />

      {/* Pipeline list */}
      <FlatList
        data={candidates}
        keyExtractor={(item) => String(item.id)}
        renderItem={({ item }) => (
          <PipelineCard
            candidate={item}
            onPress={() => router.push(`/recruiter/pipeline/${item.id}`)}
          />
        )}
        contentContainerStyle={styles.list}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
        ListEmptyComponent={
          <View style={styles.empty}>
            <Ionicons name="funnel-outline" size={48} color={colors.gray300} />
            <Text style={styles.emptyText}>No candidates in pipeline</Text>
            <Text style={styles.emptyHint}>
              Tap + to add your first candidate
            </Text>
          </View>
        }
      />

      {/* FAB */}
      <TouchableOpacity
        style={styles.fab}
        onPress={() => router.push("/recruiter/pipeline/add")}
        activeOpacity={0.8}
      >
        <Ionicons name="add" size={28} color={colors.primary} />
      </TouchableOpacity>
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
    paddingBottom: 100,
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
  fab: {
    position: "absolute",
    bottom: 24,
    left: spacing.md,
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: colors.gold,
    justifyContent: "center",
    alignItems: "center",
    shadowColor: "#000",
    shadowOpacity: 0.2,
    shadowRadius: 8,
    shadowOffset: { width: 0, height: 4 },
    elevation: 6,
  },
});
