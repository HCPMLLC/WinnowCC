# PROMPT23_Mobile_App_Expo.md

Read SPEC.md, ARCHITECTURE.md, and CLAUDE.md before making changes.

## Purpose

Build the Winnow mobile app for iOS and Android using React Native + Expo. Per SPEC §10: "Mobile (Expo) — Auth, Matches list + job detail, Trigger tailored resume generation, View/download links (or email to self), Basic profile preferences edit (full editing can remain web-only in v1)." Per SPEC §14: "Month 5 — Mobile app (Expo) core flows + alerts." The mobile app shares the existing FastAPI backend — no backend changes are needed except a small auth adaptation for token-based (non-cookie) mobile auth.

---

## Triggers — When to Use This Prompt

- Building the React Native / Expo mobile app.
- Adding mobile screens (auth, matches, job detail, profile).
- Setting up push notifications for mobile.
- Preparing for iOS App Store or Google Play submission.

---

## What Already Exists (DO NOT recreate)

1. **All backend endpoints** — the mobile app calls the same API as the web app. Nothing new needs to be built on the backend except a minor auth change (Part 2).
2. **Auth endpoints:** `POST /api/auth/signup`, `POST /api/auth/login`, `POST /api/auth/logout`, `GET /api/auth/me`.
3. **Profile endpoints:** `GET /api/profile`, `PUT /api/profile`, `GET /api/profile/completeness`.
4. **Matches endpoints:** `GET /api/matches`, `GET /api/matches/{match_id}`.
5. **Tailor endpoints:** `POST /api/tailor/{job_id}`, `GET /api/tailored/{tailored_id}`.
6. **Dashboard:** `GET /api/dashboard/metrics`.
7. **Billing:** `GET /api/billing/status`.
8. **Tracking:** `PATCH /api/matches/{match_id}/status` (application status updates).
9. **Brand colors:** hunter green `#1B3025`, gold `#E8C84A`, teal `#B8E4EA`.
10. **Monorepo structure:** `apps/web/` is the web app. The mobile app goes in `apps/mobile/`.

---

## Architecture Decision: Mobile Auth

The web app uses HttpOnly cookies (`rm_session`) for auth. Mobile apps cannot use HttpOnly cookies reliably across iOS/Android WebViews and native fetch. The mobile app will use **Bearer token auth** instead:

- On login, the API already returns a JWT. The mobile app stores this token securely using `expo-secure-store`.
- The mobile app sends the JWT as an `Authorization: Bearer <token>` header on every API request.
- The backend's `get_current_user` dependency needs a small modification to accept BOTH cookie-based auth AND Bearer token auth (Part 2).

---

# PART 1 — EXPO PROJECT SCAFFOLD

### 1.1 Create the Expo project

Run these commands from the **repo root**:

```powershell
cd apps
npx create-expo-app mobile --template blank-typescript
cd mobile
```

This creates `apps/mobile/` with a blank TypeScript Expo project.

### 1.2 Install core dependencies

```powershell
cd apps/mobile

# Navigation
npx expo install expo-router expo-linking expo-constants expo-status-bar react-native-screens react-native-safe-area-context

# Secure token storage
npx expo install expo-secure-store

# File sharing (for tailored resume download/share)
npx expo install expo-file-system expo-sharing expo-document-picker

# Push notifications
npx expo install expo-notifications expo-device

# Icons
npx expo install @expo/vector-icons

# Pull-to-refresh, lists, etc. (built into React Native)
# No additional install needed
```

### 1.3 Configure app.json

**File to modify:** `apps/mobile/app.json`

Replace the contents with:

```json
{
  "expo": {
    "name": "Winnow",
    "slug": "winnow",
    "version": "1.0.0",
    "orientation": "portrait",
    "icon": "./assets/icon.png",
    "scheme": "winnow",
    "userInterfaceStyle": "light",
    "splash": {
      "image": "./assets/splash.png",
      "resizeMode": "contain",
      "backgroundColor": "#1B3025"
    },
    "assetBundlePatterns": ["**/*"],
    "ios": {
      "supportsTablet": true,
      "bundleIdentifier": "com.winnow.app",
      "infoPlist": {
        "NSAppTransportSecurity": {
          "NSAllowsArbitraryLoads": true
        }
      }
    },
    "android": {
      "adaptiveIcon": {
        "foregroundImage": "./assets/adaptive-icon.png",
        "backgroundColor": "#1B3025"
      },
      "package": "com.winnow.app"
    },
    "plugins": [
      "expo-router",
      "expo-secure-store",
      [
        "expo-notifications",
        {
          "icon": "./assets/notification-icon.png",
          "color": "#1B3025"
        }
      ]
    ],
    "extra": {
      "eas": {
        "projectId": "YOUR_EAS_PROJECT_ID"
      }
    }
  }
}
```

### 1.4 Create environment config

**File to create:** `apps/mobile/.env` (NEW)

```env
EXPO_PUBLIC_API_BASE_URL=http://192.168.1.100:8000
```

**IMPORTANT:** Use your computer's local network IP (not `localhost`) so the phone/emulator can reach the API. Find it with `ipconfig` on Windows.

