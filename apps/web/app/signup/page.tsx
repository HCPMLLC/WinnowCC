"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";

export default function SignupPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      const res = await fetch(`${API_BASE}/api/auth/signup`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ email, password }),
      });
      if (!res.ok) throw new Error(await res.text());
      router.push("/onboarding");
    } catch (e: any) {
      setErr(e?.message || "Signup failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main style={{ padding: 24, maxWidth: 560 }}>
      <h1>Sign up</h1>
      <form onSubmit={onSubmit} style={{ display: "grid", gap: 12, marginTop: 12 }}>
        <label>
          Email
          <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} style={{ width: "100%" }} />
        </label>
        <label>
          Password (min 8 chars)
          <input type="password" required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} style={{ width: "100%" }} />
        </label>
        {err && <pre style={{ whiteSpace: "pre-wrap" }}>{err}</pre>}
        <button type="submit" disabled={busy}>{busy ? "Creating..." : "Create account"}</button>
      </form>
      <p style={{ marginTop: 12 }}>
        Already have an account? <a href="/login">Log in</a>
      </p>
    </main>
  );
}
