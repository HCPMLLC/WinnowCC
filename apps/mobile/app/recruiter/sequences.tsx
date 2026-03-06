import { useEffect, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  RefreshControl,
  TouchableOpacity,
} from "react-native";
import { useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { api } from "../../lib/api";
import { handleFeatureGateResponse } from "../../lib/featureGate";
import LoadingSpinner from "../../components/LoadingSpinner";
import type { OutreachSequence } from "../../lib/recruiter-types";
import { colors, spacing, fontSize, borderRadius } from "../../lib/theme";

export default function RecruiterSequencesScreen() {
  const router = useRouter();
  const [sequences, setSequences] = useState<OutreachSequence[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const loadData = async () => {
    try {
      const res = await api.get("/api/recruiter/sequences");
      if (await handleFeatureGateResponse(res)) return;
      if (res.ok) {
        const data = await res.json();
        setSequences(Array.isArray(data) ? data : data.sequences ?? []);
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

  if (loading) return <LoadingSpinner />;

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
      }
    >
      <Text style={styles.pageTitle}>Outreach Sequences</Text>

      {sequences.length === 0 ? (
        <View style={styles.emptyCard}>
          <Ionicons name="mail-outline" size={40} color={colors.gray300} />
          <Text style={styles.emptyText}>
            No sequences yet. Create your first outreach sequence on winnow.app.
          </Text>
        </View>
      ) : (
        sequences.map((seq) => (
          <TouchableOpacity
            key={seq.id}
            style={styles.card}
            onPress={() => router.push(`/recruiter/sequence/${seq.id}`)}
            activeOpacity={0.7}
          >
            <View style={styles.cardHeader}>
              <Text style={styles.seqName} numberOfLines={1}>
                {seq.name}
              </Text>
              <View
                style={[
                  styles.activeBadge,
                  {
                    backgroundColor: seq.is_active
                      ? colors.green500
                      : colors.gray400,
                  },
                ]}
              >
                <Text style={styles.activeBadgeText}>
                  {seq.is_active ? "Active" : "Inactive"}
                </Text>
              </View>
            </View>

            {seq.description && (
              <Text style={styles.seqDesc} numberOfLines={2}>
                {seq.description}
              </Text>
            )}

            <View style={styles.statsRow}>
              <Text style={styles.statText}>
                {seq.steps?.length ?? 0} steps
              </Text>
              <Text style={styles.statDot}>&middot;</Text>
              <Text style={styles.statText}>
                {seq.total_enrolled} enrolled
              </Text>
              <Text style={styles.statDot}>&middot;</Text>
              <Text style={styles.statText}>{seq.total_sent} sent</Text>
            </View>

            <Ionicons
              name="chevron-forward"
              size={18}
              color={colors.gray400}
              style={styles.chevron}
            />
          </TouchableOpacity>
        ))
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.gray50 },
  content: { padding: spacing.md, paddingBottom: spacing.xxl },
  pageTitle: {
    fontSize: fontSize.xxl,
    fontWeight: "700",
    color: colors.gray900,
    marginBottom: spacing.lg,
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
  seqName: {
    fontSize: fontSize.md,
    fontWeight: "600",
    color: colors.gray900,
    flex: 1,
    marginRight: spacing.sm,
  },
  activeBadge: {
    borderRadius: borderRadius.full,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
  },
  activeBadgeText: {
    fontSize: fontSize.xs,
    fontWeight: "600",
    color: colors.white,
  },
  seqDesc: {
    fontSize: fontSize.sm,
    color: colors.gray500,
    marginBottom: spacing.sm,
  },
  statsRow: {
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
  chevron: {
    position: "absolute",
    right: spacing.md,
    top: "50%",
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
});
