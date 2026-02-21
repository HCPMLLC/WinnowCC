# PROMPT27_App_Store_Submission.md

Read SPEC.md, ARCHITECTURE.md, CLAUDE.md, PROMPT23 (Mobile App), and PROMPT26 (Custom Domain) before making changes.

## Purpose

Prepare and submit the Winnow mobile app to both the Apple App Store (iOS) and Google Play Store (Android). This covers everything needed to pass store review on the first attempt: production-ready app assets (icon, splash, screenshots), store listing metadata (description, keywords, categories), a hosted privacy policy page, Apple Developer + Google Play Console account setup, EAS build configuration, production API URL, and the actual build + submit commands. Expect a 1–2 week review cycle for the initial iOS submission and 1–3 days for Android.

---

## Triggers — When to Use This Prompt

- The mobile app (PROMPT23) is built and tested.
- Custom domain (PROMPT26) is live — `api.winnowcc.ai` is serving production traffic.
- QA (PROMPT25) has been completed with mobile flows passing.
- You're ready to put the app in users' hands via the app stores.

---

## What Already Exists (DO NOT recreate)

1. **Mobile app:** `apps/mobile/` — Expo + React Native with auth, dashboard, matches, job detail, profile, tailored resume download (PROMPT23).
2. **app.json:** `apps/mobile/app.json` — configured with bundle ID `com.winnow.app`, splash, icons, plugins.
3. **eas.json:** `apps/mobile/eas.json` — build profiles for development, preview, and production.
4. **Assets directory:** `apps/mobile/assets/` — placeholder `icon.png`, `splash.png`, `adaptive-icon.png`.
5. **Production API URL:** `https://api.winnowcc.ai` — configured in `eas.json` production profile (PROMPT26).
6. **EAS CLI:** Already installed globally (`npm install -g eas-cli`).

---

## Prerequisites Before Starting

Before you begin, you need TWO paid developer accounts:

| Account | Cost | URL | What you get |
|---------|------|-----|--------------|
| Apple Developer Program | $99/year | https://developer.apple.com/programs/ | App Store Connect access, iOS distribution certificates |
| Google Play Developer | $25 (one-time) | https://play.google.com/console/signup | Google Play Console access, Android distribution |

Sign up for both now if you haven't already. Apple approval can take 24–48 hours.

---

# PART 1 — APP ASSETS (Icon, Splash, Screenshots)

### 1.1 App Icon

You need ONE master icon at **1024×1024 PNG** (no transparency, no rounded corners — the stores apply rounding automatically).

**Design specs:**
- Background: Hunter green `#1B3025`
- Foreground: Gold "W" lettermark or Winnow logo in `#E8C84A`
- No text other than the logo mark (text is too small at phone icon sizes)
- No transparency (iOS rejects transparent icons)
- PNG format, exactly 1024×1024 pixels

**Options for creating this:**

Option A — **Figma / Canva (recommended for non-designers):**
1. Go to https://www.canva.com → create a custom design at 1024×1024
2. Set background to `#1B3025`
3. Add a large "W" in a bold font, color `#E8C84A`, centered
4. Export as PNG

Option B — **Use an AI image generator:**
Generate a flat, minimal app icon with a gold "W" on a dark green background. Then resize to exactly 1024×1024.

Option C — **Hire a designer on Fiverr:**
Search "app icon design" — typical cost $20–50, turnaround 1–2 days.

**Save the file to:**
```
C:\Users\ronle\Documents\resumematch\apps\mobile\assets\icon.png
```

### 1.2 Splash Screen

The splash screen shows while the app loads. It should be simple — logo centered on a solid background.

**Design specs:**
- Size: **1284×2778 pixels** (iPhone 15 Pro Max safe area — Expo scales for other devices)
- Background: Solid `#1B3025` (hunter green)
- Center: Winnow logo or "W" mark in `#E8C84A`, roughly 200×200px
- Optionally add "Winnow" text below the logo in `#B8E4EA` (teal), 48px font

**Save to:**
```
C:\Users\ronle\Documents\resumematch\apps\mobile\assets\splash.png
```

### 1.3 Android Adaptive Icon

Android uses a special "adaptive icon" format with separate foreground and background layers.

**Foreground image specs:**
- Size: **1024×1024 PNG** with transparency
- The icon content (the "W") should be inside the center **66%** safe zone (roughly 682×682 area centered)
- Background is transparent — Android applies the `backgroundColor` from `app.json` (`#1B3025`)

**Save to:**
```
C:\Users\ronle\Documents\resumematch\apps\mobile\assets\adaptive-icon.png
```

### 1.4 Notification Icon (Android)

**Specs:**
- Size: **96×96 PNG**
- White silhouette on transparent background (Android tints it)
- Simple "W" shape

**Save to:**
```
C:\Users\ronle\Documents\resumematch\apps\mobile\assets\notification-icon.png
```

