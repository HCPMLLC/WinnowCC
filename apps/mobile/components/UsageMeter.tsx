import { View, Text, StyleSheet } from "react-native";
import { colors, spacing, fontSize, borderRadius } from "../lib/theme";

interface UsageMeterProps {
  label: string;
  used: number;
  limit: number | null;
  color?: string;
}

export default function UsageMeter({
  label,
  used,
  limit,
  color = colors.gold,
}: UsageMeterProps) {
  const pct = limit ? Math.min((used / limit) * 100, 100) : 0;
  const barColor = limit && pct >= 100 ? colors.red500 : pct >= 75 ? colors.amber500 : color;

  return (
    <View style={styles.container}>
      <View style={styles.labelRow}>
        <Text style={styles.label}>{label}</Text>
        <Text style={styles.value}>
          {used} / {limit != null ? limit : "unlimited"}
        </Text>
      </View>
      <View style={styles.track}>
        <View
          style={[
            styles.fill,
            {
              width: limit ? `${pct}%` : "0%",
              backgroundColor: barColor,
            },
          ]}
        />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { marginBottom: spacing.md },
  labelRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginBottom: spacing.xs,
  },
  label: {
    fontSize: fontSize.sm,
    fontWeight: "500",
    color: colors.gray700,
  },
  value: {
    fontSize: fontSize.sm,
    color: colors.gray500,
  },
  track: {
    height: 8,
    backgroundColor: colors.gray200,
    borderRadius: borderRadius.full,
    overflow: "hidden",
  },
  fill: {
    height: 8,
    borderRadius: borderRadius.full,
  },
});
