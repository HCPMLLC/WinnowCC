import { useEffect, useState } from "react";
import {
  View,
  Text,
  TextInput,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
  Alert,
} from "react-native";
import { Picker } from "@react-native-picker/picker";
import { useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { useAuth } from "../../lib/auth";
import { api } from "../../lib/api";
import LoadingSpinner from "../../components/LoadingSpinner";
import ProfileMenuItem from "../../components/ProfileMenuItem";
import {
  COMPANY_SIZES,
  INDUSTRIES,
  type EmployerProfile,
} from "../../lib/employer-types";
import { colors, spacing, fontSize, borderRadius } from "../../lib/theme";

export default function EmployerSettingsScreen() {
  const { email, role, logout } = useAuth();
  const router = useRouter();
  const [profile, setProfile] = useState<EmployerProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [showEditProfile, setShowEditProfile] = useState(false);

  // Edit form state
  const [editName, setEditName] = useState("");
  const [editSize, setEditSize] = useState("");
  const [editIndustry, setEditIndustry] = useState("");
  const [editWebsite, setEditWebsite] = useState("");
  const [editBillingEmail, setEditBillingEmail] = useState("");
  const [editDescription, setEditDescription] = useState("");

  const loadData = async () => {
    try {
      const profileRes = await api.get("/api/employer/profile");

      if (profileRes.ok) {
        const p = await profileRes.json();
        setProfile(p);
        setEditName(p.company_name ?? "");
        setEditSize(p.company_size ?? "");
        setEditIndustry(p.industry ?? "");
        setEditWebsite(p.company_website ?? "");
        setEditBillingEmail(p.billing_email ?? "");
        setEditDescription(p.company_description ?? "");
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
  }, []);

  const onRefresh = () => {
    setRefreshing(true);
    loadData();
  };

  const handleSaveProfile = async () => {
    if (!editName.trim()) {
      Alert.alert("Required", "Company name is required.");
      return;
    }
    setSaving(true);
    try {
      const res = await api.patch("/api/employer/profile", {
        company_name: editName.trim(),
        company_size: editSize || null,
        industry: editIndustry || null,
        company_website: editWebsite.trim() || null,
        billing_email: editBillingEmail.trim() || null,
        company_description: editDescription.trim() || null,
      });
      if (res.ok) {
        Alert.alert("Saved", "Profile updated.");
        setShowEditProfile(false);
        loadData();
      } else {
        Alert.alert("Error", "Failed to save profile.");
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

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
      }
    >
      <Text style={styles.email}>{email}</Text>

      {/* Profile card */}
      {profile && (
        <View style={[styles.card, { marginTop: spacing.md }]}>
          <Text style={styles.companyName}>{profile.company_name}</Text>
          {profile.industry && (
            <Text style={styles.companyMeta}>{profile.industry}</Text>
          )}
          {profile.company_size && (
            <Text style={styles.companyMeta}>
              {profile.company_size} employees
            </Text>
          )}
          {profile.company_website && (
            <Text style={styles.companyMeta}>{profile.company_website}</Text>
          )}
        </View>
      )}

      {/* Edit profile */}
      <ProfileMenuItem
        icon="create-outline"
        label="Edit Profile"
        subtitle="Company info, billing email"
        onPress={() => setShowEditProfile(!showEditProfile)}
      />

      {showEditProfile && (
        <View style={styles.editSection}>
          <Text style={styles.label}>Company Name</Text>
          <TextInput
            style={styles.input}
            value={editName}
            onChangeText={setEditName}
            placeholder="Company name"
            placeholderTextColor={colors.gray400}
          />

          <Text style={styles.label}>Company Size</Text>
          <View style={styles.pickerWrapper}>
            <Picker
              selectedValue={editSize}
              onValueChange={setEditSize}
              style={styles.picker}
            >
              <Picker.Item label="Select size..." value="" />
              {COMPANY_SIZES.map((s) => (
                <Picker.Item key={s} label={s} value={s} />
              ))}
            </Picker>
          </View>

          <Text style={styles.label}>Industry</Text>
          <View style={styles.pickerWrapper}>
            <Picker
              selectedValue={editIndustry}
              onValueChange={setEditIndustry}
              style={styles.picker}
            >
              <Picker.Item label="Select industry..." value="" />
              {INDUSTRIES.map((i) => (
                <Picker.Item key={i} label={i} value={i} />
              ))}
            </Picker>
          </View>

          <Text style={styles.label}>Website</Text>
          <TextInput
            style={styles.input}
            value={editWebsite}
            onChangeText={setEditWebsite}
            placeholder="https://example.com"
            placeholderTextColor={colors.gray400}
            keyboardType="url"
            autoCapitalize="none"
          />

          <Text style={styles.label}>Billing Email</Text>
          <TextInput
            style={styles.input}
            value={editBillingEmail}
            onChangeText={setEditBillingEmail}
            placeholder="billing@company.com"
            placeholderTextColor={colors.gray400}
            keyboardType="email-address"
            autoCapitalize="none"
          />

          <Text style={styles.label}>Description</Text>
          <TextInput
            style={[styles.input, styles.textArea]}
            value={editDescription}
            onChangeText={setEditDescription}
            placeholder="Brief company description"
            placeholderTextColor={colors.gray400}
            multiline
            numberOfLines={3}
          />

          <TouchableOpacity
            style={[styles.saveBtn, saving && styles.btnDisabled]}
            onPress={handleSaveProfile}
            disabled={saving}
          >
            <Text style={styles.saveBtnText}>
              {saving ? "Saving..." : "Save Profile"}
            </Text>
          </TouchableOpacity>
        </View>
      )}

      {/* Quick links */}
      <Text style={styles.sectionTitle}>Quick Links</Text>

      <ProfileMenuItem
        icon="analytics-outline"
        label="Analytics"
        subtitle="View performance metrics"
        onPress={() => router.push("/employer/analytics")}
      />

      <ProfileMenuItem
        icon="bookmark-outline"
        label="Saved Candidates"
        subtitle="Manage saved candidates"
        onPress={() => router.push("/employer/saved")}
      />

      {/* Role switcher */}
      {role === "both" && (
        <TouchableOpacity
          style={styles.switchBanner}
          onPress={() => router.push("/(tabs)/dashboard")}
        >
          <Ionicons name="swap-horizontal" size={16} color={colors.gold} />
          <Text style={styles.switchText}>Switch to Candidate View</Text>
        </TouchableOpacity>
      )}

      {(role === "recruiter" || role === "both") && (
        <TouchableOpacity
          style={styles.switchBanner}
          onPress={() => router.push("/(recruiter-tabs)/dashboard")}
        >
          <Ionicons name="swap-horizontal" size={16} color={colors.gold} />
          <Text style={styles.switchText}>Switch to Recruiter View</Text>
        </TouchableOpacity>
      )}

      {/* Logout */}
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
    marginBottom: spacing.md,
  },
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
  sectionTitle: {
    fontSize: fontSize.lg,
    fontWeight: "700",
    color: colors.gray900,
    marginBottom: spacing.sm,
    marginTop: spacing.sm,
  },
  companyName: {
    fontSize: fontSize.xl,
    fontWeight: "700",
    color: colors.gray900,
  },
  companyMeta: {
    fontSize: fontSize.sm,
    color: colors.gray500,
    marginTop: 2,
  },
  editSection: {
    backgroundColor: colors.white,
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    marginBottom: spacing.md,
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
  textArea: {
    minHeight: 80,
    textAlignVertical: "top",
  },
  pickerWrapper: {
    backgroundColor: colors.gray50,
    borderRadius: borderRadius.md,
    borderWidth: 1,
    borderColor: colors.gray200,
    marginBottom: spacing.md,
    overflow: "hidden",
  },
  picker: { color: colors.gray900 },
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
  switchBanner: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    backgroundColor: colors.primaryLight,
    borderRadius: borderRadius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    marginTop: spacing.sm,
    marginBottom: spacing.sm,
  },
  switchText: {
    fontSize: fontSize.sm,
    fontWeight: "600",
    color: colors.gold,
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
