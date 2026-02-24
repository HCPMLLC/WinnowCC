# PROMPT58: Convert Mobile App to "Reader App" — Web-Only Billing Model

Read CLAUDE.md, ARCHITECTURE.md, SPEC.md, SIEVE-IMPLEMENTATION.md, PROMPT23 (Mobile App), PROMPT20/PROMPT39 (Billing), and PROMPT18/PROMPT24 (Sieve) before making changes.

## Purpose

Convert the Winnow mobile app (Expo/React Native) into a **"reader app"** that contains **zero purchasing UI, zero pricing display, zero feature gates, and zero Stripe links**. All subscription management happens exclusively on the web at **WinnowCC.ai**. The mobile app silently checks the user's plan tier via the API and delivers the appropriate experience — but never tells the user *why* a feature is or isn't available, never shows upgrade prompts, and never links to Stripe checkout.

This is the Apple-compliant "reader app" model: the app is a consumption tool for content/services managed elsewhere. No in-app purchases, no links to external purchase flows.

---

## Why This Matters

Apple's App Store guidelines (Section 3.1.3) allow "reader apps" — apps where users consume content purchased elsewhere — as long as the app does not:
- Contain buttons, links, or calls-to-action that direct users to external purchasing mechanisms
- Display pricing information for subscriptions
- Show "upgrade" or "subscribe" prompts that reference paid plans
- Include feature-gating UI that implies "pay to unlock"

Violating these rules results in App Store rejection. This prompt ensures full compliance.

---

## Triggers — When to Use This Prompt

- Preparing the mobile app for iOS App Store submission
- Removing all billing/pricing/gate UI from the mobile app
- Updating Sieve's mobile behavior to redirect billing questions to the web
- Adding a backend mobile-specific API response mode
- Ensuring Apple App Store guideline compliance (Section 3.1.3)

---

## What Already Exists (DO NOT recreate — read first)

1. **Mobile app:** `apps/mobile/` — Expo React Native app with tabs (Dashboard, Matches, Profile), auth screens, job detail, Sieve chat
2. **Dashboard screen:** `apps/mobile/app/(tabs)/dashboard.tsx` — fetches `GET /api/dashboard/metrics` AND `GET /api/billing/status`, shows plan badge (Free / Pro)
3. **Matches screen:** `apps/mobile/app/(tabs)/matches.tsx` — match cards with scores
4. **Job detail screen:** `apps/mobile/app/match/[id].tsx` — scores, reasons, gaps, "Generate ATS Resume" button, application status picker
5. **Profile screen:** `apps/mobile/app/(tabs)/profile.tsx` — preferences editor, logout
6. **Sieve chat:** Available in mobile via `POST /api/sieve/chat` — the backend Sieve system prompt (in `services/api/app/services/sieve_chat.py` or `sieve.py`) has full context including billing status
7. **Billing status API:** `GET /api/billing/status` — returns `plan_tier`, `usage`, `limits`, `has_subscription`, pricing info
8. **Billing middleware:** `services/api/app/services/billing.py` — `CANDIDATE_PLAN_LIMITS`, `check_feature_access()`, `check_daily_limit()`
9. **Stripe checkout routes:** `services/api/app/routers/billing.py` — checkout session creation, customer portal redirect
10. **API client:** `apps/mobile/lib/api.ts` — shared fetch wrapper

---

## What to Change

This prompt covers **6 parts**. Implement in exact order.

---

## Part 1: Backend — Add Mobile-Aware API Response Mode

The backend should detect when requests come from the mobile app and strip billing/pricing details from responses. The mobile app should never receive data it shouldn't display.

### 1.1 Add mobile client detection

**File to modify:** `services/api/app/services/auth.py`

**What to do:**

1. Open `services/api/app/services/auth.py` in Cursor.
2. Find the `get_current_user` function.
3. After the user is resolved, add a check for the `X-Client-Platform` header:

```python
# Add to the function that resolves the current user, or create a new dependency
from fastapi import Request

def get_client_platform(request: Request) -> str:
    """Detect if request is from mobile app or web."""
    return request.headers.get("X-Client-Platform", "web")
```

4. Save the file.

### 1.2 Create a mobile-safe billing status endpoint

**File to modify:** `services/api/app/routers/billing.py`

**What to do:**

