import { useState, useEffect, useCallback } from "react";
import {
  View,
  Text,
  FlatList,
  TouchableOpacity,
  StyleSheet,
  RefreshControl,
  Alert,
} from "react-native";
import { useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import * as FileSystem from "expo-file-system";
import * as Sharing from "expo-sharing";
import { api } from "../../lib/api";
import { getToken } from "../../lib/auth";
import { colors, spacing, fontSize, borderRadius } from "../../lib/theme";
import LoadingSpinner from "../../components/LoadingSpinner";

const API_BASE =
  process.env.EXPO_PUBLIC_API_BASE_URL || "http://localhost:8000";

interface Document {
  id: number;
  job_id: number;
  job_title: string | null;
  company: string | null;
  has_resume: boolean;
  has_cover_letter: boolean;
  created_at: string | null;
}

export default function DocumentsScreen() {
  const router = useRouter();
  const [documents, setDocuments] = useState<Document[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    try {
      const res = await api.get("/api/tailor/documents");
      if (res.ok) {
        const data = await res.json();
        setDocuments(data.documents || []);
      }
    } catch {
      Alert.alert("Error", "Could not load documents.");
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

  async function downloadAndShare(docId: number, type: "resume" | "cover-letter") {
    const key = `${docId}-${type}`;
    setDownloadingId(key);
    try {
      const token = await getToken();
      const fileUri = `${FileSystem.cacheDirectory}doc_${docId}_${type}.docx`;
      const result = await FileSystem.downloadAsync(
        `${API_BASE}/api/tailor/files/${docId}/${type}`,
        fileUri,
        { headers: { Authorization: `Bearer ${token}` } },
      );
      await Sharing.shareAsync(result.uri, {
        mimeType:
          "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        dialogTitle: `Share ${type === "resume" ? "Resume" : "Cover Letter"}`,
      });
    } catch {
      Alert.alert("Error", "Could not download file.");
    } finally {
      setDownloadingId(null);
    }
  }

  function formatDate(dateStr: string | null): string {
    if (!dateStr) return "";
    const d = new Date(dateStr);
    return d.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  }

  if (loading) return <LoadingSpinner />;

  return (
    <FlatList
      style={styles.container}
      contentContainerStyle={styles.list}
      data={documents}
      keyExtractor={(item) => String(item.id)}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
      }
      ListEmptyComponent={
        <View style={styles.empty}>
          <Ionicons name="document-text-outline" size={48} color={colors.gray300} />
          <Text style={styles.emptyTitle}>No documents yet</Text>
          <Text style={styles.emptyText}>
            Generate tailored resumes and cover letters from your matches.
          </Text>
          <TouchableOpacity
            style={styles.linkBtn}
            onPress={() => router.push("/(tabs)/matches")}
          >
            <Text style={styles.linkBtnText}>Go to Matches</Text>
          </TouchableOpacity>
        </View>
      }
      renderItem={({ item }) => (
        <View style={styles.card}>
          <Text style={styles.jobTitle} numberOfLines={1}>
            {item.job_title || "Untitled Job"}
          </Text>
          <Text style={styles.company}>{item.company || "Unknown company"}</Text>
          {item.created_at && (
            <Text style={styles.date}>{formatDate(item.created_at)}</Text>
          )}
          <View style={styles.actions}>
            {item.has_resume && (
              <TouchableOpacity
                style={styles.actionBtn}
                onPress={() => downloadAndShare(item.id, "resume")}
                disabled={downloadingId === `${item.id}-resume`}
              >
                <Ionicons name="document-outline" size={16} color={colors.primary} />
                <Text style={styles.actionText}>
                  {downloadingId === `${item.id}-resume` ? "..." : "Resume"}
                </Text>
              </TouchableOpacity>
            )}
            {item.has_cover_letter && (
              <TouchableOpacity
                style={styles.actionBtn}
                onPress={() => downloadAndShare(item.id, "cover-letter")}
                disabled={downloadingId === `${item.id}-cover-letter`}
              >
                <Ionicons name="mail-outline" size={16} color={colors.primary} />
                <Text style={styles.actionText}>
                  {downloadingId === `${item.id}-cover-letter`
                    ? "..."
                    : "Cover Letter"}
                </Text>
              </TouchableOpacity>
            )}
          </View>
        </View>
      )}
    />
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.gray50 },
  list: { padding: spacing.md },
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
  jobTitle: {
    fontSize: fontSize.lg,
    fontWeight: "600",
    color: colors.gray900,
  },
  company: {
    fontSize: fontSize.sm,
    color: colors.gray600,
    marginTop: 2,
  },
  date: {
    fontSize: fontSize.xs,
    color: colors.gray400,
    marginTop: 4,
  },
  actions: {
    flexDirection: "row",
    gap: spacing.md,
    marginTop: spacing.md,
    paddingTop: spacing.sm,
    borderTopWidth: 1,
    borderTopColor: colors.gray100,
  },
  actionBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    backgroundColor: colors.sage,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderRadius: borderRadius.md,
  },
  actionText: {
    fontSize: fontSize.sm,
    fontWeight: "500",
    color: colors.primary,
  },
  empty: {
    alignItems: "center",
    paddingVertical: spacing.xxl,
  },
  emptyTitle: {
    fontSize: fontSize.lg,
    fontWeight: "700",
    color: colors.gray900,
    marginTop: spacing.md,
  },
  emptyText: {
    fontSize: fontSize.sm,
    color: colors.gray500,
    marginTop: spacing.sm,
    textAlign: "center",
  },
  linkBtn: {
    marginTop: spacing.md,
    backgroundColor: colors.gold,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.lg,
    borderRadius: borderRadius.md,
  },
  linkBtnText: {
    fontSize: fontSize.sm,
    fontWeight: "600",
    color: colors.primary,
  },
});
