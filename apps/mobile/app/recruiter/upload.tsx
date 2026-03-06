import { useState } from "react";
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ScrollView,
  Alert,
} from "react-native";
import * as DocumentPicker from "expo-document-picker";
import { Ionicons } from "@expo/vector-icons";
import { getToken } from "../../lib/auth";
import { API_BASE } from "../../lib/api";
import { colors, spacing, fontSize, borderRadius } from "../../lib/theme";

interface FileResult {
  filename: string;
  success: boolean;
  status: string | null;
  parsed_name: string | null;
  error: string | null;
}

interface UploadResponse {
  results: FileResult[];
  total_submitted: number;
  total_succeeded: number;
  total_failed: number;
  remaining_monthly_quota: number;
  upgrade_recommendation: string | null;
}

interface PickedFile {
  uri: string;
  name: string;
  mimeType: string | undefined;
}

const STATUS_COLORS: Record<string, string> = {
  matched: colors.green500,
  new: colors.blue500,
  linked_platform: colors.amber500,
  failed: colors.red500,
};

export default function RecruiterUploadScreen() {
  const [files, setFiles] = useState<PickedFile[]>([]);
  const [uploading, setUploading] = useState(false);
  const [response, setResponse] = useState<UploadResponse | null>(null);

  const pickFiles = async () => {
    try {
      const result = await DocumentPicker.getDocumentAsync({
        type: [
          "application/pdf",
          "application/msword",
          "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ],
        multiple: true,
      });

      if (!result.canceled && result.assets) {
        const newFiles = result.assets.map((a) => ({
          uri: a.uri,
          name: a.name,
          mimeType: a.mimeType,
        }));
        setFiles((prev) => [...prev, ...newFiles]);
        setResponse(null);
      }
    } catch {
      Alert.alert("Error", "Could not open file picker.");
    }
  };

  const removeFile = (index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const handleUpload = async () => {
    if (files.length === 0) return;
    setUploading(true);
    setResponse(null);

    try {
      const token = await getToken();
      const formData = new FormData();

      for (const file of files) {
        formData.append("files", {
          uri: file.uri,
          name: file.name,
          type: file.mimeType || "application/pdf",
        } as any);
      }

      const res = await fetch(
        `${API_BASE}/api/recruiter/pipeline/upload-resumes`,
        {
          method: "POST",
          headers: token ? { Authorization: `Bearer ${token}` } : {},
          body: formData,
        }
      );

      if (res.ok) {
        const data: UploadResponse = await res.json();
        setResponse(data);
        setFiles([]);
      } else {
        const err = await res.json().catch(() => null);
        Alert.alert("Upload Failed", err?.detail || `Error ${res.status}`);
      }
    } catch {
      Alert.alert("Error", "Could not connect to server.");
    } finally {
      setUploading(false);
    }
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.heading}>Bulk Resume Upload</Text>
      <Text style={styles.subheading}>
        Upload candidate resumes (PDF, DOC, DOCX) to automatically parse and add
        them to your pipeline.
      </Text>

      {/* Drop zone */}
      <TouchableOpacity style={styles.dropZone} onPress={pickFiles}>
        <Ionicons name="cloud-upload-outline" size={40} color={colors.gray400} />
        <Text style={styles.dropText}>Tap to select resumes</Text>
        <Text style={styles.dropHint}>PDF, DOC, DOCX</Text>
      </TouchableOpacity>

      {/* Selected files */}
      {files.length > 0 && (
        <View style={styles.fileList}>
          <Text style={styles.sectionTitle}>
            Selected ({files.length} file{files.length !== 1 ? "s" : ""})
          </Text>
          {files.map((file, i) => (
            <View key={`${file.name}-${i}`} style={styles.fileRow}>
              <Ionicons name="document-outline" size={20} color={colors.gray500} />
              <Text style={styles.fileName} numberOfLines={1}>
                {file.name}
              </Text>
              <TouchableOpacity onPress={() => removeFile(i)}>
                <Ionicons name="close-circle" size={20} color={colors.red500} />
              </TouchableOpacity>
            </View>
          ))}

          <TouchableOpacity
            style={[styles.uploadBtn, uploading && styles.uploadBtnDisabled]}
            onPress={handleUpload}
            disabled={uploading}
          >
            <Ionicons name="cloud-upload" size={20} color={colors.white} />
            <Text style={styles.uploadBtnText}>
              {uploading ? "Uploading..." : `Upload ${files.length} Resume${files.length !== 1 ? "s" : ""}`}
            </Text>
          </TouchableOpacity>
        </View>
      )}

      {/* Results */}
      {response && (
        <View style={styles.results}>
          <Text style={styles.sectionTitle}>Upload Results</Text>

          <View style={styles.summaryRow}>
            <View style={styles.summaryBox}>
              <Text style={styles.summaryValue}>{response.total_submitted}</Text>
              <Text style={styles.summaryLabel}>Submitted</Text>
            </View>
            <View style={[styles.summaryBox, { borderColor: colors.green500 }]}>
              <Text style={[styles.summaryValue, { color: colors.green500 }]}>
                {response.total_succeeded}
              </Text>
              <Text style={styles.summaryLabel}>Succeeded</Text>
            </View>
            <View style={[styles.summaryBox, { borderColor: colors.red500 }]}>
              <Text style={[styles.summaryValue, { color: colors.red500 }]}>
                {response.total_failed}
              </Text>
              <Text style={styles.summaryLabel}>Failed</Text>
            </View>
          </View>

          {response.remaining_monthly_quota >= 0 && (
            <Text style={styles.quotaText}>
              {response.remaining_monthly_quota} uploads remaining this month
            </Text>
          )}

          {response.upgrade_recommendation && (
            <Text style={styles.upgradeText}>
              {response.upgrade_recommendation}
            </Text>
          )}

          {response.results.map((r, i) => (
            <View key={i} style={styles.resultRow}>
              <View
                style={[
                  styles.resultDot,
                  {
                    backgroundColor:
                      STATUS_COLORS[r.status || (r.success ? "new" : "failed")] ||
                      colors.gray400,
                  },
                ]}
              />
              <View style={styles.resultInfo}>
                <Text style={styles.resultName} numberOfLines={1}>
                  {r.parsed_name || r.filename}
                </Text>
                {r.error && (
                  <Text style={styles.resultError}>{r.error}</Text>
                )}
              </View>
              <Text style={styles.resultStatus}>
                {r.status || (r.success ? "OK" : "Error")}
              </Text>
            </View>
          ))}
        </View>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.gray50 },
  content: { padding: spacing.md, paddingBottom: spacing.xxl },
  heading: {
    fontSize: fontSize.xxl,
    fontWeight: "700",
    color: colors.gray900,
    marginBottom: spacing.xs,
  },
  subheading: {
    fontSize: fontSize.sm,
    color: colors.gray500,
    marginBottom: spacing.lg,
    lineHeight: 20,
  },
  dropZone: {
    borderWidth: 2,
    borderColor: colors.gray200,
    borderStyle: "dashed",
    borderRadius: borderRadius.lg,
    padding: spacing.xl,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.white,
    marginBottom: spacing.lg,
  },
  dropText: {
    fontSize: fontSize.md,
    color: colors.gray600,
    marginTop: spacing.sm,
  },
  dropHint: {
    fontSize: fontSize.xs,
    color: colors.gray400,
    marginTop: spacing.xs,
  },
  sectionTitle: {
    fontSize: fontSize.lg,
    fontWeight: "700",
    color: colors.gray900,
    marginBottom: spacing.sm,
  },
  fileList: { marginBottom: spacing.lg },
  fileRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    backgroundColor: colors.white,
    borderRadius: borderRadius.md,
    padding: spacing.sm,
    marginBottom: spacing.xs,
  },
  fileName: {
    flex: 1,
    fontSize: fontSize.sm,
    color: colors.gray700,
  },
  uploadBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.sm,
    backgroundColor: colors.primary,
    borderRadius: borderRadius.md,
    paddingVertical: spacing.md,
    marginTop: spacing.md,
  },
  uploadBtnDisabled: { opacity: 0.6 },
  uploadBtnText: {
    fontSize: fontSize.md,
    fontWeight: "600",
    color: colors.white,
  },
  results: { marginTop: spacing.md },
  summaryRow: {
    flexDirection: "row",
    gap: spacing.sm,
    marginBottom: spacing.md,
  },
  summaryBox: {
    flex: 1,
    backgroundColor: colors.white,
    borderRadius: borderRadius.md,
    borderWidth: 1,
    borderColor: colors.gray200,
    padding: spacing.sm,
    alignItems: "center",
  },
  summaryValue: {
    fontSize: fontSize.xl,
    fontWeight: "700",
    color: colors.gray900,
  },
  summaryLabel: {
    fontSize: fontSize.xs,
    color: colors.gray500,
    marginTop: 2,
  },
  quotaText: {
    fontSize: fontSize.sm,
    color: colors.gray500,
    textAlign: "center",
    marginBottom: spacing.sm,
  },
  upgradeText: {
    fontSize: fontSize.sm,
    color: colors.gold,
    textAlign: "center",
    marginBottom: spacing.md,
    fontWeight: "500",
  },
  resultRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    backgroundColor: colors.white,
    borderRadius: borderRadius.md,
    padding: spacing.sm,
    marginBottom: spacing.xs,
  },
  resultDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  resultInfo: { flex: 1 },
  resultName: {
    fontSize: fontSize.sm,
    color: colors.gray700,
    fontWeight: "500",
  },
  resultError: {
    fontSize: fontSize.xs,
    color: colors.red500,
    marginTop: 2,
  },
  resultStatus: {
    fontSize: fontSize.xs,
    color: colors.gray500,
    fontWeight: "500",
    textTransform: "capitalize",
  },
});
