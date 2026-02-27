import { useState, useEffect } from "react";
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
import { useRouter } from "expo-router";
import { useAuth } from "../../lib/auth";
import { colors, spacing, fontSize, borderRadius } from "../../lib/theme";

export default function VerifyOtpScreen() {
  const { verifyOtp, resendOtp, mfaPendingEmail, mfaDeliveryMethod, mfaHasPhone, cancelMfa } = useAuth();
  const router = useRouter();
  const [otpCode, setOtpCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [resendBusy, setResendBusy] = useState(false);
  const [resendMsg, setResendMsg] = useState<string | null>(null);
  const isSms = mfaDeliveryMethod === "sms";

  // Guard: redirect to login if no pending MFA
  useEffect(() => {
    if (!mfaPendingEmail) {
      router.replace("/(auth)/login");
    }
  }, [mfaPendingEmail, router]);

  if (!mfaPendingEmail) return null;

  const handleVerify = async () => {
    if (otpCode.length < 6) return;
    setLoading(true);
    setResendMsg(null);
    try {
      await verifyOtp(otpCode);
      // Auth state update in context triggers redirect via root layout
    } catch (err: any) {
      Alert.alert("Verification Failed", err.message || "Invalid code.");
    } finally {
      setLoading(false);
    }
  };

  const handleResend = async (switchTo?: "email" | "sms") => {
    setResendBusy(true);
    setResendMsg(null);
    try {
      const usedMethod = await resendOtp(switchTo);
      setOtpCode("");
      setResendMsg(
        usedMethod === "sms"
          ? "A new code has been sent to your phone."
          : "A new code has been sent to your email."
      );
    } catch (err: any) {
      Alert.alert("Resend Failed", err.message || "Could not resend code.");
    } finally {
      setResendBusy(false);
    }
  };

  const handleBack = () => {
    cancelMfa();
    router.replace("/(auth)/login");
  };

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === "ios" ? "padding" : "height"}
    >
      <View style={styles.inner}>
        <Text style={styles.heading}>
          {isSms ? "Check your phone" : "Check your email"}
        </Text>
        <Text style={styles.body}>
          {isSms
            ? "We sent a 6-digit code to your phone number on file."
            : <>We sent a 6-digit code to{" "}
                <Text style={styles.emailHighlight}>{mfaPendingEmail}</Text>
              </>}
        </Text>

        <TextInput
          style={styles.otpInput}
          placeholder="000000"
          placeholderTextColor={colors.gray400}
          keyboardType="number-pad"
          maxLength={6}
          autoFocus
          value={otpCode}
          onChangeText={(text) => setOtpCode(text.replace(/\D/g, "").slice(0, 6))}
        />

        {resendMsg && (
          <Text style={styles.successMsg}>{resendMsg}</Text>
        )}

        <TouchableOpacity
          style={[styles.button, (loading || otpCode.length < 6) && styles.buttonDisabled]}
          onPress={handleVerify}
          disabled={loading || otpCode.length < 6}
        >
          <Text style={styles.buttonText}>
            {loading ? "Verifying..." : "Verify"}
          </Text>
        </TouchableOpacity>

        <TouchableOpacity
          style={styles.linkRow}
          onPress={() => handleResend()}
          disabled={resendBusy}
        >
          <Text style={[styles.linkText, resendBusy && styles.linkDisabled]}>
            {resendBusy ? "Sending..." : "Resend code"}
          </Text>
        </TouchableOpacity>

        {mfaHasPhone && (
          <TouchableOpacity
            style={styles.linkRow}
            onPress={() => handleResend(isSms ? "email" : "sms")}
            disabled={resendBusy}
          >
            <Text style={[styles.switchText, resendBusy && styles.linkDisabled]}>
              {isSms ? "Send to my email instead" : "Send to my phone instead"}
            </Text>
          </TouchableOpacity>
        )}

        <TouchableOpacity style={styles.linkRow} onPress={handleBack}>
          <Text style={styles.linkText}>Back to Sign In</Text>
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
    marginBottom: spacing.sm,
  },
  body: {
    fontSize: fontSize.md,
    color: colors.white,
    marginBottom: spacing.xl,
  },
  emailHighlight: {
    fontWeight: "700",
  },
  otpInput: {
    backgroundColor: colors.white,
    borderRadius: borderRadius.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.md,
    fontSize: fontSize.xxl,
    color: colors.gray900,
    textAlign: "center",
    letterSpacing: 12,
    fontFamily: Platform.OS === "ios" ? "Menlo" : "monospace",
    marginBottom: spacing.md,
  },
  successMsg: {
    fontSize: fontSize.sm,
    color: colors.green500,
    textAlign: "center",
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
  linkRow: {
    alignItems: "center",
    marginTop: spacing.md,
  },
  linkText: {
    color: colors.gray300,
    fontSize: fontSize.sm,
  },
  linkDisabled: { opacity: 0.5 },
  switchText: {
    color: colors.gray300,
    fontSize: fontSize.sm,
    textDecorationLine: "underline",
  },
});