### 1.5 App Store Screenshots

Both stores require screenshots of the app running. You need screenshots for:

**iOS (required sizes):**
- **6.7" display** (iPhone 15 Pro Max): 1290×2796 pixels — **REQUIRED**
- **5.5" display** (iPhone 8 Plus): 1242×2208 pixels — **REQUIRED if supporting older phones**

**Android (required):**
- Phone: 1080×1920 pixels minimum (16:9 ratio) — **at least 2, up to 8**
- Tablet: 1200×1920 (optional but recommended)

**How to capture screenshots:**

Option A — **Use Expo on a simulator/emulator:**
```powershell
# iOS Simulator (Mac only)
npx expo start --ios
# Navigate to each screen, then press Cmd+S to save screenshot

# Android Emulator
npx expo start --android
# Use the emulator's screenshot button
```

Option B — **Use your real phone:**
1. Run the app via Expo Go
2. Navigate to each key screen
3. Take a phone screenshot (Power + Volume Up on most phones)
4. Transfer to your computer

**Required screenshots (capture these 5 screens):**

| # | Screen | What to show |
|---|--------|--------------|
| 1 | **Login** | Clean login screen with Winnow branding |
| 2 | **Dashboard** | KPI cards, plan badge, welcome message |
| 3 | **Matches List** | Several match cards with scores and skill tags |
| 4 | **Job Detail** | Match score, reasons, gaps, "Generate Resume" button |
| 5 | **Profile** | Preferences editing screen |

**Save all screenshots to a new folder:**
```
C:\Users\ronle\Documents\resumematch\apps\mobile\assets\screenshots\
```

### 1.6 Optional: Add marketing frames to screenshots

