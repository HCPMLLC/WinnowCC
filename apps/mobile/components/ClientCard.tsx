import { View, Text, TouchableOpacity, StyleSheet } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import {
  CLIENT_STATUS_COLORS,
  type Client,
  type ClientStatus,
} from "../lib/recruiter-types";
import { colors, spacing, fontSize, borderRadius } from "../lib/theme";

interface ClientCardProps {
  client: Client;
  onPress: () => void;
}

export default function ClientCard({ client, onPress }: ClientCardProps) {
  const statusColor =
    CLIENT_STATUS_COLORS[client.status as ClientStatus] ?? colors.gray400;

  return (
    <TouchableOpacity style={styles.card} onPress={onPress} activeOpacity={0.7}>
      <View style={styles.header}>
        <Text style={styles.name} numberOfLines={1}>
          {client.company_name}
        </Text>
        <View style={[styles.statusBadge, { backgroundColor: statusColor }]}>
          <Text style={styles.statusText}>
            {client.status.charAt(0).toUpperCase() + client.status.slice(1)}
          </Text>
        </View>
      </View>

      {client.industry && (
        <Text style={styles.industry}>{client.industry}</Text>
      )}

      <View style={styles.metaRow}>
        {client.contact_name && (
          <View style={styles.metaItem}>
            <Ionicons name="person-outline" size={14} color={colors.gray400} />
            <Text style={styles.metaText}>{client.contact_name}</Text>
          </View>
        )}
        {client.contact_email && (
          <View style={styles.metaItem}>
            <Ionicons name="mail-outline" size={14} color={colors.gray400} />
            <Text style={styles.metaText} numberOfLines={1}>
              {client.contact_email}
            </Text>
          </View>
        )}
      </View>

      <View style={styles.footer}>
        <Text style={styles.footerText}>{client.job_count} jobs</Text>
        {client.fee_percentage != null && (
          <Text style={styles.footerText}>{client.fee_percentage}% fee</Text>
        )}
      </View>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.white,
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    marginBottom: spacing.sm,
    shadowColor: "#000",
    shadowOpacity: 0.05,
    shadowRadius: 8,
    elevation: 2,
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: spacing.xs,
  },
  name: {
    fontSize: fontSize.md,
    fontWeight: "600",
    color: colors.gray900,
    flex: 1,
    marginRight: spacing.sm,
  },
  statusBadge: {
    paddingHorizontal: 8,
    paddingVertical: 3,
    borderRadius: borderRadius.full,
  },
  statusText: {
    fontSize: fontSize.xs,
    fontWeight: "600",
    color: colors.white,
  },
  industry: {
    fontSize: fontSize.sm,
    color: colors.gray600,
    marginBottom: spacing.xs,
  },
  metaRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: spacing.md,
    marginBottom: spacing.xs,
  },
  metaItem: {
    flexDirection: "row",
    alignItems: "center",
    gap: 4,
  },
  metaText: {
    fontSize: fontSize.xs,
    color: colors.gray500,
  },
  footer: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginTop: spacing.xs,
  },
  footerText: {
    fontSize: fontSize.xs,
    color: colors.gray400,
    fontWeight: "600",
  },
});
