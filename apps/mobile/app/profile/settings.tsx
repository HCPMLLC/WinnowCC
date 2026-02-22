import { useState, useEffect, useCallback } from "react";
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  ScrollView,
  Switch,
  StyleSheet,
  RefreshControl,
  Alert,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import * as FileSystem from "expo-file-system";
import * as Sharing from "expo-sharing";
import { api } from "../../lib/api";
import { getToken } from "../../lib/auth";
import { useAuth } from "../../lib/auth";
import { colors, spacing, fontSize, borderRadius } from "../../lib/theme";
import LoadingSpinner from "../../components/LoadingSpinner";

const API_BASE =
  process.env.EXPO_PUBLIC_API_BASE_URL || "http://localhost:8000";

export default function SettingsScreen() {
  const { logout } = useAuth();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [openToIntros, setOpenToIntros] = useState(false);
  const [togglingIntros, setTogglingIntros] = useState(false);
  const [exportPreview, setExportPreview] = useState<any>(null);
  const [exporting, setExporting] = useState(false);
  const [confirmText, setConfirmText] = useState("");
  const [deleting, setDeleting] = useState(false);

  const loadData = useCallback(async () => {
    try {
      const [profileRes, exportRes] = await Promise.all([
        api.get("/api/profile"),
        api.get("/api/account/export/preview"),
      ]);
      if (profileRes.ok) {
        const profile = await profileRes.json();
        setOpenToIntros(
          profile.profile_json?.preferences?.open_to_introductions ?? false,
        );
      }
      if (exportRes.ok) {
        setExportPreview(await exportRes.json());
      }
    } catch {
      // Silent — non-critical
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const onRefresh = () => {
    setRefreshing(true);
    loadData();
  };

  async function toggleIntros(value: boolean) {
    setTogglingIntros(true);
    try {
      const res = await api.patch("/api/profile/introduction-preferences", {
        open_to_introductions: value,
      });
      if (res.ok) {
        setOpenToIntros(value);
      }
    } catch {
      Alert.alert("Error", "Could not update preference.");
    } finally {
      setTogglingIntros(false);
    }
  }

  async function handleExport() {
    setExporting(true);
    try {
      const token = await getToken();
      const fileUri = `${FileSystem.cacheDirectory}winnow_export.zip`;
      const result = await FileSystem.downloadAsync(
        `${API_BASE}/api/account/export`,
        fileUri,
        { headers: { Authorization: `Bearer ${token}` } },
      );
      await Sharing.shareAsync(result.uri, {
        mimeType: "application/zip",
        dialogTitle: "Your Winnow Data Export",
      });
    } catch {
      Alert.alert("Error", "Could not export data.");
    } finally {
      setExporting(false);
    }
  }

  function handleDeleteAccount() {
    if (confirmText !== "DELETE MY ACCOUNT") {
      Alert.alert("Error", 'Please type "DELETE MY ACCOUNT" to confirm.');
      return;
    }
    Alert.alert(
      "Delete Account",
      "This will permanently delete your account and all data. This cannot be undone.",
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Delete Forever",
          style: "destructive",
          onPress: async () => {
            setDeleting(true);
            try {
              const res = await api.post("/api/account/delete", {
                confirm: "DELETE MY ACCOUNT",
              });
              if (res.ok) {
                Alert.alert("Account Deleted", "Your account has been removed.");
                logout();
              } else {
                const body = await res.text();
                let detail = "Failed to delete account.";
                try { detail = JSON.parse(body).detail || detail; } catch {}
                Alert.alert("Error", detail);
              }
            } catch {
              Alert.alert("Error", "Could not delete account.");
            } finally {
              setDeleting(false);
            }
          },
        },
      ],
    );
  }

  if (loading) return <LoadingSpinner />;

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
      }
    >
      {/* Introduction Preferences */}
      <Text style={styles.sectionTitle}>Recruiter Introductions</Text>
      <View style={styles.card}>
        <View style={styles.toggleRow}>
          <View style={{ flex: 1 }}>
            <Text style={styles.toggleLabel}>Open to introductions</Text>
            <Text style={styles.toggleDesc}>
              Allow recruiters and employers to request an introduction
            </Text>
          </View>
          <Switch
            value={openToIntros}
            onValueChange={toggleIntros}
            disabled={togglingIntros}
            trackColor={{ false: colors.gray300, true: colors.green500 }}
            thumbColor={colors.white}
          />
        </View>
      </View>

      {/* Data Export */}
      <Text style={styles.sectionTitle}>Export My Data</Text>
      <View style={styles.card}>
        <View>
          {exportPreview && (
            <Text style={styles.previewText}>
              {exportPreview.profile_versions} profile versions,{" "}
              {exportPreview.resume_documents} resumes,{" "}
              {exportPreview.matches} matches,{" "}
              {exportPreview.tailored_resumes} tailored documents
            </Text>
          )}
          <TouchableOpacity
            style={[styles.exportBtn, exporting && styles.disabled]}
            onPress={handleExport}
            disabled={exporting}
          >
            <Ionicons name="download-outline" size={18} color={colors.primary} />
            <Text style={styles.exportBtnText}>
              {exporting ? "Exporting..." : "Download My Data"}
            </Text>
          </TouchableOpacity>
        </View>
      </View>

      {/* Danger Zone */}
      <Text style={[styles.sectionTitle, { color: colors.red500 }]}>
        Danger Zone
      </Text>
      <View style={[styles.card, styles.dangerCard]}>
        <Text style={styles.dangerTitle}>Delete Account</Text>
        <Text style={styles.dangerDesc}>
          Permanently delete your account and all associated data. This action
          cannot be undone.
        </Text>
        <TextInput
          style={styles.confirmInput}
          value={confirmText}
          onChangeText={setConfirmText}
          placeholder='Type "DELETE MY ACCOUNT"'
          autoCapitalize="characters"
        />
        <TouchableOpacity
          style={[
            styles.deleteBtn,
            confirmText !== "DELETE MY ACCOUNT" && styles.disabled,
          ]}
          onPress={handleDeleteAccount}
          disabled={confirmText !== "DELETE MY ACCOUNT" || deleting}
        >
          <Text style={styles.deleteBtnText}>
            {deleting ? "Deleting..." : "Delete My Account"}
          </Text>
        </TouchableOpacity>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.gray50 },
  content: { padding: spacing.md, paddingBottom: spacing.xxl },
  sectionTitle: {
    fontSize: fontSize.lg,
    fontWeight: "700",
    color: colors.gray900,
    marginTop: spacing.lg,
    marginBottom: spacing.sm,
  },
  card: {
    backgroundColor: colors.white,
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    shadowColor: "#000",
    shadowOpacity: 0.05,
    shadowRadius: 8,
    elevation: 2,
  },
  toggleRow: {
    flexDirection: "row",
    alignItems: "center",
  },
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
  lockedText: {
    fontSize: fontSize.sm,
    color: colors.gray500,
    fontStyle: "italic",
  },
  previewText: {
    fontSize: fontSize.sm,
    color: colors.gray600,
    marginBottom: spacing.md,
  },
  exportBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    backgroundColor: colors.gold,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    borderRadius: borderRadius.md,
    alignSelf: "flex-start",
  },
  exportBtnText: {
    fontSize: fontSize.sm,
    fontWeight: "600",
    color: colors.primary,
  },
  dangerCard: {
    borderWidth: 1,
    borderColor: colors.red500,
  },
  dangerTitle: {
    fontSize: fontSize.md,
    fontWeight: "700",
    color: colors.red500,
  },
  dangerDesc: {
    fontSize: fontSize.sm,
    color: colors.gray600,
    marginTop: spacing.xs,
    marginBottom: spacing.md,
  },
  confirmInput: {
    borderWidth: 1,
    borderColor: colors.gray200,
    borderRadius: borderRadius.md,
    padding: spacing.md,
    fontSize: fontSize.sm,
    color: colors.gray900,
    backgroundColor: colors.white,
  },
  deleteBtn: {
    backgroundColor: colors.red500,
    paddingVertical: spacing.sm,
    borderRadius: borderRadius.md,
    alignItems: "center",
    marginTop: spacing.md,
  },
  deleteBtnText: {
    fontSize: fontSize.md,
    fontWeight: "600",
    color: colors.white,
  },
  disabled: { opacity: 0.5 },
});