1. Open `services/api/app/routers/billing.py` in Cursor.
2. Find the `GET /api/billing/status` endpoint.
3. Modify it to check `X-Client-Platform` and return a stripped response for mobile clients:

```python
from app.services.auth import get_client_platform

@router.get("/status")
async def get_billing_status(
    request: Request,
    user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    platform = get_client_platform(request)

    # ... existing logic to build full billing status ...

    if platform == "mobile":
        # Mobile gets ONLY the tier — no pricing, no limits, no Stripe URLs
        return {
            "plan_tier": billing_data["plan_tier"],  # "free", "starter", or "pro"
            "platform": "mobile",
            # NO: prices, plan_names, upgrade_urls, stripe_customer_id,
            #     usage counts, limit numbers, checkout URLs, portal URLs
        }

    # Web gets the full response (unchanged)
    return billing_data
```

4. Save the file.

### 1.3 Strip feature-limit error details for mobile

**File to modify:** `services/api/app/services/billing.py`

**What to do:**

1. Open `services/api/app/services/billing.py` in Cursor.
2. Find the `check_feature_access()` and `check_daily_limit()` functions.
3. When these functions raise HTTP 403 errors for limit violations, currently they return messages like *"Free tier limited to 10 matches. Upgrade to Starter for 50."*
4. Modify these to detect the mobile platform and return a generic message instead:

```python
from fastapi import Request

def check_feature_access(user, feature: str, request: Request = None):
    # ... existing check logic ...
    if not allowed:
        if request and get_client_platform(request) == "mobile":
            raise HTTPException(
                status_code=403,
                detail="This feature is available on WinnowCC.ai. Please log in at winnowcc.ai for more information."
            )
        else:
            # Existing web message with pricing/upgrade info
            raise HTTPException(status_code=403, detail=existing_detailed_message)
```

5. Apply the same pattern to `check_daily_limit()` and any other billing enforcement function.
6. Save the file.

---

## Part 2: Mobile App — Add Platform Header to All API Calls

Every API call from the mobile app must identify itself so the backend can return mobile-safe responses.

**File to modify:** `apps/mobile/lib/api.ts`

**What to do:**

1. Open `apps/mobile/lib/api.ts` in Cursor.
2. Find the shared fetch wrapper function (e.g., `apiFetch`, `apiClient`, or similar).
3. Add the `X-Client-Platform: mobile` header to every request:

```typescript
// In the shared fetch wrapper, add this header to every request:
const headers = {
  'Content-Type': 'application/json',
  'X-Client-Platform': 'mobile',   // ← ADD THIS LINE
  ...(token ? { Authorization: `Bearer ${token}` } : {}),
  ...options?.headers,
};
```

4. Save the file.

---

## Part 3: Mobile App — Remove All Billing, Pricing, and Feature Gate UI

Systematically remove every trace of pricing, billing, upgrade prompts, and feature gating from the mobile app.

### 3.1 Dashboard screen — remove plan badge and billing fetch

**File to modify:** `apps/mobile/app/(tabs)/dashboard.tsx`

**What to do:**

1. Open `apps/mobile/app/(tabs)/dashboard.tsx` in Cursor.
2. **Remove** the `GET /api/billing/status` fetch call entirely. The dashboard should NOT fetch billing data.
3. **Remove** the plan badge component (the element showing "Free" / "Pro" / "Starter").
4. **Remove** any "Upgrade" button or CTA that links to billing.
5. **Keep** the `GET /api/dashboard/metrics` fetch — this shows profile completeness, qualified jobs, applications, interviews, offers. These are fine.
6. **Keep** the "View Matches" CTA button — this is navigation, not billing.
7. The dashboard should look clean: welcome header, 4 metric cards, "View Matches" button. No plan references.
8. Save the file.

### 3.2 Matches screen — remove tier-limited messaging

**File to modify:** `apps/mobile/app/(tabs)/matches.tsx`

**What to do:**

1. Open `apps/mobile/app/(tabs)/matches.tsx` in Cursor.
2. **Remove** any text like "Showing 10 of 47 matches" or "Upgrade to see all matches" or "Free tier: 10 matches visible."
3. **Remove** any conditional rendering that checks `plan_tier` to show/hide matches or show upgrade prompts.
4. The matches list should simply show whatever the API returns — if the API returns 10 matches for a free user, the app shows 10 matches with no mention of limits.
5. **Remove** any "Unlock more matches" or similar CTA.
6. Save the file.

