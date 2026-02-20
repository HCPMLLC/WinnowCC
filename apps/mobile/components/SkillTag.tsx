import { View, Text, StyleSheet } from "react-native";
import { colors, spacing, fontSize, borderRadius } from "../lib/theme";

interface SkillTagProps {
  name: string;
}

export default function SkillTag({ name }: SkillTagProps) {
  return (
    <View style={styles.tag}>
      <Text style={styles.text}>{name}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  tag: {
    backgroundColor: colors.sage,
    borderRadius: borderRadius.full,
    paddingHorizontal: spacing.sm,
    paddingVertical: spacing.xs,
  },
  text: {
    fontSize: fontSize.xs,
    color: colors.primary,
    fontWeight: "500",
  },
});
