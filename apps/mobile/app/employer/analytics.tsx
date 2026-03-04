import { useEffect, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  RefreshControl,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { api } from "../../lib/api";
import LoadingSpinner from "../../components/LoadingSpinner";
import type {
  AnalyticsOverview,
  CostMetrics,
  BoardRecommendation,
  FunnelData,
  AnalyticsRecommendation,
} from "../../lib/employer-types";
import { colors, spacing, fontSize, borderRadius } from "../../lib/theme";

const RECOMMENDATION_COLORS: Record<string, { bg: string; text: string }> = {
  high_performer: { bg: "#DCFCE7", text: "#166534" },
  moderate: { bg: "#FEF3C7", text: "#92400E" },
  low: { bg: "#FEE2E2", text: "#991B1B" },
};

export default function EmployerAnalyticsScreen() {
  const [overview, setOverview] = useState<AnalyticsOverview | null>(null);
  const [cost, setCost] = useState<CostMetrics | null>(null);
  const [recommendations, setRecommendations] = useState<
    BoardRecommendation[]
  >([]);
  const [funnel, setFunnel] = useState<FunnelData | null>(null);
  const [aiRecs, setAiRecs] = useState<AnalyticsRecommendation[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadData = async () => {
    try {
      setError(null);
      const [overviewRes, costRes, recRes, funnelRes, aiRecRes] = await Promise.all([
        api.get("/api/employer/analytics/overview"),
        api.get("/api/employer/analytics/cost").catch(() => null),
        api.get("/api/employer/analytics/recommendations").catch(() => null),
        api.get("/api/employer/analytics/funnel").catch(() => null),
        api.get("/api/employer/analytics/recommendations").catch(() => null),
      ]);

      if (overviewRes.ok) {
        setOverview(await overviewRes.json());
      } else {
        setError("Failed to load analytics.");
      }
      if (costRes && costRes.ok) {
        setCost(await costRes.json());
      }
      if (recRes && recRes.ok) {
        const data = await recRes.json();
        setRecommendations(
          Array.isArray(data) ? data : data.recommendations ?? [],
        );
      }
      if (funnelRes && funnelRes.ok) {
        setFunnel(await funnelRes.json());
      }
      if (aiRecRes && aiRecRes.ok) {
        const data = await aiRecRes.json();
        const recs = Array.isArray(data)
          ? data
          : data.ai_recommendations ?? data.recommendations ?? [];
        setAiRecs(recs);
      }
    } catch {
      setError("Could not connect to server.");
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

  if (error) {
    return (
      <View style={styles.errorContainer}>
        <Ionicons name="alert-circle-outline" size={48} color={colors.gray300} />
        <Text style={styles.errorText}>{error}</Text>
      </View>
    );
  }

  const statCards = [
    {
      label: "Active Jobs",
      value: String(overview?.active_jobs ?? 0),
      color: colors.sage,
      icon: "briefcase-outline" as const,
    },
    {
      label: "Impressions",
      value: String(overview?.total_impressions ?? 0),
      color: colors.blue500,
      icon: "eye-outline" as const,
    },
    {
      label: "Clicks",
      value: String(overview?.total_clicks ?? 0),
      color: colors.amber500,
      icon: "hand-left-outline" as const,
    },
    {
      label: "Applications",
      value: String(overview?.total_applications ?? 0),
      color: colors.green500,
      icon: "document-text-outline" as const,
    },
  ];

  const formatCurrency = (val: number) =>
    `$${val.toFixed(2)}`;

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
      }
    >
      {/* Overview stats */}
      <Text style={styles.sectionTitle}>Overview</Text>
      <View style={styles.grid}>
        {statCards.map((card) => (
          <View key={card.label} style={styles.statCard}>
            <Ionicons name={card.icon} size={20} color={card.color} />
            <Text style={[styles.statValue, { color: card.color }]}>
              {card.value}
            </Text>
            <Text style={styles.statLabel}>{card.label}</Text>
          </View>
        ))}
      </View>

      {/* Cost metrics */}
      {cost && (
        <>
          <Text style={styles.sectionTitle}>Cost Metrics</Text>
          <View style={styles.card}>
            <View style={styles.costRow}>
              <Text style={styles.costLabel}>Total Spend</Text>
              <Text style={styles.costValue}>
                {formatCurrency(cost.total_cost)}
              </Text>
            </View>
            <View style={styles.costRow}>
              <Text style={styles.costLabel}>Cost per Click</Text>
              <Text style={styles.costValue}>
                {formatCurrency(cost.cost_per_click)}
              </Text>
            </View>
            <View style={[styles.costRow, { borderBottomWidth: 0 }]}>
              <Text style={styles.costLabel}>Cost per Application</Text>
              <Text style={styles.costValue}>
                {formatCurrency(cost.cost_per_application)}
              </Text>
            </View>
          </View>
        </>
      )}

      {/* Hiring Funnel */}
      {funnel && funnel.stages && funnel.stages.length > 0 && (
        <>
          <Text style={styles.sectionTitle}>Hiring Funnel</Text>
          <View style={styles.card}>
            {funnel.stages.map((stage) => {
              const pct = funnel.total > 0 ? (stage.count / funnel.total) * 100 : 0;
              return (
                <View key={stage.stage} style={styles.funnelRow}>
                  <Text style={styles.funnelLabel}>{stage.stage}</Text>
                  <View style={styles.funnelBarTrack}>
                    <View
                      style={[
                        styles.funnelBarFill,
                        { width: `${Math.max(pct, 2)}%` },
                      ]}
                    />
                  </View>
                  <Text style={styles.funnelCount}>{stage.count}</Text>
                </View>
              );
            })}
          </View>
        </>
      )}

      {/* AI Recommendations */}
      {aiRecs.length > 0 && (
        <>
          <Text style={styles.sectionTitle}>AI Recommendations</Text>
          {aiRecs.map((rec, i) => (
            <View key={i} style={styles.card}>
              <Text style={styles.aiRecTitle}>{rec.title}</Text>
              <Text style={styles.aiRecDesc}>{rec.description}</Text>
            </View>
          ))}
        </>
      )}

      {/* Board recommendations */}
      {recommendations.length > 0 && (
        <>
          <Text style={styles.sectionTitle}>Board Recommendations</Text>
          {recommendations.map((rec) => {
            const palette =
              RECOMMENDATION_COLORS[rec.recommendation] ??
              RECOMMENDATION_COLORS.moderate;
            return (
              <View key={rec.board_connection_id} style={styles.card}>
                <View style={styles.recHeader}>
                  <Text style={styles.recBoard}>
                    Board #{rec.board_connection_id}
                  </Text>
                  <View
                    style={[styles.recBadge, { backgroundColor: palette.bg }]}
                  >
                    <Text style={[styles.recBadgeText, { color: palette.text }]}>
                      {rec.recommendation.replace(/_/g, " ")}
                    </Text>
                  </View>
                </View>
                <View style={styles.recStats}>
                  <Text style={styles.recStat}>
                    {rec.total_applications} applications
                  </Text>
                  <Text style={styles.recStatDot}>&middot;</Text>
                  <Text style={styles.recStat}>
                    {rec.total_clicks} clicks
                  </Text>
                  <Text style={styles.recStatDot}>&middot;</Text>
                  <Text style={styles.recStat}>
                    {formatCurrency(rec.cost_per_application)}/app
                  </Text>
                </View>
              </View>
            );
          })}
        </>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.gray50 },
  content: { padding: spacing.md, paddingBottom: spacing.xxl },
  errorContainer: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    padding: spacing.xl,
    backgroundColor: colors.gray50,
  },
  errorText: {
    fontSize: fontSize.md,
    color: colors.gray500,
    marginTop: spacing.md,
    textAlign: "center",
  },
  sectionTitle: {
    fontSize: fontSize.lg,
    fontWeight: "700",
    color: colors.gray900,
    marginBottom: spacing.md,
  },
  grid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.md,
    marginBottom: spacing.lg,
  },
  statCard: {
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
  statValue: {
    fontSize: fontSize.xxxl,
    fontWeight: "700",
    marginTop: spacing.xs,
  },
  statLabel: {
    fontSize: fontSize.sm,
    color: colors.gray500,
    marginTop: spacing.xs,
  },
  card: {
    backgroundColor: colors.white,
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    marginBottom: spacing.md,
    shadowColor: "#000",
    shadowOpacity: 0.05,
    shadowRadius: 8,
    elevation: 2,
  },
  costRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.gray100,
  },
  costLabel: {
    fontSize: fontSize.md,
    color: colors.gray700,
  },
  costValue: {
    fontSize: fontSize.md,
    fontWeight: "700",
    color: colors.gray900,
  },
  recHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: spacing.sm,
  },
  recBoard: {
    fontSize: fontSize.md,
    fontWeight: "600",
    color: colors.gray900,
  },
  recBadge: {
    borderRadius: borderRadius.full,
    paddingHorizontal: spacing.sm,
    paddingVertical: 3,
  },
  recBadgeText: {
    fontSize: fontSize.xs,
    fontWeight: "600",
    textTransform: "capitalize",
  },
  recStats: {
    flexDirection: "row",
    alignItems: "center",
  },
  recStat: {
    fontSize: fontSize.xs,
    color: colors.gray500,
  },
  recStatDot: {
    marginHorizontal: spacing.xs,
    color: colors.gray300,
  },
  funnelRow: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: spacing.sm,
    gap: spacing.sm,
  },
  funnelLabel: {
    fontSize: fontSize.xs,
    color: colors.gray700,
    width: 80,
    textTransform: "capitalize",
  },
  funnelBarTrack: {
    flex: 1,
    height: 16,
    backgroundColor: colors.gray100,
    borderRadius: borderRadius.sm,
    overflow: "hidden",
  },
  funnelBarFill: {
    height: 16,
    backgroundColor: colors.gold,
    borderRadius: borderRadius.sm,
  },
  funnelCount: {
    fontSize: fontSize.xs,
    fontWeight: "600",
    color: colors.gray900,
    width: 30,
    textAlign: "right",
  },
  aiRecTitle: {
    fontSize: fontSize.md,
    fontWeight: "600",
    color: colors.gray900,
    marginBottom: spacing.xs,
  },
  aiRecDesc: {
    fontSize: fontSize.sm,
    color: colors.gray600,
    lineHeight: 20,
  },
});