### 3.3 Job detail screen — remove gating on "Generate ATS Resume"

**File to modify:** `apps/mobile/app/match/[id].tsx`

**What to do:**

1. Open `apps/mobile/app/match/[id].tsx` in Cursor.
2. Find the "Generate ATS Resume" button.
3. **Remove** any pre-check that disables the button based on plan tier or remaining usage count.
4. The button should always be visible and tappable. If the user taps it and the backend returns 403 (limit reached), show a **generic** alert:

```typescript
// When the API returns 403 for a tailor request:
Alert.alert(
  "Feature Available on Web",
  "To access this feature, please log in at WinnowCC.ai on your computer or mobile browser.",
  [{ text: "OK" }]
);
```

5. **Remove** any usage counters displayed on this screen (e.g., "2 of 5 tailored resumes used").
6. **Remove** any "Upgrade to Pro" button on this screen.
7. Apply the same pattern to the cover letter generation button if present.
8. Save the file.

### 3.4 Profile screen — remove billing/settings section

**File to modify:** `apps/mobile/app/(tabs)/profile.tsx`

**What to do:**

1. Open `apps/mobile/app/(tabs)/profile.tsx` in Cursor.
2. **Remove** any "Subscription" or "Billing" section showing the current plan.
3. **Remove** any "Manage Subscription" or "Upgrade Plan" button.
4. **Remove** any link to Stripe Customer Portal.
5. **Remove** any usage meters (e.g., "3/20 tailored resumes this month").
6. **Keep** the preferences editor (job titles, locations, remote preference, salary range, job type).
7. **Keep** the "Save Preferences" button.
8. **Keep** the "Log Out" button.
9. Optionally **add** a simple informational line at the bottom of the screen:

```typescript
<Text style={styles.infoText}>
  Manage your account and subscription at WinnowCC.ai
</Text>
```

Style this as small, muted text (gray, 12px) — NOT as a tappable link or button. This is informational, not a CTA.

10. Save the file.

### 3.5 Remove any standalone billing/settings screen

**Check these locations and remove or modify:**

- `apps/mobile/app/settings.tsx` — if this screen exists and shows billing, either remove the billing section or remove the entire screen if billing was its only purpose.
- `apps/mobile/app/subscription.tsx` or `apps/mobile/app/billing.tsx` — if these screens exist, **delete them entirely**.
- Tab navigator or drawer navigator — if there's a "Settings" or "Billing" tab that links to removed screens, remove it from the navigator.

**Files to check:**
- `apps/mobile/app/(tabs)/_layout.tsx` — remove any billing/settings tab
- Any navigation files that reference billing screens

---

## Part 4: Sieve Mobile Behavior — Redirect Billing Questions to Web

When Sieve is used from the mobile app, it must never discuss pricing, suggest upgrades, or provide Stripe links. Instead, it should helpfully redirect the user to the web.

### 4.1 Backend — Add mobile-specific Sieve system prompt rules

**File to modify:** `services/api/app/services/sieve_chat.py` (or `sieve.py`, whichever contains the system prompt and `handle_chat` function)

**What to do:**

1. Open the Sieve service file in Cursor.
2. Find where the system prompt is constructed (the string that begins with something like `"You are Sieve, Winnow's personal career concierge..."` or similar).
3. The system prompt currently has access to billing context. Modify the function to detect the platform and append mobile-specific rules:

```python
async def handle_chat(user_id, message, conversation_history, db, platform="web"):
    # ... existing context loading ...

    # Build the system prompt
    system_prompt = BASE_SIEVE_SYSTEM_PROMPT  # existing prompt

    if platform == "mobile":
        system_prompt += """

CRITICAL MOBILE APP RULES (you are running inside the iOS/Android app):
- NEVER mention pricing, dollar amounts, subscription tiers, plan names (Free/Starter/Pro), or costs.
- NEVER suggest upgrading, subscribing, or purchasing anything.
- NEVER provide links to Stripe, checkout pages, or billing portals.
- NEVER mention feature limits, usage quotas, or gating (e.g., "you've used 3 of 5").
- NEVER say "this feature requires Pro" or "upgrade to unlock" or similar.
- If the user asks about pricing, plans, upgrades, billing, subscription, payments, or feature limits, respond ONLY with:
  "For information about plans and account management, please visit WinnowCC.ai on your computer or mobile browser. You can log in there to manage your account."
- If a user asks why a feature didn't work or seems limited, say:
  "For the best experience with all features, please visit WinnowCC.ai. You can manage your full account there."
- Do NOT say "I can't discuss pricing" — just naturally redirect to the web.
- Continue to provide full career guidance, match advice, profile tips, and interview prep as normal.
"""
    # ... rest of the function (call Claude API, return response) ...
```