**File to create:** `apps/mobile/.env.example` (NEW)

```env
EXPO_PUBLIC_API_BASE_URL=http://YOUR_LOCAL_IP:8000
```

### 1.5 Create the directory structure

Create these directories inside `apps/mobile/`:

```
apps/mobile/
├── app/                    # Expo Router file-based routing
│   ├── (auth)/             # Auth screens (no tab bar)
│   │   ├── login.tsx
│   │   └── signup.tsx
│   ├── (tabs)/             # Main app screens (with tab bar)
│   │   ├── _layout.tsx     # Tab bar layout
│   │   ├── matches.tsx     # Matches list
│   │   ├── dashboard.tsx   # Dashboard / home
│   │   └── profile.tsx     # Profile preferences
│   ├── match/
│   │   └── [id].tsx        # Job detail screen
│   ├── _layout.tsx         # Root layout
│   └── index.tsx           # Entry point (redirects based on auth)
├── components/             # Shared components
│   ├── MatchCard.tsx
│   ├── ScoreBadge.tsx
│   ├── SkillTag.tsx
│   └── LoadingSpinner.tsx
├── lib/                    # Utilities
│   ├── api.ts              # API client with auth headers
│   ├── auth.ts             # Auth context + secure store
│   └── theme.ts            # Colors, fonts, spacing
├── assets/                 # Icons, splash, etc.
│   ├── icon.png
│   ├── splash.png
│   ├── adaptive-icon.png
│   └── notification-icon.png
└── .env
```

---

# PART 2 — BACKEND: SUPPORT BEARER TOKEN AUTH

The only backend change needed. Modify `get_current_user` to accept either a cookie OR a Bearer token.

**File to modify:** `services/api/app/services/auth.py`

Find the existing `get_current_user` function. Update it to check for a Bearer token first, then fall back to the cookie:

```python
from fastapi import Request, HTTPException, Depends


async def get_current_user(request: Request, db: Session = Depends(get_db)):
    """
    Extract the current user from either:
    1. Authorization: Bearer <token> header (mobile app)
    2. HttpOnly cookie (web app)
    
    Returns the User object or raises 401.
    """
    token = None
    
    # 1. Check Authorization header first (mobile)
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]  # Strip "Bearer " prefix
    
    # 2. Fall back to cookie (web)
    if not token:
        cookie_name = os.environ.get("AUTH_COOKIE_NAME", "rm_session")
        token = request.cookies.get(cookie_name)
    
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        payload = decode_jwt(token)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    user_id = payload.get("sub") or payload.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    
    return user
```

Also modify the **login endpoint** to return the JWT in the response body (in addition to setting the cookie) so the mobile app can capture it:

**File to modify:** `services/api/app/routers/auth.py`

In the `login` handler, add the token to the JSON response:

```python
@router.post("/login")
async def login(body: AuthRequest, db: Session = Depends(get_db)):
    # ... existing validation ...
    
    token = create_jwt(user.id, user.email)
    
    response = JSONResponse(content={
        "user_id": user.id,
        "email": user.email,
        "onboarding_complete": user.onboarding_completed_at is not None,
        "token": token,  # ADD THIS LINE — mobile app captures this
    })
    
    set_auth_cookie(response, token)  # Still set cookie for web
    return response
```

Do the same for the `signup` handler — include `"token": token` in the response body.

Add `CORS` origin for the mobile dev server if needed:

**File to modify:** `services/api/app/main.py`

In the `ALLOWED_ORIGINS` list, add:

```python
ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8081",       # Expo dev server
    "http://localhost:19006",      # Expo web
    # ... existing origins
]
```

---

# PART 3 — API CLIENT + AUTH CONTEXT

### 3.1 Theme constants

**File to create:** `apps/mobile/lib/theme.ts` (NEW)

```typescript
export const colors = {
  primary: '#1B3025',       // Hunter green
  primaryLight: '#2D4A3A',
  gold: '#E8C84A',
  teal: '#B8E4EA',
  tealDark: '#7CBFC8',
  white: '#FFFFFF',
  gray50: '#F9FAFB',
  gray100: '#F3F4F6',
  gray200: '#E5E7EB',
  gray300: '#D1D5DB',
  gray400: '#9CA3AF',
  gray500: '#6B7280',
  gray600: '#4B5563',
  gray700: '#374151',
  gray800: '#1F2937',
  gray900: '#111827',
  red500: '#EF4444',
  green500: '#22C55E',
  blue500: '#3B82F6',
  amber500: '#F59E0B',
};

export const spacing = {
  xs: 4,
  sm: 8,
  md: 16,
  lg: 24,
  xl: 32,
  xxl: 48,
};

export const fontSize = {
  xs: 12,
  sm: 14,
  md: 16,
  lg: 18,
  xl: 20,
  xxl: 24,
  xxxl: 32,
};

export const borderRadius = {
  sm: 6,
  md: 10,
  lg: 16,
  full: 9999,
};
```

### 3.2 Auth context with secure storage

**File to create:** `apps/mobile/lib/auth.ts` (NEW)

