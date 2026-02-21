import { createContext, useContext } from "react";
import { Platform } from "react-native";

const TOKEN_KEY = "winnow_auth_token";

export interface AuthState {
  token: string | null;
  userId: number | null;
  email: string | null;
  role: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
}

export interface AuthContextType extends AuthState {
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string, role?: string) => Promise<void>;
  logout: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextType | null>(null);

export function useAuth(): AuthContextType {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

// expo-secure-store doesn't work on web — fall back to localStorage
async function getSecureStore() {
  if (Platform.OS === "web") return null;
  try {
    return await import("expo-secure-store");
  } catch {
    return null;
  }
}

export async function saveToken(token: string): Promise<void> {
  const store = await getSecureStore();
  if (store) {
    await store.setItemAsync(TOKEN_KEY, token);
  } else if (typeof localStorage !== "undefined") {
    localStorage.setItem(TOKEN_KEY, token);
  }
}

export async function getToken(): Promise<string | null> {
  const store = await getSecureStore();
  if (store) {
    return await store.getItemAsync(TOKEN_KEY);
  } else if (typeof localStorage !== "undefined") {
    return localStorage.getItem(TOKEN_KEY);
  }
  return null;
}

export async function removeToken(): Promise<void> {
  const store = await getSecureStore();
  if (store) {
    await store.deleteItemAsync(TOKEN_KEY);
  } else if (typeof localStorage !== "undefined") {
    localStorage.removeItem(TOKEN_KEY);
  }
}