4. Save the file.

### 4.2 Backend — Pass platform to Sieve from the router

**File to modify:** `services/api/app/routers/sieve.py`

**What to do:**

1. Open `services/api/app/routers/sieve.py` in Cursor.
2. Find the `POST /api/sieve/chat` endpoint.
3. Add the `Request` dependency and pass the platform to the `handle_chat` function:

```python
from fastapi import Request
from app.services.auth import get_client_platform

@router.post("/chat")
async def sieve_chat(
    payload: SieveChatRequest,
    request: Request,
    user = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    platform = get_client_platform(request)

    # ... existing validation ...

    response_text = await handle_chat(
        user_id=user.id,
        message=payload.message,
        conversation_history=history,
        db=db,
        platform=platform,  # ← ADD THIS PARAMETER
    )

    # ... rest unchanged ...
```

4. Save the file.

### 4.3 Mobile Sieve widget — handle 403 gracefully

If the mobile app has its own Sieve chat component, ensure it handles 403 (daily message limit reached) with the same generic redirect:

**File to check:** `apps/mobile/components/SieveChat.tsx` or wherever the mobile Sieve UI lives

**What to do:**

1. Find where the mobile app sends messages to `POST /api/sieve/chat`.
2. In the error handler for 403 responses, show:

```typescript
if (response.status === 403) {
  // Don't show "You've reached your daily limit. Upgrade to Pro."
  // Instead show:
  addMessage({
    role: 'assistant',
    content: 'For the best experience with all features, please visit WinnowCC.ai on your computer or mobile browser.',
  });
  return;
}
```

3. Save the file.

---

## Part 5: Global Error Handling — Catch All 403s in Mobile

Create a single place that catches any 403 response from the API in the mobile app and shows the generic web redirect message.

**File to modify:** `apps/mobile/lib/api.ts`

**What to do:**

1. Open `apps/mobile/lib/api.ts` in Cursor.
2. In the shared fetch wrapper, add a global 403 handler:

```typescript
// In the shared API client, after each fetch:
if (response.status === 403) {
  // Check if this is a billing/feature-gate 403
  const data = await response.json().catch(() => ({}));

  // If the response mentions WinnowCC.ai, it's already mobile-safe from the backend.
  // If not (in case of older endpoints), wrap it:
  const message = data.detail || "For more information, please visit WinnowCC.ai.";

  // You can throw a custom error that screens can catch:
  throw new FeatureGateError(message);
}
```

3. Create a simple `FeatureGateError` class:

```typescript
export class FeatureGateError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'FeatureGateError';
  }
}
```

4. In each screen that calls gated features (tailor, cover letter, career intelligence, semantic search), catch `FeatureGateError` and show the Alert:

```typescript
import { Alert } from 'react-native';

try {
  const result = await api.post(`/api/tailor/${jobId}`);
  // success handling...
} catch (error) {
  if (error instanceof FeatureGateError) {
    Alert.alert(
      "Available on Web",
      "For full access to all features, please visit WinnowCC.ai on your computer or mobile browser.",
      [{ text: "OK" }]
    );
  } else {
    // Handle other errors normally
  }
}
```

5. Save the file.

---

## Part 6: Verification and Testing

### 6.1 Visual audit checklist

After completing Parts 1–5, go through every mobile screen and verify:

