import { useEffect, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  RefreshControl,
  TouchableOpacity,
  ActivityIndicator,
  Alert,
} from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { api } from "../../lib/api";
import { handleFeatureGateResponse } from "../../lib/featureGate";
import LoadingSpinner from "../../components/LoadingSpinner";
import { colors, spacing, fontSize, borderRadius } from "../../lib/theme";

interface AuditLogEntry {
  id: number;
  action: string;
  details: string | null;
  created_at: string;
  user_email?: string;
}

interface OfccpReport {
  total_applicants: number;
  demographics_summary: Record<string, number>;
  compliance_status: string;
  generated_at: string;
}

export default function EmployerComplianceScreen() {
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [report, setReport] = useState<OfccpReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [reportLoading, setReportLoading] = useState(false);

  const loadData = async () => {
    try {
      const res = await api.get("/api/employer/compliance/log");
      if (handleFeatureGateResponse(res)) return;
      if (res.ok) {
        const data = await res.json();
        setLogs(Array.isArray(data) ? data : data.logs ?? []);
      }
    } catch {
      // silently fail
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const loadReport = async () => {
    setReportLoading(true);
    try {
      const res = await api.get("/api/employer/compliance/report/ofccp");
      if (handleFeatureGateResponse(res)) return;
      if (res.ok) {
        setReport(await res.json());
      } else {
        Alert.alert("Error", "Could not load OFCCP report.");
      }
    } catch {
      Alert.alert("Error", "Something went wrong.");
    } finally {
      setReportLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const onRefresh = () => {
    setRefreshing(true);
    loadData();
  };

  const formatDate = (d: string) => {
    try {
      return new Date(d).toLocaleDateString(undefined, {
        month: "short",
        day: "numeric",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return d;
    }
  };

  if (loading) return <LoadingSpinner />;

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
      }
    >
      {/* OFCCP Report */}
      <Text style={styles.sectionTitle}>OFCCP Report</Text>
      {report ? (
        <View style={styles.card}>
          <View style={styles.reportRow}>
            <Text style={styles.reportLabel}>Status</Text>
            <Text style={styles.reportValue}>{report.compliance_status}</Text>
          </View>
          <View style={styles.reportRow}>
            <Text style={styles.reportLabel}>Total Applicants</Text>
            <Text style={styles.reportValue}>{report.total_applicants}</Text>
          </View>
          <View style={styles.reportRow}>
            <Text style={styles.reportLabel}>Generated</Text>
            <Text style={styles.reportValue}>
              {formatDate(report.generated_at)}
            </Text>
          </View>
          {Object.entries(report.demographics_summary).map(([key, val]) => (
            <View key={key} style={styles.reportRow}>
              <Text style={styles.reportLabel}>{key}</Text>
              <Text style={styles.reportValue}>{val}</Text>
            </View>
          ))}
        </View>
      ) : (
        <TouchableOpacity
          style={styles.generateBtn}
          onPress={loadReport}
          disabled={reportLoading}
        >
          {reportLoading ? (
            <ActivityIndicator color={colors.primary} />
          ) : (
            <Text style={styles.generateBtnText}>Generate OFCCP Report</Text>
          )}
        </TouchableOpacity>
      )}

      {/* Audit Log */}
      <Text style={styles.sectionTitle}>Audit Log</Text>
      {logs.length === 0 ? (
        <View style={styles.emptyCard}>
          <Text style={styles.emptyText}>No audit log entries yet.</Text>
        </View>
      ) : (
        logs.map((entry) => (
          <View key={entry.id} style={styles.logEntry}>
            <View style={styles.logHeader}>
              <Text style={styles.logAction}>{entry.action}</Text>
              <Text style={styles.logDate}>{formatDate(entry.created_at)}</Text>
            </View>
            {entry.details && (
              <Text style={styles.logDetails}>{entry.details}</Text>
            )}
            {entry.user_email && (
              <Text style={styles.logUser}>{entry.user_email}</Text>
            )}
          </View>
        ))
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.gray50 },
  content: { padding: spacing.md, paddingBottom: spacing.xxl },
  sectionTitle: {
    fontSize: fontSize.lg,
    fontWeight: "700",
    color: colors.gray900,
    marginBottom: spacing.md,
    marginTop: spacing.md,
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
  reportRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    paddingVertical: spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: colors.gray100,
  },
  reportLabel: {
    fontSize: fontSize.sm,
    color: colors.gray600,
  },
  reportValue: {
    fontSize: fontSize.sm,
    fontWeight: "600",
    color: colors.gray900,
  },
  generateBtn: {
    backgroundColor: colors.gold,
    borderRadius: borderRadius.md,
    paddingVertical: spacing.md,
    alignItems: "center",
    marginBottom: spacing.md,
  },
  generateBtnText: {
    fontSize: fontSize.md,
    fontWeight: "600",
    color: colors.primary,
  },
  emptyCard: {
    backgroundColor: colors.white,
    borderRadius: borderRadius.lg,
    padding: spacing.lg,
    alignItems: "center",
  },
  emptyText: {
    fontSize: fontSize.sm,
    color: colors.gray400,
    fontStyle: "italic",
  },
  logEntry: {
    backgroundColor: colors.white,
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    marginBottom: spacing.sm,
    shadowColor: "#000",
    shadowOpacity: 0.03,
    shadowRadius: 4,
    elevation: 1,
  },
  logHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: spacing.xs,
  },
  logAction: {
    fontSize: fontSize.sm,
    fontWeight: "600",
    color: colors.gray900,
    flex: 1,
  },
  logDate: {
    fontSize: fontSize.xs,
    color: colors.gray400,
  },
  logDetails: {
    fontSize: fontSize.sm,
    color: colors.gray600,
    marginTop: 2,
  },
  logUser: {
    fontSize: fontSize.xs,
    color: colors.gray400,
    marginTop: 4,
  },
});
