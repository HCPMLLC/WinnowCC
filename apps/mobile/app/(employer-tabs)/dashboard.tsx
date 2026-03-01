import { useEffect, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
} from "react-native";
import { useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { useAuth } from "../../lib/auth";
import { api } from "../../lib/api";
import LoadingSpinner from "../../components/LoadingSpinner";
import { colors, spacing, fontSize, borderRadius } from "../../lib/theme";

interface Analytics {
  active_jobs: number;
  total_job_views: number;
  total_applications: number;
  candidate_views_this_month: number;
  saved_candidates: number;
}

export default function EmployerDashboardScreen() {
  const { email, role } = useAuth();
  const router = useRouter();
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const loadData = async () => {
    try {
      const res = await api.get("/api/employer/analytics/summary");
      if (res.status === 404) {
        // No employer profile — go to onboarding
        router.replace("/employer-onboarding");
        return;
      }
      if (res.ok) {
        setAnalytics(await res.json());
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

  if (loading) return <LoadingSpinner />;

  const cards = [
    {
      label: "Active Jobs",
      value: String(analytics?.active_jobs ?? 0),
      color: colors.sage,
    },
    {
      label: "Total Views",
      value: String(analytics?.total_job_views ?? 0),
      color: colors.green500,
    },
    {
      label: "Applications",
      value: String(analytics?.total_applications ?? 0),
      color: colors.blue500,
    },
    {
      label: "Saved",
      value: String(analytics?.saved_candidates ?? 0),
      color: colors.amber500,
    },
  ];

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
      }
    >
      <Text style={styles.greeting}>
        Welcome
      </Text>

      {/* Role switcher for "both" users */}
      {role === "both" && (
        <TouchableOpacity
          style={styles.switchBanner}
          onPress={() => router.push("/(tabs)/dashboard")}
        >
          <Ionicons name="swap-horizontal" size={16} color={colors.gold} />
          <Text style={styles.switchText}>Switch to Candidate View</Text>
        </TouchableOpacity>
      )}

      {/* Recruiter switcher */}
      {(role === "recruiter" || role === "both") && (
        <TouchableOpacity
          style={styles.switchBanner}
          onPress={() => router.push("/(recruiter-tabs)/dashboard")}
        >
          <Ionicons name="swap-horizontal" size={16} color={colors.gold} />
          <Text style={styles.switchText}>Switch to Recruiter View</Text>
        </TouchableOpacity>
      )}

      {/* Metric cards */}
      <View style={styles.grid}>
        {cards.map((card) => (
          <View key={card.label} style={styles.card}>
            <Text style={[styles.cardValue, { color: card.color }]}>
              {card.value}
            </Text>
            <Text style={styles.cardLabel}>{card.label}</Text>
          </View>
        ))}
      </View>

      {/* Quick actions */}
      <Text style={styles.sectionTitle}>Quick Actions</Text>

      <TouchableOpacity
        style={styles.actionCard}
        onPress={() => router.push("/employer/job/new")}
      >
        <Ionicons name="add-circle-outline" size={24} color={colors.gold} />
        <View style={styles.actionContent}>
          <Text style={styles.actionTitle}>Post a Job</Text>
          <Text style={styles.actionDesc}>
            Create a new job posting to attract candidates
          </Text>
        </View>
      </TouchableOpacity>

      <TouchableOpacity
        style={styles.actionCard}
        onPress={() => router.push("/(employer-tabs)/candidates")}
      >
        <Ionicons name="search-outline" size={24} color={colors.sage} />
        <View style={styles.actionContent}>
          <Text style={styles.actionTitle}>Search Candidates</Text>
          <Text style={styles.actionDesc}>
            Find candidates that match your requirements
          </Text>
        </View>
      </TouchableOpacity>

      <TouchableOpacity
        style={styles.actionCard}
        onPress={() => router.push("/employer/analytics")}
      >
        <Ionicons name="analytics-outline" size={24} color={colors.blue500} />
        <View style={styles.actionContent}>
          <Text style={styles.actionTitle}>View Analytics</Text>
          <Text style={styles.actionDesc}>
            Track performance across your job postings
          </Text>
        </View>
      </TouchableOpacity>

      <TouchableOpacity
        style={styles.actionCard}
        onPress={() => router.push("/employer/saved")}
      >
        <Ionicons name="bookmark-outline" size={24} color={colors.amber500} />
        <View style={styles.actionContent}>
          <Text style={styles.actionTitle}>Saved Candidates</Text>
          <Text style={styles.actionDesc}>
            Review and manage your saved candidates
          </Text>
        </View>
      </TouchableOpacity>

      <TouchableOpacity
        style={styles.actionCard}
        onPress={() => router.push("/(employer-tabs)/pipeline")}
      >
        <Ionicons name="layers-outline" size={24} color={colors.green500} />
        <View style={styles.actionContent}>
          <Text style={styles.actionTitle}>Talent Pipeline</Text>
          <Text style={styles.actionDesc}>
            Manage candidates through your hiring stages
          </Text>
        </View>
      </TouchableOpacity>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.gray50 },
  content: { padding: spacing.md, paddingBottom: spacing.xxl },
  greeting: {
    fontSize: fontSize.xxl,
    fontWeight: "700",
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
    marginBottom: spacing.sm,
  },
  switchText: {
    fontSize: fontSize.sm,
    fontWeight: "600",
    color: colors.gold,
  },
  grid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.md,
    marginBottom: spacing.lg,
  },
  card: {
    width: "47%",
    backgroundColor: colors.white,
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    alignItems: "center",
    shadowColor: "#000",
    shadowOpacity: 0.05,
    shadowRadius: 8,
    elevation: 2,
  },
  cardValue: {
    fontSize: fontSize.xxxl,
    fontWeight: "700",
  },
  cardLabel: {
    fontSize: fontSize.sm,
    color: colors.gray500,
    marginTop: spacing.xs,
  },
  sectionTitle: {
    fontSize: fontSize.lg,
    fontWeight: "700",
    color: colors.gray900,
    marginBottom: spacing.md,
  },
  actionCard: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    backgroundColor: colors.white,
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    marginBottom: spacing.sm,
    shadowColor: "#000",
    shadowOpacity: 0.05,
    shadowRadius: 8,
    elevation: 2,
  },
  actionContent: { flex: 1 },
  actionTitle: {
    fontSize: fontSize.md,
    fontWeight: "600",
    color: colors.gray900,
  },
  actionDesc: {
    fontSize: fontSize.sm,
    color: colors.gray500,
    marginTop: 2,
  },
});
