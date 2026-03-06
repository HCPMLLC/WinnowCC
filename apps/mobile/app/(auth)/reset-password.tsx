import { useState } from "react";
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
  Alert,
} from "react-native";
import { useRouter, useLocalSearchParams } from "expo-router";
import { colors, spacing, fontSize, borderRadius } from "../../lib/theme";
import { API_BASE } from "../../lib/api";

export default function ResetPasswordScreen() {
  const router = useRouter();
  const { token: paramToken } = useLocalSearchParams<{ token?: string }>();
  const [token, setToken] = useState(paramToken || "");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [loading, setLoading] = useState(false);

  const passwordsMatch = password.length > 0 && password === confirm;
  const canSubmit = token.trim().length > 0 && passwordsMatch && !loading;

  const handleReset = async () => {
    if (!canSubmit) return;

    if (password.length < 8) {
      Alert.alert("Weak Password", "Password must be at least 8 characters.");
      return;
    }

    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/auth/reset-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token: token.trim(), password }),
      });

      if (res.ok) {
        Alert.alert(
          "Password Reset",
          "Your password has been updated. Please sign in.",
          [{ text: "OK", onPress: () => router.replace("/(auth)/login") }]
        );
      } else {
        const data = await res.json().catch(() => ({}));
        Alert.alert(
          "Reset Failed",
          (data as any).detail || "Invalid or expired reset link. Please request a new one."
        );
      }
    } catch {
      Alert.alert("Error", "Could not connect to server. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === "ios" ? "padding" : "height"}
    >
      <View style={styles.inner}>
        <Text style={styles.heading}>Set new password</Text>
        <Text style={styles.body}>
          Paste the reset token from your email and choose a new password.
        </Text>

        <TextInput
          style={styles.input}
          placeholder="Reset token"
          placeholderTextColor={colors.gray400}
          autoCapitalize="none"
          autoCorrect={false}
          value={token}
          onChangeText={setToken}
        />

        <TextInput
          style={styles.input}
          placeholder="New password"
          placeholderTextColor={colors.gray400}
          secureTextEntry
          value={password}
          onChangeText={setPassword}
        />

        <TextInput
          style={styles.input}
          placeholder="Confirm password"
          placeholderTextColor={colors.gray400}
          secureTextEntry
          value={confirm}
          onChangeText={setConfirm}
        />

        {password.length > 0 && confirm.length > 0 && !passwordsMatch && (
          <Text style={styles.error}>Passwords do not match</Text>
        )}

        <TouchableOpacity
          style={[styles.button, !canSubmit && styles.buttonDisabled]}
          onPress={handleReset}
          disabled={!canSubmit}
        >
          <Text style={styles.buttonText}>
            {loading ? "Resetting..." : "Reset Password"}
          </Text>
        </TouchableOpacity>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.primary },
  inner: {
    flex: 1,
    justifyContent: "center",
    paddingHorizontal: spacing.xl,
  },
  heading: {
    fontSize: fontSize.xxl,
    fontWeight: "700",
    color: colors.gold,
    textAlign: "center",
    marginBottom: spacing.md,
  },
  body: {
    fontSize: fontSize.sm,
    color: colors.gray300,
    textAlign: "center",
    marginBottom: spacing.lg,
    lineHeight: 20,
  },
  input: {
    backgroundColor: colors.white,
    borderRadius: borderRadius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    fontSize: fontSize.md,
    color: colors.gray900,
    marginBottom: spacing.md,
  },
  error: {
    color: colors.red500,
    fontSize: fontSize.xs,
    textAlign: "center",
    marginBottom: spacing.sm,
  },
  button: {
    backgroundColor: colors.gold,
    borderRadius: borderRadius.md,
    paddingVertical: spacing.md,
    alignItems: "center",
    marginTop: spacing.sm,
  },
  buttonDisabled: { opacity: 0.6 },
  buttonText: {
    fontSize: fontSize.lg,
    fontWeight: "600",
    color: colors.primary,
  },
});
