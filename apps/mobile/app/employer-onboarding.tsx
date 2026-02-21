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
import { useAuth } from "../lib/auth";
import { api } from "../lib/api";
import { colors, spacing, fontSize, borderRadius } from "../lib/theme";

const COMPANY_SIZES = ["1-10", "11-50", "51-200", "201-500", "501-1000", "1000+"];

export default function EmployerOnboardingScreen() {
  const router = useRouter();
  const { markOnboardingComplete } = useAuth();
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState({
    company_name: "",
    company_size: "",
    industry: "",
    company_website: "",
    company_description: "",
  });

  const handleSubmit = async () => {
    if (!form.company_name.trim()) {
      Alert.alert("Required", "Please enter your company name.");
      return;
    }

    setLoading(true);
    try {
      const res = await api.post("/api/employer/profile", {
        company_name: form.company_name.trim(),
        company_size: form.company_size || null,
        industry: form.industry.trim() || null,
        company_website: form.company_website.trim() || null,
        company_description: form.company_description.trim() || null,
      });

      if (!res.ok) {
        const err = await res.json().catch(() => null);
        throw new Error(err?.detail || "Failed to create profile");
      }

      markOnboardingComplete();
      router.replace("/(employer-tabs)/dashboard");
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
        <Text style={styles.heading}>Set up your company profile</Text>
        <Text style={styles.subheading}>
          Tell candidates about your company to attract the best talent.
        </Text>

        <Text style={styles.label}>Company Name *</Text>
        <TextInput
          style={styles.input}
          placeholder="Acme Corp"
          placeholderTextColor={colors.gray400}
          value={form.company_name}
          onChangeText={(v) => setForm((f) => ({ ...f, company_name: v }))}
        />

        <Text style={styles.label}>Company Size</Text>
        <View style={styles.pickerWrapper}>
          <Picker
            selectedValue={form.company_size}
            onValueChange={(v) => setForm((f) => ({ ...f, company_size: v }))}
            style={styles.picker}
          >
            <Picker.Item label="Select size..." value="" />
            {COMPANY_SIZES.map((s) => (
              <Picker.Item key={s} label={`${s} employees`} value={s} />
            ))}
          </Picker>
        </View>

        <Text style={styles.label}>Industry</Text>
        <TextInput
          style={styles.input}
          placeholder="e.g. Technology, Healthcare"
          placeholderTextColor={colors.gray400}
          value={form.industry}
          onChangeText={(v) => setForm((f) => ({ ...f, industry: v }))}
        />

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

        <Text style={styles.label}>Company Description</Text>
        <TextInput
          style={[styles.input, styles.textArea]}
          placeholder="Tell candidates about your company culture, mission, and values..."
          placeholderTextColor={colors.gray400}
          multiline
          numberOfLines={4}
          textAlignVertical="top"
          value={form.company_description}
          onChangeText={(v) =>
            setForm((f) => ({ ...f, company_description: v }))
          }
        />

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
    minHeight: 100,
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
