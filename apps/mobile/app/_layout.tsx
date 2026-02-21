import { useEffect, useState, useCallback } from "react";
import { Stack, useRouter, useSegments } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { View, ActivityIndicator, Platform, Text } from "react-native";
import {
  AuthContext,
  AuthState,
  saveToken,
  getToken,
  removeToken,
  onTokenCleared,
} from "../lib/auth";
import { colors } from "../lib/theme";

const API_BASE =
  Platform.OS === "web"
    ? "http://localhost:8000"
    : process.env.EXPO_PUBLIC_API_BASE_URL || "http://localhost:8000";

export default function RootLayout() {
  const [authState, setAuthState] = useState<AuthState>({
    token: null,
    userId: null,
    email: null,
    role: null,
    onboardingComplete: false,
    isAuthenticated: false,
    isLoading: true,
  });

  const router = useRouter();
  const segments = useSegments();

  // Listen for forced token removal (e.g. 401 from API)
  useEffect(() => {
    onTokenCleared(() => {
      setAuthState({
        token: null,
        userId: null,
        email: null,
        role: null,
        onboardingComplete: false,
        isAuthenticated: false,
        isLoading: false,
      });
    });
  }, []);

  // Check for stored token on app launch
  useEffect(() => {
    (async () => {
      console.log("[RootLayout] Checking stored token...");
      try {
        const token = await getToken();
        console.log("[RootLayout] Token retrieved:", token ? "exists" : "none");
        if (token) {
          try {
            const res = await fetch(`${API_BASE}/api/auth/me`, {
              headers: { Authorization: `Bearer ${token}` },
            });
            if (res.ok) {
              const data = await res.json();
              setAuthState({
                token,
                userId: data.user_id,
                email: data.email,
                role: data.role || "candidate",
                onboardingComplete: !!data.onboarding_complete,
                isAuthenticated: true,
                isLoading: false,
              });
              return;
            }
          } catch (e) {
            console.log("[RootLayout] Auth check failed:", e);
          }
          await removeToken();
        }
      } catch (e) {
        console.log("[RootLayout] getToken error:", e);
      }
      console.log("[RootLayout] Setting isLoading=false");
      setAuthState((s) => ({ ...s, isLoading: false }));
    })();
  }, []);

  // Redirect based on auth state, onboarding, and role
  useEffect(() => {
    if (authState.isLoading) return;

    const inAuthGroup = segments[0] === "(auth)";
    const inOnboarding =
      segments[0] === "candidate-onboarding" ||
      segments[0] === "employer-onboarding" ||
      segments[0] === "recruiter-onboarding";

    if (!authState.isAuthenticated && !inAuthGroup) {
      router.replace("/(auth)/login");
    } else if (authState.isAuthenticated && inAuthGroup) {
      // Just logged in — check onboarding
      if (!authState.onboardingComplete) {
        if (authState.role === "recruiter") {
          router.replace("/recruiter-onboarding");
        } else if (authState.role === "employer") {
          router.replace("/employer-onboarding");
        } else {
          router.replace("/candidate-onboarding");
        }
      } else if (authState.role === "recruiter") {
        router.replace("/(recruiter-tabs)/dashboard");
      } else if (authState.role === "employer") {
        router.replace("/(employer-tabs)/dashboard");
      } else {
        router.replace("/(tabs)/dashboard");
      }
    }
  }, [authState.isAuthenticated, authState.isLoading, authState.onboardingComplete, segments, router]);

  const login = useCallback(async (email: string, password: string) => {
    const res = await fetch(`${API_BASE}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Login failed");
    }

    const data = await res.json();
    await saveToken(data.token);
    setAuthState({
      token: data.token,
      userId: data.user_id,
      email: data.email,
      role: data.role || "candidate",
      onboardingComplete: !!data.onboarding_complete,
      isAuthenticated: true,
      isLoading: false,
    });
  }, []);

  const signup = useCallback(
    async (email: string, password: string, role?: string) => {
      const res = await fetch(`${API_BASE}/api/auth/signup`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password, role: role || "candidate" }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Signup failed");
      }

      const data = await res.json();
      await saveToken(data.token);
      setAuthState({
        token: data.token,
        userId: data.user_id,
        email: data.email,
        role: data.role || role || "candidate",
        onboardingComplete: !!data.onboarding_complete,
        isAuthenticated: true,
        isLoading: false,
      });
    },
    [],
  );

  const markOnboardingComplete = useCallback(() => {
    setAuthState((s) => ({ ...s, onboardingComplete: true }));
  }, []);

  const logout = useCallback(async () => {
    try {
      const token = await getToken();
      await fetch(`${API_BASE}/api/auth/logout`, {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
    } catch {
      // Logout API call is best-effort
    }
    await removeToken();
    setAuthState({
      token: null,
      userId: null,
      email: null,
      role: null,
      onboardingComplete: false,
      isAuthenticated: false,
      isLoading: false,
    });
  }, []);

  console.log("[RootLayout] Render — isLoading:", authState.isLoading, "isAuth:", authState.isAuthenticated);

  if (authState.isLoading) {
    return (
      <View
        style={{
          flex: 1,
          justifyContent: "center",
          alignItems: "center",
          backgroundColor: colors.primary,
        }}
      >
        <ActivityIndicator size="large" color={colors.gold} />
        <Text style={{ color: "#E8C84A", marginTop: 16 }}>Loading Winnow...</Text>
      </View>
    );
  }

  return (
    <AuthContext.Provider value={{ ...authState, login, signup, logout, markOnboardingComplete }}>
      <StatusBar style="light" />
      <Stack
        screenOptions={{
          headerStyle: { backgroundColor: colors.primary },
          headerTintColor: colors.white,
          headerTitleStyle: { fontWeight: "600" },
          contentStyle: { backgroundColor: colors.gray50 },
        }}
      >
        <Stack.Screen name="(auth)" options={{ headerShown: false }} />
        <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
        <Stack.Screen
          name="(employer-tabs)"
          options={{ headerShown: false }}
        />
        <Stack.Screen
          name="(recruiter-tabs)"
          options={{ headerShown: false }}
        />
        <Stack.Screen
          name="candidate-onboarding"
          options={{ title: "Complete Your Profile", presentation: "card" }}
        />
        <Stack.Screen
          name="recruiter-onboarding"
          options={{ title: "Setup Recruiter Profile", presentation: "card" }}
        />
        <Stack.Screen
          name="recruiter/job/[id]"
          options={{ title: "Job Details", presentation: "card" }}
        />
        <Stack.Screen
          name="recruiter/client/[id]"
          options={{ title: "Client Details", presentation: "card" }}
        />
        <Stack.Screen
          name="recruiter/upload"
          options={{ title: "Bulk Resume Upload", presentation: "card" }}
        />
        <Stack.Screen
          name="recruiter/pipeline/add"
          options={{ title: "Add to Pipeline", presentation: "card" }}
        />
        <Stack.Screen
          name="recruiter/pipeline/[id]"
          options={{ title: "Pipeline Candidate", presentation: "card" }}
        />
        <Stack.Screen
          name="match/[id]"
          options={{ title: "Job Details", presentation: "card" }}
        />
        <Stack.Screen
          name="employer-onboarding"
          options={{ title: "Setup Company Profile", presentation: "card" }}
        />
        <Stack.Screen
          name="employer/job/[id]"
          options={{ title: "Job Details", presentation: "card" }}
        />
        <Stack.Screen
          name="employer/job/new"
          options={{ title: "Post a Job", presentation: "card" }}
        />
        <Stack.Screen
          name="employer/candidate/[id]"
          options={{ title: "Candidate", presentation: "card" }}
        />
        <Stack.Screen
          name="employer/analytics"
          options={{ title: "Analytics", presentation: "card" }}
        />
        <Stack.Screen
          name="employer/saved"
          options={{ title: "Saved Candidates", presentation: "card" }}
        />
        <Stack.Screen
          name="sieve"
          options={{
            title: "Sieve",
            presentation: "fullScreenModal",
            headerStyle: { backgroundColor: colors.primary },
            headerTintColor: colors.white,
          }}
        />
        <Stack.Screen
          name="profile/upload"
          options={{ title: "Upload Resume", presentation: "card" }}
        />
        <Stack.Screen
          name="profile/documents"
          options={{ title: "Documents", presentation: "card" }}
        />
        <Stack.Screen
          name="profile/references"
          options={{ title: "References", presentation: "card" }}
        />
        <Stack.Screen
          name="profile/insights"
          options={{ title: "Career Insights", presentation: "card" }}
        />
        <Stack.Screen
          name="profile/billing"
          options={{ title: "Billing", presentation: "card" }}
        />
        <Stack.Screen
          name="profile/settings"
          options={{ title: "Settings", presentation: "card" }}
        />
      </Stack>
    </AuthContext.Provider>
  );
}
