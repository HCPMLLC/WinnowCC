import { Redirect } from "expo-router";
import { useAuth } from "../lib/auth";

export default function Index() {
  const { isAuthenticated, role } = useAuth();

  if (!isAuthenticated) {
    return <Redirect href="/(auth)/login" />;
  }

  if (role === "employer") {
    return <Redirect href="/(employer-tabs)/dashboard" />;
  }

  return <Redirect href="/(tabs)/dashboard" />;
}