```typescript
import { createContext, useContext } from 'react';
import * as SecureStore from 'expo-secure-store';

const TOKEN_KEY = 'winnow_auth_token';

export interface AuthState {
  token: string | null;
  userId: number | null;
  email: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
}

export interface AuthContextType extends AuthState {
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextType | null>(null);

export function useAuth(): AuthContextType {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}

// Secure token storage helpers
export async function saveToken(token: string): Promise<void> {
  await SecureStore.setItemAsync(TOKEN_KEY, token);
}

export async function getToken(): Promise<string | null> {
  return await SecureStore.getItemAsync(TOKEN_KEY);
}

export async function removeToken(): Promise<void> {
  await SecureStore.deleteItemAsync(TOKEN_KEY);
}
```

### 3.3 API client with Bearer auth

**File to create:** `apps/mobile/lib/api.ts` (NEW)

```typescript
import { getToken } from './auth';

const API_BASE = process.env.EXPO_PUBLIC_API_BASE_URL || 'http://localhost:8000';

interface RequestOptions extends Omit<RequestInit, 'headers'> {
  headers?: Record<string, string>;
}

/**
 * Make an authenticated API request.
 * Automatically adds the Bearer token from secure storage.
 */
export async function apiFetch(
  path: string,
  options: RequestOptions = {},
): Promise<Response> {
  const token = await getToken();

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...options.headers,
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const url = `${API_BASE}${path}`;

  const response = await fetch(url, {
    ...options,
    headers,
  });

  // If unauthorized, token may be expired
  if (response.status === 401) {
    // The auth context will handle logout
    throw new AuthError('Session expired. Please log in again.');
  }

  return response;
}

export class AuthError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'AuthError';
  }
}

/**
 * Convenience helpers for common HTTP methods.
 */
export const api = {
  get: (path: string) => apiFetch(path, { method: 'GET' }),

  post: (path: string, body?: unknown) =>
    apiFetch(path, {
      method: 'POST',
      body: body ? JSON.stringify(body) : undefined,
    }),

  put: (path: string, body: unknown) =>
    apiFetch(path, {
      method: 'PUT',
      body: JSON.stringify(body),
    }),

  patch: (path: string, body: unknown) =>
    apiFetch(path, {
      method: 'PATCH',
      body: JSON.stringify(body),
    }),

  delete: (path: string) => apiFetch(path, { method: 'DELETE' }),
};
```

---

# PART 4 — ROOT LAYOUT + AUTH PROVIDER

### 4.1 Root layout with AuthProvider

**File to create:** `apps/mobile/app/_layout.tsx` (NEW)

