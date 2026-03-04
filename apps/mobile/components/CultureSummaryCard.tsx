import { useEffect, useState } from "react";
import { View, Text, StyleSheet, ActivityIndicator } from "react-native";
import { api } from "../lib/api";
import ExpandableSection from "./ExpandableSection";
import type { CultureSummary } from "../lib/match-feature-types";
import { colors, spacing, fontSize, borderRadius } from "../lib/theme";

interface Props {
  jobId: number;
}

export default function CultureSummaryCard({ jobId }: Props) {
  const [data, setData] = useState<CultureSummary | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const res = await api.get(`/api/jobs/${jobId}/culture`);
        if (res.ok) setData(await res.json());
      } catch {
        // Silently hidden if error
      } finally {
        setLoading(false);
      }
    })();
  }, [jobId]);

  if (loading) return <ActivityIndicator style={{ marginVertical: spacing.md }} color={colors.primary} />;
  if (!data) return null;

  const tags = [
    data.work_style && `Work style: ${data.work_style}`,
    data.pace && `Pace: ${data.pace}`,
    data.remote_policy && `Remote: ${data.remote_policy}`,
    data.growth && `Growth: ${data.growth}`,
  ].filter(Boolean) as string[];

  return (
    <View style={styles.card}>
      <Text style={styles.title}>Company Culture</Text>
      <Text style={styles.summary}>{data.summary}</Text>

      {tags.length > 0 && (
        <View style={styles.tagsRow}>
          {tags.map((tag) => (
            <View key={tag} style={styles.tag}>
              <Text style={styles.tagText}>{tag}</Text>
            </View>
          ))}
        </View>
      )}

      {(data.values?.length ?? 0) > 0 && (
        <ExpandableSection title="Values">
          {data.values!.map((v, i) => (
            <Text key={i} style={styles.bulletText}>{"\u2022"} {v}</Text>
          ))}
        </ExpandableSection>
      )}

      {(data.signals?.length ?? 0) > 0 && (
        <ExpandableSection title="Signals">
          {data.signals!.map((s, i) => (
            <Text key={i} style={styles.bulletText}>{"\u2022"} {s}</Text>
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
  summary: {
    fontSize: fontSize.sm,
    color: colors.gray700,
    lineHeight: 20,
    marginBottom: spacing.sm,
  },
  tagsRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.xs,
    marginBottom: spacing.sm,
  },
  tag: {
    backgroundColor: colors.sage,
    borderRadius: borderRadius.full,
    paddingHorizontal: spacing.sm,
    paddingVertical: 3,
  },
  tagText: {
    fontSize: fontSize.xs,
    color: colors.primary,
    fontWeight: "500",
  },
  bulletText: {
    fontSize: fontSize.sm,
    color: colors.gray700,
    lineHeight: 20,
    marginBottom: spacing.xs,
  },
});
