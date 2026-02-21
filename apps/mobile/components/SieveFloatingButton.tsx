import { useEffect, useRef } from "react";
import { TouchableOpacity, Animated, StyleSheet, View, Text } from "react-native";
import { useRouter } from "expo-router";
import SieveLogo from "./SieveLogo";
import { colors, spacing } from "../lib/theme";

interface SieveFloatingButtonProps {
  badgeCount?: number;
}

export default function SieveFloatingButton({ badgeCount = 0 }: SieveFloatingButtonProps) {
  const router = useRouter();
  const pulseAnim = useRef(new Animated.Value(0)).current;
  const scaleAnim = useRef(new Animated.Value(1)).current;

  // Pulse glow animation
  useEffect(() => {
    const pulse = Animated.loop(
      Animated.sequence([
        Animated.timing(pulseAnim, {
          toValue: 1,
          duration: 1500,
          useNativeDriver: false,
        }),
        Animated.timing(pulseAnim, {
          toValue: 0,
          duration: 1500,
          useNativeDriver: false,
        }),
      ])
    );
    pulse.start();
    return () => pulse.stop();
  }, [pulseAnim]);

  const handlePressIn = () => {
    Animated.spring(scaleAnim, {
      toValue: 0.92,
      useNativeDriver: true,
    }).start();
  };

  const handlePressOut = () => {
    Animated.spring(scaleAnim, {
      toValue: 1,
      friction: 3,
      useNativeDriver: true,
    }).start();
  };

  const shadowOpacity = pulseAnim.interpolate({
    inputRange: [0, 1],
    outputRange: [0.2, 0.5],
  });

  const shadowRadius = pulseAnim.interpolate({
    inputRange: [0, 1],
    outputRange: [8, 18],
  });

  return (
    <Animated.View
      style={[
        styles.container,
        {
          transform: [{ scale: scaleAnim }],
          shadowOpacity,
          shadowRadius,
        },
      ]}
    >
      <TouchableOpacity
        style={styles.fab}
        onPress={() => router.push("/sieve")}
        onPressIn={handlePressIn}
        onPressOut={handlePressOut}
        activeOpacity={1}
      >
        <SieveLogo size={60} animate />

        {/* Badge */}
        {badgeCount > 0 && (
          <View style={styles.badge}>
            <Text style={styles.badgeText}>{badgeCount}</Text>
          </View>
        )}
      </TouchableOpacity>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  container: {
    position: "absolute",
    bottom: 90,
    right: spacing.md,
    zIndex: 100,
    shadowColor: "#3B945E",
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
    // Dark green gradient approximation
    backgroundColor: colors.primary,
    borderWidth: 1,
    borderColor: "rgba(42, 80, 56, 0.6)",
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
