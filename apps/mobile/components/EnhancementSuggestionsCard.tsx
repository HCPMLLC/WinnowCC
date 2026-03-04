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
import type { EnhancementSuggestionsData, EnhancementSuggestion } from "../lib/match-feature-types";
import { colors, spacing, fontSize, borderRadius } from "../lib/theme";

const PRIORITY_COLORS: Record<string, { bg: string; text: string }> = {
  high: { bg: "#FEE2E2", text: "#991B1B" },
  medium: { bg: "#FEF3C7", text: "#92400E" },
  low: { bg: "#DCFCE7", text: "#166534" },
};

export default function EnhancementSuggestionsCard() {
  const [data, setData] = useState<EnhancementSuggestionsData | null>(null);
  const [loading, setLoading] = useState(false);
  const [polling, setPolling] = useState(false);

  const fetchSuggestions = useCallback(async () => {
    const res = await api.get("/api/profile/enhancement-suggestions");
    if (handleFeatureGateResponse(res)) return { status: "gated" } as EnhancementSuggestionsData;
    const d = await res.json();
    setData(d);
    return d as EnhancementSuggestionsData;
  }, []);

  usePolling<EnhancementSuggestionsData>({
    fetchFn: fetchSuggestions,
    intervalMs: 2000,
    shouldPoll: (d) => d.status === "generating",
    onComplete: (d) => {
      setData(d);
      setPolling(false);
    },
    enabled: polling,
  });

  const handleGenerate = async () => {
    setLoading(true);
    try {
      const res = await api.get("/api/profile/enhancement-suggestions");
      if (handleFeatureGateResponse(res)) return;
      if (res.ok) {
        const d = await res.json();
        setData(d);
        if (d.status === "generating") {
          setPolling(true);
        }
      }
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  const handleRegenerate = async () => {
    setLoading(true);
    try {
      const res = await api.post("/api/profile/enhancement-suggestions/regenerate");
      if (!handleFeatureGateResponse(res) && res.ok) {
        setData({ status: "generating" });
        setPolling(true);
      }
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  };

  if (!data) {
    return (
      <View style={styles.card}>
        <Text style={styles.title}>Profile Enhancements</Text>
        <Text style={styles.description}>
          Get AI-powered suggestions to improve your profile.
        </Text>
        <TouchableOpacity
          style={styles.actionBtn}
          onPress={handleGenerate}
          disabled={loading}
        >
          {loading ? (
            <ActivityIndicator color={colors.primary} />
          ) : (
            <Text style={styles.actionBtnText}>Generate Suggestions</Text>
          )}
        </TouchableOpacity>
      </View>
    );
  }

  if (data.status === "gated") return null;

  if (data.status === "generating") {
    return (
      <View style={styles.card}>
        <Text style={styles.title}>Profile Enhancements</Text>
        <ActivityIndicator color={colors.primary} />
        <Text style={styles.pendingText}>Analyzing your profile...</Text>
      </View>
    );
  }

  if (data.status === "failed") {
    return (
      <View style={styles.card}>
        <Text style={styles.title}>Profile Enhancements</Text>
        <Text style={styles.errorText}>{data.error_message || "Failed."}</Text>
        <TouchableOpacity style={styles.retryBtn} onPress={handleRegenerate} disabled={loading}>
          <Text style={styles.retryBtnText}>Retry</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <View style={styles.card}>
      <View style={styles.headerRow}>
        <Text style={styles.title}>Profile Enhancements</Text>
        <TouchableOpacity onPress={handleRegenerate} disabled={loading}>
          <Ionicons name="refresh" size={20} color={colors.gray500} />
        </TouchableOpacity>
      </View>

      {data.overall_assessment && (
        <View style={styles.assessment}>
          {data.overall_assessment.strengths.length > 0 && (
            <View style={styles.assessSection}>
              <Text style={styles.assessLabel}>Strengths</Text>
              {data.overall_assessment.strengths.map((s, i) => (
                <View key={i} style={styles.bulletRow}>
                  <Ionicons name="checkmark-circle" size={14} color={colors.green500} />
                  <Text style={styles.bulletText}>{s}</Text>
                </View>
              ))}
            </View>
          )}
          <View style={styles.assessSection}>
            <Text style={styles.assessLabel}>Biggest Opportunity</Text>
            <Text style={styles.opportunityText}>
              {data.overall_assessment.biggest_opportunity}
            </Text>
          </View>
        </View>
      )}

      {(data.suggestions || []).map((s: EnhancementSuggestion, i: number) => {
        const palette = PRIORITY_COLORS[s.priority] || PRIORITY_COLORS.medium;
        return (
          <ExpandableSection key={i} title={`${s.category}: ${s.issue}`}>
            <View style={styles.suggestionMeta}>
              <View style={[styles.priorityBadge, { backgroundColor: palette.bg }]}>
                <Text style={[styles.priorityText, { color: palette.text }]}>
                  {s.priority}
                </Text>
              </View>
              <Text style={styles.impactText}>Impact: {s.impact}</Text>
            </View>
            <Text style={styles.suggestionLabel}>Suggestion</Text>
            <Text style={styles.suggestionText}>{s.suggestion}</Text>
            <Text style={styles.suggestionLabel}>Example</Text>
            <Text style={styles.exampleText}>{s.example}</Text>
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
  headerRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: spacing.sm,
  },
  title: {
    fontSize: fontSize.lg,
    fontWeight: "600",
    color: colors.gray900,
    marginBottom: spacing.sm,
  },
  description: {
    fontSize: fontSize.sm,
    color: colors.gray500,
    marginBottom: spacing.md,
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
  assessment: {
    backgroundColor: colors.gray50,
    borderRadius: borderRadius.md,
    padding: spacing.sm,
    marginBottom: spacing.md,
  },
  assessSection: {
    marginBottom: spacing.sm,
  },
  assessLabel: {
    fontSize: fontSize.xs,
    fontWeight: "600",
    color: colors.gray500,
    marginBottom: spacing.xs,
  },
  bulletRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: spacing.xs,
    marginBottom: 4,
  },
  bulletText: {
    fontSize: fontSize.sm,
    color: colors.gray700,
    flex: 1,
  },
  opportunityText: {
    fontSize: fontSize.sm,
    color: colors.gray900,
    fontWeight: "500",
  },
  suggestionMeta: {
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
  impactText: {
    fontSize: fontSize.xs,
    color: colors.gray500,
  },
  suggestionLabel: {
    fontSize: fontSize.xs,
    fontWeight: "600",
    color: colors.gray500,
    marginBottom: 2,
  },
  suggestionText: {
    fontSize: fontSize.sm,
    color: colors.gray700,
    lineHeight: 20,
    marginBottom: spacing.sm,
  },
  exampleText: {
    fontSize: fontSize.sm,
    color: colors.gray600,
    fontStyle: "italic",
    lineHeight: 20,
  },
});
