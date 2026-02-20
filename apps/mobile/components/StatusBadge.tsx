import { View, Text, StyleSheet } from "react-native";
import { colors, fontSize, borderRadius, spacing } from "../lib/theme";

const STATUS_COLORS: Record<string, { bg: string; text: string }> = {
  draft: { bg: colors.gray200, text: colors.gray700 },
  active: { bg: "#DCFCE7", text: "#166534" },
  paused: { bg: "#FEF3C7", text: "#92400E" },
  closed: { bg: "#FEE2E2", text: "#991B1B" },
};

export default function StatusBadge({ status }: { status: string }) {
  const palette = STATUS_COLORS[status] || STATUS_COLORS.draft;

  return (
    <View style={[styles.badge, { backgroundColor: palette.bg }]}>
      <Text style={[styles.text, { color: palette.text }]}>
        {status.charAt(0).toUpperCase() + status.slice(1)}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    alignSelf: "flex-start",
    borderRadius: borderRadius.full,
    paddingHorizontal: spacing.sm,
    paddingVertical: 3,
  },
  text: {
    fontSize: fontSize.xs,
    fontWeight: "600",
  },
});
