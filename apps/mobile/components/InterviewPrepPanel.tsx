import { useState, useCallback } from "react";
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  ActivityIndicator,
} from "react-native";
import { api } from "../lib/api";
import { handleFeatureGateResponse } from "../lib/featureGate";
import { usePolling } from "../lib/usePolling";
import ExpandableSection from "./ExpandableSection";
import type { InterviewPrepData, InterviewQuestion } from "../lib/match-feature-types";
import { colors, spacing, fontSize, borderRadius } from "../lib/theme";

interface Props {
  matchId: number;
}

export default function InterviewPrepPanel({ matchId }: Props) {
  const [data, setData] = useState<InterviewPrepData | null>(null);
  const [loading, setLoading] = useState(true);
  const [retrying, setRetrying] = useState(false);

  const fetchPrep = useCallback(async () => {
    const res = await api.get(`/api/matches/${matchId}/interview-prep`);
    if (await handleFeatureGateResponse(res)) {
      setLoading(false);
      return { status: "gated" } as InterviewPrepData;
    }
    const d = await res.json();
    setData(d);
    setLoading(false);
    return d as InterviewPrepData;
  }, [matchId]);

  usePolling<InterviewPrepData>({
    fetchFn: fetchPrep,
    intervalMs: 2000,
    shouldPoll: (d) => d.status === "pending" || d.status === "processing",
    onComplete: (d) => setData(d),
    enabled: true,
  });

  const handleRetry = async () => {
    setRetrying(true);
    try {
      const res = await api.post(`/api/matches/${matchId}/interview-prep/retry`);
      if (!(await handleFeatureGateResponse(res)) && res.ok) {
        setData({ status: "pending" });
      }
    } catch {
      // ignore
    } finally {
      setRetrying(false);
    }
  };

  if (loading) {
    return <ActivityIndicator style={{ marginVertical: spacing.md }} color={colors.primary} />;
  }

  if (!data || data.status === "gated") return null;

  if (data.status === "pending" || data.status === "processing") {
    return (
      <View style={styles.card}>
        <Text style={styles.title}>Interview Prep</Text>
        <ActivityIndicator color={colors.primary} />
        <Text style={styles.pendingText}>Generating interview prep...</Text>
      </View>
    );
  }

  if (data.status === "failed") {
    return (
      <View style={styles.card}>
        <Text style={styles.title}>Interview Prep</Text>
        <Text style={styles.errorText}>
          {data.error_message || "Failed to generate."}
        </Text>
        <TouchableOpacity style={styles.retryBtn} onPress={handleRetry} disabled={retrying}>
          <Text style={styles.retryBtnText}>{retrying ? "Retrying..." : "Retry"}</Text>
        </TouchableOpacity>
      </View>
    );
  }

  // Group questions by category
  const categories: Record<string, InterviewQuestion[]> = {};
  (data.questions || []).forEach((q) => {
    const cat = q.category || "General";
    if (!categories[cat]) categories[cat] = [];
    categories[cat].push(q);
  });

  return (
    <View style={styles.card}>
      <Text style={styles.title}>Interview Prep</Text>

      {Object.entries(categories).map(([cat, questions]) => (
        <ExpandableSection key={cat} title={`${cat} (${questions.length})`}>
          {questions.map((q, i) => (
            <View key={i} style={styles.questionItem}>
              <Text style={styles.questionText}>{q.question}</Text>
              {q.star_answer && (
                <View style={styles.starBox}>
                  <Text style={styles.starLabel}>S: <Text style={styles.starValue}>{q.star_answer.situation}</Text></Text>
                  <Text style={styles.starLabel}>T: <Text style={styles.starValue}>{q.star_answer.task}</Text></Text>
                  <Text style={styles.starLabel}>A: <Text style={styles.starValue}>{q.star_answer.action}</Text></Text>
                  <Text style={styles.starLabel}>R: <Text style={styles.starValue}>{q.star_answer.result}</Text></Text>
                </View>
              )}
            </View>
          ))}
        </ExpandableSection>
      ))}

      {(data.company_insights?.length ?? 0) > 0 && (
        <ExpandableSection title="Company Insights">
          {data.company_insights!.map((insight, i) => (
            <Text key={i} style={styles.bulletText}>{"\u2022"} {insight}</Text>
          ))}
        </ExpandableSection>
      )}

      {(data.gap_strategies?.length ?? 0) > 0 && (
        <ExpandableSection title="Gap Strategies">
          {data.gap_strategies!.map((s, i) => (
            <Text key={i} style={styles.bulletText}>{"\u2022"} {s}</Text>
          ))}
        </ExpandableSection>
      )}

      {(data.closing_questions?.length ?? 0) > 0 && (
        <ExpandableSection title="Closing Questions">
          {data.closing_questions!.map((q, i) => (
            <Text key={i} style={styles.bulletText}>{"\u2022"} {q}</Text>
          ))}
        </ExpandableSection>
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
  questionItem: {
    marginBottom: spacing.sm,
    paddingBottom: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.gray100,
  },
  questionText: {
    fontSize: fontSize.sm,
    fontWeight: "600",
    color: colors.gray900,
    marginBottom: spacing.xs,
  },
  starBox: {
    backgroundColor: colors.gray50,
    borderRadius: borderRadius.md,
    padding: spacing.sm,
  },
  starLabel: {
    fontSize: fontSize.xs,
    fontWeight: "700",
    color: colors.primary,
    marginBottom: 2,
  },
  starValue: {
    fontWeight: "400",
    color: colors.gray700,
  },
  bulletText: {
    fontSize: fontSize.sm,
    color: colors.gray700,
    lineHeight: 20,
    marginBottom: spacing.xs,
  },
});
