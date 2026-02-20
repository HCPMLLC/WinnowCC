import { useEffect, useState } from "react";
import {
  View,
  Text,
  TextInput,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Switch,
  RefreshControl,
  Alert,
  Linking,
} from "react-native";
import { Picker } from "@react-native-picker/picker";
import { useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { useAuth } from "../../lib/auth";
import { api } from "../../lib/api";
import LoadingSpinner from "../../components/LoadingSpinner";
import ProfileMenuItem from "../../components/ProfileMenuItem";
import type {
  RecruiterProfile,
  RecruiterPlan,
  TeamMember,
} from "../../lib/recruiter-types";
import { colors, spacing, fontSize, borderRadius } from "../../lib/theme";

const COMPANY_TYPES = [
  { label: "Agency", value: "agency" },
  { label: "Boutique", value: "boutique" },
  { label: "Corporate", value: "corporate" },
  { label: "Independent", value: "independent" },
];

export default function RecruiterSettingsScreen() {
  const { email, role, logout } = useAuth();
  const router = useRouter();
  const [profile, setProfile] = useState<RecruiterProfile | null>(null);
  const [plan, setPlan] = useState<RecruiterPlan | null>(null);
  const [team, setTeam] = useState<TeamMember[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [showEditProfile, setShowEditProfile] = useState(false);

  // Edit form
  const [editName, setEditName] = useState("");
  const [editType, setEditType] = useState("");
  const [editWebsite, setEditWebsite] = useState("");
  const [autoPopulate, setAutoPopulate] = useState(false);

  const loadData = async () => {
    try {
      const [profileRes, planRes, teamRes] = await Promise.all([
        api.get("/api/recruiter/profile"),
        api.get("/api/recruiter/plan").catch(() => null),
        api.get("/api/recruiter/team").catch(() => null),
      ]);

      if (profileRes.ok) {
        const p = await profileRes.json();
        setProfile(p);
        setEditName(p.company_name ?? "");
        setEditType(p.company_type ?? "");
        setEditWebsite(p.company_website ?? "");
        setAutoPopulate(p.auto_populate_pipeline ?? false);
      }
      if (planRes && planRes.ok) {
        setPlan(await planRes.json());
      }
      if (teamRes && teamRes.ok) {
        const data = await teamRes.json();
        setTeam(Array.isArray(data) ? data : data.members ?? []);
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
      const res = await api.patch("/api/recruiter/profile", {
        company_name: editName.trim(),
        company_type: editType || null,
        company_website: editWebsite.trim() || null,
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

  const handleToggleAutoPopulate = async (value: boolean) => {
    setAutoPopulate(value);
    try {
      await api.patch("/api/recruiter/profile", {
        auto_populate_pipeline: value,
      });
    } catch {
      setAutoPopulate(!value);
    }
  };

  const handleUpgrade = async (tier: string) => {
    try {
      const res = await api.post("/api/billing/unified-checkout", {
        segment: "recruiter",
        tier,
        interval: "monthly",
      });
      if (res.ok) {
        const data = await res.json();
        if (data.checkout_url) {
          Linking.openURL(data.checkout_url);
        }
      } else {
        Alert.alert("Error", "Failed to start checkout.");
      }
    } catch {
      Alert.alert("Error", "Something went wrong.");
    }
  };

  const handleManageBilling = async () => {
    try {
      const res = await api.post("/api/billing/portal", {});
      if (res.ok) {
        const data = await res.json();
        if (data.portal_url) {
          Linking.openURL(data.portal_url);
        }
      } else {
        Alert.alert("Error", "Failed to open billing portal.");
      }
    } catch {
      Alert.alert("Error", "Something went wrong.");
    }
  };

  const handleLogout = () => {
    Alert.alert("Log Out", "Are you sure you want to log out?", [
      { text: "Cancel", style: "cancel" },
      { text: "Log Out", style: "destructive", onPress: logout },
    ]);
  };

  if (loading) return <LoadingSpinner />;

  const tier = plan?.tier ?? profile?.subscription_tier ?? "free";

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
        <View style={styles.card}>
          <Text style={styles.companyName}>{profile.company_name}</Text>
          {profile.company_type && (
            <Text style={styles.companyMeta}>
              {profile.company_type.charAt(0).toUpperCase() +
                profile.company_type.slice(1)}
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
        subtitle="Company name, type, website"
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

          <Text style={styles.label}>Company Type</Text>
          <View style={styles.pickerWrapper}>
            <Picker
              selectedValue={editType}
              onValueChange={setEditType}
              style={styles.picker}
            >
              <Picker.Item label="Select type..." value="" />
              {COMPANY_TYPES.map((t) => (
                <Picker.Item key={t.value} label={t.label} value={t.value} />
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

      {/* Plan & Billing */}
      <Text style={styles.sectionTitle}>Plan & Billing</Text>

      {/* Trial banner */}
      {profile?.is_trial_active && (
        <View style={styles.trialBanner}>
          <Ionicons name="time-outline" size={16} color={colors.primary} />
          <Text style={styles.trialText}>
            Trial: {profile.trial_days_remaining} days remaining
          </Text>
        </View>
      )}

      <View style={styles.card}>
        <View style={styles.planRow}>
          <Text style={styles.planLabel}>Current Plan</Text>
          <View style={styles.planBadge}>
            <Text style={styles.planBadgeText}>{tier.toUpperCase()}</Text>
          </View>
        </View>

        {tier !== "agency" && (
          <View style={styles.upgradeSection}>
            {tier === "free" && (
              <>
                <UpgradeButton
                  label="Solo — $79/mo"
                  onPress={() => handleUpgrade("solo")}
                />
                <UpgradeButton
                  label="Team — $149/mo"
                  onPress={() => handleUpgrade("team")}
                />
                <UpgradeButton
                  label="Agency — $299/mo"
                  onPress={() => handleUpgrade("agency")}
                />
              </>
            )}
            {tier === "solo" && (
              <>
                <UpgradeButton
                  label="Team — $149/mo"
                  onPress={() => handleUpgrade("team")}
                />
                <UpgradeButton
                  label="Agency — $299/mo"
                  onPress={() => handleUpgrade("agency")}
                />
              </>
            )}
            {tier === "team" && (
              <UpgradeButton
                label="Agency — $299/mo"
                onPress={() => handleUpgrade("agency")}
              />
            )}
          </View>
        )}

        {tier !== "free" && (
          <TouchableOpacity
            style={styles.manageBtn}
            onPress={handleManageBilling}
          >
            <Text style={styles.manageBtnText}>Manage Subscription</Text>
          </TouchableOpacity>
        )}
      </View>

      {/* Team */}
      <Text style={styles.sectionTitle}>Team</Text>
      <View style={styles.card}>
        {profile && (
          <Text style={styles.seatInfo}>
            Seats: {profile.seats_used} / {profile.seats_purchased} used
          </Text>
        )}
        {team.length > 0 ? (
          team.map((member) => (
            <View key={member.id} style={styles.teamRow}>
              <View style={styles.teamInfo}>
                <Text style={styles.teamEmail}>{member.email}</Text>
                <Text style={styles.teamRole}>{member.role}</Text>
              </View>
              <Text style={styles.teamStatus}>
                {member.accepted_at ? "Active" : "Invited"}
              </Text>
            </View>
          ))
        ) : (
          <Text style={styles.noData}>
            No team members. Invite teammates on winnow.app.
          </Text>
        )}
      </View>

      {/* Pipeline Preferences */}
      <Text style={styles.sectionTitle}>Pipeline Preferences</Text>
      <View style={styles.card}>
        <View style={styles.toggleRow}>
          <View style={styles.toggleInfo}>
            <Text style={styles.toggleLabel}>Auto-populate Pipeline</Text>
            <Text style={styles.toggleDesc}>
              Automatically add matched candidates to your pipeline
            </Text>
          </View>
          <Switch
            value={autoPopulate}
            onValueChange={handleToggleAutoPopulate}
            trackColor={{ false: colors.gray300, true: colors.gold }}
            thumbColor={colors.white}
          />
        </View>
      </View>

      {/* Role switcher */}
      {role === "both" && (
        <TouchableOpacity
          style={styles.switchBanner}
          onPress={() => router.replace("/(tabs)/dashboard")}
        >
          <Ionicons name="swap-horizontal" size={16} color={colors.gold} />
          <Text style={styles.switchText}>Switch to Candidate View</Text>
        </TouchableOpacity>
      )}

      {/* Logout */}
      <TouchableOpacity style={styles.logoutBtn} onPress={handleLogout}>
        <Text style={styles.logoutBtnText}>Log Out</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

function UpgradeButton({
  label,
  onPress,
}: {
  label: string;
  onPress: () => void;
}) {
  return (
    <TouchableOpacity style={upgradeStyles.btn} onPress={onPress}>
      <Text style={upgradeStyles.text}>{label}</Text>
      <Ionicons name="arrow-forward" size={16} color={colors.primary} />
    </TouchableOpacity>
  );
}

const upgradeStyles = StyleSheet.create({
  btn: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    backgroundColor: colors.sage,
    borderRadius: borderRadius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    marginTop: spacing.sm,
  },
  text: {
    fontSize: fontSize.sm,
    fontWeight: "600",
    color: colors.primary,
  },
});

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
  sectionTitle: {
    fontSize: fontSize.lg,
    fontWeight: "700",
    color: colors.gray900,
    marginBottom: spacing.sm,
    marginTop: spacing.sm,
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
  trialBanner: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    backgroundColor: colors.gold,
    borderRadius: borderRadius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    marginBottom: spacing.sm,
  },
  trialText: {
    fontSize: fontSize.sm,
    fontWeight: "600",
    color: colors.primary,
  },
  planRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  planLabel: {
    fontSize: fontSize.md,
    fontWeight: "600",
    color: colors.gray700,
  },
  planBadge: {
    backgroundColor: colors.primary,
    borderRadius: borderRadius.full,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
  },
  planBadgeText: {
    color: colors.gold,
    fontSize: fontSize.xs,
    fontWeight: "600",
  },
  upgradeSection: { marginTop: spacing.sm },
  manageBtn: {
    borderWidth: 1,
    borderColor: colors.primary,
    borderRadius: borderRadius.md,
    paddingVertical: spacing.sm,
    alignItems: "center",
    marginTop: spacing.md,
  },
  manageBtnText: {
    fontSize: fontSize.sm,
    fontWeight: "600",
    color: colors.primary,
  },
  seatInfo: {
    fontSize: fontSize.sm,
    color: colors.gray600,
    marginBottom: spacing.sm,
  },
  teamRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    paddingVertical: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.gray100,
  },
  teamInfo: { flex: 1 },
  teamEmail: {
    fontSize: fontSize.sm,
    fontWeight: "600",
    color: colors.gray900,
  },
  teamRole: {
    fontSize: fontSize.xs,
    color: colors.gray500,
    marginTop: 2,
  },
  teamStatus: {
    fontSize: fontSize.xs,
    fontWeight: "600",
    color: colors.gray400,
  },
  noData: {
    fontSize: fontSize.sm,
    color: colors.gray400,
    fontStyle: "italic",
  },
  toggleRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  toggleInfo: { flex: 1, marginRight: spacing.md },
  toggleLabel: {
    fontSize: fontSize.md,
    fontWeight: "600",
    color: colors.gray900,
  },
  toggleDesc: {
    fontSize: fontSize.xs,
    color: colors.gray500,
    marginTop: 2,
  },
  switchBanner: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    backgroundColor: colors.primaryLight,
    borderRadius: borderRadius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    marginTop: spacing.md,
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
