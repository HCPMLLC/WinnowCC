import { View, Text, StyleSheet } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { colors, spacing, fontSize, borderRadius } from "../lib/theme";

interface RecruiterStatCardProps {
  icon: string;
  label: string;
  value: number | string;
  color?: string;
}

export default function RecruiterStatCard({
  icon,
  label,
  value,
  color = colors.primary,
}: RecruiterStatCardProps) {
  return (
    <View style={styles.card}>
      <Ionicons name={icon as any} size={24} color={color} />
      <Text style={[styles.value, { color }]}>{value}</Text>
      <Text style={styles.label}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
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
  value: {
    fontSize: fontSize.xxxl,
    fontWeight: "700",
    marginTop: spacing.xs,
  },
  label: {
    fontSize: fontSize.sm,
    color: colors.gray500,
    marginTop: spacing.xs,
  },
});
