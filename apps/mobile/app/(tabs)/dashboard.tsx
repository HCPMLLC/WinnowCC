import { useEffect, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
} from "react-native";
import { useRouter } from "expo-router";
import { useAuth } from "../../lib/auth";
import { api } from "../../lib/api";
import LoadingSpinner from "../../components/LoadingSpinner";
import { colors, spacing, fontSize, borderRadius } from "../../lib/theme";

interface Metrics {
  display_name: string | null;
  profile_completeness_score: number;
  qualified_jobs_count: number;
  submitted_applications_count: number;
  interviews_requested_count: number;
}

export default function DashboardScreen() {
  const { email } = useAuth();
  const router = useRouter();
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const loadData = async () => {
    try {
      const metricsRes = await api.get("/api/dashboard/metrics");
      if (metricsRes.ok) {
        setMetrics(await metricsRes.json());
      }
    } catch {
      // Silently fail — metrics are non-critical
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

  const cards = [
    {
      label: "Profile",
      value: `${metrics?.profile_completeness_score ?? 0}%`,
      color: colors.sage,
    },
    {
      label: "Qualified Jobs",
      value: String(metrics?.qualified_jobs_count ?? 0),
      color: colors.green500,
    },
    {
      label: "Applications",
      value: String(metrics?.submitted_applications_count ?? 0),
      color: colors.blue500,
    },
    {
      label: "Interviews",
      value: String(metrics?.interviews_requested_count ?? 0),
      color: colors.amber500,
    },
  ];

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
      }
    >
      <Text style={styles.greeting}>
        Welcome back
        {metrics?.display_name
          ? `, ${metrics.display_name}`
          : email
            ? `, ${email.split("@")[0]}`
            : ""}
      </Text>

      <View style={styles.grid}>
        {cards.map((card) => (
          <View key={card.label} style={styles.card}>
            <Text style={[styles.cardValue, { color: card.color }]}>
              {card.value}
            </Text>
            <Text style={styles.cardLabel}>{card.label}</Text>
          </View>
        ))}
      </View>

      <TouchableOpacity
        style={styles.cta}
        onPress={() => router.push("/(tabs)/matches")}
      >
        <Text style={styles.ctaText}>View Matches</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.gray50 },
  content: { padding: spacing.md },
  greeting: {
    fontSize: fontSize.xxl,
    fontWeight: "700",
    color: colors.gray900,
    marginBottom: spacing.sm,
  },
  grid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.md,
    marginBottom: spacing.lg,
  },
  card: {
    width: "47%",
    backgroundColor: colors.white,
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    alignItems: "center",
    shadowColor: "#000",
    shadowOpacity: 0.05,
    shadowRadius: 8,
    elevation: 2,
  },
  cardValue: {
    fontSize: fontSize.xxxl,
    fontWeight: "700",
  },
  cardLabel: {
    fontSize: fontSize.sm,
    color: colors.gray500,
    marginTop: spacing.xs,
  },
  cta: {
    backgroundColor: colors.gold,
    borderRadius: borderRadius.md,
    paddingVertical: spacing.md,
    alignItems: "center",
  },
  ctaText: {
    fontSize: fontSize.lg,
    fontWeight: "600",
    color: colors.primary,
  },
});
