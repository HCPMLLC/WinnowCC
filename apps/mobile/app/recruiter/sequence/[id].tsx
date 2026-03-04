import { useEffect, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  RefreshControl,
  TextInput,
  TouchableOpacity,
  Alert,
  ActivityIndicator,
} from "react-native";
import { useLocalSearchParams } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { api } from "../../../lib/api";
import { handleFeatureGateResponse } from "../../../lib/featureGate";
import LoadingSpinner from "../../../components/LoadingSpinner";
import ExpandableSection from "../../../components/ExpandableSection";
import type {
  OutreachSequence,
  OutreachEnrollment,
} from "../../../lib/recruiter-types";
import { colors, spacing, fontSize, borderRadius } from "../../../lib/theme";

export default function SequenceDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const [sequence, setSequence] = useState<OutreachSequence | null>(null);
  const [enrollments, setEnrollments] = useState<OutreachEnrollment[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [editName, setEditName] = useState("");
  const [editDesc, setEditDesc] = useState("");

  const loadData = async () => {
    try {
      const [seqRes, enrollRes] = await Promise.all([
        api.get(`/api/recruiter/sequences/${id}`),
        api.get(`/api/recruiter/sequences/${id}/enrollments`).catch(() => null),
      ]);
      if (handleFeatureGateResponse(seqRes)) return;
      if (seqRes.ok) {
        const s = await seqRes.json();
        setSequence(s);
        setEditName(s.name);
        setEditDesc(s.description ?? "");
      }
      if (enrollRes && enrollRes.ok) {
        const data = await enrollRes.json();
        setEnrollments(
          Array.isArray(data) ? data : data.enrollments ?? [],
        );
      }
    } catch {
      // silently fail
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
    if (!editName.trim()) {
      Alert.alert("Required", "Sequence name is required.");
      return;
    }
    setSaving(true);
    try {
      const res = await api.patch(`/api/recruiter/sequences/${id}`, {
        name: editName.trim(),
        description: editDesc.trim() || null,
      });
      if (res.ok) {
        Alert.alert("Saved", "Sequence updated.");
        loadData();
      } else {
        Alert.alert("Error", "Failed to save.");
      }
    } catch {
      Alert.alert("Error", "Something went wrong.");
    } finally {
      setSaving(false);
    }
  };

  const ENROLLMENT_COLORS: Record<string, string> = {
    active: colors.green500,
    completed: colors.blue500,
    paused: colors.amber500,
    bounced: colors.red500,
  };

  if (loading) return <LoadingSpinner />;
  if (!sequence) {
    return (
      <View style={styles.center}>
        <Text style={styles.errorText}>Sequence not found.</Text>
      </View>
    );
  }

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
      }
    >
      {/* Edit Name/Description */}
      <Text style={styles.label}>Sequence Name</Text>
      <TextInput
        style={styles.input}
        value={editName}
        onChangeText={setEditName}
        placeholder="Sequence name"
        placeholderTextColor={colors.gray400}
      />

      <Text style={styles.label}>Description</Text>
      <TextInput
        style={[styles.input, styles.textArea]}
        value={editDesc}
        onChangeText={setEditDesc}
        placeholder="Optional description"
        placeholderTextColor={colors.gray400}
        multiline
        numberOfLines={3}
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

      {/* Steps */}
      <Text style={styles.sectionTitle}>
        Steps ({sequence.steps?.length ?? 0})
      </Text>
      {(sequence.steps || []).map((step) => (
        <ExpandableSection
          key={step.id}
          title={`Step ${step.step_number} — ${step.channel} (${step.delay_days}d delay)`}
        >
          <Text style={styles.stepLabel}>Subject</Text>
          <Text style={styles.stepText}>{step.subject}</Text>
          <Text style={styles.stepLabel}>Body</Text>
          <Text style={styles.stepBody}>{step.body}</Text>
        </ExpandableSection>
      ))}

      {/* Enrollments */}
      <Text style={styles.sectionTitle}>
        Enrollments ({enrollments.length})
      </Text>
      {enrollments.length === 0 ? (
        <View style={styles.emptyCard}>
          <Text style={styles.emptyText}>No enrollments yet.</Text>
        </View>
      ) : (
        enrollments.map((e) => (
          <View key={e.id} style={styles.enrollmentCard}>
            <View style={styles.enrollHeader}>
              <Text style={styles.enrollName}>
                {e.candidate_name || e.candidate_email || `#${e.id}`}
              </Text>
              <View
                style={[
                  styles.enrollBadge,
                  {
                    backgroundColor:
                      ENROLLMENT_COLORS[e.status] || colors.gray400,
                  },
                ]}
              >
                <Text style={styles.enrollBadgeText}>{e.status}</Text>
              </View>
            </View>
            <Text style={styles.enrollMeta}>
              Step {e.current_step} &middot;{" "}
              {new Date(e.enrolled_at).toLocaleDateString()}
            </Text>
          </View>
        ))
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.gray50 },
  content: { padding: spacing.md, paddingBottom: spacing.xxl },
  center: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: colors.gray50,
  },
  errorText: {
    fontSize: fontSize.md,
    color: colors.gray500,
  },
  label: {
    fontSize: fontSize.sm,
    fontWeight: "600",
    color: colors.gray700,
    marginBottom: spacing.xs,
  },
  input: {
    backgroundColor: colors.white,
    borderRadius: borderRadius.md,
    borderWidth: 1,
    borderColor: colors.gray200,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    fontSize: fontSize.md,
    color: colors.gray900,
    marginBottom: spacing.md,
  },
  textArea: {
    minHeight: 80,
    textAlignVertical: "top",
  },
  saveBtn: {
    backgroundColor: colors.gold,
    borderRadius: borderRadius.md,
    paddingVertical: spacing.md,
    alignItems: "center",
    marginBottom: spacing.lg,
  },
  btnDisabled: { opacity: 0.6 },
  saveBtnText: {
    fontSize: fontSize.md,
    fontWeight: "600",
    color: colors.primary,
  },
  sectionTitle: {
    fontSize: fontSize.lg,
    fontWeight: "700",
    color: colors.gray900,
    marginBottom: spacing.md,
    marginTop: spacing.sm,
  },
  stepLabel: {
    fontSize: fontSize.xs,
    fontWeight: "600",
    color: colors.gray500,
    marginBottom: 2,
  },
  stepText: {
    fontSize: fontSize.sm,
    fontWeight: "500",
    color: colors.gray900,
    marginBottom: spacing.sm,
  },
  stepBody: {
    fontSize: fontSize.sm,
    color: colors.gray700,
    lineHeight: 20,
  },
  enrollmentCard: {
    backgroundColor: colors.white,
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    marginBottom: spacing.sm,
    shadowColor: "#000",
    shadowOpacity: 0.03,
    shadowRadius: 4,
    elevation: 1,
  },
  enrollHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: spacing.xs,
  },
  enrollName: {
    fontSize: fontSize.sm,
    fontWeight: "600",
    color: colors.gray900,
    flex: 1,
  },
  enrollBadge: {
    borderRadius: borderRadius.full,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
  },
  enrollBadgeText: {
    fontSize: fontSize.xs,
    fontWeight: "600",
    color: colors.white,
    textTransform: "capitalize",
  },
  enrollMeta: {
    fontSize: fontSize.xs,
    color: colors.gray400,
  },
  emptyCard: {
    backgroundColor: colors.white,
    borderRadius: borderRadius.lg,
    padding: spacing.lg,
    alignItems: "center",
  },
  emptyText: {
    fontSize: fontSize.sm,
    color: colors.gray400,
    fontStyle: "italic",
  },
});
