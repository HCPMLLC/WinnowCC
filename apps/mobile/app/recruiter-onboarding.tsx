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
import { api } from "../lib/api";
import { colors, spacing, fontSize, borderRadius } from "../lib/theme";

const COMPANY_TYPES = [
  { label: "Select type...", value: "" },
  { label: "Agency", value: "agency" },
  { label: "Boutique", value: "boutique" },
  { label: "Corporate", value: "corporate" },
  { label: "Independent", value: "independent" },
];

export default function RecruiterOnboardingScreen() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState({
    company_name: "",
    company_type: "",
    company_website: "",
    specializations: "",
  });

  const handleSubmit = async () => {
    if (!form.company_name.trim()) {
      Alert.alert("Required", "Please enter your company name.");
      return;
    }

    setLoading(true);
    try {
      const res = await api.post("/api/recruiter/profile", {
        company_name: form.company_name.trim(),
        company_type: form.company_type || null,
        company_website: form.company_website.trim() || null,
        specializations: form.specializations
          ? form.specializations
              .split(",")
              .map((s) => s.trim())
              .filter(Boolean)
          : null,
      });

      if (!res.ok) {
        const err = await res.json().catch(() => null);
        throw new Error(err?.detail || "Failed to create profile");
      }

      router.replace("/(recruiter-tabs)/dashboard");
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
        <Text style={styles.heading}>Set up your recruiter profile</Text>
        <Text style={styles.subheading}>
          Tell us about your recruiting practice to get started.
        </Text>

        <Text style={styles.label}>Company Name *</Text>
        <TextInput
          style={styles.input}
          placeholder="e.g. Talent Partners Inc."
          placeholderTextColor={colors.gray400}
          value={form.company_name}
          onChangeText={(v) => setForm((f) => ({ ...f, company_name: v }))}
        />

        <Text style={styles.label}>Company Type</Text>
        <View style={styles.pickerWrapper}>
          <Picker
            selectedValue={form.company_type}
            onValueChange={(v) => setForm((f) => ({ ...f, company_type: v }))}
            style={styles.picker}
          >
            {COMPANY_TYPES.map((t) => (
              <Picker.Item key={t.value} label={t.label} value={t.value} />
            ))}
          </Picker>
        </View>

        <Text style={styles.label}>Website</Text>
        <TextInput
          style={styles.input}
          placeholder="https://example.com"
          placeholderTextColor={colors.gray400}
          keyboardType="url"
          autoCapitalize="none"
          value={form.company_website}
          onChangeText={(v) => setForm((f) => ({ ...f, company_website: v }))}
        />

        <Text style={styles.label}>Specializations</Text>
        <TextInput
          style={styles.input}
          placeholder="e.g. Tech, Healthcare, Finance"
          placeholderTextColor={colors.gray400}
          value={form.specializations}
          onChangeText={(v) => setForm((f) => ({ ...f, specializations: v }))}
        />
        <Text style={styles.hint}>Comma-separated list of industries</Text>

        <TouchableOpacity
          style={[styles.button, loading && styles.buttonDisabled]}
          onPress={handleSubmit}
          disabled={loading}
        >
          <Text style={styles.buttonText}>
            {loading ? "Creating..." : "Continue"}
          </Text>
        </TouchableOpacity>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.gray50 },
  content: { padding: spacing.lg, paddingBottom: spacing.xxl },
  heading: {
    fontSize: fontSize.xxl,
    fontWeight: "700",
    color: colors.gray900,
    marginBottom: spacing.xs,
  },
  subheading: {
    fontSize: fontSize.md,
    color: colors.gray500,
    marginBottom: spacing.lg,
    lineHeight: 22,
  },
  label: {
    fontSize: fontSize.sm,
    fontWeight: "600",
    color: colors.gray700,
    marginBottom: spacing.xs,
  },
  hint: {
    fontSize: fontSize.xs,
    color: colors.gray400,
    marginTop: -spacing.sm,
    marginBottom: spacing.md,
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
