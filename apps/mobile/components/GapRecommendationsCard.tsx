import { useState, useCallback } from "react";
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ActivityIndicator,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { api } from "../lib/api";
import { handleFeatureGateResponse } from "../lib/featureGate";
import { usePolling } from "../lib/usePolling";
import ExpandableSection from "./ExpandableSection";
import type { GapRecommendations, GapSkillRec } from "../lib/match-feature-types";
import { colors, spacing, fontSize, borderRadius } from "../lib/theme";

interface Props {
  matchId: number;
}

const PRIORITY_COLORS: Record<string, { bg: string; text: string }> = {
  high: { bg: "#FEE2E2", text: "#991B1B" },
  medium: { bg: "#FEF3C7", text: "#92400E" },
  low: { bg: "#DCFCE7", text: "#166534" },
};

export default function GapRecommendationsCard({ matchId }: Props) {
  const [data, setData] = useState<GapRecommendations | null>(null);
  const [requesting, setRequesting] = useState(false);
  const [polling, setPolling] = useState(false);

  const fetchRecs = useCallback(async () => {
    const res = await api.get(`/api/matches/${matchId}/gap-recs`);
    if (handleFeatureGateResponse(res)) return { status: "gated" } as GapRecommendations;
    const d = await res.json();
    setData(d);
    return d as GapRecommendations;
  }, [matchId]);

  usePolling<GapRecommendations>({
    fetchFn: fetchRecs,
    intervalMs: 3000,
    shouldPoll: (d) => d.status === "pending" || d.status === "processing",
    onComplete: (d) => {
      setData(d);
      setPolling(false);
    },
    enabled: polling,
  });

  const handleRequest = async () => {
    setRequesting(true);
    try {
      const res = await api.get(`/api/matches/${matchId}/gap-recs`);
      if (handleFeatureGateResponse(res)) return;
      if (res.ok) {
        const d = await res.json();
        setData(d);
        if (d.status === "pending" || d.status === "processing") {
          setPolling(true);
        }
      }
    } catch {
      // ignore
    } finally {
      setRequesting(false);
    }
  };

  const handleRetry = async () => {
    setRequesting(true);
    try {
      const res = await api.post(`/api/matches/${matchId}/gap-recs/retry`);
      if (!handleFeatureGateResponse(res) && res.ok) {
        setData({ status: "pending" });
        setPolling(true);
      }
    } catch {
      // ignore
    } finally {
      setRequesting(false);
    }
  };

  if (!data) {
    return (
      <View style={styles.card}>
        <Text style={styles.title}>Learning Plan</Text>
        <TouchableOpacity
          style={styles.actionBtn}
          onPress={handleRequest}
          disabled={requesting}
        >
          {requesting ? (
            <ActivityIndicator color={colors.primary} />
          ) : (
            <Text style={styles.actionBtnText}>Get Learning Plan</Text>
          )}
        </TouchableOpacity>
      </View>
    );
  }

  if (data.status === "gated") return null;

  if (data.status === "pending" || data.status === "processing") {
    return (
      <View style={styles.card}>
        <Text style={styles.title}>Learning Plan</Text>
        <ActivityIndicator color={colors.primary} />
        <Text style={styles.pendingText}>Generating recommendations...</Text>
      </View>
    );
  }

  if (data.status === "failed") {
    return (
      <View style={styles.card}>
        <Text style={styles.title}>Learning Plan</Text>
        <Text style={styles.errorText}>{data.error_message || "Failed."}</Text>
        <TouchableOpacity style={styles.retryBtn} onPress={handleRetry} disabled={requesting}>
          <Text style={styles.retryBtnText}>Retry</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <View style={styles.card}>
      <Text style={styles.title}>Learning Plan</Text>

      {data.overall_strategy && (
        <Text style={styles.strategy}>{data.overall_strategy}</Text>
      )}

      {(data.skill_recs || []).map((rec: GapSkillRec, i: number) => {
        const palette = PRIORITY_COLORS[rec.priority] || PRIORITY_COLORS.medium;
        return (
          <ExpandableSection key={i} title={rec.skill}>
            <View style={styles.recMeta}>
              <View style={[styles.priorityBadge, { backgroundColor: palette.bg }]}>
                <Text style={[styles.priorityText, { color: palette.text }]}>
                  {rec.priority} priority
                </Text>
              </View>
              <Text style={styles.timeEstimate}>{rec.time_estimate}</Text>
            </View>
            <Text style={styles.quickWinLabel}>Quick Win</Text>
            <Text style={styles.quickWinText}>{rec.quick_win}</Text>
            {rec.resources.length > 0 && (
              <View style={styles.resources}>
                <Text style={styles.resourcesLabel}>Resources</Text>
                {rec.resources.map((r, j) => (
                  <View key={j} style={styles.resourceRow}>
                    <Ionicons name="link" size={12} color={colors.blue500} />
                    <Text style={styles.resourceText}>{r.title} ({r.type})</Text>
                  </View>
                ))}
              </View>
            )}
          </ExpandableSection>
        );
      })}
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
  actionBtn: {
    backgroundColor: colors.gold,
    borderRadius: borderRadius.md,
    paddingVertical: spacing.sm,
    alignItems: "center",
  },
  actionBtnText: {
    fontSize: fontSize.sm,
    fontWeight: "600",
    color: colors.primary,
  },
  pendingText: {
    fontSize: fontSize.sm,
    color: colors.gray500,
    textAlign: "center",
    marginTop: spacing.sm,
  },
  errorText: {
    fontSize: fontSize.sm,
    color: colors.red500,
    marginBottom: spacing.sm,
  },
  retryBtn: {
    backgroundColor: colors.gold,
    borderRadius: borderRadius.md,
    paddingVertical: spacing.sm,
    alignItems: "center",
  },
  retryBtnText: {
    fontSize: fontSize.sm,
    fontWeight: "600",
    color: colors.primary,
  },
  strategy: {
    fontSize: fontSize.sm,
    color: colors.gray700,
    lineHeight: 20,
    marginBottom: spacing.md,
  },
  recMeta: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    marginBottom: spacing.sm,
  },
  priorityBadge: {
    borderRadius: borderRadius.full,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
  },
  priorityText: {
    fontSize: fontSize.xs,
    fontWeight: "600",
    textTransform: "capitalize",
  },
  timeEstimate: {
    fontSize: fontSize.xs,
    color: colors.gray500,
  },
  quickWinLabel: {
    fontSize: fontSize.xs,
    fontWeight: "600",
    color: colors.gray500,
    marginBottom: 2,
  },
  quickWinText: {
    fontSize: fontSize.sm,
    color: colors.gray700,
    lineHeight: 20,
    marginBottom: spacing.sm,
  },
  resources: {
    marginTop: spacing.xs,
  },
  resourcesLabel: {
    fontSize: fontSize.xs,
    fontWeight: "600",
    color: colors.gray500,
    marginBottom: spacing.xs,
  },
  resourceRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    marginBottom: 4,
  },
  resourceText: {
    fontSize: fontSize.xs,
    color: colors.blue500,
  },
});
