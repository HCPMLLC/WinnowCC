import { useState, useEffect, useCallback } from "react";
import {
  View,
  Text,
  FlatList,
  TouchableOpacity,
  StyleSheet,
  RefreshControl,
  Alert,
} from "react-native";
import { useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { api } from "../../lib/api";
import LoadingSpinner from "../../components/LoadingSpinner";
import ApplicationCard from "../../components/ApplicationCard";
import { colors, spacing, fontSize, borderRadius } from "../../lib/theme";

interface MatchItem {
  id: number;
  job: {
    id: number;
    title: string;
    company: string;
  };
  match_score: number;
  application_status: string | null;
}

const FILTERS = [
  { key: "all", label: "All" },
  { key: "saved", label: "Saved" },
  { key: "applied", label: "Applied" },
  { key: "interviewing", label: "Interviewing" },
  { key: "offer", label: "Offer" },
  { key: "rejected", label: "Rejected" },
];

export default function ApplicationsScreen() {
  const router = useRouter();
  const [matches, setMatches] = useState<MatchItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [filter, setFilter] = useState("all");

  const loadData = useCallback(async () => {
    try {
      const res = await api.get("/api/matches/all");
      if (res.ok) {
        const data = await res.json();
        const items = (data.matches || data || []) as MatchItem[];
        setMatches(items.filter((m) => m.application_status != null));
      }
    } catch {
      Alert.alert("Error", "Could not load applications.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const onRefresh = () => {
    setRefreshing(true);
    loadData();
  };

  async function handleStatusChange(matchId: number, newStatus: string) {
    // Optimistic update
    setMatches((prev) =>
      prev.map((m) =>
        m.id === matchId ? { ...m, application_status: newStatus } : m,
      ),
    );
    try {
      const res = await api.patch(`/api/matches/${matchId}/status`, {
        status: newStatus,
      });
      if (!res.ok) {
        Alert.alert("Error", "Failed to update status.");
        loadData();
      }
    } catch {
      Alert.alert("Error", "Could not connect to server.");
      loadData();
    }
  }

  const filtered =
    filter === "all"
      ? matches
      : matches.filter((m) => m.application_status === filter);

  const counts: Record<string, number> = { all: matches.length };
  for (const m of matches) {
    if (m.application_status) {
      counts[m.application_status] = (counts[m.application_status] || 0) + 1;
    }
  }

  if (loading) return <LoadingSpinner />;

  return (
    <View style={styles.container}>
      {/* Filter chips */}
      <FlatList
        horizontal
        showsHorizontalScrollIndicator={false}
        data={FILTERS}
        keyExtractor={(item) => item.key}
        contentContainerStyle={styles.filterRow}
        renderItem={({ item }) => {
          const isActive = filter === item.key;
          const count = counts[item.key] || 0;
          return (
            <TouchableOpacity
              style={[styles.filterChip, isActive && styles.filterChipActive]}
              onPress={() => setFilter(item.key)}
            >
              <Text
                style={[
                  styles.filterChipText,
                  isActive && styles.filterChipTextActive,
                ]}
              >
                {item.label}
              </Text>
              {count > 0 && (
                <View
                  style={[
                    styles.countBadge,
                    isActive && styles.countBadgeActive,
                  ]}
                >
                  <Text
                    style={[
                      styles.countText,
                      isActive && styles.countTextActive,
                    ]}
                  >
                    {count}
                  </Text>
                </View>
              )}
            </TouchableOpacity>
          );
        }}
      />

      {/* Application list */}
      <FlatList
        data={filtered}
        keyExtractor={(item) => String(item.id)}
        contentContainerStyle={styles.list}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
        ListEmptyComponent={
          <View style={styles.empty}>
            <Ionicons
              name="clipboard-outline"
              size={48}
              color={colors.gray300}
            />
            <Text style={styles.emptyTitle}>No tracked applications</Text>
            <Text style={styles.emptyText}>
              Mark a job match as "Saved" or "Applied" to start tracking it
              here.
            </Text>
            <TouchableOpacity
              style={styles.goMatchesBtn}
              onPress={() => router.push("/(tabs)/matches")}
            >
              <Text style={styles.goMatchesBtnText}>Browse Matches</Text>
            </TouchableOpacity>
          </View>
        }
        renderItem={({ item }) => (
          <ApplicationCard
            id={item.id}
            title={item.job.title}
            company={item.job.company}
            matchScore={item.match_score}
            status={item.application_status || "saved"}
            onPress={() => router.push(`/match/${item.id}`)}
            onStatusChange={(s) => handleStatusChange(item.id, s)}
          />
        )}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.gray50 },
  filterRow: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    gap: spacing.xs,
  },
  filterChip: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: borderRadius.full,
    borderWidth: 1,
    borderColor: colors.gray300,
    backgroundColor: colors.white,
  },
  filterChipActive: {
    backgroundColor: colors.primary,
    borderColor: colors.primary,
  },
  filterChipText: {
    fontSize: fontSize.sm,
    fontWeight: "500",
    color: colors.gray600,
  },
  filterChipTextActive: {
    color: colors.gold,
  },
  countBadge: {
    backgroundColor: colors.gray200,
    borderRadius: borderRadius.full,
    paddingHorizontal: 6,
    paddingVertical: 1,
    minWidth: 20,
    alignItems: "center",
  },
  countBadgeActive: {
    backgroundColor: colors.primaryLight,
  },
  countText: {
    fontSize: fontSize.xs,
    fontWeight: "600",
    color: colors.gray600,
  },
  countTextActive: {
    color: colors.gold,
  },
  list: { padding: spacing.md, paddingBottom: spacing.xxl },
  empty: {
    alignItems: "center",
    paddingVertical: spacing.xxl,
  },
  emptyTitle: {
    fontSize: fontSize.lg,
    fontWeight: "700",
    color: colors.gray900,
    marginTop: spacing.md,
  },
  emptyText: {
    fontSize: fontSize.sm,
    color: colors.gray500,
    marginTop: spacing.sm,
    textAlign: "center",
    paddingHorizontal: spacing.lg,
  },
  goMatchesBtn: {
    backgroundColor: colors.gold,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.lg,
    borderRadius: borderRadius.md,
    marginTop: spacing.lg,
  },
  goMatchesBtnText: {
    fontSize: fontSize.md,
    fontWeight: "600",
    color: colors.primary,
  },
});
