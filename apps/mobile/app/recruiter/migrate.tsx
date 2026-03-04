import { useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  ActivityIndicator,
  Alert,
} from "react-native";
import * as DocumentPicker from "expo-document-picker";
import { Ionicons } from "@expo/vector-icons";
import { uploadFile, api } from "../../lib/api";
import { handleFeatureGateResponse } from "../../lib/featureGate";
import { usePolling } from "../../lib/usePolling";
import { colors, spacing, fontSize, borderRadius } from "../../lib/theme";

type Step = "upload" | "preview" | "importing" | "done";

interface PreviewData {
  migration_id: number;
  detected_platform: string;
  total_records: number;
  record_types: Record<string, number>;
}

interface ImportStatus {
  status: string;
  imported: number;
  total: number;
  errors: string[];
}

export default function RecruiterMigrateScreen() {
  const [step, setStep] = useState<Step>("upload");
  const [uploading, setUploading] = useState(false);
  const [preview, setPreview] = useState<PreviewData | null>(null);
  const [importStatus, setImportStatus] = useState<ImportStatus | null>(null);
  const [polling, setPolling] = useState(false);

  usePolling<ImportStatus>({
    fetchFn: async () => {
      if (!preview) return { status: "done", imported: 0, total: 0, errors: [] };
      const res = await api.get(`/api/recruiter/migration/${preview.migration_id}`);
      const d = await res.json();
      setImportStatus(d);
      return d;
    },
    intervalMs: 2000,
    shouldPoll: (d) => d.status === "processing" || d.status === "pending",
    onComplete: (d) => {
      setImportStatus(d);
      setPolling(false);
      setStep("done");
    },
    enabled: polling,
  });

  const handleUpload = async () => {
    try {
      const result = await DocumentPicker.getDocumentAsync({
        type: [
          "text/csv",
          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
          "application/json",
        ],
      });

      if (result.canceled || !result.assets?.[0]) return;

      const file = result.assets[0];
      setUploading(true);

      const res = await uploadFile(
        "/api/recruiter/migration/upload",
        file.uri,
        file.name,
        file.mimeType || "text/csv",
      );

      if (handleFeatureGateResponse(res)) return;

      if (res.ok) {
        const data = await res.json();
        setPreview(data);
        setStep("preview");
      } else {
        const err = await res.json().catch(() => ({}));
        Alert.alert("Error", err.detail || "Upload failed.");
      }
    } catch {
      Alert.alert("Error", "Something went wrong.");
    } finally {
      setUploading(false);
    }
  };

  const handleStartImport = async () => {
    if (!preview) return;
    try {
      const res = await api.post(`/api/recruiter/migration/${preview.migration_id}/start`);
      if (handleFeatureGateResponse(res)) return;
      if (res.ok) {
        setStep("importing");
        setPolling(true);
      } else {
        Alert.alert("Error", "Could not start import.");
      }
    } catch {
      Alert.alert("Error", "Something went wrong.");
    }
  };

  const handleReset = () => {
    setStep("upload");
    setPreview(null);
    setImportStatus(null);
    setPolling(false);
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.pageTitle}>CRM Migration</Text>

      {step === "upload" && (
        <View style={styles.uploadCard}>
          <Ionicons name="cloud-upload-outline" size={48} color={colors.gray300} />
          <Text style={styles.uploadText}>
            Upload your CRM export file (CSV, XLSX, or JSON) to migrate data
            into Winnow.
          </Text>
          <TouchableOpacity
            style={styles.uploadBtn}
            onPress={handleUpload}
            disabled={uploading}
          >
            {uploading ? (
              <ActivityIndicator color={colors.primary} />
            ) : (
              <Text style={styles.uploadBtnText}>Choose File</Text>
            )}
          </TouchableOpacity>
        </View>
      )}

      {step === "preview" && preview && (
        <View>
          <View style={styles.card}>
            <Text style={styles.sectionTitle}>Preview</Text>
            <View style={styles.previewRow}>
              <Text style={styles.previewLabel}>Detected Platform</Text>
              <Text style={styles.previewValue}>{preview.detected_platform}</Text>
            </View>
            <View style={styles.previewRow}>
              <Text style={styles.previewLabel}>Total Records</Text>
              <Text style={styles.previewValue}>{preview.total_records}</Text>
            </View>
            {Object.entries(preview.record_types).map(([type, count]) => (
              <View key={type} style={styles.previewRow}>
                <Text style={styles.previewLabel}>{type}</Text>
                <Text style={styles.previewValue}>{count}</Text>
              </View>
            ))}
          </View>

          <View style={styles.actionRow}>
            <TouchableOpacity style={styles.cancelBtn} onPress={handleReset}>
              <Text style={styles.cancelBtnText}>Cancel</Text>
            </TouchableOpacity>
            <TouchableOpacity style={styles.importBtn} onPress={handleStartImport}>
              <Text style={styles.importBtnText}>Start Import</Text>
            </TouchableOpacity>
          </View>
        </View>
      )}

      {step === "importing" && (
        <View style={styles.progressCard}>
          <ActivityIndicator size="large" color={colors.primary} />
          <Text style={styles.progressTitle}>Importing...</Text>
          {importStatus && (
            <Text style={styles.progressText}>
              {importStatus.imported} / {importStatus.total} records
            </Text>
          )}
        </View>
      )}

      {step === "done" && importStatus && (
        <View style={styles.doneCard}>
          <Ionicons name="checkmark-circle" size={48} color={colors.green500} />
          <Text style={styles.doneTitle}>Import Complete</Text>
          <Text style={styles.doneText}>
            {importStatus.imported} of {importStatus.total} records imported.
          </Text>
          {importStatus.errors.length > 0 && (
            <View style={styles.errorsBox}>
              <Text style={styles.errorsLabel}>
                {importStatus.errors.length} error(s):
              </Text>
              {importStatus.errors.slice(0, 5).map((e, i) => (
                <Text key={i} style={styles.errorItem}>{"\u2022"} {e}</Text>
              ))}
            </View>
          )}
          <TouchableOpacity style={styles.resetBtn} onPress={handleReset}>
            <Text style={styles.resetBtnText}>Import Another File</Text>
          </TouchableOpacity>
        </View>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.gray50 },
  content: { padding: spacing.md, paddingBottom: spacing.xxl },
  pageTitle: {
    fontSize: fontSize.xxl,
    fontWeight: "700",
    color: colors.gray900,
    marginBottom: spacing.lg,
  },
  uploadCard: {
    backgroundColor: colors.white,
    borderRadius: borderRadius.lg,
    padding: spacing.xl,
    alignItems: "center",
    gap: spacing.md,
    borderWidth: 2,
    borderColor: colors.gray200,
    borderStyle: "dashed",
  },
  uploadText: {
    fontSize: fontSize.sm,
    color: colors.gray500,
    textAlign: "center",
    lineHeight: 20,
  },
  uploadBtn: {
    backgroundColor: colors.gold,
    borderRadius: borderRadius.md,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.xl,
  },
  uploadBtnText: {
    fontSize: fontSize.md,
    fontWeight: "600",
    color: colors.primary,
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
    marginBottom: spacing.md,
  },
  previewRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingVertical: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.gray100,
  },
  previewLabel: {
    fontSize: fontSize.sm,
    color: colors.gray600,
    textTransform: "capitalize",
  },
  previewValue: {
    fontSize: fontSize.sm,
    fontWeight: "600",
    color: colors.gray900,
  },
  actionRow: {
    flexDirection: "row",
    gap: spacing.sm,
  },
  cancelBtn: {
    flex: 1,
    borderWidth: 1,
    borderColor: colors.gray300,
    borderRadius: borderRadius.md,
    paddingVertical: spacing.md,
    alignItems: "center",
  },
  cancelBtnText: {
    fontSize: fontSize.md,
    fontWeight: "500",
    color: colors.gray600,
  },
  importBtn: {
    flex: 1,
    backgroundColor: colors.gold,
    borderRadius: borderRadius.md,
    paddingVertical: spacing.md,
    alignItems: "center",
  },
  importBtnText: {
    fontSize: fontSize.md,
    fontWeight: "600",
    color: colors.primary,
  },
  progressCard: {
    backgroundColor: colors.white,
    borderRadius: borderRadius.lg,
    padding: spacing.xl,
    alignItems: "center",
    gap: spacing.md,
  },
  progressTitle: {
    fontSize: fontSize.lg,
    fontWeight: "600",
    color: colors.gray900,
  },
  progressText: {
    fontSize: fontSize.md,
    color: colors.gray500,
  },
  doneCard: {
    backgroundColor: colors.white,
    borderRadius: borderRadius.lg,
    padding: spacing.xl,
    alignItems: "center",
    gap: spacing.sm,
  },
  doneTitle: {
    fontSize: fontSize.xl,
    fontWeight: "700",
    color: colors.gray900,
  },
  doneText: {
    fontSize: fontSize.md,
    color: colors.gray600,
  },
  errorsBox: {
    backgroundColor: "#FEF2F2",
    borderRadius: borderRadius.md,
    padding: spacing.md,
    width: "100%",
    marginTop: spacing.sm,
  },
  errorsLabel: {
    fontSize: fontSize.sm,
    fontWeight: "600",
    color: "#991B1B",
    marginBottom: spacing.xs,
  },
  errorItem: {
    fontSize: fontSize.xs,
    color: "#B91C1C",
    lineHeight: 18,
  },
  resetBtn: {
    borderWidth: 1,
    borderColor: colors.gray300,
    borderRadius: borderRadius.md,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.xl,
    marginTop: spacing.md,
  },
  resetBtnText: {
    fontSize: fontSize.md,
    fontWeight: "500",
    color: colors.gray600,
  },
});
