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
import { Link } from "expo-router";
import { colors, spacing, fontSize, borderRadius } from "../../lib/theme";
import { API_BASE } from "../../lib/api";

export default function ForgotPasswordScreen() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);

  const handleSubmit = async () => {
    const trimmed = email.trim().toLowerCase();
    if (!trimmed) return;
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/auth/forgot-password`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: trimmed }),
      });
      if (res.ok) {
        setSent(true);
      } else {
        // API always returns 200 to prevent enumeration, but handle edge cases
        setSent(true);
      }
    } catch {
      Alert.alert("Error", "Could not connect to server. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  if (sent) {
    return (
      <View style={styles.container}>
        <View style={styles.inner}>
          <Text style={styles.heading}>Check your email</Text>
          <Text style={styles.body}>
            If an account exists for {email.trim().toLowerCase()}, we sent a
            password reset link. The link expires in 30 minutes.
          </Text>
          <Text style={styles.body}>
            Check your spam folder if you don't see it.
          </Text>

          <Link href="/(auth)/reset-password" asChild>
            <TouchableOpacity style={styles.button}>
              <Text style={styles.buttonText}>I have a reset code</Text>
            </TouchableOpacity>
          </Link>

          <TouchableOpacity
            style={styles.secondaryBtn}
            onPress={() => setSent(false)}
          >
            <Text style={styles.secondaryBtnText}>Send again</Text>
          </TouchableOpacity>

          <Link href="/(auth)/login" asChild>
            <TouchableOpacity style={styles.backRow}>
              <Text style={styles.backText}>Back to Login</Text>
            </TouchableOpacity>
          </Link>
        </View>
      </View>
    );
  }

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === "ios" ? "padding" : "height"}
    >
      <View style={styles.inner}>
        <Text style={styles.heading}>Reset your password</Text>
        <Text style={styles.body}>
          Enter the email address associated with your account and we'll send
          you a link to reset your password.
        </Text>

        <TextInput
          style={styles.input}
          placeholder="Email"
          placeholderTextColor={colors.gray400}
          keyboardType="email-address"
          autoCapitalize="none"
          autoCorrect={false}
          value={email}
          onChangeText={setEmail}
        />

        <TouchableOpacity
          style={[styles.button, loading && styles.buttonDisabled]}
          onPress={handleSubmit}
          disabled={loading || !email.trim()}
        >
          <Text style={styles.buttonText}>
            {loading ? "Sending..." : "Send Reset Link"}
          </Text>
        </TouchableOpacity>

        <Link href="/(auth)/login" asChild>
          <TouchableOpacity style={styles.backRow}>
            <Text style={styles.backText}>Back to Login</Text>
          </TouchableOpacity>
        </Link>
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
    marginBottom: spacing.md,
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
    marginTop: spacing.md,
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
  secondaryBtn: {
    alignItems: "center",
    marginTop: spacing.md,
    paddingVertical: spacing.sm,
  },
  secondaryBtnText: {
    color: colors.gold,
    fontSize: fontSize.sm,
    fontWeight: "600",
  },
  backRow: { alignItems: "center", marginTop: spacing.lg },
  backText: { color: colors.gray300, fontSize: fontSize.sm },
});
