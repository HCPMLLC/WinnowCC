import { TouchableOpacity, Image, StyleSheet, View, Text } from "react-native";
import { useRouter } from "expo-router";
import { colors, spacing } from "../lib/theme";

const SieveImage = require("../assets/golden-sieve-static.png");

interface SieveFloatingButtonProps {
  badgeCount?: number;
}

export default function SieveFloatingButton({ badgeCount = 0 }: SieveFloatingButtonProps) {
  const router = useRouter();

  return (
    <View style={styles.container}>
      <TouchableOpacity
        style={styles.fab}
        onPress={() => router.push("/sieve")}
        activeOpacity={0.8}
      >
        <Image
          source={SieveImage}
          style={styles.sieveImage}
          resizeMode="contain"
        />

        {/* Badge */}
        {badgeCount > 0 && (
          <View style={styles.badge}>
            <Text style={styles.badgeText}>{badgeCount}</Text>
          </View>
        )}
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    position: "absolute",
    bottom: 90,
    right: spacing.md,
    zIndex: 100,
    shadowColor: "#C49528",
    shadowOpacity: 0.35,
    shadowRadius: 10,
    shadowOffset: { width: 0, height: 4 },
    elevation: 8,
  },
  fab: {
    width: 64,
    height: 64,
    borderRadius: 32,
    justifyContent: "center",
    alignItems: "center",
    overflow: "hidden",
    backgroundColor: colors.primary,
    borderWidth: 2,
    borderColor: "rgba(232, 200, 74, 0.3)",
  },
  sieveImage: {
    width: 52,
    height: 52,
    tintColor: "#E8C84A",
  },
  badge: {
    position: "absolute",
    top: -2,
    right: -2,
    width: 22,
    height: 22,
    borderRadius: 11,
    backgroundColor: colors.gold,
    justifyContent: "center",
    alignItems: "center",
    borderWidth: 2,
    borderColor: colors.primary,
    shadowColor: "#C49528",
    shadowOpacity: 0.4,
    shadowRadius: 6,
    shadowOffset: { width: 0, height: 2 },
    elevation: 4,
  },
  badgeText: {
    color: colors.primary,
    fontSize: 12,
    fontWeight: "700",
  },
});
