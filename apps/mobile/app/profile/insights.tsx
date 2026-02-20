import { useState, useEffect, useCallback } from "react";
import {
  View,
  Text,
  TextInput,
  ScrollView,
  TouchableOpacity,
  StyleSheet,
  RefreshControl,
  Alert,
} from "react-native";
import { useRouter } from "expo-router";
import { Ionicons } from "@expo/vector-icons";
import { api } from "../../lib/api";
import { useBilling } from "../../lib/billing";
import { colors, spacing, fontSize, borderRadius } from "../../lib/theme";
import LoadingSpinner from "../../components/LoadingSpinner";
import SkillTag from "../../components/SkillTag";

interface Trajectory {
  current_level: string;
  career_velocity: string;
  trajectory_6mo: { role: string; likelihood: string; salary_range_min?: number; salary_range_max?: number };
  trajectory_12mo: { role: string; likelihood: string; salary_range_min?: number; salary_range_max?: number };
  detailed_analysis: {
    strengths?: string[];
    potential_obstacles?: string[];
    opportunities?: string[];
  };
  key_growth_areas: string[];
  recommended_skills: string[];
}

interface SalaryData {
  role: string;
  location: string | null;
  p10?: number;
  p25?: number;
  p50?: number;
  p75?: number;
  p90?: number;
  sample_size?: number;
  source?: string;
}

function formatSalary(val?: number): string {
  if (val == null) return "—";
  return `$${Math.round(val / 1000)}k`;
}

