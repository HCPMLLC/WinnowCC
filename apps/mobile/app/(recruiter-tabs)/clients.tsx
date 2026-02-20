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
import ClientCard from "../../components/ClientCard";
import AddClientForm from "../../components/AddClientForm";
import {
  CLIENT_STATUSES,
  CLIENT_STATUS_COLORS,
  type Client,
  type ClientStatus,
} from "../../lib/recruiter-types";
import { colors, spacing, fontSize, borderRadius } from "../../lib/theme";

export default function ClientsScreen() {
  const router = useRouter();
  const [clients, setClients] = useState<Client[]>([]);
  const [filter, setFilter] = useState<string>("all");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [showAddForm, setShowAddForm] = useState(false);

  const loadData = useCallback(async () => {
    try {
      const query = filter === "all" ? "" : `?status=${filter}`;
      const res = await api.get(`/api/recruiter/clients${query}`);
      if (res.ok) {
        const data = await res.json();
        setClients(Array.isArray(data) ? data : data.items ?? []);
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
    active: "Active",
    inactive: "Inactive",
    prospect: "Prospect",
  };

  return (
    <View style={styles.container}>
      {/* Filter chips */}
      <FlatList
        horizontal
        showsHorizontalScrollIndicator={false}
        style={styles.filtersContainer}
        contentContainerStyle={styles.filters}
        data={["all", ...CLIENT_STATUSES]}
        keyExtractor={(item) => item}
        renderItem={({ item: status }) => {
          const isActive = filter === status;
          const chipColor =
            status === "all"
              ? colors.primary
              : CLIENT_STATUS_COLORS[status as ClientStatus];

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

      {/* Clients list */}
      <FlatList
        data={clients}
        keyExtractor={(item) => String(item.id)}
        renderItem={({ item }) => (
          <ClientCard
            client={item}
            onPress={() => router.push(`/recruiter/client/${item.id}`)}
          />
        )}
        contentContainerStyle={styles.list}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
        ListEmptyComponent={
          <View style={styles.empty}>
            <Ionicons
              name="business-outline"
              size={48}
              color={colors.gray300}
            />
            <Text style={styles.emptyText}>No clients yet</Text>
            <Text style={styles.emptyHint}>
              Tap + to add your first client
            </Text>
          </View>
        }
      />

      {/* FAB */}
      <TouchableOpacity
        style={styles.fab}
        onPress={() => setShowAddForm(true)}
        activeOpacity={0.8}
      >
        <Ionicons name="add" size={28} color={colors.primary} />
      </TouchableOpacity>

      <AddClientForm
        visible={showAddForm}
        onClose={() => setShowAddForm(false)}
        onCreated={loadData}
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
