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
  Switch,
  Alert,
} from "react-native";
import { Picker } from "@react-native-picker/picker";
import { useRouter } from "expo-router";
import { api } from "../../../lib/api";
import { colors, spacing, fontSize, borderRadius } from "../../../lib/theme";

export default function CreateJobScreen() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState({
    title: "",
    description: "",
    requirements: "",
    nice_to_haves: "",
    location: "",
    remote_policy: "",
    employment_type: "",
    salary_min: "",
    salary_max: "",
    equity_offered: false,
    application_email: "",
  });

  const handleSubmit = async () => {
    if (!form.title.trim()) {
      Alert.alert("Required", "Please enter a job title.");
      return;
    }
    if (!form.description.trim() || form.description.trim().length < 10) {
      Alert.alert("Required", "Please enter a description (at least 10 characters).");
      return;
    }

    setLoading(true);
    try {
      const payload: Record<string, unknown> = {
        title: form.title.trim(),
        description: form.description.trim(),
      };
      if (form.requirements.trim()) payload.requirements = form.requirements.trim();
      if (form.nice_to_haves.trim()) payload.nice_to_haves = form.nice_to_haves.trim();
      if (form.location.trim()) payload.location = form.location.trim();
      if (form.remote_policy) payload.remote_policy = form.remote_policy;
      if (form.employment_type) payload.employment_type = form.employment_type;
      if (form.salary_min) payload.salary_min = parseInt(form.salary_min, 10);
      if (form.salary_max) payload.salary_max = parseInt(form.salary_max, 10);
      payload.equity_offered = form.equity_offered;
      if (form.application_email.trim())
        payload.application_email = form.application_email.trim();

      const res = await api.post("/api/employer/jobs", payload);
      if (!res.ok) {
        const err = await res.json().catch(() => null);
        throw new Error(err?.detail || "Failed to create job");
      }

      const job = await res.json();
      Alert.alert("Success", "Job created successfully.", [
        { text: "OK", onPress: () => router.replace(`/employer/job/${job.id}`) },
      ]);
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
        <Text style={styles.label}>Job Title *</Text>
        <TextInput
          style={styles.input}
          placeholder="e.g. Senior Software Engineer"
          placeholderTextColor={colors.gray400}
          value={form.title}
          onChangeText={(v) => setForm((f) => ({ ...f, title: v }))}
        />

        <Text style={styles.label}>Description *</Text>
        <TextInput
          style={[styles.input, styles.textArea]}
          placeholder="Describe the role, responsibilities, and what a typical day looks like..."
          placeholderTextColor={colors.gray400}
          multiline
          numberOfLines={6}
          textAlignVertical="top"
          value={form.description}
          onChangeText={(v) => setForm((f) => ({ ...f, description: v }))}
        />

        <Text style={styles.label}>Requirements</Text>
        <TextInput
          style={[styles.input, styles.textArea]}
          placeholder="List the required qualifications and skills..."
          placeholderTextColor={colors.gray400}
          multiline
          numberOfLines={4}
          textAlignVertical="top"
          value={form.requirements}
          onChangeText={(v) => setForm((f) => ({ ...f, requirements: v }))}
        />

        <Text style={styles.label}>Nice to Haves</Text>
        <TextInput
          style={[styles.input, styles.textArea]}
          placeholder="Preferred but not required qualifications..."
          placeholderTextColor={colors.gray400}
          multiline
          numberOfLines={3}
          textAlignVertical="top"
          value={form.nice_to_haves}
          onChangeText={(v) => setForm((f) => ({ ...f, nice_to_haves: v }))}
        />

        <Text style={styles.label}>Location</Text>
        <TextInput
          style={styles.input}
          placeholder="e.g. San Francisco, CA"
          placeholderTextColor={colors.gray400}
          value={form.location}
          onChangeText={(v) => setForm((f) => ({ ...f, location: v }))}
        />

        <Text style={styles.label}>Remote Policy</Text>
        <View style={styles.pickerWrapper}>
          <Picker
            selectedValue={form.remote_policy}
            onValueChange={(v) => setForm((f) => ({ ...f, remote_policy: v }))}
            style={styles.picker}
          >
            <Picker.Item label="Select..." value="" />
            <Picker.Item label="On-site" value="on-site" />
            <Picker.Item label="Hybrid" value="hybrid" />
            <Picker.Item label="Remote" value="remote" />
          </Picker>
        </View>

        <Text style={styles.label}>Employment Type</Text>
        <View style={styles.pickerWrapper}>
          <Picker
            selectedValue={form.employment_type}
            onValueChange={(v) =>
              setForm((f) => ({ ...f, employment_type: v }))
            }
            style={styles.picker}
          >
            <Picker.Item label="Select..." value="" />
            <Picker.Item label="Full-time" value="full-time" />
            <Picker.Item label="Part-time" value="part-time" />
            <Picker.Item label="Contract" value="contract" />
            <Picker.Item label="Internship" value="internship" />
          </Picker>
        </View>

        <Text style={styles.label}>Salary Range</Text>
        <View style={styles.row}>
          <TextInput
            style={[styles.input, styles.halfInput]}
            placeholder="Min"
            placeholderTextColor={colors.gray400}
            keyboardType="numeric"
            value={form.salary_min}
            onChangeText={(v) => setForm((f) => ({ ...f, salary_min: v }))}
          />
          <TextInput
            style={[styles.input, styles.halfInput]}
            placeholder="Max"
            placeholderTextColor={colors.gray400}
            keyboardType="numeric"
            value={form.salary_max}
            onChangeText={(v) => setForm((f) => ({ ...f, salary_max: v }))}
          />
        </View>

        <View style={styles.switchRow}>
          <Text style={styles.label}>Equity Offered</Text>
          <Switch
            value={form.equity_offered}
            onValueChange={(v) =>
              setForm((f) => ({ ...f, equity_offered: v }))
            }
            trackColor={{ false: colors.gray300, true: colors.gold }}
            thumbColor={colors.white}
          />
        </View>

        <Text style={styles.label}>Application Email</Text>
        <TextInput
          style={styles.input}
          placeholder="hiring@company.com"
          placeholderTextColor={colors.gray400}
          keyboardType="email-address"
          autoCapitalize="none"
          value={form.application_email}
          onChangeText={(v) =>
            setForm((f) => ({ ...f, application_email: v }))
          }
        />

        <TouchableOpacity
          style={[styles.submitBtn, loading && styles.btnDisabled]}
          onPress={handleSubmit}
          disabled={loading}
        >
          <Text style={styles.submitText}>
            {loading ? "Creating..." : "Create Job"}
          </Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={styles.cancelBtn}
          onPress={() => router.back()}
        >
          <Text style={styles.cancelText}>Cancel</Text>
        </TouchableOpacity>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.gray50 },
  content: { padding: spacing.md, paddingBottom: spacing.xxl },
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
  textArea: { minHeight: 80 },
  pickerWrapper: {
    backgroundColor: colors.white,
    borderRadius: borderRadius.md,
    borderWidth: 1,
    borderColor: colors.gray200,
    marginBottom: spacing.md,
    overflow: "hidden",
  },
  picker: { color: colors.gray900 },
  row: { flexDirection: "row", gap: spacing.sm },
  halfInput: { flex: 1 },
  switchRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: spacing.md,
  },
  submitBtn: {
    backgroundColor: colors.gold,
    borderRadius: borderRadius.md,
    paddingVertical: spacing.md,
    alignItems: "center",
    marginTop: spacing.md,
  },
  btnDisabled: { opacity: 0.6 },
  submitText: {
    fontSize: fontSize.lg,
    fontWeight: "600",
    color: colors.primary,
  },
  cancelBtn: {
    borderRadius: borderRadius.md,
    paddingVertical: spacing.md,
    alignItems: "center",
    marginTop: spacing.sm,
  },
  cancelText: {
    fontSize: fontSize.md,
    color: colors.gray500,
  },
});
