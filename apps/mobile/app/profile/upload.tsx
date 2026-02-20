import { useState, useRef, useEffect } from "react";
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  Alert,
  ActivityIndicator,
} from "react-native";
import { useRouter } from "expo-router";
import * as DocumentPicker from "expo-document-picker";
import * as FileSystem from "expo-file-system";
import { Ionicons } from "@expo/vector-icons";
import { uploadFile, api } from "../../lib/api";
import { colors, spacing, fontSize, borderRadius } from "../../lib/theme";

type Step = "pick" | "uploading" | "parsing" | "success" | "error";

export default function UploadScreen() {
  const router = useRouter();
  const abortRef = useRef(false);
  const [step, setStep] = useState<Step>("pick");
  const [fileName, setFileName] = useState("");
  const [error, setError] = useState("");
  const [pollProgress, setPollProgress] = useState("");

  useEffect(() => {
    return () => {
      abortRef.current = true;
    };
  }, []);

  async function pickAndUpload() {
    try {
      const result = await DocumentPicker.getDocumentAsync({
        type: [
          "application/pdf",
          "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ],
        copyToCacheDirectory: true,
      });

      if (result.canceled) return;

      const file = result.assets[0];
      if (!file) return;

      // Validate size
      const info = await FileSystem.getInfoAsync(file.uri);
      if (info.exists && info.size && info.size > 10 * 1024 * 1024) {
        Alert.alert("Error", "File must be under 10 MB.");
        return;
      }

      setFileName(file.name);
      setStep("uploading");
      setError("");

      // Upload
      const uploadRes = await uploadFile(
        "/api/resume/upload",
        file.uri,
        file.name,
        file.mimeType || "application/octet-stream",
      );

      if (!uploadRes.ok) {
        const body = await uploadRes.text();
        let detail = "Upload failed.";
        try { detail = JSON.parse(body).detail || detail; } catch {}
        throw new Error(detail);
      }

      const { resume_document_id } = await uploadRes.json();

      // Parse
      setStep("parsing");
      const parseRes = await api.post(`/api/resume/${resume_document_id}/parse`);
      if (!parseRes.ok) {
        throw new Error("Failed to start parsing.");
      }

      const { job_run_id } = await parseRes.json();

      // Poll
      let attempts = 0;
      while (attempts < 20 && !abortRef.current) {
        await new Promise((r) => setTimeout(r, 1000));
        attempts++;
        setPollProgress(`Parsing... ${attempts}/20`);

        const pollRes = await api.get(`/api/resume/parse/${job_run_id}`);
        if (!pollRes.ok) continue;

        const pollData = await pollRes.json();
        if (pollData.status === "finished" || pollData.status === "succeeded") {
          setStep("success");
          return;
        }
        if (pollData.status === "failed") {
          throw new Error(pollData.error_message || "Parsing failed.");
        }
      }

      if (!abortRef.current) {
        throw new Error("Parsing timed out. Check your profile later.");
      }
    } catch (e: any) {
      setError(e?.message || "Something went wrong.");
      setStep("error");
    }
  }

  if (step === "success") {
    return (
      <View style={styles.container}>
        <View style={styles.center}>
          <Ionicons name="checkmark-circle" size={64} color={colors.green500} />
          <Text style={styles.heading}>Resume Parsed</Text>
          <Text style={styles.subtitle}>
            Your profile has been updated with the parsed data. Review it on your
            Profile tab.
          </Text>
          <TouchableOpacity style={styles.primaryBtn} onPress={() => router.back()}>
            <Text style={styles.primaryBtnText}>Done</Text>
          </TouchableOpacity>
        </View>
      </View>
    );
  }

  if (step === "uploading" || step === "parsing") {
    return (
      <View style={styles.container}>
        <View style={styles.center}>
          <ActivityIndicator size="large" color={colors.gold} />
          <Text style={styles.heading}>
            {step === "uploading" ? "Uploading..." : "Parsing Resume..."}
          </Text>
          {step === "parsing" && (
            <Text style={styles.subtitle}>{pollProgress}</Text>
          )}
          <Text style={[styles.subtitle, { marginTop: spacing.sm }]}>
            {fileName}
          </Text>
        </View>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <View style={styles.center}>
        <Ionicons
          name={step === "error" ? "alert-circle" : "cloud-upload-outline"}
          size={64}
          color={step === "error" ? colors.red500 : colors.gray300}
        />
        <Text style={styles.heading}>
          {step === "error" ? "Upload Failed" : "Upload Resume"}
        </Text>
        {step === "error" && (
          <View style={styles.errorBox}>
            <Text style={styles.errorText}>{error}</Text>
          </View>
        )}
        <Text style={styles.subtitle}>
          Upload your resume (PDF or DOCX, max 10 MB) and we'll parse it to build
          your profile.
        </Text>
        <TouchableOpacity style={styles.primaryBtn} onPress={pickAndUpload}>
          <Ionicons name="document-attach" size={20} color={colors.primary} />
          <Text style={styles.primaryBtnText}>
            {step === "error" ? "Try Again" : "Select Resume"}
          </Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.gray50 },
  center: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    padding: spacing.xl,
  },
  heading: {
    fontSize: fontSize.xxl,
    fontWeight: "700",
    color: colors.gray900,
    marginTop: spacing.md,
    textAlign: "center",
  },
  subtitle: {
    fontSize: fontSize.sm,
    color: colors.gray500,
    marginTop: spacing.sm,
    textAlign: "center",
    lineHeight: 20,
  },
  primaryBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    backgroundColor: colors.gold,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.xl,
    borderRadius: borderRadius.md,
    marginTop: spacing.lg,
  },
  primaryBtnText: {
    fontSize: fontSize.md,
    fontWeight: "600",
    color: colors.primary,
  },
  errorBox: {
    backgroundColor: "#FEE2E2",
    borderWidth: 1,
    borderColor: "#FECACA",
    borderRadius: borderRadius.md,
    padding: spacing.md,
    marginTop: spacing.md,
    width: "100%",
  },
  errorText: { fontSize: fontSize.sm, color: "#991B1B" },
});
