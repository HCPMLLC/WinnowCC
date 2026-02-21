# Winnow LinkedIn Sourcing — Chrome Extension

Chrome Manifest V3 extension that lets recruiters source candidates from LinkedIn profiles directly into Winnow.

## Features

- **OAuth sign-in**: Authenticate with your Winnow account via Auth0 (supports LinkedIn, Google, GitHub, Microsoft, Apple)
- **One-click extraction**: Extracts name, headline, experience, education, and skills from LinkedIn profile pages
- **Preview before save**: Review extracted data before importing into Winnow
- **Job tagging**: Optionally tag imported candidates to specific job openings
- **Secure**: Session tokens stored in Chrome's extension storage; no passwords stored locally

## How It Works

1. Click the extension icon and sign in with your Winnow employer account
2. Navigate to any LinkedIn profile page (`linkedin.com/in/*`)
3. Click the extension icon again and click **Extract Profile**
4. Review the extracted data preview (name, headline, experience count, etc.)
5. Optionally select a job to tag the candidate to
6. Click **Save to Winnow** to import the profile

## Development Setup

### Prerequisites

- Chrome 88+ (Manifest V3 support)
- Winnow API running locally (`http://127.0.0.1:8000`)
- Python 3.11+ with Pillow for icon generation

### 1. Generate Icons

The manifest references PNG icons that must be generated from the SVG source:

```powershell
cd apps/chrome-extension/icons
python generate_icons.py
# Or use the API venv:
..\..\services\api\.venv\Scripts\python.exe generate_icons.py
```

This produces `icon16.png`, `icon48.png`, and `icon128.png`.

### 2. Configure Auth0 (Optional for Dev)

For OAuth sign-in, set your Auth0 credentials in `popup/popup.js`:

```javascript
const AUTH0_DOMAIN = "your-domain.us.auth0.com";
const AUTH0_CLIENT_ID = "your-client-id";
```

These should match your `NEXT_PUBLIC_AUTH0_DOMAIN` and `NEXT_PUBLIC_AUTH0_CLIENT_ID` from the web app.

**Add the extension's redirect URI to Auth0:**

1. Load the extension in Chrome (see step 3 below)
2. Note the extension ID from `chrome://extensions/`
3. In your Auth0 dashboard, add this to "Allowed Callback URLs":
   ```
   https://<YOUR-EXTENSION-ID>.chromiumapp.org/
   ```

If Auth0 is not configured, the extension falls back to manual token input for development.

### 3. Load in Chrome

1. Navigate to `chrome://extensions/`
2. Enable **Developer mode** (toggle in top-right)
3. Click **Load unpacked** and select the `apps/chrome-extension/` directory
4. The Winnow icon appears in the toolbar

### 4. Local API Override

For development against a local API, use the **Developer settings** section in the sign-in popup to set the API URL to `http://127.0.0.1:8000`. When using the manual token fallback, paste a JWT from your local Winnow session.

## Architecture

```
apps/chrome-extension/
  manifest.json                 Manifest V3 config (permissions, content scripts, icons)
  popup/
    popup.html                  Extension popup UI (3 states: sign-in, not-linkedin, extract)
    popup.js                    Popup logic: OAuth flow, extraction, API save
    popup.css                   Popup styles
  content/
    linkedin.js                 Content script injected on linkedin.com/in/* pages
  background/
    service-worker.js           Background worker for message relay
  icons/
    icon.svg                    Source icon (blue rounded rect + white W)
    icon16.png                  Toolbar icon (generated)
    icon48.png                  Extensions page icon (generated)
    icon128.png                 Web Store / install icon (generated)
    generate_icons.py           Pillow script to generate PNGs from the brand design
  STORE_LISTING.md              Chrome Web Store listing metadata and submission checklist
```

### Message Flow

```
User clicks "Extract Profile"
  -> popup.js sends message to content script via chrome.tabs.sendMessage()
  -> content/linkedin.js reads DOM and extracts profile data
  -> Returns data to popup.js
  -> User clicks "Save to Winnow"
  -> popup.js POSTs to /api/career-intelligence/source/linkedin
  -> API returns candidate_profile_id and status
```

### Auth Flow (OAuth)

```
User clicks "Sign in with Winnow"
  -> popup.js calls chrome.identity.launchWebAuthFlow() with Auth0 authorize URL
  -> Auth0 handles provider selection and authentication
  -> Callback returns authorization code to extension
  -> popup.js POSTs code to /api/auth/oauth/callback
  -> Backend returns session_token (JWT)
  -> Token stored in chrome.storage.local for future API calls
```

## Chrome Web Store Submission

See `STORE_LISTING.md` for the full submission checklist. Key steps:

1. Ensure PNG icons are generated
2. Set `AUTH0_DOMAIN` and `AUTH0_CLIENT_ID` in `popup/popup.js`
3. Register the extension's redirect URI in Auth0
4. Verify privacy policy is live at `https://winnowcc.ai/privacy/chrome-extension`
5. Capture screenshots (sign-in state, extraction preview, save confirmation)
6. Create a ZIP of the extension directory (exclude `generate_icons.py`, `icon.svg`, `STORE_LISTING.md`, `README.md`)
7. Upload to the [Chrome Web Store Developer Dashboard](https://chrome.google.com/webstore/devconsole)
8. Fill in listing details from `STORE_LISTING.md`
9. Submit for review

## Requirements

- Chrome 88+ (Manifest V3 support)
- Winnow account with employer role
- Auth0 tenant configured (or use manual token fallback for development)
