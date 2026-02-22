export type AuthMe = {
  user_id: number;
  email: string;
  onboarding_complete: boolean;
  is_admin: boolean;
  role: string;
};

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

function getTokenFromCookie(): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(/(?:^|;\s*)rm_token=([^;]*)/);
  return match ? match[1] : null;
}

export async function fetchAuthMe(): Promise<AuthMe | null> {
  const headers: Record<string, string> = {};
  const token = getTokenFromCookie();
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE}/api/auth/me`, {
    credentials: "include",
    headers,
  });
  if (!response.ok) {
    return null;
  }
  return (await response.json()) as AuthMe;
}
