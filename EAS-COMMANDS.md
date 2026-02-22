# EAS Build & Update Commands

All commands should be run from the `apps/mobile/` directory.

```bash
cd apps/mobile
```

---

## Table of Contents

1. [EAS Build Commands](#eas-build-commands)
   - [Development](#1-development-build)
   - [Preview](#2-preview-build)
   - [Production](#3-production-build)
2. [EAS Update Commands](#eas-update-commands)
   - [Development Channel](#1-update-development-channel)
   - [Preview Channel](#2-update-preview-channel)
   - [Production Channel](#3-update-production-channel)
3. [EAS Submit Commands](#eas-submit-commands)
4. [Quick Reference](#quick-reference)

---

## EAS Build Commands

Builds compile native code and produce installable binaries (`.apk`, `.ipa`, `.aab`). You need a new build whenever you add/remove native modules, update the Expo SDK, or change `app.json` native config (icons, splash, permissions, etc.).

### 1. Development Build

**What it does:** Creates a debug build with the Expo development client (`developmentClient: true`). This replaces Expo Go and lets you load your JS bundle from a local dev server while still having access to all native modules. Distributed internally (`distribution: "internal"`), meaning it uses ad-hoc provisioning (iOS) or a direct APK (Android) -- not via the App Store / Play Store.

**When to use:**
- First-time setup on a device or simulator
- After adding a new native module (e.g., `expo-notifications`, `expo-camera`)
- After upgrading the Expo SDK
- After changing native config in `app.json` (bundle identifier, permissions, plugins)
- When a teammate needs a dev build on their physical device

**API URL:** Uses your local dev server (default `http://127.0.0.1:8000` or whatever `EXPO_PUBLIC_API_BASE_URL` you set locally).

```bash
# Both platforms
eas build --profile development

# iOS only
eas build --profile development --platform ios

# Android only
eas build --profile development --platform android

# Build for local simulator/emulator (no EAS cloud, faster)
eas build --profile development --platform ios --local
eas build --profile development --platform android --local
```

**After the build completes:**
1. Install the `.apk` (Android) or scan the QR code for ad-hoc install (iOS)
2. Start the local dev server: `npx expo start --dev-client`
3. Open the app -- it connects to your local bundler for hot reload

---

### 2. Preview Build

**What it does:** Creates a release-mode build (optimized JS bundle baked in) distributed internally. This is your staging/QA build. It points at the staging API (`https://winnow-api-cdn2d6pc5q-uc.a.run.app`). No dev client -- the app runs standalone like production, but is distributed via internal links (not the stores).

**When to use:**
- QA testing before a production release
- Sharing a near-production build with teammates or stakeholders
- Testing OTA updates via `eas update` before pushing to production
- Regression testing after major changes
- Testing push notifications (which don't work in dev client)

**API URL:** `https://winnow-api-cdn2d6pc5q-uc.a.run.app` (set in `eas.json`).

```bash
# Both platforms
eas build --profile preview

# iOS only
eas build --profile preview --platform ios

# Android only
eas build --profile preview --platform android
```

**After the build completes:**
1. Install the build on test devices via the EAS link or QR code
2. Test the full app flow against the staging API
3. Use `eas update --channel preview` to push JS-only fixes without rebuilding

---

### 3. Production Build

**What it does:** Creates a store-ready build for App Store (iOS) and Google Play (Android). The JS bundle is optimized and embedded. This is what end users download. Points at the production API.

**When to use:**
- Submitting a new version to the App Store / Google Play
- After all QA passes on the preview build
- When native code changes are needed in production (new SDK, new native module, changed permissions)

**API URL:** `https://winnow-api-cdn2d6pc5q-uc.a.run.app` (set in `eas.json`).

```bash
# Both platforms
eas build --profile production

# iOS only
eas build --profile production --platform ios

# Android only
eas build --profile production --platform android

# Auto-submit to stores after build completes
eas build --profile production --auto-submit
eas build --profile production --platform ios --auto-submit
eas build --profile production --platform android --auto-submit
```

**After the build completes:**
1. Submit to stores (if not using `--auto-submit`): see [EAS Submit](#eas-submit-commands)
2. Once the app is live, use `eas update --channel production` for JS-only hotfixes

---

## EAS Update Commands

Updates push **JavaScript-only** changes over the air (OTA) without going through the app stores. They are instant -- users get the update on next app launch. Each build profile maps to a **channel**, and each channel can receive updates.

**Channel mapping (from `eas.json` build profiles):**
| Build Profile | Channel      | Branch (default) |
|---------------|-------------|-------------------|
| development   | development | development       |
| preview       | preview     | preview           |
| production    | production  | production        |

**When to use updates (instead of a new build):**
- Bug fixes that are JS-only (no native code changes)
- Copy/text changes, styling tweaks
- Adding or modifying screens/components
- Updating API calls or business logic
- Hotfixes that need to reach users immediately

**When you CANNOT use updates (need a new build):**
- Adding/removing native modules (`expo-camera`, etc.)
- Updating `app.json` native config (icons, splash, permissions, bundle ID)
- Upgrading the Expo SDK or React Native version
- Changing native code in `ios/` or `android/` directories

---

### 1. Update Development Channel

**What it does:** Pushes a JS update to all development builds. Useful for sharing work-in-progress changes with teammates who have the dev build installed but aren't running a local dev server.

**When to use:**
- Sharing a JS change with a teammate on a dev build without them pulling code
- Testing an update flow in development before pushing to preview

```bash
# Update with auto-generated message
eas update --channel development

# Update with a descriptive message
eas update --channel development --message "Fix login screen layout"

# Update targeting a specific branch
eas update --branch development --message "Fix login screen layout"

# Update only one platform
eas update --channel development --platform ios
eas update --channel development --platform android
```

---

### 2. Update Preview Channel

**What it does:** Pushes a JS update to all preview (staging/QA) builds. This is your staging OTA pipeline -- test updates here before rolling them to production.

**When to use:**
- QA verification of a JS-only fix before production
- Iterating quickly on a staging build without rebuilding
- Testing that the OTA update mechanism works correctly

```bash
# Update with auto-generated message
eas update --channel preview

# Update with a descriptive message
eas update --channel preview --message "Fix match score display bug"

# Update targeting a specific branch
eas update --branch preview --message "Fix match score display bug"

# Update only one platform
eas update --channel preview --platform ios
eas update --channel preview --platform android
```

---

### 3. Update Production Channel

**What it does:** Pushes a JS update to all production builds (live users). This is your hotfix pipeline. Users receive the update on next app launch with no store review required.

**When to use:**
- Critical bug fix that needs to reach users immediately
- JS-only change that has been verified on preview
- Copy or styling fix in production
- Emergency hotfix

```bash
# Update with auto-generated message
eas update --channel production

# Update with a descriptive message
eas update --channel production --message "Hotfix: fix crash on profile screen"

# Update targeting a specific branch
eas update --branch production --message "Hotfix: fix crash on profile screen"

# Update only one platform
eas update --channel production --platform ios
eas update --channel production --platform android
```

**Rolling back a production update:**

```bash
# List recent updates to find the ID of the good version
eas update:list

# Roll back by republishing a previous update group
eas update:rollback --channel production
```

---

## EAS Submit Commands

Submit a completed production build to the app stores.

### iOS (App Store Connect)

Configured in `eas.json` with:
- Apple ID: `rlevi@hcpm.llc`
- Team ID: `5Q23CSC47U`
- App Store Connect App ID: `6759479359`

```bash
# Submit the latest production iOS build
eas submit --platform ios --latest

# Submit a specific build by ID
eas submit --platform ios --id <build-id>
```

### Android (Google Play)

Configured in `eas.json` with:
- Service account key: `./google-play-key.json`
- Track: `production`

```bash
# Submit the latest production Android build
eas submit --platform android --latest

# Submit a specific build by ID
eas submit --platform android --id <build-id>
```

---

## Quick Reference

### Build Commands (native changes required)

| Command | Platform | Use Case |
|---------|----------|----------|
| `eas build --profile development` | Both | Dev client for local development |
| `eas build --profile development --platform ios` | iOS | Dev client for iOS |
| `eas build --profile development --platform android` | Android | Dev client for Android |
| `eas build --profile preview` | Both | QA/staging build |
| `eas build --profile preview --platform ios` | iOS | QA build for iOS |
| `eas build --profile preview --platform android` | Android | QA build for Android |
| `eas build --profile production` | Both | Store release build |
| `eas build --profile production --platform ios` | iOS | App Store build |
| `eas build --profile production --platform android` | Android | Play Store build |
| `eas build --profile production --auto-submit` | Both | Build + auto-submit to stores |

### Update Commands (JS-only changes)

| Command | Channel | Use Case |
|---------|---------|----------|
| `eas update --channel development` | development | Push JS changes to dev builds |
| `eas update --channel preview` | preview | Push JS changes to QA builds |
| `eas update --channel production` | production | Hotfix to live users (OTA) |

### Submit Commands

| Command | Store | Use Case |
|---------|-------|----------|
| `eas submit --platform ios --latest` | App Store | Submit latest iOS build |
| `eas submit --platform android --latest` | Google Play | Submit latest Android build |

### Typical Release Workflow

```
1. Develop locally with dev build
   eas build --profile development

2. Push to preview for QA
   eas build --profile preview
   (or OTA: eas update --channel preview)

3. QA passes -> build for production
   eas build --profile production

4. Submit to stores
   eas submit --platform ios --latest
   eas submit --platform android --latest

5. Hotfix needed after release?
   eas update --channel production --message "Fix: description"
```
