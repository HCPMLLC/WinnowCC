import { useEffect, useState } from "react";
import {
  View,
  Text,
  TextInput,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Alert,
  RefreshControl,
} from "react-native";
import { Picker } from "@react-native-picker/picker";
import { useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { useAuth } from "../../lib/auth";
import { api } from "../../lib/api";
import LoadingSpinner from "../../components/LoadingSpinner";
import ProfileMenuItem from "../../components/ProfileMenuItem";
import { colors, spacing, fontSize, borderRadius } from "../../lib/theme";

interface ProfileData {
  version: number;
  profile_json: Record<string, unknown>;
}

interface Preferences {
  desired_titles?: string;
  desired_locations?: string;
  remote_preference?: string;
  salary_min?: number | null;
  salary_max?: number | null;
  job_type?: string;
}

interface ProfileSummary {
  name: string;
  skillsCount: number;
  experienceCount: number;
  educationCount: number;
  topSkills: string[];
}

function extractSummary(pj: Record<string, unknown>): ProfileSummary {
  const basics = (pj.basics || {}) as Record<string, string>;
  const skills = (pj.skills || []) as string[];
  const experience = (pj.experience || []) as unknown[];
  const education = (pj.education || []) as unknown[];

  const name = [basics.first_name, basics.last_name]
    .filter(Boolean)
    .join(" ");

  return {
    name: name || "",
    skillsCount: skills.length,
    experienceCount: experience.length,
    educationCount: education.length,
    topSkills: skills.slice(0, 8),
  };
}

export default function ProfileScreen() {
  const { email, role, logout } = useAuth();
  const router = useRouter();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [summary, setSummary] = useState<ProfileSummary>({
    name: "",
    skillsCount: 0,
    experienceCount: 0,
    educationCount: 0,
    topSkills: [],
  });
  const [prefs, setPrefs] = useState<Preferences>({
    desired_titles: "",
    desired_locations: "",
    remote_preference: "any",
    salary_min: null,
    salary_max: null,
    job_type: "any",
  });
  const [completeness, setCompleteness] = useState<number | null>(null);

  const loadProfile = async () => {
    try {
      setError(null);
      const [res, compRes] = await Promise.all([
        api.get("/api/profile"),
        api.get("/api/profile/completeness").catch(() => null),
      ]);
      if (res.ok) {
        const data: ProfileData = await res.json();
        const pj = (data.profile_json || {}) as Record<string, unknown>;
        const p = (pj.preferences || {}) as Record<string, unknown>;

        setSummary(extractSummary(pj));
        setPrefs({
          desired_titles: Array.isArray(p.desired_titles)
            ? (p.desired_titles as string[]).join(", ")
            : (p.desired_titles as string) || "",
          desired_locations: Array.isArray(p.desired_locations)
            ? (p.desired_locations as string[]).join(", ")
            : (p.desired_locations as string) || "",
          remote_preference: (p.remote_preference as string) || "any",
          salary_min: (p.salary_min as number) ?? null,
          salary_max: (p.salary_max as number) ?? null,
          job_type: (p.job_type as string) || "any",
        });
      } else if (res.status === 403) {
        setError("Please complete onboarding to access your profile.");
      } else {
        setError("Failed to load profile.");
      }
      if (compRes && compRes.ok) {
        const compData = await compRes.json();
        setCompleteness(compData.score ?? compData.completeness ?? null);
      }
    } catch {
      setError("Could not connect to server.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadProfile();
  }, []);

  const onRefresh = () => {
    setRefreshing(true);
    loadProfile();
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const res = await api.get("/api/profile");
      if (!res.ok) throw new Error("Failed to load profile");
      const data = await res.json();
      const profileJson = data.profile_json || {};

      profileJson.preferences = {
        ...profileJson.preferences,
        desired_titles: prefs.desired_titles
          ?.split(",")
          .map((s) => s.trim())
          .filter(Boolean),
        desired_locations: prefs.desired_locations
          ?.split(",")
          .map((s) => s.trim())
          .filter(Boolean),
        remote_preference: prefs.remote_preference,
        salary_min: prefs.salary_min || null,
        salary_max: prefs.salary_max || null,
        job_type: prefs.job_type,
      };

      const saveRes = await api.put("/api/profile", {
        profile_json: profileJson,
      });
      if (saveRes.ok) {
        Alert.alert("Saved", "Your preferences have been updated.");
      } else {
        Alert.alert("Error", "Failed to save preferences.");
      }
    } catch {
      Alert.alert("Error", "Something went wrong.");
    } finally {
      setSaving(false);
    }
  };

  const handleLogout = () => {
    Alert.alert("Log Out", "Are you sure you want to log out?", [
      { text: "Cancel", style: "cancel" },
      { text: "Log Out", style: "destructive", onPress: logout },
    ]);
  };

  if (loading) return <LoadingSpinner />;

  if (error) {
    return (
      <ScrollView
        style={styles.container}
        contentContainerStyle={styles.content}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
      >
        <Text style={styles.email}>{email}</Text>
        <View style={styles.errorBox}>
          <Text style={styles.errorText}>{error}</Text>
          <Text style={styles.errorHint}>Pull down to retry.</Text>
        </View>
        <TouchableOpacity style={styles.logoutBtn} onPress={handleLogout}>
          <Text style={styles.logoutBtnText}>Log Out</Text>
        </TouchableOpacity>
      </ScrollView>
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
      <Text style={styles.email}>{email}</Text>

      {/* Role switcher for "both" users */}
      {role === "both" && (
        <TouchableOpacity
          style={styles.switchBanner}
          onPress={() => router.push("/(employer-tabs)/dashboard")}
        >
          <Ionicons name="swap-horizontal" size={16} color={colors.gold} />
          <Text style={styles.switchBannerText}>Switch to Employer View</Text>
        </TouchableOpacity>
      )}

      {/* Recruiter switcher */}
      {(role === "recruiter" || role === "both") && (
        <TouchableOpacity
          style={styles.switchBanner}
          onPress={() => router.push("/(recruiter-tabs)/dashboard")}
        >
          <Ionicons name="swap-horizontal" size={16} color={colors.gold} />
          <Text style={styles.switchBannerText}>Switch to Recruiter View</Text>
        </TouchableOpacity>
      )}

      {/* Profile Summary */}
      {(summary.name || summary.skillsCount > 0) && (
        <View style={styles.summaryCard}>
          {summary.name ? (
            <Text style={styles.summaryName}>{summary.name}</Text>
          ) : null}
          <View style={styles.statsRow}>
            <View style={styles.stat}>
              <Text style={styles.statNumber}>{summary.skillsCount}</Text>
              <Text style={styles.statLabel}>Skills</Text>
            </View>
            <View style={styles.stat}>
              <Text style={styles.statNumber}>{summary.experienceCount}</Text>
              <Text style={styles.statLabel}>Experiences</Text>
            </View>
            <View style={styles.stat}>
              <Text style={styles.statNumber}>{summary.educationCount}</Text>
              <Text style={styles.statLabel}>Education</Text>
            </View>
          </View>
          {summary.topSkills.length > 0 && (
            <View style={styles.skillsRow}>
              {summary.topSkills.map((s) => (
                <View key={s} style={styles.skillChip}>
                  <Text style={styles.skillChipText}>{s}</Text>
                </View>
              ))}
            </View>
          )}
        </View>
      )}

      {/* Completeness */}
      {completeness != null && (
        <View style={styles.completenessCard}>
          <View style={styles.completenessHeader}>
            <Text style={styles.completenessLabel}>Profile Completeness</Text>
            <Text style={styles.completenessPercent}>{completeness}%</Text>
          </View>
          <View style={styles.completenessTrack}>
            <View
              style={[
                styles.completenessFill,
                { width: `${Math.min(completeness, 100)}%` },
              ]}
            />
          </View>
        </View>
      )}

      {/* Profile Hub */}
      <Text style={styles.sectionTitle}>Manage</Text>
      <ProfileMenuItem
        icon="cloud-upload-outline"
        label="Upload Resume"
        subtitle="Upload a new resume"
        onPress={() => router.push("/profile/upload")}
      />
      <ProfileMenuItem
        icon="document-text-outline"
        label="Documents"
        subtitle="Tailored resumes & cover letters"
        onPress={() => router.push("/profile/documents")}
      />
      <ProfileMenuItem
        icon="people-outline"
        label="References"
        subtitle="Professional references"
        onPress={() => router.push("/profile/references")}
      />
      <ProfileMenuItem
        icon="settings-outline"
        label="Settings"
        subtitle="Export data, manage account"
        onPress={() => router.push("/profile/settings")}
      />

      <View style={styles.notice}>
        <Text style={styles.noticeText}>
          For full profile editing (experience, education, skills), visit
          winnow.app on your computer.
        </Text>
      </View>

      <Text style={styles.sectionTitle}>Job Preferences</Text>

      <Text style={styles.label}>Desired Job Titles</Text>
      <TextInput
        style={styles.input}
        placeholder="e.g. Product Manager, PM, Program Manager"
        placeholderTextColor={colors.gray400}
        value={prefs.desired_titles}
        onChangeText={(v) => setPrefs((p) => ({ ...p, desired_titles: v }))}
      />

      <Text style={styles.label}>Desired Locations</Text>
      <TextInput
        style={styles.input}
        placeholder="e.g. San Francisco, New York, Remote"
        placeholderTextColor={colors.gray400}
        value={prefs.desired_locations}
        onChangeText={(v) => setPrefs((p) => ({ ...p, desired_locations: v }))}
      />

      <Text style={styles.label}>Remote Preference</Text>
      <View style={styles.pickerWrapper}>
        <Picker
          selectedValue={prefs.remote_preference}
          onValueChange={(v) =>
            setPrefs((p) => ({ ...p, remote_preference: v }))
          }
          style={styles.picker}
        >
          <Picker.Item label="Any" value="any" />
          <Picker.Item label="Remote Only" value="remote" />
          <Picker.Item label="Hybrid" value="hybrid" />
          <Picker.Item label="On-site" value="onsite" />
        </Picker>
      </View>

      <Text style={styles.label}>Salary Range</Text>
      <View style={styles.row}>
        <TextInput
          style={[styles.input, styles.halfInput]}
          placeholder="Min"
          placeholderTextColor={colors.gray400}
          keyboardType="numeric"
          value={prefs.salary_min ? String(prefs.salary_min) : ""}
          onChangeText={(v) =>
            setPrefs((p) => ({ ...p, salary_min: v ? parseInt(v, 10) : null }))
          }
        />
        <TextInput
          style={[styles.input, styles.halfInput]}
          placeholder="Max"
          placeholderTextColor={colors.gray400}
          keyboardType="numeric"
          value={prefs.salary_max ? String(prefs.salary_max) : ""}
          onChangeText={(v) =>
            setPrefs((p) => ({ ...p, salary_max: v ? parseInt(v, 10) : null }))
          }
        />
      </View>

      <Text style={styles.label}>Job Type</Text>
      <View style={styles.pickerWrapper}>
        <Picker
          selectedValue={prefs.job_type}
          onValueChange={(v) => setPrefs((p) => ({ ...p, job_type: v }))}
          style={styles.picker}
        >
          <Picker.Item label="Any" value="any" />
          <Picker.Item label="Full-time" value="full-time" />
          <Picker.Item label="Part-time" value="part-time" />
          <Picker.Item label="Contract" value="contract" />
        </Picker>
      </View>

      <TouchableOpacity
        style={[styles.saveBtn, saving && styles.btnDisabled]}
        onPress={handleSave}
        disabled={saving}
      >
        <Text style={styles.saveBtnText}>
          {saving ? "Saving..." : "Save Preferences"}
        </Text>
      </TouchableOpacity>

      <Text style={styles.webManageText}>
        Manage your account and subscription at WinnowCC.ai
      </Text>

      <TouchableOpacity style={styles.logoutBtn} onPress={handleLogout}>
        <Text style={styles.logoutBtnText}>Log Out</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.gray50 },
  content: { padding: spacing.md, paddingBottom: spacing.xxl },
  email: {
    fontSize: fontSize.lg,
    fontWeight: "600",
    color: colors.gray900,
    marginBottom: spacing.sm,
  },
  switchBanner: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    backgroundColor: colors.primaryLight,
    borderRadius: borderRadius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    marginBottom: spacing.md,
  },
  switchBannerText: {
    fontSize: fontSize.sm,
    fontWeight: "600",
    color: colors.gold,
  },
  summaryCard: {
    backgroundColor: colors.white,
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    marginBottom: spacing.md,
    shadowColor: "#000",
    shadowOpacity: 0.05,
    shadowRadius: 8,
    elevation: 2,
  },
  summaryName: {
    fontSize: fontSize.xl,
    fontWeight: "700",
    color: colors.gray900,
    marginBottom: spacing.sm,
  },
  statsRow: {
    flexDirection: "row",
    justifyContent: "space-around",
    marginBottom: spacing.sm,
  },
  stat: { alignItems: "center" },
  statNumber: {
    fontSize: fontSize.xl,
    fontWeight: "700",
    color: colors.primary,
  },
  statLabel: {
    fontSize: fontSize.xs,
    color: colors.gray500,
    marginTop: 2,
  },
  skillsRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.xs,
    marginTop: spacing.xs,
  },
  skillChip: {
    backgroundColor: colors.sage,
    borderRadius: borderRadius.full,
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
  },
  skillChipText: {
    fontSize: fontSize.xs,
    color: colors.primary,
    fontWeight: "500",
  },
  completenessCard: {
    backgroundColor: colors.white,
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    marginBottom: spacing.md,
    shadowColor: "#000",
    shadowOpacity: 0.05,
    shadowRadius: 8,
    elevation: 2,
  },
  completenessHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: spacing.sm,
  },
  completenessLabel: {
    fontSize: fontSize.sm,
    fontWeight: "600",
    color: colors.gray700,
  },
  completenessPercent: {
    fontSize: fontSize.sm,
    fontWeight: "700",
    color: colors.primary,
  },
  completenessTrack: {
    height: 8,
    backgroundColor: colors.gray200,
    borderRadius: borderRadius.full,
    overflow: "hidden",
  },
  completenessFill: {
    height: 8,
    backgroundColor: colors.gold,
    borderRadius: borderRadius.full,
  },
  errorBox: {
    backgroundColor: "#FEF2F2",
    borderRadius: borderRadius.md,
    padding: spacing.md,
    marginBottom: spacing.lg,
    borderWidth: 1,
    borderColor: "#FECACA",
  },
  errorText: {
    fontSize: fontSize.md,
    color: "#991B1B",
    fontWeight: "600",
  },
  errorHint: {
    fontSize: fontSize.sm,
    color: "#B91C1C",
    marginTop: spacing.xs,
  },
  notice: {
    backgroundColor: colors.sage,
    borderRadius: borderRadius.md,
    padding: spacing.md,
    marginBottom: spacing.lg,
  },
  noticeText: {
    fontSize: fontSize.sm,
    color: colors.primary,
    lineHeight: 20,
  },
  sectionTitle: {
    fontSize: fontSize.xl,
    fontWeight: "700",
    color: colors.gray900,
    marginBottom: spacing.md,
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
  pickerWrapper: {
    backgroundColor: colors.white,
    borderRadius: borderRadius.md,
    borderWidth: 1,
    borderColor: colors.gray200,
    marginBottom: spacing.md,
    overflow: "hidden",
  },
  picker: {
    color: colors.gray900,
  },
  row: {
    flexDirection: "row",
    gap: spacing.sm,
  },
  halfInput: {
    flex: 1,
  },
  saveBtn: {
    backgroundColor: colors.gold,
    borderRadius: borderRadius.md,
    paddingVertical: spacing.md,
    alignItems: "center",
    marginTop: spacing.md,
  },
  btnDisabled: { opacity: 0.6 },
  saveBtnText: {
    fontSize: fontSize.lg,
    fontWeight: "600",
    color: colors.primary,
  },
  webManageText: {
    fontSize: 12,
    color: colors.gray400,
    textAlign: "center",
    marginTop: spacing.lg,
    marginBottom: spacing.xs,
  },
  logoutBtn: {
    borderRadius: borderRadius.md,
    paddingVertical: spacing.md,
    alignItems: "center",
    marginTop: spacing.lg,
    borderWidth: 1,
    borderColor: colors.red500,
  },
  logoutBtnText: {
    fontSize: fontSize.md,
    fontWeight: "600",
    color: colors.red500,
  },
});
