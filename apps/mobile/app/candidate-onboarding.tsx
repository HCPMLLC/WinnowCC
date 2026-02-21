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
  Switch,
} from "react-native";
import { useRouter } from "expo-router";
import { useAuth } from "../lib/auth";
import { api } from "../lib/api";
import { colors, spacing, fontSize, borderRadius } from "../lib/theme";

const REMOTE_OPTIONS = [
  { label: "No preference", value: "" },
  { label: "Remote only", value: "remote" },
  { label: "Hybrid", value: "hybrid" },
  { label: "On-site", value: "onsite" },
];

export default function CandidateOnboardingScreen() {
  const router = useRouter();
  const { markOnboardingComplete } = useAuth();
  const [loading, setLoading] = useState(false);
  const [step, setStep] = useState(0);

  const [form, setForm] = useState({
    first_name: "",
    last_name: "",
    phone: "",
    location_city: "",
    state: "",
    country: "",
    years_experience: "",
    desired_job_types: "",
    desired_locations: "",
    desired_salary_min: "",
    desired_salary_max: "",
    remote_preference: "",
    consent_terms: false,
    consent_privacy: false,
  });

  const set = (field: string, value: string | boolean) =>
    setForm((f) => ({ ...f, [field]: value }));

  const handleSubmit = async () => {
    if (!form.consent_terms || !form.consent_privacy) {
      Alert.alert("Required", "Please accept the Terms and Privacy Policy.");
      return;
    }

    setLoading(true);
    try {
      const payload = {
        first_name: form.first_name.trim() || null,
        last_name: form.last_name.trim() || null,
        phone: form.phone.trim() || null,
        location_city: form.location_city.trim() || null,
        state: form.state.trim() || null,
        country: form.country.trim() || null,
        years_experience: form.years_experience
          ? parseInt(form.years_experience, 10)
          : null,
        desired_job_types: form.desired_job_types
          ? form.desired_job_types.split(",").map((s) => s.trim()).filter(Boolean)
          : [],
        desired_locations: form.desired_locations
          ? form.desired_locations.split(",").map((s) => s.trim()).filter(Boolean)
          : [],
        desired_salary_min: form.desired_salary_min
          ? parseInt(form.desired_salary_min, 10)
          : null,
        desired_salary_max: form.desired_salary_max
          ? parseInt(form.desired_salary_max, 10)
          : null,
        remote_preference: form.remote_preference || null,
        consent_terms: form.consent_terms,
        consent_privacy: form.consent_privacy,
      };

      const res = await api.post("/api/onboarding/complete", payload);

      if (!res.ok) {
        const err = await res.json().catch(() => null);
        throw new Error(err?.detail || "Failed to complete onboarding");
      }

      markOnboardingComplete();
      router.replace("/(tabs)/dashboard");
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
        {/* Progress dots */}
        <View style={styles.progressRow}>
          {[0, 1, 2].map((i) => (
            <View
              key={i}
              style={[styles.dot, i <= step && styles.dotActive]}
            />
          ))}
        </View>

        {step === 0 && (
          <>
            <Text style={styles.heading}>About you</Text>
            <Text style={styles.subheading}>
              Help us personalize your experience.
            </Text>

            <Text style={styles.label}>First Name</Text>
            <TextInput
              style={styles.input}
              placeholder="Jane"
              placeholderTextColor={colors.gray400}
              value={form.first_name}
              onChangeText={(v) => set("first_name", v)}
            />

            <Text style={styles.label}>Last Name</Text>
            <TextInput
              style={styles.input}
              placeholder="Doe"
              placeholderTextColor={colors.gray400}
              value={form.last_name}
              onChangeText={(v) => set("last_name", v)}
            />

            <Text style={styles.label}>Phone</Text>
            <TextInput
              style={styles.input}
              placeholder="+1 555-555-5555"
              placeholderTextColor={colors.gray400}
              keyboardType="phone-pad"
              value={form.phone}
              onChangeText={(v) => set("phone", v)}
            />

            <Text style={styles.label}>City</Text>
            <TextInput
              style={styles.input}
              placeholder="San Francisco"
              placeholderTextColor={colors.gray400}
              value={form.location_city}
              onChangeText={(v) => set("location_city", v)}
            />

            <View style={styles.row}>
              <View style={styles.halfCol}>
                <Text style={styles.label}>State</Text>
                <TextInput
                  style={styles.input}
                  placeholder="CA"
                  placeholderTextColor={colors.gray400}
                  value={form.state}
                  onChangeText={(v) => set("state", v)}
                />
              </View>
              <View style={styles.halfCol}>
                <Text style={styles.label}>Country</Text>
                <TextInput
                  style={styles.input}
                  placeholder="US"
                  placeholderTextColor={colors.gray400}
                  value={form.country}
                  onChangeText={(v) => set("country", v)}
                />
              </View>
            </View>

            <Text style={styles.label}>Years of Experience</Text>
            <TextInput
              style={styles.input}
              placeholder="5"
              placeholderTextColor={colors.gray400}
              keyboardType="number-pad"
              value={form.years_experience}
              onChangeText={(v) => set("years_experience", v)}
            />

            <TouchableOpacity
              style={styles.button}
              onPress={() => setStep(1)}
            >
              <Text style={styles.buttonText}>Next</Text>
            </TouchableOpacity>
          </>
        )}

        {step === 1 && (
          <>
            <Text style={styles.heading}>Job preferences</Text>
            <Text style={styles.subheading}>
              What kind of roles are you looking for?
            </Text>

            <Text style={styles.label}>Desired Job Types</Text>
            <TextInput
              style={styles.input}
              placeholder="e.g. Full-time, Contract"
              placeholderTextColor={colors.gray400}
              value={form.desired_job_types}
              onChangeText={(v) => set("desired_job_types", v)}
            />
            <Text style={styles.hint}>Comma-separated</Text>

            <Text style={styles.label}>Desired Locations</Text>
            <TextInput
              style={styles.input}
              placeholder="e.g. Remote, New York, London"
              placeholderTextColor={colors.gray400}
              value={form.desired_locations}
              onChangeText={(v) => set("desired_locations", v)}
            />
            <Text style={styles.hint}>Comma-separated</Text>

            <Text style={styles.label}>Remote Preference</Text>
            <View style={styles.optionRow}>
              {REMOTE_OPTIONS.map((opt) => (
                <TouchableOpacity
                  key={opt.value}
                  style={[
                    styles.optionChip,
                    form.remote_preference === opt.value &&
                      styles.optionChipActive,
                  ]}
                  onPress={() => set("remote_preference", opt.value)}
                >
                  <Text
                    style={[
                      styles.optionChipText,
                      form.remote_preference === opt.value &&
                        styles.optionChipTextActive,
                    ]}
                  >
                    {opt.label}
                  </Text>
                </TouchableOpacity>
              ))}
            </View>

            <Text style={styles.label}>Salary Range (USD)</Text>
            <View style={styles.row}>
              <View style={styles.halfCol}>
                <TextInput
                  style={styles.input}
                  placeholder="Min (e.g. 80000)"
                  placeholderTextColor={colors.gray400}
                  keyboardType="number-pad"
                  value={form.desired_salary_min}
                  onChangeText={(v) => set("desired_salary_min", v)}
                />
              </View>
              <View style={styles.halfCol}>
                <TextInput
                  style={styles.input}
                  placeholder="Max (e.g. 120000)"
                  placeholderTextColor={colors.gray400}
                  keyboardType="number-pad"
                  value={form.desired_salary_max}
                  onChangeText={(v) => set("desired_salary_max", v)}
                />
              </View>
            </View>

            <View style={styles.navRow}>
              <TouchableOpacity
                style={styles.backButton}
                onPress={() => setStep(0)}
              >
                <Text style={styles.backButtonText}>Back</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.button, { flex: 1 }]}
                onPress={() => setStep(2)}
              >
                <Text style={styles.buttonText}>Next</Text>
              </TouchableOpacity>
            </View>
          </>
        )}

        {step === 2 && (
          <>
            <Text style={styles.heading}>Almost done</Text>
            <Text style={styles.subheading}>
              Please review and accept our terms to get started.
            </Text>

            <View style={styles.consentRow}>
              <Switch
                value={form.consent_terms}
                onValueChange={(v) => set("consent_terms", v)}
                trackColor={{ true: colors.gold, false: colors.gray200 }}
                thumbColor={colors.white}
              />
              <Text style={styles.consentText}>
                I accept the Terms of Service *
              </Text>
            </View>

            <View style={styles.consentRow}>
              <Switch
                value={form.consent_privacy}
                onValueChange={(v) => set("consent_privacy", v)}
                trackColor={{ true: colors.gold, false: colors.gray200 }}
                thumbColor={colors.white}
              />
              <Text style={styles.consentText}>
                I accept the Privacy Policy *
              </Text>
            </View>

            <View style={styles.navRow}>
              <TouchableOpacity
                style={styles.backButton}
                onPress={() => setStep(1)}
              >
                <Text style={styles.backButtonText}>Back</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[
                  styles.button,
                  { flex: 1 },
                  loading && styles.buttonDisabled,
                ]}
                onPress={handleSubmit}
                disabled={loading}
              >
                <Text style={styles.buttonText}>
                  {loading ? "Saving..." : "Get Started"}
                </Text>
              </TouchableOpacity>
            </View>
          </>
        )}
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.gray50 },
  content: { padding: spacing.lg, paddingBottom: spacing.xxl },
  progressRow: {
    flexDirection: "row",
    justifyContent: "center",
    gap: 8,
    marginBottom: spacing.lg,
  },
  dot: {
    width: 10,
    height: 10,
    borderRadius: 5,
    backgroundColor: colors.gray200,
  },
  dotActive: { backgroundColor: colors.gold },
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
  row: { flexDirection: "row", gap: spacing.sm },
  halfCol: { flex: 1 },
  optionRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.sm,
    marginBottom: spacing.lg,
  },
  optionChip: {
    borderWidth: 1,
    borderColor: colors.gray300,
    borderRadius: borderRadius.full,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
  },
  optionChipActive: {
    borderColor: colors.gold,
    backgroundColor: colors.gold,
  },
  optionChipText: {
    fontSize: fontSize.sm,
    color: colors.gray600,
  },
  optionChipTextActive: {
    color: colors.primary,
    fontWeight: "600",
  },
  consentRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    marginBottom: spacing.md,
    paddingVertical: spacing.xs,
  },
  consentText: {
    fontSize: fontSize.sm,
    color: colors.gray700,
    flex: 1,
  },
  navRow: { flexDirection: "row", gap: spacing.sm, marginTop: spacing.md },
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
  backButton: {
    borderWidth: 1,
    borderColor: colors.gray300,
    borderRadius: borderRadius.md,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.lg,
    alignItems: "center",
    marginTop: spacing.md,
  },
  backButtonText: {
    fontSize: fontSize.md,
    color: colors.gray600,
  },
});
