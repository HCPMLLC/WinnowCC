import { Stack } from "expo-router";
import { colors } from "../../lib/theme";

export default function AuthLayout() {
  return (
    <Stack
      screenOptions={{
        headerStyle: { backgroundColor: colors.primary },
        headerTintColor: colors.white,
        headerTitleStyle: { fontWeight: "600" },
      }}
    >
      <Stack.Screen name="login" options={{ title: "Login" }} />
      <Stack.Screen name="signup" options={{ title: "Sign Up" }} />
      <Stack.Screen name="forgot-password" options={{ title: "Reset Password" }} />
      <Stack.Screen name="reset-password" options={{ title: "New Password" }} />
    </Stack>
  );
}
