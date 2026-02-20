import { View, Text, TouchableOpacity, StyleSheet } from "react-native";
import { Ionicons } from "@expo/vector-icons";
import { colors, spacing, fontSize, borderRadius } from "../lib/theme";

interface ProfileMenuItemProps {
  icon: string;
  label: string;
  subtitle?: string;
  onPress: () => void;
  badge?: string;
  badgeColor?: string;
}

export default function ProfileMenuItem({
  icon,
  label,
  subtitle,
  onPress,
  badge,
  badgeColor,
}: ProfileMenuItemProps) {
  return (
    <TouchableOpacity style={styles.card} onPress={onPress} activeOpacity={0.7}>
      <View style={styles.iconWrap}>
        <Ionicons name={icon as any} size={22} color={colors.primary} />
      </View>
      <View style={styles.content}>
        <Text style={styles.label}>{label}</Text>
        {subtitle && <Text style={styles.subtitle}>{subtitle}</Text>}
      </View>
      {badge && (
        <View
          style={[
            styles.badge,
            { backgroundColor: badgeColor || colors.gold },
          ]}
        >
          <Text style={styles.badgeText}>{badge}</Text>
        </View>
      )}
      <Ionicons name="chevron-forward" size={18} color={colors.gray400} />
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  card: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: colors.white,
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    marginBottom: spacing.sm,
    shadowColor: "#000",
    shadowOpacity: 0.05,
    shadowRadius: 8,
    elevation: 2,
  },
  iconWrap: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: colors.sage,
    justifyContent: "center",
    alignItems: "center",
    marginRight: spacing.md,
  },
  content: { flex: 1 },
  label: {
    fontSize: fontSize.md,
    fontWeight: "600",
    color: colors.gray900,
  },
  subtitle: {
    fontSize: fontSize.xs,
    color: colors.gray500,
    marginTop: 2,
  },
  badge: {
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
    borderRadius: borderRadius.full,
    marginRight: spacing.sm,
  },
  badgeText: {
    fontSize: fontSize.xs,
    fontWeight: "600",
    color: colors.primary,
  },
});