- [ ] **Dashboard:** No plan badge. No "Free" / "Pro" / "Starter" label anywhere. No upgrade button. Metrics cards still work.
- [ ] **Matches list:** No "X of Y matches" limit text. No "Upgrade to see more" prompt. List shows whatever the API returns.
- [ ] **Job detail:** "Generate ATS Resume" button is always visible. No usage counter ("2/5 used"). If tapped and API returns 403, shows generic "visit WinnowCC.ai" alert. No "Upgrade to Pro" button.
- [ ] **Profile:** No billing section. No subscription status. No "Manage Subscription" button. No usage meters. Only preferences + save + logout. Small "Manage your account at WinnowCC.ai" text (non-tappable).
- [ ] **Sieve chat:** Ask "What plan am I on?" → Sieve redirects to WinnowCC.ai. Ask "How do I upgrade?" → Sieve redirects to WinnowCC.ai. Ask "Why can't I generate more resumes?" → Sieve redirects to WinnowCC.ai. Ask "Help me prepare for an interview" → Sieve answers normally with career advice (NOT redirected).
- [ ] **No Stripe references anywhere:** Search the entire `apps/mobile/` directory for "stripe", "checkout", "upgrade", "pricing", "subscribe", "plan_tier", "$9", "$29", "$49", "$79", "$149", "$299". None of these should appear in user-visible UI text.
- [ ] **No external purchase links:** No `Linking.openURL` calls to Stripe checkout, billing portal, or pricing pages.

### 6.2 Automated grep verification

Run these commands in your terminal from the project root to find any remaining violations:

```powershell
# From the project root directory:
cd apps/mobile

# Search for pricing/billing text in all TypeScript files:
Select-String -Path "**/*.tsx","**/*.ts" -Pattern "upgrade|pricing|subscribe|stripe|checkout|billing|plan_tier|\$9|\$29|\$49|\$79|\$149|\$299|Manage Subscription|Unlock|free tier|pro tier|starter tier" -Recurse

# The ONLY acceptable matches should be:
#   - This prompt file itself
#   - The generic "visit WinnowCC.ai" redirect messages
#   - Comments explaining the reader-app model
#   - The X-Client-Platform header in api.ts
```

If any matches are found in UI-visible code (not comments), go back and remove them.

### 6.3 Sieve conversation test script

Test these conversations with Sieve from the mobile app:

| User Message | Expected Sieve Response |
|---|---|
| "What plan am I on?" | Redirects to WinnowCC.ai |
| "How much does Pro cost?" | Redirects to WinnowCC.ai |
| "I want to upgrade" | Redirects to WinnowCC.ai |
| "Why can I only see 10 matches?" | Redirects to WinnowCC.ai |
| "How do I get more tailored resumes?" | Redirects to WinnowCC.ai |
| "Help me with my resume" | Normal career advice (NOT redirected) |
| "Which matches should I apply to?" | Normal match advice (NOT redirected) |
| "How can I improve my profile?" | Normal profile tips (NOT redirected) |

---

## File and Component Reference

| What | Where | Action |
|------|-------|--------|
| Mobile client detection | `services/api/app/services/auth.py` | MODIFY — add `get_client_platform()` |
| Billing status (mobile-safe) | `services/api/app/routers/billing.py` | MODIFY — strip pricing for mobile |
| Feature gate errors (mobile-safe) | `services/api/app/services/billing.py` | MODIFY — generic 403 messages for mobile |
| Sieve system prompt (mobile rules) | `services/api/app/services/sieve_chat.py` | MODIFY — add mobile prompt rules |
| Sieve router (pass platform) | `services/api/app/routers/sieve.py` | MODIFY — pass platform to handle_chat |
| Mobile API client (platform header) | `apps/mobile/lib/api.ts` | MODIFY — add X-Client-Platform header |
| Mobile API client (403 handler) | `apps/mobile/lib/api.ts` | MODIFY — add FeatureGateError |
| Dashboard screen | `apps/mobile/app/(tabs)/dashboard.tsx` | MODIFY — remove plan badge + billing fetch |
| Matches screen | `apps/mobile/app/(tabs)/matches.tsx` | MODIFY — remove limit text + upgrade CTAs |
| Job detail screen | `apps/mobile/app/match/[id].tsx` | MODIFY — remove gating on buttons + usage counters |
| Profile screen | `apps/mobile/app/(tabs)/profile.tsx` | MODIFY — remove billing section |
| Sieve mobile chat | `apps/mobile/components/SieveChat.tsx` | MODIFY — handle 403 with generic redirect |
| Billing/settings screens | `apps/mobile/app/settings.tsx` etc. | DELETE or strip billing content |
| Tab navigator | `apps/mobile/app/(tabs)/_layout.tsx` | MODIFY — remove billing tab if present |

---

## Implementation Order (step by step for Cursor)

### Phase 1: Backend Changes (Steps 1–5)

