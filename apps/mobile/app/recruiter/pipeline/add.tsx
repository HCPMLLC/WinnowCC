import { useState } from "react";
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
  KeyboardAvoidingView,
  Platform,
  Alert,
} from "react-native";
import { Picker } from "@react-native-picker/picker";
import { useRouter } from "expo-router";
import { api } from "../../../lib/api";
import { PIPELINE_STAGES, STAGE_LABELS, type PipelineStage } from "../../../lib/recruiter-types";
import { colors, spacing, fontSize, borderRadius } from "../../../lib/theme";

export default function AddPipelineScreen() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState({
    external_name: "",
    external_email: "",
    external_phone: "",
    source: "",
    stage: "sourced" as string,
    notes: "",
  });

  const handleSubmit = async () => {
    if (!form.external_name.trim()) {
      Alert.alert("Required", "Please enter the candidate's name.");
      return;
    }
    if (!form.source.trim()) {
      Alert.alert("Required", "Please enter the source.");
      return;
    }

    setLoading(true);
    try {
      const res = await api.post("/api/recruiter/pipeline", {
        external_name: form.external_name.trim(),
        external_email: form.external_email.trim() || null,
        external_phone: form.external_phone.trim() || null,
        source: form.source.trim(),
        stage: form.stage,
        notes: form.notes.trim() || null,
      });

      if (!res.ok) {
        const err = await res.json().catch(() => null);
        throw new Error(err?.detail || "Failed to add candidate");
      }

      router.back();
    } catch (err: any) {
      Alert.alert("Error", err.message || "Something went wrong.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === "ios" ? "padding" : "height"}
    >
      <ScrollView
        contentContainerStyle={styles.content}
        keyboardShouldPersistTaps="handled"
      >
        <Text style={styles.label}>Candidate Name *</Text>
        <TextInput
          style={styles.input}
          placeholder="Full name"
          placeholderTextColor={colors.gray400}
          value={form.external_name}
          onChangeText={(v) => setForm((f) => ({ ...f, external_name: v }))}
        />

        <Text style={styles.label}>Email</Text>
        <TextInput
          style={styles.input}
          placeholder="email@example.com"
          placeholderTextColor={colors.gray400}
          keyboardType="email-address"
          autoCapitalize="none"
          value={form.external_email}
          onChangeText={(v) => setForm((f) => ({ ...f, external_email: v }))}
        />

        <Text style={styles.label}>Phone</Text>
        <TextInput
          style={styles.input}
          placeholder="+1 555-123-4567"
          placeholderTextColor={colors.gray400}
          keyboardType="phone-pad"
          value={form.external_phone}
          onChangeText={(v) => setForm((f) => ({ ...f, external_phone: v }))}
        />

        <Text style={styles.label}>Source *</Text>
        <TextInput
          style={styles.input}
          placeholder="e.g. LinkedIn, Referral, Job Board"
          placeholderTextColor={colors.gray400}
          value={form.source}
          onChangeText={(v) => setForm((f) => ({ ...f, source: v }))}
        />

        <Text style={styles.label}>Stage</Text>
        <View style={styles.pickerWrapper}>
          <Picker
            selectedValue={form.stage}
            onValueChange={(v) => setForm((f) => ({ ...f, stage: v }))}
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

        <Text style={styles.label}>Notes</Text>
        <TextInput
          style={[styles.input, styles.textArea]}
          placeholder="Any notes about this candidate..."
          placeholderTextColor={colors.gray400}
          multiline
          numberOfLines={4}
          textAlignVertical="top"
          value={form.notes}
          onChangeText={(v) => setForm((f) => ({ ...f, notes: v }))}
        />

        <TouchableOpacity
          style={[styles.button, loading && styles.buttonDisabled]}
          onPress={handleSubmit}
          disabled={loading}
        >
          <Text style={styles.buttonText}>
            {loading ? "Adding..." : "Add to Pipeline"}
          </Text>
        </TouchableOpacity>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.gray50 },
  content: { padding: spacing.lg, paddingBottom: spacing.xxl },
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
  textArea: { minHeight: 100 },
  pickerWrapper: {
    backgroundColor: colors.white,
    borderRadius: borderRadius.md,
    borderWidth: 1,
    borderColor: colors.gray200,
    marginBottom: spacing.md,
    overflow: "hidden",
  },
  picker: { color: colors.gray900 },
  button: {
    backgroundColor: colors.gold,
    borderRadius: borderRadius.md,
    paddingVertical: spacing.md,
    alignItems: "center",
    marginTop: spacing.md,
  },
  buttonDisabled: { opacity: 0.6 },
  buttonText: {
    fontSize: fontSize.lg,
    fontWeight: "600",
    color: colors.primary,
  },
});
