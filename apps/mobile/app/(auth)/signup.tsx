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
import { Ionicons } from "@expo/vector-icons";
import { useAuth } from "../../lib/auth";
import { colors, spacing, fontSize, borderRadius } from "../../lib/theme";

export default function SignupScreen() {
  const { signup } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [role, setRole] = useState<"candidate" | "employer" | "recruiter">("candidate");
  const [loading, setLoading] = useState(false);

  const handleSignup = async () => {
    if (!email.trim() || !password) return;
    if (password !== confirmPassword) {
      Alert.alert("Error", "Passwords do not match.");
      return;
    }
    setLoading(true);
    try {
      await signup(email.trim().toLowerCase(), password, role);
    } catch (err: any) {
      Alert.alert("Signup Failed", err.message || "Please try again.");
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
        <Text style={styles.logo}>Winnow</Text>
        <Text style={styles.subtitle}>Create your account</Text>

        {/* Role Picker */}
        <View style={styles.rolePicker}>
          <TouchableOpacity
            style={[
              styles.roleOption,
              role === "candidate" && styles.roleOptionActive,
            ]}
            onPress={() => setRole("candidate")}
          >
            <Ionicons
              name="person-outline"
              size={20}
              color={role === "candidate" ? colors.primary : colors.gray400}
            />
            <Text
              style={[
                styles.roleText,
                role === "candidate" && styles.roleTextActive,
              ]}
            >
              Job Seeker
            </Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[
              styles.roleOption,
              role === "employer" && styles.roleOptionActive,
            ]}
            onPress={() => setRole("employer")}
          >
            <Ionicons
              name="business-outline"
              size={20}
              color={role === "employer" ? colors.primary : colors.gray400}
            />
            <Text
              style={[
                styles.roleText,
                role === "employer" && styles.roleTextActive,
              ]}
            >
              Employer
            </Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={[
              styles.roleOption,
              role === "recruiter" && styles.roleOptionActive,
            ]}
            onPress={() => setRole("recruiter")}
          >
            <Ionicons
              name="people-outline"
              size={20}
              color={role === "recruiter" ? colors.primary : colors.gray400}
            />
            <Text
              style={[
                styles.roleText,
                role === "recruiter" && styles.roleTextActive,
              ]}
            >
              Recruiter
            </Text>
          </TouchableOpacity>
        </View>

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

        <TextInput
          style={styles.input}
          placeholder="Password"
          placeholderTextColor={colors.gray400}
          secureTextEntry
          value={password}
          onChangeText={setPassword}
        />

        <TextInput
          style={styles.input}
          placeholder="Confirm Password"
          placeholderTextColor={colors.gray400}
          secureTextEntry
          value={confirmPassword}
          onChangeText={setConfirmPassword}
        />

        <TouchableOpacity
          style={[styles.button, loading && styles.buttonDisabled]}
          onPress={handleSignup}
          disabled={loading}
        >
          <Text style={styles.buttonText}>
            {loading ? "Creating account..." : "Create Account"}
          </Text>
        </TouchableOpacity>

        <View style={styles.footer}>
          <Text style={styles.footerText}>Already have an account? </Text>
          <Link href="/(auth)/login" asChild>
            <TouchableOpacity>
              <Text style={styles.link}>Sign In</Text>
            </TouchableOpacity>
          </Link>
        </View>
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
  logo: {
    fontSize: fontSize.xxxl,
    fontWeight: "700",
    color: colors.gold,
    textAlign: "center",
    marginBottom: spacing.xs,
  },
  subtitle: {
    fontSize: fontSize.md,
    color: colors.sage,
    textAlign: "center",
    marginBottom: spacing.lg,
  },
  rolePicker: {
    flexDirection: "row",
    gap: spacing.sm,
    marginBottom: spacing.lg,
  },
  roleOption: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.xs,
    paddingVertical: spacing.md,
    borderRadius: borderRadius.md,
    backgroundColor: colors.primaryLight,
    borderWidth: 2,
    borderColor: "transparent",
  },
  roleOptionActive: {
    backgroundColor: colors.gold,
    borderColor: colors.gold,
  },
  roleText: {
    fontSize: fontSize.sm,
    fontWeight: "600",
    color: colors.gray400,
  },
  roleTextActive: {
    color: colors.primary,
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
  footer: {
    flexDirection: "row",
    justifyContent: "center",
    marginTop: spacing.lg,
  },
  footerText: { color: colors.gray300, fontSize: fontSize.sm },
  link: { color: colors.gold, fontSize: fontSize.sm, fontWeight: "600" },
});