```tsx
import { useEffect, useState, useCallback } from 'react';
import { Stack, useRouter, useSegments } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { View, ActivityIndicator } from 'react-native';
import {
  AuthContext,
  AuthState,
  saveToken,
  getToken,
  removeToken,
} from '../lib/auth';
import { colors } from '../lib/theme';

const API_BASE = process.env.EXPO_PUBLIC_API_BASE_URL || 'http://localhost:8000';

export default function RootLayout() {
  const [authState, setAuthState] = useState<AuthState>({
    token: null,
    userId: null,
    email: null,
    isAuthenticated: false,
    isLoading: true,
  });

  const router = useRouter();
  const segments = useSegments();

  // Check for stored token on app launch
  useEffect(() => {
    (async () => {
      const token = await getToken();
      if (token) {
        // Validate token with /api/auth/me
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
              isAuthenticated: true,
              isLoading: false,
            });
            return;
          }
        } catch {}
        // Token invalid — clear it
        await removeToken();
      }
      setAuthState((s) => ({ ...s, isLoading: false }));
    })();
  }, []);

  // Redirect based on auth state
  useEffect(() => {
    if (authState.isLoading) return;

    const inAuthGroup = segments[0] === '(auth)';

    if (!authState.isAuthenticated && !inAuthGroup) {
      router.replace('/(auth)/login');
    } else if (authState.isAuthenticated && inAuthGroup) {
      router.replace('/(tabs)/dashboard');
    }
  }, [authState.isAuthenticated, authState.isLoading, segments]);

  const login = useCallback(async (email: string, password: string) => {
    const res = await fetch(`${API_BASE}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Login failed');
    }

    const data = await res.json();
    await saveToken(data.token);
    setAuthState({
      token: data.token,
      userId: data.user_id,
      email: data.email,
      isAuthenticated: true,
      isLoading: false,
    });
  }, []);

  const signup = useCallback(async (email: string, password: string) => {
    const res = await fetch(`${API_BASE}/api/auth/signup`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });

    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || 'Signup failed');
    }

    const data = await res.json();
    await saveToken(data.token);
    setAuthState({
      token: data.token,
      userId: data.user_id,
      email: data.email,
      isAuthenticated: true,
      isLoading: false,
    });
  }, []);

  const logout = useCallback(async () => {
    try {
      const token = await getToken();
      await fetch(`${API_BASE}/api/auth/logout`, {
        method: 'POST',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
    } catch {}
    await removeToken();
    setAuthState({
      token: null,
      userId: null,
      email: null,
      isAuthenticated: false,
      isLoading: false,
    });
  }, []);

  if (authState.isLoading) {
    return (
      <View style={{ flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: colors.primary }}>
        <ActivityIndicator size="large" color={colors.gold} />
      </View>
    );
  }

  return (
    <AuthContext.Provider value={{ ...authState, login, signup, logout }}>
      <StatusBar style="light" />
      <Stack
        screenOptions={{
          headerStyle: { backgroundColor: colors.primary },
          headerTintColor: colors.white,
          headerTitleStyle: { fontWeight: '600' },
          contentStyle: { backgroundColor: colors.gray50 },
        }}
      >
        <Stack.Screen name="(auth)" options={{ headerShown: false }} />
        <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
        <Stack.Screen
          name="match/[id]"
          options={{ title: 'Job Details', presentation: 'card' }}
        />
      </Stack>
    </AuthContext.Provider>
  );
}
```

### 4.2 Entry point (redirect)

**File to create:** `apps/mobile/app/index.tsx` (NEW)

```tsx
import { Redirect } from 'expo-router';
import { useAuth } from '../lib/auth';

export default function Index() {
  const { isAuthenticated } = useAuth();
  return <Redirect href={isAuthenticated ? '/(tabs)/dashboard' : '/(auth)/login'} />;
}
```

---

# PART 5 — AUTH SCREENS

### 5.1 Login screen

**File to create:** `apps/mobile/app/(auth)/login.tsx` (NEW)

```tsx
import { useState } from 'react';
import {
  View, Text, TextInput, TouchableOpacity,
  StyleSheet, KeyboardAvoidingView, Platform, Alert,
} from 'react-native';
import { Link } from 'expo-router';
import { useAuth } from '../../lib/auth';
import { colors, spacing, fontSize, borderRadius } from '../../lib/theme';

export default function LoginScreen() {
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);

  const handleLogin = async () => {
    if (!email.trim() || !password) return;
    setLoading(true);
    try {
      await login(email.trim().toLowerCase(), password);
    } catch (err: any) {
      Alert.alert('Login Failed', err.message || 'Please check your credentials.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <KeyboardAvoidingView
      style={styles.container}
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
    >
      <View style={styles.inner}>
        <Text style={styles.logo}>🌿 Winnow</Text>
        <Text style={styles.subtitle}>Your job search, sharpened.</Text>

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

        <TouchableOpacity
          style={[styles.button, loading && styles.buttonDisabled]}
          onPress={handleLogin}
          disabled={loading}
        >
          <Text style={styles.buttonText}>
            {loading ? 'Signing in...' : 'Sign In'}
          </Text>
        </TouchableOpacity>

        <View style={styles.footer}>
          <Text style={styles.footerText}>Don't have an account? </Text>
          <Link href="/(auth)/signup" asChild>
            <TouchableOpacity>
              <Text style={styles.link}>Sign Up</Text>
            </TouchableOpacity>
          </Link>
        </View>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.primary },
  inner: { flex: 1, justifyContent: 'center', paddingHorizontal: spacing.xl },
  logo: { fontSize: fontSize.xxxl, fontWeight: '700', color: colors.gold, textAlign: 'center', marginBottom: spacing.xs },
  subtitle: { fontSize: fontSize.md, color: colors.teal, textAlign: 'center', marginBottom: spacing.xxl },
  input: {
    backgroundColor: colors.white, borderRadius: borderRadius.md,
    paddingHorizontal: spacing.md, paddingVertical: spacing.md,
    fontSize: fontSize.md, color: colors.gray900, marginBottom: spacing.md,
  },
  button: {
    backgroundColor: colors.gold, borderRadius: borderRadius.md,
    paddingVertical: spacing.md, alignItems: 'center', marginTop: spacing.sm,
  },
  buttonDisabled: { opacity: 0.6 },
  buttonText: { fontSize: fontSize.lg, fontWeight: '600', color: colors.primary },
  footer: { flexDirection: 'row', justifyContent: 'center', marginTop: spacing.lg },
  footerText: { color: colors.gray300, fontSize: fontSize.sm },
  link: { color: colors.gold, fontSize: fontSize.sm, fontWeight: '600' },
});
```

### 5.2 Signup screen

**File to create:** `apps/mobile/app/(auth)/signup.tsx` (NEW)

Same structure as login but calls `signup` instead of `login`. Include password confirmation field. (Follow the pattern from login.tsx — change button text to "Create Account", add a confirm password field, swap the footer link to point to login.)

---

# PART 6 — TAB BAR LAYOUT

**File to create:** `apps/mobile/app/(tabs)/_layout.tsx` (NEW)

```tsx
import { Tabs } from 'expo-router';
import { Ionicons } from '@expo/vector-icons';
import { colors } from '../../lib/theme';

export default function TabLayout() {
  return (
    <Tabs
      screenOptions={{
        tabBarActiveTintColor: colors.gold,
        tabBarInactiveTintColor: colors.gray400,
        tabBarStyle: {
          backgroundColor: colors.primary,
          borderTopColor: colors.primaryLight,
        },
        headerStyle: { backgroundColor: colors.primary },
        headerTintColor: colors.white,
        headerTitleStyle: { fontWeight: '600' },
      }}
    >
      <Tabs.Screen
        name="dashboard"
        options={{
          title: 'Dashboard',
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="grid-outline" size={size} color={color} />
          ),
        }}
      />
      <Tabs.Screen
        name="matches"
        options={{
          title: 'Matches',
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="briefcase-outline" size={size} color={color} />
          ),
        }}
      />
      <Tabs.Screen
        name="profile"
        options={{
          title: 'Profile',
          tabBarIcon: ({ color, size }) => (
            <Ionicons name="person-outline" size={size} color={color} />
          ),
        }}
      />
    </Tabs>
  );
}
```

---

# PART 7 — CORE SCREENS

### 7.1 Dashboard screen

**File to create:** `apps/mobile/app/(tabs)/dashboard.tsx` (NEW)

Fetches `GET /api/dashboard/metrics` and `GET /api/billing/status`. Shows:

- Welcome header with user's email
- 4 metric cards in a 2×2 grid: Profile Completeness, Qualified Jobs, Applications, Interviews
- Plan badge (Free / Pro)
- "View Matches" CTA button

### 7.2 Matches list screen

**File to create:** `apps/mobile/app/(tabs)/matches.tsx` (NEW)

Fetches `GET /api/matches`. Shows:

- Pull-to-refresh FlatList
- Each match card (component: `MatchCard.tsx`) shows:
  - Job title (bold)
  - Company name
  - Location + remote badge
  - Match Score as a colored badge (green ≥70, amber 50–69, red <50)
  - Interview Readiness Score
  - Top 2–3 matched skills as tags
  - Application status indicator (if set)
- Tapping a card navigates to `match/[id]`
- Empty state: "No matches yet. Upload your resume on the web app to get started."

### 7.3 Job detail screen

**File to create:** `apps/mobile/app/match/[id].tsx` (NEW)

Fetches `GET /api/matches/{id}`. Shows:

- Job title, company, location, salary range (if available)
- Match Score + Interview Readiness Score (large, with progress circles)
- **Reasons section:** Matched skills list with green checkmarks
- **Gaps section:** Missing skills with amber warning icons
- **Application status picker** (saved / applied / interviewing / rejected / offer)
- **"Generate ATS Resume" button:**
  - Calls `POST /api/tailor/{job_id}`
  - Shows a loading/progress state
  - On completion, shows a "Download" or "Share" button
  - Download uses `expo-file-system` + `expo-sharing` to save/share the DOCX
- **"View Job Posting" link** — opens the job URL in the in-app browser

### 7.4 Profile preferences screen

**File to create:** `apps/mobile/app/(tabs)/profile.tsx` (NEW)

Fetches `GET /api/profile`. Shows (editable):

- Desired job titles (text input, comma-separated or tag-style)
- Desired locations (text input)
- Remote preference (picker: Remote Only / Hybrid / On-site / Any)
- Desired salary range (min/max number inputs)
- Job type (picker: Full-time / Part-time / Contract / Any)
- "Save Preferences" button → calls `PUT /api/profile`
- "Log Out" button at the bottom → calls `logout()` from auth context

Full profile editing (experience, education, skills) stays web-only for v1 — show a notice: "For full profile editing, visit winnow.app on your computer."

---

# PART 8 — SHARED COMPONENTS

### 8.1 MatchCard component

**File to create:** `apps/mobile/components/MatchCard.tsx` (NEW)

```tsx
import { View, Text, TouchableOpacity, StyleSheet } from 'react-native';
import { useRouter } from 'expo-router';
import { colors, spacing, fontSize, borderRadius } from '../lib/theme';
import ScoreBadge from './ScoreBadge';
import SkillTag from './SkillTag';

