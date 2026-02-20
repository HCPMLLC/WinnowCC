import { View, Text, StyleSheet } from "react-native";
import { colors, fontSize, borderRadius } from "../lib/theme";

interface ScoreBadgeProps {
  score: number;
  label?: string;
}

function getScoreColor(score: number): string {
  if (score >= 70) return colors.green500;
  if (score >= 50) return colors.amber500;
  return colors.red500;
}

export default function ScoreBadge({ score, label }: ScoreBadgeProps) {
  const color = getScoreColor(score);

  return (
    <View style={[styles.badge, { borderColor: color }]}>
      <Text style={[styles.score, { color }]}>{score}</Text>
      {label && <Text style={styles.label}>{label}</Text>}
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    width: 56,
    height: 56,
    borderRadius: borderRadius.full,
    borderWidth: 3,
    justifyContent: "center",
    alignItems: "center",
  },
  score: {
    fontSize: fontSize.lg,
    fontWeight: "700",
  },
  label: {
    fontSize: 9,
    color: colors.gray500,
    marginTop: -2,
  },
});
