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
import RecruiterStatCard from "../../components/RecruiterStatCard";
import {
  STAGE_LABELS,
  STAGE_COLORS,
  type DashboardStats,
  type RecruiterProfile,
  type PipelineStage,
} from "../../lib/recruiter-types";
import { colors, spacing, fontSize, borderRadius } from "../../lib/theme";

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export default function RecruiterDashboardScreen() {
  const { firstName } = useAuth();
  const router = useRouter();
  const [profile, setProfile] = useState<RecruiterProfile | null>(null);
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const loadData = async () => {
    try {
      const [profileRes, dashRes] = await Promise.all([
        api.get("/api/recruiter/profile"),
        api.get("/api/recruiter/dashboard"),
      ]);

      if (profileRes.status === 404) {
        router.replace("/recruiter-onboarding");
        return;
      }

      if (profileRes.ok) setProfile(await profileRes.json());
      if (dashRes.ok) setStats(await dashRes.json());
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

  const pipelineByStage = stats?.pipeline_by_stage ?? {};
  const maxStageCount = Math.max(...Object.values(pipelineByStage), 1);

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
      }
    >
      <Text style={styles.greeting}>
        Welcome{firstName ? `, ${firstName}` : ""}
      </Text>

      {/* Trial banner */}
      {profile?.is_trial_active && (
        <View style={styles.trialBanner}>
          <Ionicons name="time-outline" size={16} color={colors.primary} />
          <Text style={styles.trialText}>
            Trial: {profile.trial_days_remaining} days remaining
          </Text>
        </View>
      )}

      {/* Plan badge */}
      <View style={styles.planBadge}>
        <Text style={styles.planText}>
          {(profile?.subscription_tier ?? "free").toUpperCase()} Plan
        </Text>
      </View>

      {/* Stats grid */}
      <View style={styles.grid}>
        <RecruiterStatCard
          icon="briefcase-outline"
          label="Active Jobs"
          value={stats?.total_active_jobs ?? 0}
          color={colors.sage}
        />
        <RecruiterStatCard
          icon="funnel-outline"
          label="Pipeline"
          value={stats?.total_pipeline_candidates ?? 0}
          color={colors.blue500}
        />
        <RecruiterStatCard
          icon="business-outline"
          label="Clients"
          value={stats?.total_clients ?? 0}
          color={colors.amber500}
        />
        <RecruiterStatCard
          icon="checkmark-circle-outline"
          label="Placements"
          value={stats?.total_placements ?? 0}
          color={colors.green500}
        />
      </View>

      {/* Pipeline by stage */}
      {Object.keys(pipelineByStage).length > 0 && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Pipeline by Stage</Text>
          {Object.entries(pipelineByStage).map(([stage, count]) => (
            <View key={stage} style={styles.stageRow}>
              <Text style={styles.stageLabel}>
                {STAGE_LABELS[stage as PipelineStage] ?? stage}
              </Text>
              <View style={styles.stageBarBg}>
                <View
                  style={[
                    styles.stageBarFill,
                    {
                      width: `${(count / maxStageCount) * 100}%`,
                      backgroundColor:
                        STAGE_COLORS[stage as PipelineStage] ?? colors.gray400,
                    },
                  ]}
                />
              </View>
              <Text style={styles.stageCount}>{count}</Text>
            </View>
          ))}
        </View>
      )}

      {/* Recent activity */}
      {stats?.recent_activities && stats.recent_activities.length > 0 && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Recent Activity</Text>
          {stats.recent_activities.slice(0, 5).map((activity) => (
            <View key={activity.id} style={styles.activityRow}>
              <View style={styles.activityDot} />
              <View style={styles.activityContent}>
                <Text style={styles.activitySubject}>{activity.subject}</Text>
                {activity.body && (
                  <Text style={styles.activityBody} numberOfLines={1}>
                    {activity.body}
                  </Text>
                )}
              </View>
              <Text style={styles.activityTime}>
                {timeAgo(activity.created_at)}
              </Text>
            </View>
          ))}
        </View>
      )}

      {/* Quick actions */}
      <Text style={styles.sectionTitle}>Quick Actions</Text>

      <TouchableOpacity
        style={styles.actionCard}
        onPress={() => router.push("/(recruiter-tabs)/pipeline")}
      >
        <Ionicons name="funnel-outline" size={24} color={colors.gold} />
        <View style={styles.actionContent}>
          <Text style={styles.actionTitle}>Manage Pipeline</Text>
          <Text style={styles.actionDesc}>
            Review and advance your candidates
          </Text>
        </View>
      </TouchableOpacity>

      <TouchableOpacity
        style={styles.actionCard}
        onPress={() => router.push("/(recruiter-tabs)/jobs")}
      >
        <Ionicons name="briefcase-outline" size={24} color={colors.sage} />
        <View style={styles.actionContent}>
          <Text style={styles.actionTitle}>View Jobs</Text>
          <Text style={styles.actionDesc}>
            Check job orders and matched candidates
          </Text>
        </View>
      </TouchableOpacity>

      <TouchableOpacity
        style={styles.actionCard}
        onPress={() => router.push("/(recruiter-tabs)/clients")}
      >
        <Ionicons name="business-outline" size={24} color={colors.blue500} />
        <View style={styles.actionContent}>
          <Text style={styles.actionTitle}>Client Management</Text>
          <Text style={styles.actionDesc}>
            View and manage your client relationships
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
  section: {
    backgroundColor: colors.white,
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    marginBottom: spacing.lg,
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
  stageRow: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: spacing.sm,
  },
  stageLabel: {
    width: 90,
    fontSize: fontSize.xs,
    fontWeight: "600",
    color: colors.gray700,
  },
  stageBarBg: {
    flex: 1,
    height: 8,
    backgroundColor: colors.gray200,
    borderRadius: borderRadius.full,
    overflow: "hidden",
    marginHorizontal: spacing.sm,
  },
  stageBarFill: {
    height: 8,
    borderRadius: borderRadius.full,
  },
  stageCount: {
    width: 28,
    fontSize: fontSize.xs,
    fontWeight: "600",
    color: colors.gray600,
    textAlign: "right",
  },
  activityRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    marginBottom: spacing.sm,
  },
  activityDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
    backgroundColor: colors.gold,
    marginTop: 6,
    marginRight: spacing.sm,
  },
  activityContent: { flex: 1 },
  activitySubject: {
    fontSize: fontSize.sm,
    fontWeight: "600",
    color: colors.gray900,
  },
  activityBody: {
    fontSize: fontSize.xs,
    color: colors.gray500,
    marginTop: 2,
  },
  activityTime: {
    fontSize: fontSize.xs,
    color: colors.gray400,
    marginLeft: spacing.sm,
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
