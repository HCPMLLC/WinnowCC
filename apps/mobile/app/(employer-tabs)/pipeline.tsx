import { useEffect, useState, useCallback } from "react";
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  TouchableOpacity,
  RefreshControl,
  ScrollView,
  Alert,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { api } from "../../lib/api";
import LoadingSpinner from "../../components/LoadingSpinner";
import EmployerPipelineCard from "../../components/EmployerPipelineCard";
import {
  PIPELINE_STATUSES,
  PIPELINE_STATUS_LABELS,
  type PipelineEntry,
  type PipelineStatus,
} from "../../lib/employer-types";
import { colors, spacing, fontSize, borderRadius } from "../../lib/theme";

const FILTERS = ["all", ...PIPELINE_STATUSES];

export default function EmployerPipelineScreen() {
  const [entries, setEntries] = useState<PipelineEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [statusFilter, setStatusFilter] = useState("all");

  const loadEntries = useCallback(async () => {
    try {
      const query =
        statusFilter !== "all" ? `?status=${statusFilter}` : "";
      const res = await api.get(`/api/employer/pipeline${query}`);
      if (res.ok) {
        const data = await res.json();
        setEntries(Array.isArray(data) ? data : data.entries ?? []);
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
    loadEntries();
  }, [loadEntries]);

  const onRefresh = () => {
    setRefreshing(true);
    loadEntries();
  };

  const handleStatusChange = async (id: number, newStatus: string) => {
    try {
      const res = await api.put(`/api/employer/pipeline/${id}`, {
        pipeline_status: newStatus,
      });
      if (res.ok) {
        loadEntries();
      } else {
        Alert.alert("Error", "Failed to update status.");
      }
    } catch {
      Alert.alert("Error", "Something went wrong.");
    }
  };

  const getFilterLabel = (f: string) => {
    if (f === "all") return "All";
    return PIPELINE_STATUS_LABELS[f as PipelineStatus] ?? f;
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
              {getFilterLabel(f)}
            </Text>
          </TouchableOpacity>
        ))}
      </ScrollView>

      <FlatList
        data={entries}
        keyExtractor={(item) => String(item.id)}
        renderItem={({ item }) => (
          <EmployerPipelineCard
            entry={item}
            onStatusChange={handleStatusChange}
          />
        )}
        ListEmptyComponent={
          <View style={styles.empty}>
            <Ionicons
              name="layers-outline"
              size={48}
              color={colors.gray300}
            />
            <Text style={styles.emptyTitle}>No candidates in pipeline</Text>
            <Text style={styles.emptyDesc}>
              Search and save candidates to build your talent pipeline
            </Text>
          </View>
        }
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
        contentContainerStyle={
          entries.length === 0 ? styles.emptyContainer : styles.listContent
        }
      />
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
  },
});
