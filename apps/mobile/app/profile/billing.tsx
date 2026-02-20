import { useState, useEffect, useCallback } from "react";
import {
  View,
  Text,
  ScrollView,
  TouchableOpacity,
  StyleSheet,
  RefreshControl,
  Alert,
  Linking,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { api } from "../../lib/api";
import { colors, spacing, fontSize, borderRadius } from "../../lib/theme";
import LoadingSpinner from "../../components/LoadingSpinner";
import UsageMeter from "../../components/UsageMeter";

interface BillingData {
  plan_tier: string;
  billing_cycle: string | null;
  subscription_status: string | null;
  usage: {
    match_refreshes: number;
    tailor_requests: number;
    sieve_messages_today: number;
    semantic_searches_today: number;
  };
  limits: Record<string, number>;
  features: {
    data_export: boolean;
    career_intelligence: boolean;
    ips_detail: string;
  };
}

const PLAN_LABELS: Record<string, string> = {
  free: "Free",
  starter: "Starter",
  pro: "Pro",
};

const PLAN_COLORS: Record<string, string> = {
  free: colors.gray500,
  starter: colors.blue500,
  pro: colors.gold,
};

const FEATURES = [
  { key: "data_export", label: "Data Export" },
  { key: "career_intelligence", label: "Career Intelligence" },
];

export default function BillingScreen() {
  const [billing, setBilling] = useState<BillingData | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const loadData = useCallback(async () => {
    try {
      const res = await api.get("/api/billing/status");
      if (res.ok) {
        setBilling(await res.json());
      }
    } catch {
      Alert.alert("Error", "Could not load billing info.");
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

  async function handleUpgrade(tier: string) {
    try {
      const res = await api.post("/api/billing/unified-checkout", {
        segment: "candidate",
        tier,
        interval: "monthly",
      });
      if (res.ok) {
        const { checkout_url } = await res.json();
        Linking.openURL(checkout_url);
      } else {
        Alert.alert("Error", "Could not start checkout.");
      }
    } catch {
      Alert.alert("Error", "Could not connect to billing.");
    }
  }

  async function handleManage() {
    try {
      const res = await api.post("/api/billing/portal");
      if (res.ok) {
        const { portal_url } = await res.json();
        Linking.openURL(portal_url);
      } else {
        Alert.alert("Error", "Could not open billing portal.");
      }
    } catch {
      Alert.alert("Error", "Could not connect to billing.");
    }
  }

  if (loading) return <LoadingSpinner />;
  if (!billing) return <LoadingSpinner />;

  const tier = billing.plan_tier || "free";
  const tierLabel = PLAN_LABELS[tier] || tier;
  const tierColor = PLAN_COLORS[tier] || colors.gray500;

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
      }
    >
      {/* Current Plan */}
      <View style={styles.card}>
        <View style={styles.planRow}>
          <Text style={styles.planLabel}>Current Plan</Text>
          <View style={[styles.planBadge, { backgroundColor: tierColor }]}>
            <Text style={styles.planBadgeText}>{tierLabel}</Text>
          </View>
        </View>
        {billing.billing_cycle && (
          <Text style={styles.billingCycle}>
            Billed {billing.billing_cycle}
          </Text>
        )}
        {billing.subscription_status &&
          billing.subscription_status !== "active" && (
            <Text style={[styles.statusText, { color: colors.amber500 }]}>
              Status: {billing.subscription_status}
            </Text>
          )}
      </View>

      {/* Usage */}
      <Text style={styles.sectionTitle}>Usage</Text>
      <View style={styles.card}>
        <UsageMeter
          label="Tailor Requests"
          used={billing.usage?.tailor_requests || 0}
          limit={billing.limits?.tailor_requests ?? null}
        />
        <UsageMeter
          label="Sieve Messages Today"
          used={billing.usage?.sieve_messages_today || 0}
          limit={billing.limits?.sieve_messages_per_day ?? null}
        />
        <UsageMeter
          label="Semantic Searches Today"
          used={billing.usage?.semantic_searches_today || 0}
          limit={billing.limits?.semantic_searches_per_day ?? null}
        />
      </View>

      {/* Features */}
      <Text style={styles.sectionTitle}>Features</Text>
      <View style={styles.card}>
        {FEATURES.map((f) => {
          const enabled =
            billing.features?.[f.key as keyof typeof billing.features];
          return (
            <View key={f.key} style={styles.featureRow}>
              <Ionicons
                name={enabled ? "checkmark-circle" : "lock-closed"}
                size={20}
                color={enabled ? colors.green500 : colors.gray400}
              />
              <Text
                style={[
                  styles.featureLabel,
                  !enabled && { color: colors.gray400 },
                ]}
              >
                {f.label}
              </Text>
            </View>
          );
        })}
        <View style={styles.featureRow}>
          <Ionicons name="analytics" size={20} color={colors.primary} />
          <Text style={styles.featureLabel}>
            IPS Detail: {billing.features?.ips_detail || "score_only"}
          </Text>
        </View>
      </View>

      {/* Actions */}
      <Text style={styles.sectionTitle}>Manage</Text>
      <View style={styles.actionsContainer}>
        {tier === "free" && (
          <>
            <TouchableOpacity
              style={styles.upgradeBtn}
              onPress={() => handleUpgrade("starter")}
            >
              <Text style={styles.upgradeBtnText}>Upgrade to Starter — $9/mo</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={styles.upgradeBtn}
              onPress={() => handleUpgrade("pro")}
            >
              <Text style={styles.upgradeBtnText}>Upgrade to Pro — $29/mo</Text>
            </TouchableOpacity>
          </>
        )}
        {tier === "starter" && (
          <TouchableOpacity
            style={styles.upgradeBtn}
            onPress={() => handleUpgrade("pro")}
          >
            <Text style={styles.upgradeBtnText}>Upgrade to Pro — $29/mo</Text>
          </TouchableOpacity>
        )}
        {tier !== "free" && (
          <TouchableOpacity style={styles.manageBtn} onPress={handleManage}>
            <Text style={styles.manageBtnText}>Manage Subscription</Text>
          </TouchableOpacity>
        )}
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.gray50 },
  content: { padding: spacing.md, paddingBottom: spacing.xxl },
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
  planRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  planLabel: {
    fontSize: fontSize.lg,
    fontWeight: "700",
    color: colors.gray900,
  },
  planBadge: {
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.xs,
    borderRadius: borderRadius.full,
  },
  planBadgeText: {
    fontSize: fontSize.sm,
    fontWeight: "700",
    color: colors.white,
  },
  billingCycle: {
    fontSize: fontSize.sm,
    color: colors.gray500,
    marginTop: spacing.xs,
    textTransform: "capitalize",
  },
  statusText: {
    fontSize: fontSize.sm,
    fontWeight: "600",
    marginTop: spacing.xs,
    textTransform: "capitalize",
  },
  sectionTitle: {
    fontSize: fontSize.lg,
    fontWeight: "700",
    color: colors.gray900,
    marginTop: spacing.lg,
    marginBottom: spacing.sm,
  },
  featureRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    paddingVertical: spacing.sm,
  },
  featureLabel: {
    fontSize: fontSize.md,
    color: colors.gray900,
  },
  actionsContainer: { gap: spacing.sm },
  upgradeBtn: {
    backgroundColor: colors.gold,
    paddingVertical: spacing.md,
    borderRadius: borderRadius.md,
    alignItems: "center",
  },
  upgradeBtnText: {
    fontSize: fontSize.md,
    fontWeight: "600",
    color: colors.primary,
  },
  manageBtn: {
    borderWidth: 1,
    borderColor: colors.gray300,
    paddingVertical: spacing.md,
    borderRadius: borderRadius.md,
    alignItems: "center",
  },
  manageBtnText: {
    fontSize: fontSize.md,
    fontWeight: "600",
    color: colors.gray700,
  },
});
