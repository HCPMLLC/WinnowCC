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
  candidate_views_limit: number | null;
  saved_candidates: number;
  subscription_tier: string;
  subscription_status: string;
}

export default function EmployerDashboardScreen() {
  const { email, role, logout } = useAuth();
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

  const handleLogout = () => {
    logout();
  };

  if (loading) return <LoadingSpinner />;

  const viewsUsed = analytics?.candidate_views_this_month ?? 0;
  const viewsLimit = analytics?.candidate_views_limit;
  const viewsPercent = viewsLimit ? Math.min(100, (viewsUsed / viewsLimit) * 100) : 0;

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
        Welcome{email ? `, ${email.split("@")[0]}` : ""}
      </Text>

      {/* Role switcher for "both" users */}
      {role === "both" && (
        <TouchableOpacity
          style={styles.switchBanner}
          onPress={() => router.replace("/(tabs)/dashboard")}
        >
          <Ionicons name="swap-horizontal" size={16} color={colors.gold} />
          <Text style={styles.switchText}>Switch to Candidate View</Text>
        </TouchableOpacity>
      )}

      {/* Recruiter switcher */}
      {(role === "recruiter" || role === "both") && (
        <TouchableOpacity
          style={styles.switchBanner}
          onPress={() => router.replace("/(recruiter-tabs)/dashboard")}
        >
          <Ionicons name="swap-horizontal" size={16} color={colors.gold} />
          <Text style={styles.switchText}>Switch to Recruiter View</Text>
        </TouchableOpacity>
      )}

      {/* Plan badge */}
      <View style={styles.planBadge}>
        <Text style={styles.planText}>
          {(analytics?.subscription_tier ?? "free").toUpperCase()} Plan
        </Text>
      </View>

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

      {/* Candidate views progress */}
      {viewsLimit != null && (
        <View style={styles.progressCard}>
          <Text style={styles.progressLabel}>
            Candidate Views: {viewsUsed} / {viewsLimit}
          </Text>
          <View style={styles.progressBar}>
            <View
              style={[styles.progressFill, { width: `${viewsPercent}%` }]}
            />
          </View>
        </View>
      )}

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

      {/* Logout */}
      <TouchableOpacity style={styles.logoutBtn} onPress={handleLogout}>
        <Text style={styles.logoutText}>Log Out</Text>
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
  planBadge: {
    alignSelf: "flex-start",
    backgroundColor: colors.primary,
    borderRadius: borderRadius.full,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    marginBottom: spacing.lg,
  },
  planText: {
    color: colors.gold,
    fontSize: fontSize.xs,
    fontWeight: "600",
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
  progressCard: {
    backgroundColor: colors.white,
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    marginBottom: spacing.lg,
    shadowColor: "#000",
    shadowOpacity: 0.05,
    shadowRadius: 8,
    elevation: 2,
  },
  progressLabel: {
    fontSize: fontSize.sm,
    fontWeight: "600",
    color: colors.gray700,
    marginBottom: spacing.sm,
  },
  progressBar: {
    height: 8,
    backgroundColor: colors.gray200,
    borderRadius: borderRadius.full,
    overflow: "hidden",
  },
  progressFill: {
    height: "100%",
    backgroundColor: colors.gold,
    borderRadius: borderRadius.full,
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
  logoutBtn: {
    borderRadius: borderRadius.md,
    paddingVertical: spacing.md,
    alignItems: "center",
    marginTop: spacing.lg,
    borderWidth: 1,
    borderColor: colors.red500,
  },
  logoutText: {
    fontSize: fontSize.md,
    fontWeight: "600",
    color: colors.red500,
  },
});
