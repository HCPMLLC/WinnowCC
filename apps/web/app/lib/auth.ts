export type AuthMe = {
  user_id: number;
  email: string;
  onboarding_complete: boolean;
};

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export async function fetchAuthMe(): Promise<AuthMe | null> {
  const response = await fetch(`${API_BASE}/api/auth/me`, {
    credentials: "include",
  });
  if (!response.ok) {
    return null;
  }
  return (await response.json()) as AuthMe;
}