interface MatchCardProps {
  match: {
    id: number;
    job_title: string;
    company: string;
    location: string;
    remote_flag: boolean;
    match_score: number;
    interview_readiness_score: number;
    reasons?: { matched_skills?: string[] };
    application_status?: string;
  };
}

export default function MatchCard({ match }: MatchCardProps) {
  const router = useRouter();
  const skills = match.reasons?.matched_skills?.slice(0, 3) || [];

  return (
    <TouchableOpacity
      style={styles.card}
      onPress={() => router.push(`/match/${match.id}`)}
      activeOpacity={0.7}
    >
      <View style={styles.header}>
        <View style={{ flex: 1 }}>
          <Text style={styles.title} numberOfLines={2}>{match.job_title}</Text>
          <Text style={styles.company}>{match.company}</Text>
          <Text style={styles.location}>
            {match.location}
            {match.remote_flag && '  🏠 Remote'}
          </Text>
        </View>
        <ScoreBadge score={match.match_score} label="Match" />
      </View>

      {skills.length > 0 && (
        <View style={styles.skills}>
          {skills.map((s) => <SkillTag key={s} name={s} />)}
        </View>
      )}

      {match.application_status && (
        <View style={styles.statusRow}>
          <Text style={styles.statusText}>
            Status: {match.application_status}
          </Text>
        </View>
      )}
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: colors.white,
    borderRadius: borderRadius.lg,
    padding: spacing.md,
    marginBottom: spacing.md,
    shadowColor: '#000', shadowOpacity: 0.05, shadowRadius: 8,
    elevation: 2,
  },
  header: { flexDirection: 'row', justifyContent: 'space-between' },
  title: { fontSize: fontSize.lg, fontWeight: '600', color: colors.gray900 },
  company: { fontSize: fontSize.sm, color: colors.gray600, marginTop: 2 },
  location: { fontSize: fontSize.xs, color: colors.gray400, marginTop: 2 },
  skills: { flexDirection: 'row', flexWrap: 'wrap', marginTop: spacing.sm, gap: spacing.xs },
  statusRow: { marginTop: spacing.sm, paddingTop: spacing.sm, borderTopWidth: 1, borderTopColor: colors.gray100 },
  statusText: { fontSize: fontSize.xs, color: colors.gray500, textTransform: 'capitalize' },
});
```

### 8.2 ScoreBadge component

**File to create:** `apps/mobile/components/ScoreBadge.tsx` (NEW)

Displays a circular score badge with color based on value (green ≥70, amber 50–69, red <50).

### 8.3 SkillTag component

**File to create:** `apps/mobile/components/SkillTag.tsx` (NEW)

Small rounded chip showing a skill name with teal background.

### 8.4 LoadingSpinner component

**File to create:** `apps/mobile/components/LoadingSpinner.tsx` (NEW)

Centered ActivityIndicator with the brand gold color.

---

# PART 9 — TAILORED RESUME DOWNLOAD + SHARE

On the job detail screen, after generating a tailored resume, the user can download or share the DOCX file.

```typescript
import * as FileSystem from 'expo-file-system';
import * as Sharing from 'expo-sharing';
import { getToken } from '../lib/auth';

