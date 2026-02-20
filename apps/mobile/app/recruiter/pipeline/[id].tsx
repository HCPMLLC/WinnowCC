import { useEffect, useState } from "react";
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
  Alert,
  RefreshControl,
  Linking,
} from "react-native";
import { Picker } from "@react-native-picker/picker";
import { useLocalSearchParams, useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { api } from "../../../lib/api";
import LoadingSpinner from "../../../components/LoadingSpinner";
import PipelineStageChip from "../../../components/PipelineStageChip";
import SkillTag from "../../../components/SkillTag";
import {
  PIPELINE_STAGES,
  STAGE_LABELS,
  type PipelineCandidate,
  type PipelineStage,
} from "../../../lib/recruiter-types";
import { colors, spacing, fontSize, borderRadius } from "../../../lib/theme";

export default function PipelineDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const [candidate, setCandidate] = useState<PipelineCandidate | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [editStage, setEditStage] = useState<string>("");
  const [editNotes, setEditNotes] = useState("");
  const [editRating, setEditRating] = useState(0);

  const loadData = async () => {
    try {
      const res = await api.get("/api/recruiter/pipeline");
      if (res.ok) {
        const data = await res.json();
        const items = Array.isArray(data) ? data : data.items ?? [];
        const found = items.find((c: PipelineCandidate) => c.id === Number(id));
        if (found) {
          setCandidate(found);
          setEditStage(found.stage);
          setEditNotes(found.notes ?? "");
          setEditRating(found.rating ?? 0);
        }
      }
    } catch {
      // Silently fail
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [id]);

  const onRefresh = () => {
    setRefreshing(true);
    loadData();
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const res = await api.put(`/api/recruiter/pipeline/${id}`, {
        stage: editStage,
        notes: editNotes.trim() || null,
        rating: editRating || null,
      });
      if (res.ok) {
        Alert.alert("Saved", "Pipeline entry updated.");
        loadData();
      } else {
        Alert.alert("Error", "Failed to save changes.");
      }
    } catch {
      Alert.alert("Error", "Something went wrong.");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = () => {
    Alert.alert(
      "Remove from Pipeline",
      "Are you sure you want to remove this candidate from the pipeline?",
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Remove",
          style: "destructive",
          onPress: async () => {
            try {
              await api.delete(`/api/recruiter/pipeline/${id}`);
              router.back();
            } catch {
              Alert.alert("Error", "Failed to remove candidate.");
            }
          },
        },
      ],
    );
  };

  if (loading) return <LoadingSpinner />;

  if (!candidate) {
    return (
      <View style={styles.emptyContainer}>
        <Text style={styles.emptyText}>Candidate not found</Text>
      </View>
    );
  }

  const name =
    candidate.candidate_name || candidate.external_name || "Unknown";
  const skills = candidate.skills ?? [];

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
      }
    >
      {/* Header */}
      <View style={styles.headerCard}>
        <Text style={styles.name}>{name}</Text>
        {candidate.headline && (
          <Text style={styles.headline}>{candidate.headline}</Text>
        )}
        <View style={styles.metaRow}>
          <PipelineStageChip stage={candidate.stage} />
          {candidate.match_score != null && (
            <View style={styles.scoreBadge}>
              <Text style={styles.scoreText}>
                {candidate.match_score}% match
              </Text>
            </View>
          )}
        </View>
      </View>

      {/* Contact info */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Contact</Text>
        {(candidate.external_email || candidate.candidate_name) && (
          <InfoRow
            icon="mail-outline"
            value={candidate.external_email ?? "—"}
          />
        )}
        {candidate.external_phone && (
          <InfoRow icon="call-outline" value={candidate.external_phone} />
        )}
        {(candidate.linkedin_url || candidate.external_linkedin) && (
          <TouchableOpacity
            onPress={() =>
              Linking.openURL(
                candidate.linkedin_url || candidate.external_linkedin || "",
              )
            }
          >
            <InfoRow
              icon="logo-linkedin"
              value={candidate.linkedin_url || candidate.external_linkedin || ""}
              isLink
            />
          </TouchableOpacity>
        )}
        {candidate.location && (
          <InfoRow icon="location-outline" value={candidate.location} />
        )}
        {candidate.current_company && (
          <InfoRow icon="business-outline" value={candidate.current_company} />
        )}
      </View>

      {/* Skills */}
      {skills.length > 0 && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Skills</Text>
          <View style={styles.skillsRow}>
            {skills.map((s) => (
              <SkillTag key={s} name={s} />
            ))}
          </View>
        </View>
      )}

      {/* Edit section */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Update</Text>

        <Text style={styles.label}>Stage</Text>
        <View style={styles.pickerWrapper}>
          <Picker
            selectedValue={editStage}
            onValueChange={setEditStage}
            style={styles.picker}
          >
            {PIPELINE_STAGES.map((s) => (
              <Picker.Item
                key={s}
                label={STAGE_LABELS[s as PipelineStage]}
                value={s}
              />
            ))}
          </Picker>
        </View>

        <Text style={styles.label}>Rating</Text>
        <View style={styles.ratingRow}>
          {[1, 2, 3, 4, 5].map((star) => (
            <TouchableOpacity key={star} onPress={() => setEditRating(star)}>
              <Ionicons
                name={star <= editRating ? "star" : "star-outline"}
                size={28}
                color={star <= editRating ? colors.gold : colors.gray300}
              />
            </TouchableOpacity>
          ))}
          {editRating > 0 && (
            <TouchableOpacity onPress={() => setEditRating(0)}>
              <Text style={styles.clearRating}>Clear</Text>
            </TouchableOpacity>
          )}
        </View>

        <Text style={styles.label}>Notes</Text>
        <TextInput
          style={[styles.input, styles.textArea]}
          placeholder="Add notes..."
          placeholderTextColor={colors.gray400}
          multiline
          numberOfLines={4}
          textAlignVertical="top"
          value={editNotes}
          onChangeText={setEditNotes}
        />

        <TouchableOpacity
          style={[styles.saveBtn, saving && styles.btnDisabled]}
          onPress={handleSave}
          disabled={saving}
        >
          <Text style={styles.saveBtnText}>
            {saving ? "Saving..." : "Save Changes"}
          </Text>
        </TouchableOpacity>
      </View>

      {/* Delete */}
      <TouchableOpacity style={styles.deleteBtn} onPress={handleDelete}>
        <Ionicons name="trash-outline" size={18} color={colors.red500} />
        <Text style={styles.deleteBtnText}>Remove from Pipeline</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

function InfoRow({
  icon,
  value,
  isLink,
}: {
  icon: string;
  value: string;
  isLink?: boolean;
}) {
  return (
    <View style={infoStyles.row}>
      <Ionicons
        name={icon as any}
        size={18}
        color={colors.gray500}
        style={infoStyles.icon}
      />
      <Text
        style={[infoStyles.text, isLink && infoStyles.link]}
        numberOfLines={1}
      >
        {value}
      </Text>
    </View>
  );
}

const infoStyles = StyleSheet.create({
  row: { flexDirection: "row", alignItems: "center", marginBottom: spacing.sm },
  icon: { marginRight: spacing.sm },
  text: { fontSize: fontSize.sm, color: colors.gray700, flex: 1 },
  link: { color: colors.blue500 },
});

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.gray50 },
  content: { padding: spacing.md, paddingBottom: spacing.xxl },
  emptyContainer: { flex: 1, justifyContent: "center", alignItems: "center" },
  emptyText: { fontSize: fontSize.md, color: colors.gray500 },
  headerCard: {
    backgroundColor: colors.white,
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    marginBottom: spacing.md,
    shadowColor: "#000",
    shadowOpacity: 0.05,
    shadowRadius: 8,
    elevation: 2,
  },
  name: {
    fontSize: fontSize.xl,
    fontWeight: "700",
    color: colors.gray900,
    marginBottom: spacing.xs,
  },
  headline: {
    fontSize: fontSize.sm,
    color: colors.gray600,
    marginBottom: spacing.sm,
  },
  metaRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
  },
  scoreBadge: {
    backgroundColor: colors.sage,
    borderRadius: borderRadius.full,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
  },
  scoreText: {
    fontSize: fontSize.xs,
    fontWeight: "600",
    color: colors.primary,
  },
  section: {
    backgroundColor: colors.white,
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    marginBottom: spacing.md,
    shadowColor: "#000",
    shadowOpacity: 0.05,
    shadowRadius: 8,
    elevation: 2,
  },
  sectionTitle: {
    fontSize: fontSize.lg,
    fontWeight: "700",
    color: colors.gray900,
    marginBottom: spacing.md,
  },
  skillsRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.xs,
  },
  label: {
    fontSize: fontSize.sm,
    fontWeight: "600",
    color: colors.gray700,
    marginBottom: spacing.xs,
  },
  input: {
    backgroundColor: colors.gray50,
    borderRadius: borderRadius.md,
    borderWidth: 1,
    borderColor: colors.gray200,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    fontSize: fontSize.md,
    color: colors.gray900,
    marginBottom: spacing.md,
  },
  textArea: { minHeight: 100 },
  pickerWrapper: {
    backgroundColor: colors.gray50,
    borderRadius: borderRadius.md,
    borderWidth: 1,
    borderColor: colors.gray200,
    marginBottom: spacing.md,
    overflow: "hidden",
  },
  picker: { color: colors.gray900 },
  ratingRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    marginBottom: spacing.md,
  },
  clearRating: {
    fontSize: fontSize.xs,
    color: colors.gray400,
    marginLeft: spacing.sm,
  },
  saveBtn: {
    backgroundColor: colors.gold,
    borderRadius: borderRadius.md,
    paddingVertical: spacing.md,
    alignItems: "center",
  },
  btnDisabled: { opacity: 0.6 },
  saveBtnText: {
    fontSize: fontSize.lg,
    fontWeight: "600",
    color: colors.primary,
  },
  deleteBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.xs,
    borderRadius: borderRadius.md,
    paddingVertical: spacing.md,
    borderWidth: 1,
    borderColor: colors.red500,
    marginBottom: spacing.lg,
  },
  deleteBtnText: {
    fontSize: fontSize.md,
    fontWeight: "600",
    color: colors.red500,
  },
});