Use a tool like **Screenshots Pro** (https://screenshots.pro), **AppMockUp** (https://app-mockup.com), or **Figma** to wrap your raw screenshots in device frames with marketing text. Examples:

- Frame 1: "AI-Powered Job Matching" + Dashboard screenshot
- Frame 2: "Find Your Best Matches" + Matches list screenshot
- Frame 3: "Tailored ATS Resumes" + Job detail screenshot

This is optional but significantly improves conversion rates.

---

# PART 2 — PRIVACY POLICY + TERMS

Both Apple and Google **require** a publicly accessible privacy policy URL. Apple will reject your app without one.

### 2.1 Create a privacy policy page

**File to create:** `apps/web/app/privacy/page.tsx`

```tsx
export const metadata = {
  title: 'Privacy Policy — Winnow',
  description: 'Winnow privacy policy',
};

export default function PrivacyPage() {
  return (
    <main style={{ maxWidth: 800, margin: '0 auto', padding: '40px 20px', fontFamily: 'system-ui' }}>
      <h1>Privacy Policy</h1>
      <p><strong>Last updated:</strong> February 2026</p>
      <p><strong>Winnow</strong> ("we", "our", "us") operates the Winnow mobile application and web platform (winnowcc.ai). This policy explains how we collect, use, and protect your information.</p>

      <h2>Information We Collect</h2>
      <p><strong>Account information:</strong> Email address and password when you create an account.</p>
      <p><strong>Resume data:</strong> Resume files you upload (PDF/DOCX) and the profile data extracted from them, including work experience, education, skills, and contact information.</p>
      <p><strong>Job preferences:</strong> Target job titles, preferred locations, salary expectations, and remote work preferences you provide.</p>
      <p><strong>Usage data:</strong> Pages visited, features used, and interaction patterns to improve the product.</p>
      <p><strong>Device information:</strong> Device type, operating system, and app version for troubleshooting.</p>

      <h2>How We Use Your Information</h2>
      <p>We use your data to: match you with relevant job opportunities, generate tailored ATS-optimized resumes, provide dashboard analytics about your job search, and improve our matching algorithms.</p>

      <h2>Data Storage and Security</h2>
      <p>Your data is stored on Google Cloud Platform with encryption at rest and in transit (TLS). Resume files are stored in Google Cloud Storage. We never store raw resume text in application logs.</p>

      <h2>Third-Party Services</h2>
      <p>We use the following third-party services:</p>
      <ul style={{ paddingLeft: 20 }}>
        <li><strong>Anthropic (Claude AI):</strong> For resume parsing, job matching, and tailored resume generation. Your resume content is sent to Claude's API for processing.</li>
        <li><strong>Stripe:</strong> For payment processing. We do not store your credit card information.</li>
        <li><strong>Sentry:</strong> For error tracking. Personal data is scrubbed from error reports.</li>
        <li><strong>Posthog:</strong> For product analytics. Usage patterns are collected anonymously.</li>
      </ul>

      <h2>Data Retention and Deletion</h2>
      <p>Your data is retained as long as your account is active. You can export all your data or permanently delete your account at any time from Settings. Account deletion removes all stored data including resumes, profiles, matches, and tailored resumes within 30 days.</p>

      <h2>Your Rights</h2>
      <p>You have the right to: access your data (via data export), correct your data (via profile editing), delete your data (via account deletion), and opt out of analytics tracking.</p>

      <h2>Children's Privacy</h2>
      <p>Winnow is not intended for users under 16. We do not knowingly collect data from children.</p>

      <h2>Changes to This Policy</h2>
      <p>We may update this policy. Changes will be posted on this page with an updated date.</p>

      <h2>Contact</h2>
      <p>Questions about this policy? Contact us at <a href="mailto:privacy@winnowcc.ai">privacy@winnowcc.ai</a>.</p>
    </main>
  );
}
```

### 2.2 Create a terms of service page

**File to create:** `apps/web/app/terms/page.tsx`

```tsx
export const metadata = {
  title: 'Terms of Service — Winnow',
  description: 'Winnow terms of service',
};

export default function TermsPage() {
  return (
    <main style={{ maxWidth: 800, margin: '0 auto', padding: '40px 20px', fontFamily: 'system-ui' }}>
      <h1>Terms of Service</h1>
      <p><strong>Last updated:</strong> February 2026</p>
      <p>By using Winnow, you agree to these terms.</p>

      <h2>Service Description</h2>
      <p>Winnow is a job matching platform that analyzes your resume, matches you with relevant job opportunities, and generates tailored ATS-optimized resumes. We do not guarantee employment outcomes.</p>

      <h2>Account Responsibilities</h2>
      <p>You are responsible for maintaining the security of your account credentials. You must provide accurate information in your profile and resume.</p>

      <h2>Acceptable Use</h2>
      <p>You agree not to: upload fraudulent resumes, use the service to spam employers, attempt to circumvent usage limits, or reverse-engineer the matching algorithms.</p>

      <h2>Content Ownership</h2>
      <p>You retain ownership of your resume and profile data. By uploading content, you grant Winnow a license to process it for the purpose of providing our services.</p>

      <h2>Subscription and Billing</h2>
      <p>Free accounts have limited features. Paid subscriptions are billed through Stripe. You can cancel anytime via the Stripe Customer Portal. Refunds are handled per Stripe's policies.</p>

      <h2>AI-Generated Content</h2>
      <p>Tailored resumes and cover letters are generated by AI. While grounded in your actual experience, you are responsible for reviewing all generated content before use. Winnow does not guarantee that generated resumes will pass any specific ATS system.</p>

      <h2>Limitation of Liability</h2>
      <p>Winnow is provided "as is." We are not liable for job search outcomes, interview results, or hiring decisions. Our maximum liability is limited to the amount you've paid in the past 12 months.</p>

      <h2>Termination</h2>
      <p>We may suspend accounts that violate these terms. You may delete your account at any time.</p>

      <h2>Contact</h2>
      <p>Questions? Contact us at <a href="mailto:support@winnowcc.ai">support@winnowcc.ai</a>.</p>
    </main>
  );
}
```

### 2.3 Deploy the pages

These pages are part of the Next.js web app. Push to `main` and let CI/CD deploy, or manually rebuild and deploy:

```powershell
cd C:\Users\ronle\Documents\resumematch\apps\web
docker build --build-arg NEXT_PUBLIC_API_BASE_URL=https://api.winnowcc.ai -t us-central1-docker.pkg.dev/YOUR_PROJECT/winnow/web:latest .
docker push us-central1-docker.pkg.dev/YOUR_PROJECT/winnow/web:latest
gcloud run deploy winnow-web --image=us-central1-docker.pkg.dev/YOUR_PROJECT/winnow/web:latest --region=us-central1
```

Verify both URLs load:
- `https://winnowcc.ai/privacy`
- `https://winnowcc.ai/terms`

---

# PART 3 — UPDATE APP CONFIGURATION

### 3.1 Update `app.json` with final values

**File to modify:** `C:\Users\ronle\Documents\resumematch\apps\mobile\app.json`

Update these fields:

```json
{
  "expo": {
    "name": "Winnow — AI Job Matching",
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
      "bundleIdentifier": "ai.winnowcc.app",
      "buildNumber": "1",
      "infoPlist": {
        "NSAppTransportSecurity": {
          "NSExceptionDomains": {
            "winnowcc.ai": {
              "NSExceptionAllowsInsecureHTTPLoads": false
            }
          }
        },
        "ITSAppUsesNonExemptEncryption": false
      }
    },
    "android": {
      "adaptiveIcon": {
        "foregroundImage": "./assets/adaptive-icon.png",
        "backgroundColor": "#1B3025"
      },
      "package": "ai.winnowcc.app",
      "versionCode": 1
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

**Key changes from PROMPT23:**
- `name`: Changed to "Winnow — AI Job Matching" (stores show this name)
- `bundleIdentifier` (iOS) and `package` (Android): Changed to `ai.winnowcc.app` (reverse-domain of `winnowcc.ai`)
- `buildNumber` / `versionCode`: Set to `"1"` / `1` for initial submission
- `ITSAppUsesNonExemptEncryption`: Set to `false` (standard HTTPS only — avoids export compliance paperwork)
- Removed `NSAllowsArbitraryLoads: true` (not needed in production — everything is HTTPS)

### 3.2 Update `eas.json` with store credentials

**File to modify:** `C:\Users\ronle\Documents\resumematch\apps\mobile\eas.json`

```json
{
  "cli": {
    "version": ">= 12.0.0",
    "appVersionSource": "remote"
  },
  "build": {
    "development": {
      "developmentClient": true,
      "distribution": "internal"
    },
    "preview": {
      "distribution": "internal",
      "env": {
        "EXPO_PUBLIC_API_BASE_URL": "https://api.winnowcc.ai"
      }
    },
    "production": {
      "autoIncrement": true,
      "env": {
        "EXPO_PUBLIC_API_BASE_URL": "https://api.winnowcc.ai"
      }
    }
  },
  "submit": {
    "production": {
      "ios": {
        "appleId": "YOUR_APPLE_ID_EMAIL",
        "ascAppId": "YOUR_APP_STORE_CONNECT_APP_ID",
        "appleTeamId": "YOUR_TEAM_ID"
      },
      "android": {
        "serviceAccountKeyPath": "./google-play-key.json",
        "track": "production"
      }
    }
  }
}
```

**You'll fill in the actual values in Parts 4 and 5.**

---

# PART 4 — APPLE APP STORE SETUP

### 4.1 Register your App ID in Apple Developer Portal

1. Go to https://developer.apple.com/account/resources/identifiers/list
2. Click the **+** button → **App IDs** → **App**
3. Description: `Winnow AI Job Matching`
4. Bundle ID: Select **Explicit** → enter `ai.winnowcc.app`
5. Capabilities: Check **Push Notifications** (if you implemented push in PROMPT23)
6. Click **Register**

### 4.2 Create the app in App Store Connect

1. Go to https://appstoreconnect.apple.com/apps
2. Click **+** → **New App**
3. Fill in:
   - **Platforms:** iOS
   - **Name:** `Winnow — AI Job Matching`
   - **Primary Language:** English (U.S.)
   - **Bundle ID:** Select `ai.winnowcc.app` (from step 4.1)
   - **SKU:** `winnow-ios-v1`
   - **User Access:** Full Access
4. Click **Create**

### 4.3 Fill in the App Store listing

In App Store Connect, navigate to your app → **App Information**:

| Field | Value |
|-------|-------|
| **Subtitle** | `Smart Resume Matching & ATS Tailoring` |
| **Category** | Business |
| **Secondary Category** | Productivity |
| **Privacy Policy URL** | `https://winnowcc.ai/privacy` |
| **Age Rating** | 4+ (no objectionable content) |

Navigate to **Version 1.0.0** → fill in:

| Field | Value |
|-------|-------|
| **What's New** | `Initial release` |
| **Description** | *(see Part 6 below)* |
| **Keywords** | `job search,resume,ATS,career,matching,tailored resume,interview,job match,AI resume,career tools` |
| **Support URL** | `https://winnowcc.ai` |
| **Marketing URL** | `https://winnowcc.ai` |

### 4.4 Upload screenshots

In App Store Connect → Version 1.0.0 → **Screenshots**:

- Drag your 6.7" screenshots into the **6.7" Display** section
- Drag your 5.5" screenshots into the **5.5" Display** section (if you have them)
- You can use the same screenshots for both sizes — App Store Connect will warn but accept

### 4.5 Get your App Store Connect credentials for `eas.json`

You need three values:

| Value | Where to find it |
|-------|-----------------|
| `appleId` | Your Apple ID email (the one you log in with) |
| `ascAppId` | App Store Connect → your app → **App Information** → scroll down → **Apple ID** (a numeric ID like `6448523891`) |
| `appleTeamId` | https://developer.apple.com/account → **Membership** → **Team ID** (10-char alphanumeric like `ABC123DEF4`) |

Update `eas.json` with these values (Step 3.2 above).

---

# PART 5 — GOOGLE PLAY STORE SETUP

### 5.1 Create the app in Google Play Console

1. Go to https://play.google.com/console
2. Click **Create app**
3. Fill in:
   - **App name:** `Winnow — AI Job Matching`
   - **Default language:** English (United States)
   - **App or game:** App
   - **Free or paid:** Free (with in-app purchases via web billing)
4. Accept the declarations and click **Create app**

### 5.2 Complete the store listing

Navigate to **Main store listing**:

| Field | Value |
|-------|-------|
| **Short description** (80 chars max) | `AI-powered job matching with tailored ATS-optimized resumes` |
| **Full description** | *(see Part 6 below)* |
| **App icon** | Upload your 512×512 icon (Play Console will resize from your 1024×1024) |
| **Feature graphic** | 1024×500 PNG — banner image shown at the top of your listing (use Canva: green background + "Winnow" logo + tagline) |
| **Phone screenshots** | Upload your Android screenshots (min 2, max 8) |

### 5.3 Complete content rating

Navigate to **Policy** → **App content** → **Content rating**:
1. Start the questionnaire
2. Category: **Utility, Productivity, Communication, or Other**
3. Answer "No" to violence, sexual content, drugs, etc.
4. Result: **Rated for Everyone** (equivalent to 4+ on iOS)

### 5.4 Complete data safety

Navigate to **Policy** → **App content** → **Data safety**:

| Data type | Collected | Shared | Purpose |
|-----------|-----------|--------|---------|
| Email address | Yes | No | Account management |
| Name | Yes | No | App functionality (profile) |
| Resume/CV files | Yes | No | App functionality (matching) |
| Job search activity | Yes | No | App functionality, analytics |
| App interactions | Yes | No | Analytics |
| Crash logs | Yes | No | App functionality (Sentry) |

Mark that:
- Data is encrypted in transit: **Yes**
- Users can request data deletion: **Yes**
- Link to privacy policy: `https://winnowcc.ai/privacy`

### 5.5 Create a Google Play service account key

EAS needs a service account key to upload builds automatically:

1. Go to **Google Play Console** → **Setup** → **API access**
2. Click **Link** to link your Google Cloud project (or create one)
3. Click **Create new service account** → follow the link to Google Cloud Console
4. In GCP: **IAM & Admin** → **Service Accounts** → **Create Service Account**
   - Name: `winnow-play-upload`
   - Role: **Service Account User**
5. Create a **JSON key** for this service account → download it
6. Back in Google Play Console → **API access** → find the service account → **Grant access**
   - App permissions: Select your app → **Admin (all permissions)**

Save the JSON key to:
```
C:\Users\ronle\Documents\resumematch\apps\mobile\google-play-key.json
```

**IMPORTANT:** Add this file to `.gitignore` so it's never committed:

**File to modify:** `C:\Users\ronle\Documents\resumematch\apps\mobile\.gitignore`

Add this line:
```
google-play-key.json
```

---

# PART 6 — APP STORE DESCRIPTIONS

Use the same description for both stores (adjust length for Google's 4,000 char limit vs Apple's unlimited).

### 6.1 Full description

```
Winnow uses AI to match your resume with the best job opportunities and generate tailored, ATS-optimized resumes — so you spend less time applying and more time interviewing.

HOW IT WORKS

1. Upload your resume (PDF or DOCX) on the web app at winnowcc.ai
2. Winnow's AI parses your experience, skills, and preferences
3. Get ranked job matches with detailed match scores and explainability
4. Generate tailored resumes customized for each job — grounded in your real experience
5. Track your applications from saved through offer

KEY FEATURES

• Smart Matching — AI scores jobs based on skill overlap, title fit, location, salary, and seniority. Every score comes with clear reasons and gap analysis.

• Tailored ATS Resumes — Generate job-specific resumes that pass Applicant Tracking Systems. Every change is documented in a transparent change log. No fabricated experience, ever.

• Interview Readiness Score — Know your probability of landing an interview before you apply, based on resume strength, application timing, and job fit.

• Sieve AI Concierge — Ask questions about your matches, get proactive suggestions, and receive guidance throughout your job search.

• Application Tracking — Track every job from saved to offer with a simple status pipeline.

• Dashboard Analytics — See your profile completeness, qualified job count, application funnel, and more at a glance.

PRIVACY FIRST

Your resume is sensitive data. Winnow encrypts everything in transit and at rest, never logs resume text, and lets you export or delete your data at any time.

Get started free at winnowcc.ai, then use the mobile app to check matches and manage your job search on the go.
```

### 6.2 Short description (Google Play — 80 chars)

```
AI-powered job matching with tailored ATS-optimized resumes
```

### 6.3 Promotional text (iOS — 170 chars)

```
Upload your resume, get AI-matched jobs, and generate tailored ATS resumes. Track applications from saved to offer. Privacy-first, explainable, grounded in your real experience.
```

### 6.4 Keywords (iOS — 100 chars max, comma-separated)

```
job search,resume,ATS,career,matching,tailored resume,interview,job match,AI resume,career tools
```

---

# PART 7 — BUILD + SUBMIT

### 7.1 Link the Expo project to EAS

If you haven't already linked your project:

```powershell
cd C:\Users\ronle\Documents\resumematch\apps\mobile
eas init
```

This creates/updates the `projectId` in `app.json` → `extra.eas.projectId`. Follow the prompts to select your Expo account and project name.

### 7.2 Build for iOS

```powershell
cd C:\Users\ronle\Documents\resumematch\apps\mobile
eas build --platform ios --profile production
```

**What happens:**
- EAS uploads your project to Expo's build servers
- Builds an `.ipa` file (iOS app binary)
- Handles code signing automatically (creates certificates + provisioning profiles)
- Takes 10–30 minutes
- You'll see a URL to track build progress

**First time:** EAS will prompt you to log into your Apple Developer account. Enter your Apple ID and password. If you have 2FA, you'll be prompted for the code.

### 7.3 Build for Android

```powershell
eas build --platform android --profile production
```

**What happens:**
- Builds an `.aab` file (Android App Bundle — required by Google Play)
- Handles keystore generation automatically
- Takes 10–20 minutes

### 7.4 Submit iOS to App Store Connect

After the iOS build completes:

```powershell
eas submit --platform ios --profile production
```

This uploads the `.ipa` to App Store Connect. After upload:

1. Go to https://appstoreconnect.apple.com → your app
2. The build will appear under **TestFlight** → **Builds** (takes 5–15 minutes for processing)
3. Navigate to **App Store** → **Version 1.0.0**
4. Under **Build**, click **+** and select the uploaded build
5. Fill in any remaining fields (review notes — see Part 8)
6. Click **Submit for Review**

### 7.5 Submit Android to Google Play Console

After the Android build completes:

```powershell
eas submit --platform android --profile production
```

This uploads the `.aab` to Google Play Console. After upload:

1. Go to https://play.google.com/console → your app
2. Navigate to **Production** → **Create new release**
3. The uploaded build should appear automatically
4. Add release notes: `Initial release of Winnow — AI-powered job matching`
5. Click **Review release** → **Start rollout to production**

---

# PART 8 — APP REVIEW PREPARATION

App store reviewers test your app and may reject it if they can't log in, features don't work, or policies are violated.

### 8.1 Create a demo account for reviewers

Create a dedicated test account that reviewers can use:

**In your production database** (or via the signup flow on `https://winnowcc.ai`):

| Field | Value |
|-------|-------|
| Email | `demo@winnowcc.ai` |
| Password | `WinnowDemo2026!` |

After creating the account:
1. Log in as `demo@winnowcc.ai` on the web app
2. Upload a sample resume
3. Wait for parsing to complete
4. Verify matches appear
5. Generate at least one tailored resume

This ensures the reviewer sees a fully populated experience.

### 8.2 iOS App Review notes

In App Store Connect → Version 1.0.0 → **App Review Information**:

**Contact Information:**
- First name: `Ronald`
- Last name: `Levi`
- Phone: (your phone number)
- Email: `support@winnowcc.ai`

**Sign-In Information:**
- Username: `demo@winnowcc.ai`
- Password: `WinnowDemo2026!`

**Notes for reviewer:**
```
Winnow is a job search platform that matches resumes with job opportunities and generates tailored ATS-optimized resumes.

To test the app:
1. Log in with the provided demo credentials
2. The Dashboard tab shows job search metrics
3. The Matches tab shows AI-ranked job matches — tap any match to see details
4. On a job detail screen, tap "Generate ATS Resume" to create a tailored resume
5. The Profile tab allows editing job preferences

Resume upload is done on the web app (winnowcc.ai) — the mobile app is for viewing matches, generating resumes, and tracking applications.

The app requires an internet connection to function as it communicates with our API at api.winnowcc.ai.
```

### 8.3 Common rejection reasons and how to avoid them

| Rejection Reason | Prevention |
|-----------------|------------|
| **Guideline 2.1 — App Completeness:** App crashes or has broken features | Complete QA (PROMPT25) before submitting |
| **Guideline 5.1.1 — Data Collection:** No privacy policy | Privacy policy is at `winnowcc.ai/privacy` (Part 2) |
| **Guideline 2.3.3 — Screenshots:** Screenshots don't match app | Use real screenshots from the actual app, not mockups |
| **Guideline 4.0 — Design:** App is a thin wrapper around a website | Our app has native screens, not a WebView — it uses React Native components |
| **Guideline 5.1.2 — Data Use:** App collects data without explaining why | Data safety section filled in (Google), privacy labels set (Apple) |
| **Guideline 2.1 — Performance:** Login doesn't work | Demo account is pre-populated and tested |
| **Guideline 3.1.1 — In-App Purchase:** Directing users to web for payment | We use web billing (Stripe), which is allowed for SaaS/business apps |

### 8.4 iOS Privacy Nutrition Labels

In App Store Connect → **App Privacy**:

Click **Get Started** and answer the questionnaire:

| Data type | Usage | Linked to identity? | Tracking? |
|-----------|-------|---------------------|-----------|
| Contact Info (email) | App Functionality | Yes | No |
| Name | App Functionality | Yes | No |
| User Content (resumes) | App Functionality | Yes | No |
| Usage Data | Analytics | No | No |
| Diagnostics (crash data) | App Functionality | No | No |
| Identifiers (user ID) | App Functionality | Yes | No |

---

# PART 9 — POST-SUBMISSION

### 9.1 Monitor review status

- **iOS:** App Store Connect → your app → **Activity** tab shows review status
  - Typical timeline: 1–2 days for review, but can take up to 7 days for first submission
  - If rejected: Read the resolution center feedback, fix the issue, resubmit
- **Android:** Google Play Console → your app → **Publishing overview**
  - Typical timeline: 1–3 days (sometimes hours)
  - If rejected: Check the notification email for the specific policy violation

### 9.2 After approval

Once approved and live:

1. **Test the store listing:** Search for "Winnow" on each store — verify it appears
2. **Download and test:** Install from the store on a real device, verify login + all flows work
3. **Announce:** Share the store links on your website, social media, etc.
4. **Add store badges to the website:**

**File to modify:** `C:\Users\ronle\Documents\resumematch\apps\web\app\page.tsx` (or landing page)

Add App Store and Google Play badges linking to your store listings.

### 9.3 Future updates

For subsequent updates:

1. Bump `version` in `app.json` (e.g., `"1.0.0"` → `"1.1.0"`)
2. EAS auto-increments `buildNumber` / `versionCode` if `autoIncrement: true`
3. Build and submit:
   ```powershell
   eas build --platform all --profile production
   eas submit --platform all --profile production
   ```
4. Updates typically review in 24 hours (faster than initial submission)

---

## File and Component Reference

| What | Where | Action |
|------|-------|--------|
| App icon | `apps/mobile/assets/icon.png` | CREATE (1024×1024 PNG) |
| Splash screen | `apps/mobile/assets/splash.png` | CREATE (1284×2778 PNG) |
| Adaptive icon | `apps/mobile/assets/adaptive-icon.png` | CREATE (1024×1024 PNG w/ transparency) |
| Notification icon | `apps/mobile/assets/notification-icon.png` | CREATE (96×96 PNG white silhouette) |
| Screenshots | `apps/mobile/assets/screenshots/` | CREATE (5 screens, per-platform sizes) |
| Feature graphic | `apps/mobile/assets/feature-graphic.png` | CREATE (1024×500 PNG, Android only) |
| Privacy policy | `apps/web/app/privacy/page.tsx` | CREATE |
| Terms of service | `apps/web/app/terms/page.tsx` | CREATE |
| App config | `apps/mobile/app.json` | MODIFY — final bundle IDs, name, version |
| EAS config | `apps/mobile/eas.json` | MODIFY — store credentials, autoIncrement |
| Git ignore | `apps/mobile/.gitignore` | MODIFY — add google-play-key.json |
| Landing page (badges) | `apps/web/app/page.tsx` | MODIFY — add store badges (after approval) |

---

## Implementation Order (for a beginner following in Cursor)

### Phase 1: Store Accounts (Steps 1–2)

1. **Step 1:** Enroll in the Apple Developer Program ($99/year). Wait for approval (24–48 hrs).
2. **Step 2:** Register for a Google Play Developer account ($25 one-time).

### Phase 2: App Assets (Steps 3–7)

3. **Step 3:** Create the app icon (1024×1024 PNG) and save to `C:\Users\ronle\Documents\resumematch\apps\mobile\assets\icon.png` (Part 1.1).
4. **Step 4:** Create the splash screen and save to `C:\Users\ronle\Documents\resumematch\apps\mobile\assets\splash.png` (Part 1.2).
5. **Step 5:** Create the adaptive icon and save to `C:\Users\ronle\Documents\resumematch\apps\mobile\assets\adaptive-icon.png` (Part 1.3).
6. **Step 6:** Create the notification icon (96×96) and save to `C:\Users\ronle\Documents\resumematch\apps\mobile\assets\notification-icon.png` (Part 1.4).
7. **Step 7:** Capture 5 screenshots per platform (Part 1.5). Save to `C:\Users\ronle\Documents\resumematch\apps\mobile\assets\screenshots\`.

### Phase 3: Privacy + Terms (Steps 8–9)

8. **Step 8:** Create `C:\Users\ronle\Documents\resumematch\apps\web\app\privacy\page.tsx` (Part 2.1).
9. **Step 9:** Create `C:\Users\ronle\Documents\resumematch\apps\web\app\terms\page.tsx` (Part 2.2). Deploy the web app (Part 2.3). Verify `https://winnowcc.ai/privacy` and `https://winnowcc.ai/terms` load.

### Phase 4: App Configuration (Steps 10–11)

10. **Step 10:** Open `C:\Users\ronle\Documents\resumematch\apps\mobile\app.json` in Cursor. Update with final values (Part 3.1).
11. **Step 11:** Open `C:\Users\ronle\Documents\resumematch\apps\mobile\eas.json` in Cursor. Update with store credentials (Part 3.2).

### Phase 5: Apple Setup (Steps 12–14)

12. **Step 12:** Register App ID in Apple Developer Portal (Part 4.1).
13. **Step 13:** Create the app in App Store Connect (Part 4.2).
14. **Step 14:** Fill in the store listing: description, keywords, screenshots, privacy policy URL (Parts 4.3–4.4). Complete privacy nutrition labels (Part 8.4). Note your `ascAppId` and `appleTeamId` (Part 4.5) and update `eas.json`.

### Phase 6: Google Play Setup (Steps 15–18)

15. **Step 15:** Create the app in Google Play Console (Part 5.1).
16. **Step 16:** Complete the store listing: description, screenshots, feature graphic (Part 5.2).
17. **Step 17:** Complete content rating + data safety questionnaires (Parts 5.3–5.4).
18. **Step 18:** Create a Google Play service account key (Part 5.5). Save to `C:\Users\ronle\Documents\resumematch\apps\mobile\google-play-key.json`. Add to `.gitignore`.

### Phase 7: Demo Account (Step 19)

19. **Step 19:** Create the `demo@winnowcc.ai` account, upload a resume, wait for matches, generate a tailored resume (Part 8.1).

### Phase 8: Build + Submit (Steps 20–23)

20. **Step 20:** Link the project to EAS:
    ```powershell
    cd C:\Users\ronle\Documents\resumematch\apps\mobile
    eas init
    ```
21. **Step 21:** Build for both platforms:
    ```powershell
    eas build --platform ios --profile production
    eas build --platform android --profile production
    ```
22. **Step 22:** Submit iOS:
    ```powershell
    eas submit --platform ios --profile production
    ```
    Then go to App Store Connect → select the build → add review notes (Part 8.2) → **Submit for Review**.
23. **Step 23:** Submit Android:
    ```powershell
    eas submit --platform android --profile production
    ```
    Then go to Google Play Console → create a release → add the build → **Start rollout**.

### Phase 9: Monitor + Post-Approval (Steps 24–25)

24. **Step 24:** Monitor review status daily. If rejected, read feedback, fix, and resubmit (Part 9.1).
25. **Step 25:** After approval, test the live store listing, install on a real device, and add store badges to your website (Part 9.2).

---

## Non-Goals (Do NOT implement in this prompt)

- In-app purchases or StoreKit integration (Winnow uses web-based Stripe billing)
- App Store Optimization (ASO) beyond basic keywords
- Localization into non-English languages
- Apple Watch or Wear OS companion apps
- TestFlight beta distribution (go straight to production)
- App clips or instant apps
- Paid user acquisition (ads, ASA campaigns)
- Custom store listing A/B tests (Google Play Experiments)

---

## Summary Checklist

### Developer Accounts
- [ ] Apple Developer Program enrolled and approved
- [ ] Google Play Developer account registered

### Assets
- [ ] App icon: 1024×1024 PNG at `assets/icon.png`
- [ ] Splash screen: 1284×2778 PNG at `assets/splash.png`
- [ ] Adaptive icon: 1024×1024 PNG (transparent BG) at `assets/adaptive-icon.png`
- [ ] Notification icon: 96×96 PNG at `assets/notification-icon.png`
- [ ] iOS screenshots: 6.7" (and optionally 5.5") — 5 screens
- [ ] Android screenshots: 1080×1920 minimum — 5 screens
- [ ] Android feature graphic: 1024×500 PNG

### Legal Pages
- [ ] Privacy policy live at `https://winnowcc.ai/privacy`
- [ ] Terms of service live at `https://winnowcc.ai/terms`

### App Configuration
- [ ] `app.json` updated with final name, bundle IDs (`ai.winnowcc.app`), version
- [ ] `eas.json` updated with Apple + Google credentials, `autoIncrement: true`
- [ ] `google-play-key.json` saved and added to `.gitignore`
- [ ] Production API URL: `https://api.winnowcc.ai`

### Store Listings
- [ ] iOS: App created in App Store Connect with description, keywords, screenshots, privacy labels
- [ ] Android: App created in Google Play Console with description, screenshots, content rating, data safety

### Demo Account
- [ ] `demo@winnowcc.ai` created with uploaded resume, matches, and tailored resume

### Build + Submit
- [ ] iOS build completed via `eas build --platform ios --profile production`
- [ ] Android build completed via `eas build --platform android --profile production`
- [ ] iOS submitted to App Store Connect with review notes
- [ ] Android submitted to Google Play Console with release notes

### Post-Approval
- [ ] App live on both stores
- [ ] Tested by installing from store on real device
- [ ] Store badges added to website landing page

Return code changes only.
