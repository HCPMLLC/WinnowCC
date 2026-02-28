import { useEffect, useState, useCallback } from "react";
import {
  View,
  Text,
  FlatList,
  StyleSheet,
  RefreshControl,
  TouchableOpacity,
} from "react-native";
import { useRouter } from "expo-router";
import { api } from "../../lib/api";
import MatchCard from "../../components/MatchCard";
import LoadingSpinner from "../../components/LoadingSpinner";
import { colors, spacing, fontSize, borderRadius } from "../../lib/theme";

interface MatchJob {
  id: number;
  title: string;
  company: string;
  location?: string;
  remote_flag?: boolean;
}

interface Match {
  id: number;
  job: MatchJob;
  match_score: number;
  interview_readiness_score: number;
  interview_probability?: number;
  reasons?: { matched_skills?: string[] };
  application_status?: string;
}

export default function MatchesScreen() {
  const router = useRouter();
  const [matches, setMatches] = useState<Match[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [needsResume, setNeedsResume] = useState(false);

  const loadMatches = useCallback(async () => {
    try {
      setError(null);
      setNeedsResume(false);
      const res = await api.get("/api/matches/all");
      if (res.ok) {
        const data = await res.json();
        const all: Match[] = Array.isArray(data) ? data : data.matches || [];
        // Only show qualified matches (score >= 45), matching web app and dashboard
        setMatches(all.filter((m) => m.match_score >= 45));
      } else if (res.status === 403) {
        const body = await res.json().catch(() => ({}));
        const detail: string = body.detail || "";
        if (detail.toLowerCase().includes("onboarding")) {
          router.replace("/candidate-onboarding");
          return;
        }
        setNeedsResume(true);
        setError("Upload your resume to unlock matches.");
      } else {
        setError("Failed to load matches.");
      }
    } catch {
      setError("Could not connect to server.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadMatches();
  }, [loadMatches]);

  const onRefresh = () => {
    setRefreshing(true);
    loadMatches();
  };

  if (loading) return <LoadingSpinner />;

  return (
    <View style={styles.container}>
      <FlatList
        data={matches}
        keyExtractor={(item) => String(item.id)}
        renderItem={({ item }) => (
          <MatchCard
            match={{
              id: item.id,
              job_title: item.job.title,
              company: item.job.company,
              location: item.job.location || "",
              remote_flag: item.job.remote_flag || false,
              match_score: item.match_score,
              interview_readiness_score: item.interview_readiness_score,
              reasons: item.reasons,
              application_status: item.application_status,
            }}
          />
        )}
        contentContainerStyle={styles.list}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
        }
        ListEmptyComponent={
          <View style={styles.empty}>
            <Text style={styles.emptyTitle}>
              {error || "No matches yet"}
            </Text>
            <Text style={styles.emptyText}>
              {needsResume
                ? "We need your resume to find the best jobs for you."
                : error
                  ? "Pull down to retry."
                  : "Upload your resume to get started."}
            </Text>
            {needsResume && (
              <TouchableOpacity
                style={styles.uploadBtn}
                onPress={() => router.push("/profile/upload")}
              >
                <Text style={styles.uploadBtnText}>Upload Resume</Text>
              </TouchableOpacity>
            )}
          </View>
        }
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.gray50 },
  list: { padding: spacing.md },
  empty: {
    alignItems: "center",
    paddingTop: spacing.xxl,
    paddingHorizontal: spacing.xl,
  },
  emptyTitle: {
    fontSize: fontSize.xl,
    fontWeight: "600",
    color: colors.gray700,
    marginBottom: spacing.sm,
  },
  emptyText: {
    fontSize: fontSize.md,
    color: colors.gray500,
    textAlign: "center",
  },
  uploadBtn: {
    backgroundColor: colors.gold,
    borderRadius: borderRadius.md,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.xl,
    marginTop: spacing.lg,
  },
  uploadBtnText: {
    fontSize: fontSize.md,
    fontWeight: "600",
    color: colors.primary,
  },
});
