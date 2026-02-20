import { View, Text, StyleSheet } from "react-native";
import { Picker } from "@react-native-picker/picker";
import EmployerPipelineStatusChip from "./EmployerPipelineStatusChip";
import {
  PIPELINE_STATUSES,
  PIPELINE_STATUS_LABELS,
  type PipelineEntry,
  type PipelineStatus,
} from "../lib/employer-types";
import { colors, spacing, fontSize, borderRadius } from "../lib/theme";

interface Props {
  entry: PipelineEntry;
  onStatusChange: (id: number, status: string) => void;
}

export default function EmployerPipelineCard({ entry, onStatusChange }: Props) {
  const created = new Date(entry.created_at).toLocaleDateString();

  return (
    <View style={styles.card}>
      <View style={styles.header}>
        <Text style={styles.name}>
          Candidate #{entry.candidate_profile_id ?? entry.id}
        </Text>
        {entry.match_score != null && (
          <View style={styles.scoreBadge}>
            <Text style={styles.scoreText}>{entry.match_score}%</Text>
          </View>
        )}
      </View>

      <View style={styles.metaRow}>
        <EmployerPipelineStatusChip status={entry.pipeline_status} />
        <Text style={styles.date}>{created}</Text>
      </View>

      {entry.tags && entry.tags.length > 0 && (
        <View style={styles.tagsRow}>
          {entry.tags.map((tag) => (
            <View key={tag} style={styles.tag}>
              <Text style={styles.tagText}>{tag}</Text>
            </View>
          ))}
        </View>
      )}

      {entry.notes ? (
        <Text style={styles.notes} numberOfLines={2}>
          {entry.notes}
        </Text>
      ) : null}

      <View style={styles.pickerWrapper}>
        <Picker
          selectedValue={entry.pipeline_status}
          onValueChange={(value) => {
            if (value !== entry.pipeline_status) {
              onStatusChange(entry.id, value);
            }
          }}
          style={styles.picker}
        >
          {PIPELINE_STATUSES.map((s) => (
            <Picker.Item
              key={s}
              label={PIPELINE_STATUS_LABELS[s as PipelineStatus]}
              value={s}
            />
          ))}
        </Picker>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
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
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: spacing.sm,
  },
  name: {
    fontSize: fontSize.md,
    fontWeight: "600",
    color: colors.gray900,
    flex: 1,
  },
  scoreBadge: {
    backgroundColor: colors.sage,
    borderRadius: borderRadius.full,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
  },
  scoreText: {
    fontSize: fontSize.xs,
    fontWeight: "700",
    color: colors.primary,
  },
  metaRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    marginBottom: spacing.sm,
  },
  date: {
    fontSize: fontSize.xs,
    color: colors.gray400,
  },
  tagsRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.xs,
    marginBottom: spacing.sm,
  },
  tag: {
    backgroundColor: colors.gray100,
    borderRadius: borderRadius.full,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
  },
  tagText: {
    fontSize: fontSize.xs,
    color: colors.gray600,
  },
  notes: {
    fontSize: fontSize.sm,
    color: colors.gray500,
    marginBottom: spacing.sm,
  },
  pickerWrapper: {
    backgroundColor: colors.gray50,
    borderRadius: borderRadius.md,
    borderWidth: 1,
    borderColor: colors.gray200,
    overflow: "hidden",
  },
  picker: {
    color: colors.gray900,
    height: 44,
  },
});