const API_BASE = process.env.EXPO_PUBLIC_API_BASE_URL || 'http://localhost:8000';

async function downloadAndShareResume(tailoredId: number) {
  const token = await getToken();
  
  // Download the DOCX file to the device's cache
  const fileUri = FileSystem.cacheDirectory + `tailored_resume_${tailoredId}.docx`;
  
  const download = await FileSystem.downloadAsync(
    `${API_BASE}/api/tailored/${tailoredId}/download`,
    fileUri,
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    },
  );
  
  if (download.status !== 200) {
    throw new Error('Download failed');
  }
  
  // Share the file (opens iOS share sheet / Android share dialog)
  if (await Sharing.isAvailableAsync()) {
    await Sharing.shareAsync(download.uri, {
      mimeType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      dialogTitle: 'Share Tailored Resume',
    });
  }
}
```

**Note:** If `GET /api/tailored/{id}/download` doesn't exist yet, create it in the tailor router to return the DOCX file as a `StreamingResponse`. Alternatively, the existing `docx_url` field can be used if it's a public URL.

---

# PART 10 — PUSH NOTIFICATIONS (Optional v1)

### 10.1 Register for push notifications

**File to create:** `apps/mobile/lib/notifications.ts` (NEW)

```typescript
import * as Notifications from 'expo-notifications';
import * as Device from 'expo-device';
import { Platform } from 'react-native';
import { api } from './api';

// Configure notification behavior
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge: true,
  }),
});

/**
 * Register for push notifications and send the token to the backend.
 */
export async function registerForPushNotifications(): Promise<string | null> {
  if (!Device.isDevice) {
    console.log('Push notifications require a physical device');
    return null;
  }

  const { status: existing } = await Notifications.getPermissionsAsync();
  let finalStatus = existing;

  if (existing !== 'granted') {
    const { status } = await Notifications.requestPermissionsAsync();
    finalStatus = status;
  }

  if (finalStatus !== 'granted') {
    return null;
  }

  // Get the Expo push token
  const tokenData = await Notifications.getExpoPushTokenAsync();
  const pushToken = tokenData.data;

  // Send to backend (you'd need to create this endpoint)
  try {
    await api.post('/api/profile/push-token', { push_token: pushToken });
  } catch (err) {
    console.warn('Failed to register push token:', err);
  }

  // Android requires a notification channel
  if (Platform.OS === 'android') {
    Notifications.setNotificationChannelAsync('default', {
      name: 'Default',
      importance: Notifications.AndroidImportance.MAX,
    });
  }

  return pushToken;
}
```

**Backend endpoint (if implementing push):** Create `POST /api/profile/push-token` that stores the Expo push token on the user's profile. Then use the Expo Push API (`https://exp.host/--/api/v2/push/send`) from a worker job to send notifications for new high-match jobs.

---

# PART 11 — TESTING ON DEVICE

### 11.1 Start the development server

```powershell
cd apps/mobile
npx expo start
```

### 11.2 Test on your phone

1. Install **Expo Go** from the App Store (iOS) or Google Play (Android).
2. Scan the QR code shown in the terminal.
3. The app loads on your phone connected to your local API.

### 11.3 Test on emulator

**iOS (Mac only):**
```powershell
npx expo start --ios
```

**Android:**
```powershell
npx expo start --android
```

### 11.4 Important: API URL for physical devices

When testing on a physical phone, `localhost` doesn't work. Use your computer's local IP address:

```powershell
# Find your IP on Windows:
ipconfig
# Look for "IPv4 Address" under your Wi-Fi adapter, e.g., 192.168.1.100
```

