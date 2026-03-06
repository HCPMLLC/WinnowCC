import { useEffect, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  RefreshControl,
  TouchableOpacity,
  ActivityIndicator,
  Alert,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { api } from "../../lib/api";
import { handleFeatureGateResponse } from "../../lib/featureGate";
import LoadingSpinner from "../../components/LoadingSpinner";
import { colors, spacing, fontSize, borderRadius } from "../../lib/theme";

interface BoardConnection {
  id: number;
  board_name: string;
  status: string;
  created_at: string;
}

interface DistributionStatus {
  board_name: string;
  status: string;
  posted_at: string | null;
}

export default function EmployerDistributionScreen() {
  const [connections, setConnections] = useState<BoardConnection[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [distributing, setDistributing] = useState<number | null>(null);

  const loadData = async () => {
    try {
      const res = await api.get("/api/distribution/connections");
      if (await handleFeatureGateResponse(res)) return;
      if (res.ok) {
        const data = await res.json();
        setConnections(Array.isArray(data) ? data : data.connections ?? []);
      }
    } catch {
      // silently fail
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const onRefresh = () => {
    setRefreshing(true);
    loadData();
  };

  const handleDistribute = async (jobId: number) => {
    setDistributing(jobId);
    try {
      const res = await api.post(`/api/distribution/jobs/${jobId}/distribute`);
      if (await handleFeatureGateResponse(res)) return;
      if (res.ok) {
        Alert.alert("Success", "Job distributed to connected boards.");
      } else {
        const err = await res.json().catch(() => ({}));
        Alert.alert("Error", err.detail || "Distribution failed.");
      }
    } catch {
      Alert.alert("Error", "Something went wrong.");
    } finally {
      setDistributing(null);
    }
  };

  const STATUS_COLORS: Record<string, string> = {
    active: colors.green500,
    connected: colors.green500,
    pending: colors.amber500,
    disconnected: colors.gray400,
    error: colors.red500,
  };

  if (loading) return <LoadingSpinner />;

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
      }
    >
      <Text style={styles.sectionTitle}>Board Connections</Text>

      {connections.length === 0 ? (
        <View style={styles.emptyCard}>
          <Ionicons name="globe-outline" size={40} color={colors.gray300} />
          <Text style={styles.emptyText}>
            No board connections yet. Set up connections on winnow.app.
          </Text>
        </View>
      ) : (
        connections.map((conn) => (
          <View key={conn.id} style={styles.card}>
            <View style={styles.cardHeader}>
              <Text style={styles.boardName}>{conn.board_name}</Text>
              <View
                style={[
                  styles.statusBadge,
                  {
                    backgroundColor:
                      STATUS_COLORS[conn.status] || colors.gray400,
                  },
                ]}
              >
                <Text style={styles.statusBadgeText}>{conn.status}</Text>
              </View>
            </View>
            <Text style={styles.connDate}>
              Connected{" "}
              {new Date(conn.created_at).toLocaleDateString()}
            </Text>
          </View>
        ))
      )}

      <View style={styles.notice}>
        <Text style={styles.noticeText}>
          To distribute a job, go to the job details screen and tap
          "Distribute". Manage board connections at winnow.app.
        </Text>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.gray50 },
  content: { padding: spacing.md, paddingBottom: spacing.xxl },
  sectionTitle: {
    fontSize: fontSize.lg,
    fontWeight: "700",
    color: colors.gray900,
    marginBottom: spacing.md,
  },
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
  cardHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: spacing.xs,
  },
  boardName: {
    fontSize: fontSize.md,
    fontWeight: "600",
    color: colors.gray900,
  },
  statusBadge: {
    borderRadius: borderRadius.full,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
  },
  statusBadgeText: {
    fontSize: fontSize.xs,
    fontWeight: "600",
    color: colors.white,
    textTransform: "capitalize",
  },
  connDate: {
    fontSize: fontSize.xs,
    color: colors.gray400,
  },
  emptyCard: {
    backgroundColor: colors.white,
    borderRadius: borderRadius.lg,
    padding: spacing.xl,
    alignItems: "center",
    gap: spacing.sm,
  },
  emptyText: {
    fontSize: fontSize.sm,
    color: colors.gray400,
    textAlign: "center",
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
    lineHeight: 20,
  },
});