1. **Step 1:** Open `services/api/app/services/auth.py`. Add `get_client_platform()` function (Part 1.1).
2. **Step 2:** Open `services/api/app/routers/billing.py`. Modify `/status` to return stripped response for mobile (Part 1.2).
3. **Step 3:** Open `services/api/app/services/billing.py`. Modify 403 errors to be generic for mobile (Part 1.3).
4. **Step 4:** Open `services/api/app/services/sieve_chat.py`. Add mobile-specific system prompt rules (Part 4.1).
5. **Step 5:** Open `services/api/app/routers/sieve.py`. Pass platform to `handle_chat` (Part 4.2).

### Phase 2: Mobile App Changes (Steps 6–12)

6. **Step 6:** Open `apps/mobile/lib/api.ts`. Add `X-Client-Platform: mobile` header (Part 2). Add `FeatureGateError` class and global 403 handler (Part 5).
7. **Step 7:** Open `apps/mobile/app/(tabs)/dashboard.tsx`. Remove billing fetch and plan badge (Part 3.1).
8. **Step 8:** Open `apps/mobile/app/(tabs)/matches.tsx`. Remove limit text and upgrade CTAs (Part 3.2).
9. **Step 9:** Open `apps/mobile/app/match/[id].tsx`. Remove gating, add generic 403 Alert (Part 3.3).
10. **Step 10:** Open `apps/mobile/app/(tabs)/profile.tsx`. Remove billing section (Part 3.4).
11. **Step 11:** Check for and remove any standalone billing screens (Part 3.5).
12. **Step 12:** Open mobile Sieve component. Handle 403 with generic redirect (Part 4.3).

### Phase 3: Verification (Steps 13–15)

13. **Step 13:** Run the visual audit checklist (Part 6.1) on every screen.
14. **Step 14:** Run the grep commands (Part 6.2) to find remaining violations.
15. **Step 15:** Test Sieve conversations (Part 6.3) to verify redirect behavior.

---

## What This Does NOT Change

- **Web app (apps/web/):** UNCHANGED. The web app keeps all pricing, billing, Stripe checkout, upgrade CTAs, feature gates, and usage meters. This is where users subscribe and manage billing.
- **Backend billing enforcement:** UNCHANGED. The backend still enforces tier limits. Free users still get 10 matches, 5 tailored resumes, etc. The mobile app just doesn't *tell* the user about the limits.
- **Backend billing routes:** Still exist, still work for the web app. Mobile just gets stripped responses.
- **Stripe integration:** UNCHANGED. Webhooks, checkout, customer portal all work as before — just not accessible from mobile.

---

## Apple App Store Review Notes

When submitting to the App Store, in the "App Review Information" section:

- **Notes for Reviewer:** "This app is a reader app for the Winnow Career Concierge service. Users create accounts and manage subscriptions at WinnowCC.ai. The app allows authenticated users to view their job matches, manage application tracking, and access career guidance. No purchases are made within the app."
- **Sign-in credentials:** Provide a test account (free tier) for the reviewer.
- **Content rights:** Select "This app does not contain third-party content that requires rights."

---

## Success Criteria

✅ Zero pricing text visible anywhere in the mobile app
✅ Zero upgrade/subscribe buttons or CTAs in the mobile app
✅ Zero Stripe links or checkout redirects in the mobile app
✅ Zero feature-gate messaging ("X of Y used", "Upgrade to unlock")
✅ Zero plan tier badges or labels (Free/Starter/Pro)
✅ Dashboard shows metrics only — no billing info
✅ Matches list shows results with no limit messaging
✅ "Generate ATS Resume" button always visible; 403 → generic web redirect alert
✅ Profile screen has no billing section; only preferences + logout
✅ Sieve redirects ALL pricing/billing/upgrade questions to WinnowCC.ai
✅ Sieve answers career/profile/match questions normally (not redirected)
✅ Backend detects mobile via `X-Client-Platform` header and strips billing from responses
✅ All 403 errors from the API show generic "visit WinnowCC.ai" message in mobile
✅ Grep of `apps/mobile/` returns zero pricing/billing terms in UI code
✅ Web app is completely unchanged — all billing UI preserved for web users

---

**Status:** Ready for implementation
**Estimated Time:** 2–3 hours
**Dependencies:** PROMPT23 (Mobile App exists), PROMPT20/39 (Billing exists), PROMPT18/24 (Sieve exists)
**Affects:** `apps/mobile/` (primary), `services/api/` (billing + sieve routes only)
**Does NOT affect:** `apps/web/`, Stripe dashboard, database schema