Set `EXPO_PUBLIC_API_BASE_URL=http://192.168.1.100:8000` in `apps/mobile/.env`.

---

# PART 12 — APP STORE SUBMISSION (EAS Build)

### 12.1 Install EAS CLI

```powershell
npm install -g eas-cli
eas login
```

### 12.2 Configure EAS Build

**File to create:** `apps/mobile/eas.json` (NEW)

```json
{
  "cli": {
    "version": ">= 12.0.0"
  },
  "build": {
    "development": {
      "developmentClient": true,
      "distribution": "internal"
    },
    "preview": {
      "distribution": "internal",
      "env": {
        "EXPO_PUBLIC_API_BASE_URL": "https://winnow-api-xxxxx-uc.a.run.app"
      }
    },
    "production": {
      "env": {
        "EXPO_PUBLIC_API_BASE_URL": "https://api.winnow.app"
      }
    }
  },
  "submit": {
    "production": {
      "ios": {
        "appleId": "your@email.com",
        "ascAppId": "YOUR_APP_STORE_CONNECT_APP_ID",
        "appleTeamId": "YOUR_TEAM_ID"
      },
      "android": {
        "serviceAccountKeyPath": "./google-play-key.json"
      }
    }
  }
}
```

### 12.3 Build for stores

```powershell
# iOS build
eas build --platform ios --profile production

# Android build
eas build --platform android --profile production
```

### 12.4 Submit to stores

```powershell
# iOS — submit to App Store Connect
eas submit --platform ios --profile production

# Android — submit to Google Play Console
eas submit --platform android --profile production
```

### 12.5 App Store requirements checklist

Before submitting:

- [ ] App icon (1024×1024 PNG) at `apps/mobile/assets/icon.png`
- [ ] Splash screen at `apps/mobile/assets/splash.png`
- [ ] Adaptive icon (Android) at `apps/mobile/assets/adaptive-icon.png`
- [ ] Privacy policy URL (required for both stores)
- [ ] App Store screenshots (6.7" and 5.5" for iOS; phone and tablet for Android)
- [ ] App description and keywords
- [ ] Bundle IDs registered: `com.winnow.app` (iOS + Android)
- [ ] API base URL points to production (not localhost)

---

## File and Component Reference

| What | Where | Action |
|------|-------|--------|
| Expo project scaffold | `apps/mobile/` | CREATE (via `create-expo-app`) |
| App config | `apps/mobile/app.json` | CREATE |
| EAS build config | `apps/mobile/eas.json` | CREATE |
| Environment vars | `apps/mobile/.env`, `.env.example` | CREATE |
| Theme constants | `apps/mobile/lib/theme.ts` | CREATE |
| Auth context + secure store | `apps/mobile/lib/auth.ts` | CREATE |
| API client | `apps/mobile/lib/api.ts` | CREATE |
| Push notifications | `apps/mobile/lib/notifications.ts` | CREATE |
| Root layout | `apps/mobile/app/_layout.tsx` | CREATE |
| Entry redirect | `apps/mobile/app/index.tsx` | CREATE |
| Login screen | `apps/mobile/app/(auth)/login.tsx` | CREATE |
| Signup screen | `apps/mobile/app/(auth)/signup.tsx` | CREATE |
| Tab layout | `apps/mobile/app/(tabs)/_layout.tsx` | CREATE |
| Dashboard screen | `apps/mobile/app/(tabs)/dashboard.tsx` | CREATE |
| Matches list screen | `apps/mobile/app/(tabs)/matches.tsx` | CREATE |
| Profile screen | `apps/mobile/app/(tabs)/profile.tsx` | CREATE |
| Job detail screen | `apps/mobile/app/match/[id].tsx` | CREATE |
| MatchCard component | `apps/mobile/components/MatchCard.tsx` | CREATE |
| ScoreBadge component | `apps/mobile/components/ScoreBadge.tsx` | CREATE |
| SkillTag component | `apps/mobile/components/SkillTag.tsx` | CREATE |
| LoadingSpinner component | `apps/mobile/components/LoadingSpinner.tsx` | CREATE |
| Backend auth (Bearer support) | `services/api/app/services/auth.py` | MODIFY |
| Backend login (return token) | `services/api/app/routers/auth.py` | MODIFY |
| Backend CORS (Expo origins) | `services/api/app/main.py` | MODIFY |

---

## Implementation Order (for a beginner following in Cursor)

### Phase 1: Backend Auth Change (Steps 1–3)

1. **Step 1:** Open `services/api/app/services/auth.py`. Update `get_current_user` to accept Bearer tokens (Part 2).
2. **Step 2:** Open `services/api/app/routers/auth.py`. Add `"token": token` to the login and signup response bodies (Part 2).
3. **Step 3:** Open `services/api/app/main.py`. Add Expo dev server origins to `ALLOWED_ORIGINS` (Part 2).

### Phase 2: Expo Project (Steps 4–6)

4. **Step 4:** Create the Expo project:
   ```powershell
   cd apps
   npx create-expo-app mobile --template blank-typescript
   cd mobile
   ```
5. **Step 5:** Install dependencies (Part 1.2 — run all the `npx expo install` commands).
6. **Step 6:** Replace `app.json` contents (Part 1.3). Create `.env` with your local IP (Part 1.4).

