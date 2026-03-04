import { useEffect, useState } from "react";
import { View, Text, StyleSheet, ActivityIndicator } from "react-native";
import { api } from "../lib/api";
import { handleFeatureGateResponse } from "../lib/featureGate";
import type { StatusPrediction } from "../lib/match-feature-types";
import { colors, spacing, fontSize, borderRadius } from "../lib/theme";

interface Props {
  matchId: number;
}

const CONFIDENCE_COLORS: Record<string, { bg: string; text: string }> = {
  high: { bg: "#DCFCE7", text: "#166534" },
  medium: { bg: "#FEF3C7", text: "#92400E" },
  low: { bg: "#FEE2E2", text: "#991B1B" },
};

function confidenceLevel(score: number): string {
  if (score >= 0.7) return "high";
  if (score >= 0.4) return "medium";
  return "low";
}

export default function StatusPredictionCard({ matchId }: Props) {
  const [data, setData] = useState<StatusPrediction | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const res = await api.get(`/api/matches/${matchId}/status-prediction`);
        if (handleFeatureGateResponse(res)) return;
        if (res.ok) setData(await res.json());
      } catch {
        // Silently fail
      } finally {
        setLoading(false);
      }
    })();
  }, [matchId]);

  if (loading) return <ActivityIndicator style={{ marginVertical: spacing.md }} color={colors.primary} />;
  if (!data) return null;

  const level = confidenceLevel(data.confidence);
  const palette = CONFIDENCE_COLORS[level];

  return (
    <View style={styles.card}>
      <Text style={styles.title}>Status Prediction</Text>

      <View style={styles.row}>
        <View style={[styles.badge, { backgroundColor: colors.sage }]}>
          <Text style={[styles.badgeText, { color: colors.primary }]}>
            {data.predicted_stage.replace(/_/g, " ")}
          </Text>
        </View>
        <View style={[styles.badge, { backgroundColor: palette.bg }]}>
          <Text style={[styles.badgeText, { color: palette.text }]}>
            {Math.round(data.confidence * 100)}% confidence
          </Text>
        </View>
      </View>

      <Text style={styles.meta}>
        {data.days_since_applied} days since applied
      </Text>

      <Text style={styles.explanation}>{data.explanation}</Text>

      <View style={styles.milestone}>
        <Text style={styles.milestoneLabel}>Next Milestone</Text>
        <Text style={styles.milestoneText}>{data.next_milestone}</Text>
      </View>

      {data.tips.length > 0 && (
        <View style={styles.tips}>
          <Text style={styles.tipsLabel}>Tips</Text>
          {data.tips.map((tip, i) => (
            <Text key={i} style={styles.tipText}>
              {"\u2022"} {tip}
            </Text>
          ))}
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
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
  title: {
    fontSize: fontSize.lg,
    fontWeight: "600",
    color: colors.gray900,
    marginBottom: spacing.sm,
  },
  row: {
    flexDirection: "row",
    gap: spacing.sm,
    flexWrap: "wrap",
    marginBottom: spacing.sm,
  },
  badge: {
    borderRadius: borderRadius.full,
    paddingHorizontal: spacing.sm,
    paddingVertical: 3,
  },
  badgeText: {
    fontSize: fontSize.xs,
    fontWeight: "600",
    textTransform: "capitalize",
  },
  meta: {
    fontSize: fontSize.xs,
    color: colors.gray500,
    marginBottom: spacing.sm,
  },
  explanation: {
    fontSize: fontSize.sm,
    color: colors.gray700,
    lineHeight: 20,
    marginBottom: spacing.sm,
  },
  milestone: {
    backgroundColor: colors.gray50,
    borderRadius: borderRadius.md,
    padding: spacing.sm,
    marginBottom: spacing.sm,
  },
  milestoneLabel: {
    fontSize: fontSize.xs,
    fontWeight: "600",
    color: colors.gray500,
    marginBottom: 2,
  },
  milestoneText: {
    fontSize: fontSize.sm,
    color: colors.gray900,
  },
  tips: {
    marginTop: spacing.xs,
  },
  tipsLabel: {
    fontSize: fontSize.xs,
    fontWeight: "600",
    color: colors.gray500,
    marginBottom: spacing.xs,
  },
  tipText: {
    fontSize: fontSize.sm,
    color: colors.gray700,
    lineHeight: 20,
    marginBottom: 2,
  },
});