export default function InsightsScreen() {
  const router = useRouter();
  const billing = useBilling();
  const [trajectory, setTrajectory] = useState<Trajectory | null>(null);
  const [salary, setSalary] = useState<SalaryData | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [salaryRole, setSalaryRole] = useState("");
  const [salaryLocation, setSalaryLocation] = useState("");
  const [searchingSalary, setSearchingSalary] = useState(false);

  const loadTrajectory = useCallback(async () => {
    try {
      const res = await api.get("/api/insights/career-trajectory");
      if (res.ok) {
        setTrajectory(await res.json());
      }
    } catch {
      // Non-critical
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    if (billing.features.career_intelligence) {
      loadTrajectory();
    } else {
      setLoading(false);
    }
  }, [billing.features.career_intelligence, loadTrajectory]);

  const onRefresh = () => {
    setRefreshing(true);
    loadTrajectory();
  };

  async function searchSalary() {
    if (!salaryRole.trim()) {
      Alert.alert("Required", "Enter a job role to search.");
      return;
    }
    setSearchingSalary(true);
    try {
      const params = new URLSearchParams({ role: salaryRole.trim() });
      if (salaryLocation.trim()) params.append("location", salaryLocation.trim());
      const res = await api.get(`/api/insights/salary?${params}`);
      if (res.ok) {
        setSalary(await res.json());
      } else {
        Alert.alert("Error", "Could not load salary data.");
      }
    } catch {
      Alert.alert("Error", "Could not connect to server.");
    } finally {
      setSearchingSalary(false);
    }
  }

  if (billing.loading || loading) return <LoadingSpinner />;

  // Pro gate
  if (!billing.features.career_intelligence) {
    return (
      <View style={styles.gateContainer}>
        <Ionicons name="lock-closed" size={48} color={colors.gray300} />
        <Text style={styles.gateTitle}>Career Intelligence</Text>
        <Text style={styles.gateText}>
          Get AI-powered career trajectory predictions, salary benchmarks, and
          growth recommendations with a Pro plan.
        </Text>
        <TouchableOpacity
          style={styles.upgradeBtn}
          onPress={() => router.push("/profile/billing")}
        >
          <Text style={styles.upgradeBtnText}>Upgrade to Pro</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
      }
    >
      {/* Career Trajectory */}
      {trajectory && (
        <>
          <Text style={styles.sectionTitle}>Career Trajectory</Text>
          <View style={styles.card}>
            <View style={styles.levelRow}>
              <Text style={styles.levelLabel}>Current Level</Text>
              <Text style={styles.levelValue}>{trajectory.current_level}</Text>
            </View>
            <View style={styles.levelRow}>
              <Text style={styles.levelLabel}>Momentum</Text>
              <Text style={[styles.levelValue, { textTransform: "capitalize" }]}>
                {trajectory.career_velocity}
              </Text>
            </View>
          </View>

          {/* Projections */}
          <View style={styles.card}>
            <Text style={styles.cardTitle}>6-Month Projection</Text>
            <Text style={styles.projRole}>
              {trajectory.trajectory_6mo.role}
            </Text>
            <Text style={styles.projMeta}>
              Likelihood: {trajectory.trajectory_6mo.likelihood}
              {trajectory.trajectory_6mo.salary_range_min && (
                <>
                  {" "}| {formatSalary(trajectory.trajectory_6mo.salary_range_min)} –{" "}
                  {formatSalary(trajectory.trajectory_6mo.salary_range_max)}
                </>
              )}
            </Text>
          </View>

          <View style={styles.card}>
            <Text style={styles.cardTitle}>12-Month Projection</Text>
            <Text style={styles.projRole}>
              {trajectory.trajectory_12mo.role}
            </Text>
            <Text style={styles.projMeta}>
              Likelihood: {trajectory.trajectory_12mo.likelihood}
              {trajectory.trajectory_12mo.salary_range_min && (
                <>
                  {" "}| {formatSalary(trajectory.trajectory_12mo.salary_range_min)} –{" "}
                  {formatSalary(trajectory.trajectory_12mo.salary_range_max)}
                </>
              )}
            </Text>
          </View>

          {/* Strengths */}
          {trajectory.detailed_analysis?.strengths &&
            trajectory.detailed_analysis.strengths.length > 0 && (
              <View style={styles.card}>
                <Text style={styles.cardTitle}>Strengths</Text>
                {trajectory.detailed_analysis.strengths.map((s, i) => (
                  <View key={i} style={styles.bulletRow}>
                    <Ionicons
                      name="checkmark-circle"
                      size={16}
                      color={colors.green500}
                    />
                    <Text style={styles.bulletText}>{s}</Text>
                  </View>
                ))}
              </View>
            )}

          {/* Recommended Skills */}
          {trajectory.recommended_skills?.length > 0 && (
            <View style={styles.card}>
              <Text style={styles.cardTitle}>Recommended Skills</Text>
              <View style={styles.skillsWrap}>
                {trajectory.recommended_skills.map((s) => (
                  <SkillTag key={s} name={s} />
                ))}
              </View>
            </View>
          )}
        </>
      )}

      {/* Salary Intelligence */}
      <Text style={styles.sectionTitle}>Salary Intelligence</Text>
      <View style={styles.card}>
        <TextInput
          style={styles.input}
          value={salaryRole}
          onChangeText={setSalaryRole}
          placeholder="Job role (e.g., Software Engineer)"
        />
        <TextInput
          style={[styles.input, { marginTop: spacing.sm }]}
          value={salaryLocation}
          onChangeText={setSalaryLocation}
          placeholder="Location (optional)"
        />
        <TouchableOpacity
          style={[styles.searchBtn, searchingSalary && styles.disabled]}
          onPress={searchSalary}
          disabled={searchingSalary}
        >
          <Text style={styles.searchBtnText}>
            {searchingSalary ? "Searching..." : "Check Salary"}
          </Text>
        </TouchableOpacity>
      </View>

      {salary && (
        <View style={styles.card}>
          <Text style={styles.cardTitle}>
            {salary.role}
            {salary.location ? ` in ${salary.location}` : ""}
          </Text>
          {[
            { label: "Top 10%", val: salary.p90, color: colors.green500 },
            { label: "75th", val: salary.p75, color: "#22C55E" },
            { label: "Median", val: salary.p50, color: colors.gold },
            { label: "25th", val: salary.p25, color: colors.blue500 },
            { label: "Bottom 10%", val: salary.p10, color: colors.gray400 },
          ].map((row) => (
            <View key={row.label} style={styles.salaryRow}>
              <Text style={styles.salaryLabel}>{row.label}</Text>
              <View style={styles.salaryBarTrack}>
                <View
                  style={[
                    styles.salaryBarFill,
                    {
                      width: `${Math.min(((row.val || 0) / (salary.p90 || 1)) * 100, 100)}%`,
                      backgroundColor: row.color,
                    },
                  ]}
                />
              </View>
              <Text style={styles.salaryAmount}>{formatSalary(row.val)}</Text>
            </View>
          ))}
          {salary.source && (
            <Text style={styles.sourceText}>
              Source: {salary.source} ({salary.sample_size || 0} samples)
            </Text>
          )}
        </View>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.gray50 },
  content: { padding: spacing.md, paddingBottom: spacing.xxl },
  gateContainer: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    padding: spacing.xl,
    backgroundColor: colors.gray50,
  },
  gateTitle: {
    fontSize: fontSize.xxl,
    fontWeight: "700",
    color: colors.gray900,
    marginTop: spacing.md,
  },
  gateText: {
    fontSize: fontSize.sm,
    color: colors.gray500,
    marginTop: spacing.sm,
    textAlign: "center",
    lineHeight: 20,
  },
  upgradeBtn: {
    backgroundColor: colors.gold,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.xl,
    borderRadius: borderRadius.md,
    marginTop: spacing.lg,
  },
  upgradeBtnText: {
    fontSize: fontSize.md,
    fontWeight: "600",
    color: colors.primary,
  },
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
    marginBottom: spacing.md,
    shadowColor: "#000",
    shadowOpacity: 0.05,
    shadowRadius: 8,
    elevation: 2,
  },
  cardTitle: {
    fontSize: fontSize.md,
    fontWeight: "700",
    color: colors.gray900,
    marginBottom: spacing.sm,
  },
  levelRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingVertical: spacing.sm,
  },
  levelLabel: {
    fontSize: fontSize.sm,
    color: colors.gray500,
  },
  levelValue: {
    fontSize: fontSize.sm,
    fontWeight: "600",
    color: colors.gray900,
  },
  projRole: {
    fontSize: fontSize.md,
    fontWeight: "600",
    color: colors.primary,
  },
  projMeta: {
    fontSize: fontSize.sm,
    color: colors.gray500,
    marginTop: spacing.xs,
  },
  bulletRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: spacing.sm,
    paddingVertical: spacing.xs,
  },
  bulletText: {
    fontSize: fontSize.sm,
    color: colors.gray700,
    flex: 1,
  },
  skillsWrap: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.xs,
  },
  input: {
    backgroundColor: colors.gray50,
    borderWidth: 1,
    borderColor: colors.gray200,
    borderRadius: borderRadius.md,
    padding: spacing.md,
    fontSize: fontSize.md,
    color: colors.gray900,
  },
  searchBtn: {
    backgroundColor: colors.gold,
    paddingVertical: spacing.sm,
    borderRadius: borderRadius.md,
    alignItems: "center",
    marginTop: spacing.md,
  },
  searchBtnText: {
    fontSize: fontSize.md,
    fontWeight: "600",
    color: colors.primary,
  },
  salaryRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    paddingVertical: spacing.xs,
  },
  salaryLabel: {
    width: 70,
    fontSize: fontSize.xs,
    color: colors.gray500,
  },
  salaryBarTrack: {
    flex: 1,
    height: 8,
    backgroundColor: colors.gray200,
    borderRadius: borderRadius.full,
    overflow: "hidden",
  },
  salaryBarFill: {
    height: 8,
    borderRadius: borderRadius.full,
  },
  salaryAmount: {
    width: 50,
    fontSize: fontSize.sm,
    fontWeight: "600",
    color: colors.gray900,
    textAlign: "right",
  },
  sourceText: {
    fontSize: fontSize.xs,
    color: colors.gray400,
    marginTop: spacing.sm,
  },
  disabled: { opacity: 0.6 },
});