### Phase 3: Core Library Files (Steps 7–9)

7. **Step 7:** Create `apps/mobile/lib/theme.ts` (Part 3.1).
8. **Step 8:** Create `apps/mobile/lib/auth.ts` (Part 3.2).
9. **Step 9:** Create `apps/mobile/lib/api.ts` (Part 3.3).

### Phase 4: App Shell (Steps 10–12)

10. **Step 10:** Create `apps/mobile/app/_layout.tsx` (Part 4.1).
11. **Step 11:** Create `apps/mobile/app/index.tsx` (Part 4.2).
12. **Step 12:** Create `apps/mobile/app/(tabs)/_layout.tsx` (Part 6).

### Phase 5: Auth Screens (Steps 13–14)

13. **Step 13:** Create `apps/mobile/app/(auth)/login.tsx` (Part 5.1).
14. **Step 14:** Create `apps/mobile/app/(auth)/signup.tsx` (Part 5.2).
15. **Step 15:** Test — start the API + Expo dev server, open in Expo Go, verify login works.

### Phase 6: Main Screens (Steps 16–19)

16. **Step 16:** Create `apps/mobile/app/(tabs)/dashboard.tsx` (Part 7.1).
17. **Step 17:** Create `apps/mobile/components/MatchCard.tsx`, `ScoreBadge.tsx`, `SkillTag.tsx`, `LoadingSpinner.tsx` (Part 8).
18. **Step 18:** Create `apps/mobile/app/(tabs)/matches.tsx` (Part 7.2).
19. **Step 19:** Create `apps/mobile/app/match/[id].tsx` (Part 7.3).

### Phase 7: Profile + Polish (Steps 20–22)

20. **Step 20:** Create `apps/mobile/app/(tabs)/profile.tsx` (Part 7.4).
21. **Step 21:** Implement tailored resume download + share (Part 9).
22. **Step 22:** (Optional) Set up push notifications (Part 10).

### Phase 8: Test + Build (Steps 23–26)

23. **Step 23:** Test all screens on Expo Go (physical device preferred).
24. **Step 24:** Create placeholder app assets (icon.png 1024×1024, splash.png, adaptive-icon.png).
25. **Step 25:** Create `apps/mobile/eas.json` (Part 12.2).
26. **Step 26:** Build and submit:
    ```powershell
    eas build --platform all --profile production
    eas submit --platform all --profile production
    ```

---

## Non-Goals (Do NOT implement in this prompt)

- Resume upload from mobile (web-only for v1 — complex file picker + parsing flow)
- Full profile editor (experience, education, skills) — web-only for v1
- Sieve chatbot on mobile (future)
- Offline mode / data caching
- Biometric login (Face ID / fingerprint) — future
- Deep linking from email to specific match
- Tablet-optimized layout (phone-first for v1)
- In-app purchase (use web for Stripe billing)

---

## Summary Checklist

### Backend Changes
- [ ] `get_current_user` accepts both Bearer token and cookie
- [ ] Login response includes `"token"` field in JSON body
- [ ] Signup response includes `"token"` field in JSON body
- [ ] CORS includes Expo dev server origins

### Expo Project
- [ ] Project created at `apps/mobile/` with blank TypeScript template
- [ ] Dependencies installed: expo-router, expo-secure-store, expo-file-system, expo-sharing, expo-notifications, expo-device
- [ ] `app.json` configured with bundle IDs, splash, icons, plugins
- [ ] `.env` has `EXPO_PUBLIC_API_BASE_URL` pointing to local network IP

### Lib Files
- [ ] `theme.ts` with Winnow brand colors, spacing, font sizes
- [ ] `auth.ts` with AuthContext, SecureStore helpers, useAuth hook
- [ ] `api.ts` with apiFetch (auto-adds Bearer token), convenience methods

### Screens
- [ ] Root layout with AuthProvider, loading state, auth redirect logic
- [ ] Login screen with email/password + link to signup
- [ ] Signup screen with email/password/confirm + link to login
- [ ] Tab bar with Dashboard, Matches, Profile tabs (Winnow-branded)
- [ ] Dashboard screen with metric cards + plan badge + CTA
- [ ] Matches list with pull-to-refresh FlatList + MatchCard components
- [ ] Job detail screen with scores, reasons, gaps, status picker, "Generate ATS Resume" button
- [ ] Profile preferences screen with editable fields + Save + Logout

### Components
- [ ] MatchCard — job title, company, location, scores, skill tags, status
- [ ] ScoreBadge — colored circular badge (green/amber/red by value)
- [ ] SkillTag — small teal chip with skill name
- [ ] LoadingSpinner — centered ActivityIndicator

### Features
- [ ] Tailored resume download via expo-file-system + share via expo-sharing
- [ ] Application status picker on job detail (saved/applied/interviewing/rejected/offer)
- [ ] (Optional) Push notification registration + token sent to backend

### App Store Readiness
- [ ] `eas.json` with development/preview/production profiles
- [ ] App icon, splash, adaptive icon assets created
- [ ] Production API URL configured in eas.json production profile
- [ ] Build and submit commands documented

Return code changes only.
