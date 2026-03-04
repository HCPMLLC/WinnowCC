import { useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  Modal,
  TouchableOpacity,
  ScrollView,
  TextInput,
  ActivityIndicator,
  Alert,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { api } from "../lib/api";
import { handleFeatureGateResponse } from "../lib/featureGate";
import type { SalaryCoachingData } from "../lib/match-feature-types";
import { colors, spacing, fontSize, borderRadius } from "../lib/theme";

interface Props {
  visible: boolean;
  onClose: () => void;
  matchId: number;
}

const RATING_COLORS: Record<string, string> = {
  excellent: "#166534",
  good: "#22C55E",
  fair: "#F59E0B",
  below_market: "#EF4444",
  low: "#991B1B",
};

export default function SalaryCoachModal({ visible, onClose, matchId }: Props) {
  const [salary, setSalary] = useState("");
  const [bonus, setBonus] = useState("");
  const [equity, setEquity] = useState("");
  const [data, setData] = useState<SalaryCoachingData | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async () => {
    if (!salary.trim()) {
      Alert.alert("Required", "Enter the offered salary.");
      return;
    }
    setLoading(true);
    try {
      const body: Record<string, number> = {
        salary: parseInt(salary, 10),
      };
      if (bonus.trim()) body.bonus = parseInt(bonus, 10);
      if (equity.trim()) body.equity = parseInt(equity, 10);

      const res = await api.post(`/api/matches/${matchId}/salary-coaching`, body);
      if (handleFeatureGateResponse(res)) {
        onClose();
        return;
      }
      if (res.ok) {
        setData(await res.json());
      } else {
        Alert.alert("Error", "Could not get coaching data.");
      }
    } catch {
      Alert.alert("Error", "Something went wrong.");
    } finally {
      setLoading(false);
    }
  };

  const handleClose = () => {
    setData(null);
    setSalary("");
    setBonus("");
    setEquity("");
    onClose();
  };

  const ratingColor = data
    ? RATING_COLORS[data.offer_assessment.rating] || colors.gray600
    : colors.gray600;

  return (
    <Modal
      visible={visible}
      animationType="slide"
      presentationStyle="pageSheet"
      onRequestClose={handleClose}
    >
      <View style={styles.container}>
        <View style={styles.header}>
          <Text style={styles.headerTitle}>Salary Coach</Text>
          <TouchableOpacity onPress={handleClose}>
            <Ionicons name="close" size={24} color={colors.gray600} />
          </TouchableOpacity>
        </View>

        <ScrollView style={styles.scrollContent} contentContainerStyle={styles.scrollInner}>
          {!data ? (
            // Input form
            <View>
              <Text style={styles.formTitle}>Enter Your Offer Details</Text>

              <Text style={styles.label}>Base Salary</Text>
              <TextInput
                style={styles.input}
                placeholder="e.g. 120000"
                placeholderTextColor={colors.gray400}
                keyboardType="numeric"
                value={salary}
                onChangeText={setSalary}
              />

              <Text style={styles.label}>Bonus (optional)</Text>
              <TextInput
                style={styles.input}
                placeholder="e.g. 15000"
                placeholderTextColor={colors.gray400}
                keyboardType="numeric"
                value={bonus}
                onChangeText={setBonus}
              />

              <Text style={styles.label}>Equity (optional)</Text>
              <TextInput
                style={styles.input}
                placeholder="e.g. 50000"
                placeholderTextColor={colors.gray400}
                keyboardType="numeric"
                value={equity}
                onChangeText={setEquity}
              />

              <TouchableOpacity
                style={[styles.submitBtn, loading && styles.btnDisabled]}
                onPress={handleSubmit}
                disabled={loading}
              >
                {loading ? (
                  <ActivityIndicator color={colors.primary} />
                ) : (
                  <Text style={styles.submitBtnText}>Get Coaching</Text>
                )}
              </TouchableOpacity>
            </View>
          ) : (
            // Results
            <View>
              {/* Assessment */}
              <View style={styles.assessmentCard}>
                <Text style={[styles.rating, { color: ratingColor }]}>
                  {data.offer_assessment.rating.replace(/_/g, " ").toUpperCase()}
                </Text>
                <Text style={styles.assessmentSummary}>
                  {data.offer_assessment.summary}
                </Text>
              </View>

              {/* Strategy */}
              <Text style={styles.sectionTitle}>Negotiation Strategy</Text>
              <Text style={styles.bodyText}>{data.negotiation_strategy}</Text>

              {/* Counter Script */}
              <Text style={styles.sectionTitle}>Counter Script</Text>
              <View style={styles.scriptBox}>
                <Text style={styles.scriptText}>{data.counter_script}</Text>
              </View>

              {/* Justification Points */}
              {data.justification_points.length > 0 && (
                <>
                  <Text style={styles.sectionTitle}>Justification Points</Text>
                  {data.justification_points.map((p, i) => (
                    <Text key={i} style={styles.bulletText}>{"\u2022"} {p}</Text>
                  ))}
                </>
              )}

              {/* Alternative Asks */}
              {data.alternative_asks.length > 0 && (
                <>
                  <Text style={styles.sectionTitle}>Alternative Asks</Text>
                  {data.alternative_asks.map((a, i) => (
                    <Text key={i} style={styles.bulletText}>{"\u2022"} {a}</Text>
                  ))}
                </>
              )}

              {/* Flags */}
              <View style={styles.flagsRow}>
                {data.green_flags.length > 0 && (
                  <View style={styles.flagCol}>
                    <Text style={styles.greenFlagTitle}>Green Flags</Text>
                    {data.green_flags.map((f, i) => (
                      <View key={i} style={styles.flagItem}>
                        <Ionicons name="checkmark-circle" size={14} color={colors.green500} />
                        <Text style={styles.flagText}>{f}</Text>
                      </View>
                    ))}
                  </View>
                )}
                {data.red_flags.length > 0 && (
                  <View style={styles.flagCol}>
                    <Text style={styles.redFlagTitle}>Red Flags</Text>
                    {data.red_flags.map((f, i) => (
                      <View key={i} style={styles.flagItem}>
                        <Ionicons name="alert-circle" size={14} color={colors.red500} />
                        <Text style={styles.flagText}>{f}</Text>
                      </View>
                    ))}
                  </View>
                )}
              </View>

              {/* Timeline */}
              <Text style={styles.sectionTitle}>Timeline</Text>
              <Text style={styles.bodyText}>{data.timeline}</Text>

              <TouchableOpacity
                style={styles.resetBtn}
                onPress={() => setData(null)}
              >
                <Text style={styles.resetBtnText}>Try Different Offer</Text>
              </TouchableOpacity>
            </View>
          )}
        </ScrollView>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: colors.gray50,
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    padding: spacing.md,
    backgroundColor: colors.white,
    borderBottomWidth: 1,
    borderBottomColor: colors.gray200,
  },
  headerTitle: {
    fontSize: fontSize.lg,
    fontWeight: "700",
    color: colors.gray900,
  },
  scrollContent: {
    flex: 1,
  },
  scrollInner: {
    padding: spacing.md,
    paddingBottom: spacing.xxl,
  },
  formTitle: {
    fontSize: fontSize.lg,
    fontWeight: "600",
    color: colors.gray900,
    marginBottom: spacing.lg,
  },
  label: {
    fontSize: fontSize.sm,
    fontWeight: "600",
    color: colors.gray700,
    marginBottom: spacing.xs,
  },
  input: {
    backgroundColor: colors.white,
    borderRadius: borderRadius.md,
    borderWidth: 1,
    borderColor: colors.gray200,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    fontSize: fontSize.md,
    color: colors.gray900,
    marginBottom: spacing.md,
  },
  submitBtn: {
    backgroundColor: colors.gold,
    borderRadius: borderRadius.md,
    paddingVertical: spacing.md,
    alignItems: "center",
    marginTop: spacing.sm,
  },
  btnDisabled: { opacity: 0.6 },
  submitBtnText: {
    fontSize: fontSize.lg,
    fontWeight: "600",
    color: colors.primary,
  },
  assessmentCard: {
    backgroundColor: colors.white,
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    marginBottom: spacing.lg,
    alignItems: "center",
  },
  rating: {
    fontSize: fontSize.xl,
    fontWeight: "700",
    textTransform: "capitalize",
    marginBottom: spacing.sm,
  },
  assessmentSummary: {
    fontSize: fontSize.sm,
    color: colors.gray700,
    textAlign: "center",
    lineHeight: 20,
  },
  sectionTitle: {
    fontSize: fontSize.md,
    fontWeight: "600",
    color: colors.gray900,
    marginTop: spacing.md,
    marginBottom: spacing.sm,
  },
  bodyText: {
    fontSize: fontSize.sm,
    color: colors.gray700,
    lineHeight: 20,
  },
  scriptBox: {
    backgroundColor: colors.sage,
    borderRadius: borderRadius.md,
    padding: spacing.md,
  },
  scriptText: {
    fontSize: fontSize.sm,
    color: colors.primary,
    lineHeight: 20,
    fontStyle: "italic",
  },
  bulletText: {
    fontSize: fontSize.sm,
    color: colors.gray700,
    lineHeight: 20,
    marginBottom: 4,
  },
  flagsRow: {
    flexDirection: "row",
    gap: spacing.md,
    marginTop: spacing.md,
  },
  flagCol: {
    flex: 1,
  },
  greenFlagTitle: {
    fontSize: fontSize.sm,
    fontWeight: "600",
    color: colors.green500,
    marginBottom: spacing.xs,
  },
  redFlagTitle: {
    fontSize: fontSize.sm,
    fontWeight: "600",
    color: colors.red500,
    marginBottom: spacing.xs,
  },
  flagItem: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: spacing.xs,
    marginBottom: 4,
  },
  flagText: {
    fontSize: fontSize.xs,
    color: colors.gray700,
    flex: 1,
  },
  resetBtn: {
    borderWidth: 1,
    borderColor: colors.gray300,
    borderRadius: borderRadius.md,
    paddingVertical: spacing.md,
    alignItems: "center",
    marginTop: spacing.lg,
  },
  resetBtnText: {
    fontSize: fontSize.md,
    fontWeight: "500",
    color: colors.gray600,
  },
});
