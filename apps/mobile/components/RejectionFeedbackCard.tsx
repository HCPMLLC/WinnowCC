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
import type { RejectionFeedbackData } from "../lib/match-feature-types";
import { colors, spacing, fontSize, borderRadius } from "../lib/theme";

interface Props {
  matchId: number;
}

export default function RejectionFeedbackCard({ matchId }: Props) {
  const [data, setData] = useState<RejectionFeedbackData | null>(null);
  const [requesting, setRequesting] = useState(false);
  const [polling, setPolling] = useState(false);

  const fetchFeedback = useCallback(async () => {
    const res = await api.get(`/api/matches/${matchId}/rejection-feedback`);
    if (await handleFeatureGateResponse(res)) return { status: "gated" } as RejectionFeedbackData;
    const d = await res.json();
    setData(d);
    return d as RejectionFeedbackData;
  }, [matchId]);

  usePolling<RejectionFeedbackData>({
    fetchFn: fetchFeedback,
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
      const res = await api.post(`/api/matches/${matchId}/rejection-feedback`);
      if (await handleFeatureGateResponse(res)) return;
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
      const res = await api.post(`/api/matches/${matchId}/rejection-feedback/retry`);
      if (!(await handleFeatureGateResponse(res)) && res.ok) {
        setData({ status: "pending" });
        setPolling(true);
      }
    } catch {
      // ignore
    } finally {
      setRequesting(false);
    }
  };

  // Initial state: show button
  if (!data) {
    return (
      <View style={styles.card}>
        <Text style={styles.title}>Rejection Feedback</Text>
        <TouchableOpacity
          style={styles.actionBtn}
          onPress={handleRequest}
          disabled={requesting}
        >
          {requesting ? (
            <ActivityIndicator color={colors.primary} />
          ) : (
            <Text style={styles.actionBtnText}>Get Feedback</Text>
          )}
        </TouchableOpacity>
      </View>
    );
  }

  if (data.status === "gated") return null;

  if (data.status === "pending" || data.status === "processing") {
    return (
      <View style={styles.card}>
        <Text style={styles.title}>Rejection Feedback</Text>
        <ActivityIndicator color={colors.primary} />
        <Text style={styles.pendingText}>Analyzing feedback...</Text>
      </View>
    );
  }

  if (data.status === "failed") {
    return (
      <View style={styles.card}>
        <Text style={styles.title}>Rejection Feedback</Text>
        <Text style={styles.errorText}>{data.error_message || "Failed."}</Text>
        <TouchableOpacity style={styles.retryBtn} onPress={handleRetry} disabled={requesting}>
          <Text style={styles.retryBtnText}>Retry</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <View style={styles.card}>
      <Text style={styles.title}>Rejection Feedback</Text>

      {data.interpretation && (
        <Text style={styles.interpretation}>{data.interpretation}</Text>
      )}

      {(data.strengths?.length ?? 0) > 0 && (
        <View style={styles.section}>
          <Text style={styles.sectionLabel}>Your Strengths</Text>
          {data.strengths!.map((s, i) => (
            <View key={i} style={styles.bulletRow}>
              <Ionicons name="checkmark-circle" size={14} color={colors.green500} />
              <Text style={styles.bulletText}>{s}</Text>
            </View>
          ))}
        </View>
      )}

      {(data.likely_causes?.length ?? 0) > 0 && (
        <View style={styles.section}>
          <Text style={styles.sectionLabel}>Likely Causes</Text>
          {data.likely_causes!.map((c, i) => (
            <View key={i} style={styles.bulletRow}>
              <Ionicons name="alert-circle" size={14} color={colors.amber500} />
              <Text style={styles.bulletText}>{c}</Text>
            </View>
          ))}
        </View>
      )}

      {(data.next_steps?.length ?? 0) > 0 && (
        <View style={styles.section}>
          <Text style={styles.sectionLabel}>Next Steps</Text>
          {data.next_steps!.map((s, i) => (
            <Text key={i} style={styles.stepText}>{i + 1}. {s}</Text>
          ))}
        </View>
      )}

      {data.encouragement && (
        <View style={styles.encourageBox}>
          <Ionicons name="heart" size={16} color={colors.gold} />
          <Text style={styles.encourageText}>{data.encouragement}</Text>
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
  interpretation: {
    fontSize: fontSize.sm,
    color: colors.gray700,
    lineHeight: 20,
    marginBottom: spacing.md,
  },
  section: {
    marginBottom: spacing.md,
  },
  sectionLabel: {
    fontSize: fontSize.sm,
    fontWeight: "600",
    color: colors.gray900,
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
    lineHeight: 20,
  },
  stepText: {
    fontSize: fontSize.sm,
    color: colors.gray700,
    lineHeight: 20,
    marginBottom: 4,
  },
  encourageBox: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: spacing.sm,
    backgroundColor: "#FEF3C7",
    borderRadius: borderRadius.md,
    padding: spacing.sm,
  },
  encourageText: {
    fontSize: fontSize.sm,
    color: "#92400E",
    flex: 1,
    lineHeight: 20,
  },
});
