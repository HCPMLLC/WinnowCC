/**
 * Winnow Chrome Extension — Popup Logic
 *
 * States:
 *  1. signin-section — Not authenticated
 *  2. not-linkedin   — Authenticated but not on a LinkedIn profile
 *  3. extract-panel  — On a LinkedIn profile, ready to extract
 */

const $ = (id) => document.getElementById(id);

// --- Configuration ---
// These are read from the Winnow web app's public Auth0 settings.
// They are public client-side values (not secrets).
const DEFAULT_API_URL = "https://api.winnowcc.ai";
const AUTH0_DOMAIN = "dev-f21kwdkb0x1u0oqk.us.auth0.com";
const AUTH0_CLIENT_ID = "wr752tl9vqPflOZ2bmmNRKThozGLMovP";

let extractedData = null;

// --- Rate limiting ---
const EXTRACT_COOLDOWN_MS = 5000;

async function isOnCooldown() {
  const { lastExtractionTime } = await new Promise((resolve) =>
    chrome.storage.local.get(["lastExtractionTime"], resolve)
  );
  if (!lastExtractionTime) return false;
  return Date.now() - lastExtractionTime < EXTRACT_COOLDOWN_MS;
}

function startCooldown() {
  chrome.storage.local.set({ lastExtractionTime: Date.now() });
  const btn = $("btn-extract");
  btn.disabled = true;
  let remaining = Math.ceil(EXTRACT_COOLDOWN_MS / 1000);
  btn.textContent = `Please wait ${remaining}s...`;
  const interval = setInterval(() => {
    remaining--;
    if (remaining <= 0) {
      clearInterval(interval);
      btn.textContent = "Extract Profile";
      btn.disabled = false;
    } else {
      btn.textContent = `Please wait ${remaining}s...`;
    }
  }, 1000);
}

// --- Data validation ---
function validateExtractedData(data) {
  const errors = [];

  // Required: name must be non-empty string
  if (!data.name || typeof data.name !== "string" || !data.name.trim()) {
    errors.push("Name is missing");
  }

  // Required: linkedin_url must match pattern
  if (
    !data.linkedin_url ||
    typeof data.linkedin_url !== "string" ||
    !data.linkedin_url.includes("linkedin.com/in/")
  ) {
    errors.push("Invalid LinkedIn profile URL");
  }

  // Sanitize: trim and cap lengths
  if (data.name) data.name = data.name.trim().substring(0, 255);
  if (data.headline) data.headline = data.headline.trim().substring(0, 500);
  if (data.about) data.about = data.about.trim().substring(0, 5000);

  return { valid: errors.length === 0, errors };
}

// --- Storage helpers ---
async function getConfig() {
  return new Promise((resolve) =>
    chrome.storage.local.get(["apiUrl", "authToken", "userEmail"], resolve)
  );
}

async function saveConfig(apiUrl, authToken, userEmail) {
  return new Promise((resolve) =>
    chrome.storage.local.set({ apiUrl, authToken, userEmail }, resolve)
  );
}

async function clearConfig() {
  return new Promise((resolve) =>
    chrome.storage.local.remove(["apiUrl", "authToken", "userEmail"], resolve)
  );
}

// --- State management ---
function showState(state) {
  $("signin-section").classList.add("hidden");
  $("not-linkedin").classList.add("hidden");
  $("extract-panel").classList.add("hidden");
  $("connected-bar").classList.add("hidden");

  if (state === "signin") {
    $("signin-section").classList.remove("hidden");
  } else if (state === "not-linkedin") {
    $("not-linkedin").classList.remove("hidden");
    $("connected-bar").classList.remove("hidden");
  } else if (state === "extract") {
    $("extract-panel").classList.remove("hidden");
    $("connected-bar").classList.remove("hidden");
  }
}

// --- Check if on LinkedIn profile ---
async function getCurrentTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  return tab;
}

function isLinkedInProfile(url) {
  return url && url.includes("linkedin.com/in/");
}

// --- API helpers ---
function getApiUrl() {
  const override = $("api-url-override")?.value?.trim();
  return override || DEFAULT_API_URL;
}

async function apiFetch(config, path, options = {}) {
  const baseUrl = config.apiUrl.replace(/\/$/, "");
  const headers = {
    "Content-Type": "application/json",
    Authorization: `Bearer ${config.authToken}`,
    ...options.headers,
  };

  let resp;
  try {
    resp = await fetch(baseUrl + path, { ...options, headers });
  } catch (fetchErr) {
    // Network error — if using a remote URL, try local fallback
    if (!baseUrl.includes("127.0.0.1") && !baseUrl.includes("localhost")) {
      try {
        resp = await fetch("http://127.0.0.1:8000" + path, { ...options, headers });
        // Fallback worked — update stored URL so future calls go direct
        await saveConfig("http://127.0.0.1:8000", config.authToken, config.userEmail);
      } catch {
        throw new Error(`Cannot reach API at ${baseUrl} — is the server running?`);
      }
    } else {
      throw new Error(`Cannot reach API at ${baseUrl} — is the server running?`);
    }
  }

  // Handle expired/invalid tokens by clearing auth
  if (resp.status === 401) {
    await clearConfig();
    extractedData = null;
    showState("signin");
    throw new Error("Session expired. Please sign in again.");
  }

  if (!resp.ok) {
    let detail = `HTTP ${resp.status}`;
    try {
      const body = await resp.json();
      detail = body.detail || JSON.stringify(body);
    } catch {
      const text = await resp.text();
      if (text) detail += `: ${text.substring(0, 200)}`;
    }
    throw new Error(detail);
  }
  return resp.json();
}

// --- Load jobs for "Tag to Job" dropdown ---
async function loadJobs(config) {
  try {
    const me = await apiFetch(config, "/api/auth/me");
    const role = me.role || "candidate";

    let jobs = [];
    if (role === "recruiter" || role === "both") {
      jobs = await apiFetch(config, "/api/recruiter/jobs?status=active");
    } else if (role === "employer") {
      jobs = await apiFetch(config, "/api/employer/jobs?status=active");
    }

    const sel = $("job-select");
    // Clear existing options except the placeholder
    while (sel.options.length > 1) sel.remove(1);

    for (const job of jobs) {
      const opt = document.createElement("option");
      opt.value = job.id;
      let label = job.title || `Job #${job.id}`;
      if (job.client_company_name) label += ` — ${job.client_company_name}`;
      opt.textContent = label;
      sel.appendChild(opt);
    }
  } catch {
    // Silently fail — dropdown stays with placeholder only
  }
}

// --- Check if candidate already exists ---
async function checkCandidateExists(config, linkedinUrl) {
  const statusEl = $("candidate-status");
  try {
    const result = await apiFetch(
      config,
      `/api/career-intelligence/source/linkedin/check?linkedin_url=${encodeURIComponent(linkedinUrl)}`
    );
    statusEl.classList.remove("hidden");
    if (result.exists) {
      statusEl.className = "candidate-status status-existing";
      statusEl.textContent = `Existing candidate: ${result.name || "Unknown"} — will enrich profile`;
    } else {
      statusEl.className = "candidate-status status-new";
      statusEl.textContent = "New candidate";
    }
  } catch {
    statusEl.classList.add("hidden");
  }
}

// --- Init ---
async function init() {
  const config = await getConfig();

  if (!config.apiUrl || !config.authToken) {
    showState("signin");
    return;
  }

  // Show email + API URL in connected bar
  const emailLabel = config.userEmail || "Connected";
  const apiHost = config.apiUrl.replace(/^https?:\/\//, "").replace(/\/$/, "");
  $("connected-email").textContent = `${emailLabel} (${apiHost})`;

  // Allow clicking API host to change it
  $("connected-email").title = `API: ${config.apiUrl}\nClick to change`;
  $("connected-email").style.cursor = "pointer";
  $("connected-email").onclick = async () => {
    const newUrl = prompt("API URL:", config.apiUrl);
    if (newUrl && newUrl.trim() !== config.apiUrl) {
      await saveConfig(newUrl.trim(), config.authToken, config.userEmail);
      init();
    }
  };

  // Pre-load jobs for the dropdown (non-blocking)
  loadJobs(config);

  const tab = await getCurrentTab();
  if (!isLinkedInProfile(tab?.url)) {
    showState("not-linkedin");
    return;
  }

  showState("extract");

  // Restore cooldown state if still active
  const { lastExtractionTime } = await new Promise((resolve) =>
    chrome.storage.local.get(["lastExtractionTime"], resolve)
  );
  if (lastExtractionTime) {
    const elapsed = Date.now() - lastExtractionTime;
    if (elapsed < EXTRACT_COOLDOWN_MS) {
      const btn = $("btn-extract");
      btn.disabled = true;
      let remaining = Math.ceil((EXTRACT_COOLDOWN_MS - elapsed) / 1000);
      btn.textContent = `Please wait ${remaining}s...`;
      const interval = setInterval(() => {
        remaining--;
        if (remaining <= 0) {
          clearInterval(interval);
          btn.textContent = "Extract Profile";
          btn.disabled = false;
        } else {
          btn.textContent = `Please wait ${remaining}s...`;
        }
      }, 1000);
    }
  }
}

// --- OAuth Sign-in ---
$("btn-signin").addEventListener("click", async () => {
  // Check if Auth0 is configured
  if (!AUTH0_DOMAIN || !AUTH0_CLIENT_ID) {
    // Fallback: show manual token input for development
    showManualAuth();
    return;
  }

  $("btn-signin").textContent = "Signing in...";
  $("btn-signin").disabled = true;
  $("signin-error").classList.add("hidden");

  try {
    const redirectUrl = chrome.identity.getRedirectURL();
    const state = btoa(JSON.stringify({ nonce: crypto.randomUUID() }));

    const authUrl =
      `https://${AUTH0_DOMAIN}/authorize?` +
      `response_type=code&` +
      `client_id=${AUTH0_CLIENT_ID}&` +
      `redirect_uri=${encodeURIComponent(redirectUrl)}&` +
      `scope=openid%20profile%20email&` +
      `state=${encodeURIComponent(state)}`;

    const callbackUrl = await chrome.identity.launchWebAuthFlow({
      url: authUrl,
      interactive: true,
    });

    // Parse the authorization code from the callback URL
    const url = new URL(callbackUrl);
    const code = url.searchParams.get("code");
    const error = url.searchParams.get("error");

    if (error) {
      const desc = url.searchParams.get("error_description") || error;
      throw new Error(desc);
    }
    if (!code) throw new Error("No authorization code received");

    // Get API URL (default or developer override)
    const apiUrl = getApiUrl();

    // Exchange code for session token via backend
    const resp = await fetch(`${apiUrl.replace(/\/$/, "")}/api/auth/oauth/callback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        code,
        redirect_uri: redirectUrl,
      }),
    });

    if (!resp.ok) {
      const body = await resp.json().catch(() => ({}));
      throw new Error(body.detail || `Authentication failed (${resp.status})`);
    }

    const data = await resp.json();
    await saveConfig(apiUrl, data.token, data.email || "");
    init();
  } catch (err) {
    // User closing the popup is not an error
    if (err.message?.includes("canceled") || err.message?.includes("closed")) {
      // Silently ignore user cancellation
    } else {
      $("signin-error").textContent = err.message;
      $("signin-error").classList.remove("hidden");
    }
  } finally {
    $("btn-signin").innerHTML =
      '<svg class="btn-icon" viewBox="0 0 128 128" width="18" height="18">' +
      '<rect width="128" height="128" rx="20" fill="#fff"/>' +
      '<text x="64" y="88" font-family="Arial, sans-serif" font-size="72" font-weight="800" fill="#2563eb" text-anchor="middle">W</text>' +
      "</svg> Sign in with Winnow";
    $("btn-signin").disabled = false;
  }
});

// --- Manual auth fallback (for development without Auth0) ---
function showManualAuth() {
  const section = $("signin-section");
  section.innerHTML = `
    <p class="signin-text">Auth0 is not configured. Enter credentials manually for development.</p>
    <label>API URL</label>
    <input id="manual-api-url" type="url" placeholder="http://127.0.0.1:8000" value="${getApiUrl()}" />
    <label>Auth Token</label>
    <input id="manual-auth-token" type="password" placeholder="Paste your session token" />
    <button id="btn-manual-connect" class="btn btn-primary">Connect</button>
    <div id="manual-error" class="error hidden"></div>
  `;

  document.getElementById("btn-manual-connect").addEventListener("click", async () => {
    const apiUrl = document.getElementById("manual-api-url").value.trim();
    const authToken = document.getElementById("manual-auth-token").value.trim();
    const errorEl = document.getElementById("manual-error");

    if (!apiUrl || !authToken) {
      errorEl.textContent = "Both fields are required";
      errorEl.classList.remove("hidden");
      return;
    }

    try {
      await saveConfig(apiUrl, authToken, "");
      errorEl.classList.add("hidden");
      init();
    } catch (err) {
      errorEl.textContent = "Connection failed: " + err.message;
      errorEl.classList.remove("hidden");
    }
  });
}

// --- Sign out ---
$("btn-disconnect").addEventListener("click", async () => {
  await clearConfig();
  extractedData = null;
  showState("signin");
});

// --- Helper: send message to content script, injecting it first if needed ---
async function sendToContentScript(tabId, message) {
  try {
    const response = await chrome.tabs.sendMessage(tabId, message);
    return response;
  } catch (err) {
    // Content script not loaded — inject it programmatically and retry
    if (err.message?.includes("Receiving end does not exist") || err.message?.includes("Could not establish connection")) {
      await chrome.scripting.executeScript({
        target: { tabId },
        files: ["content/linkedin.js"],
      });
      // Wait a beat for the script to initialize
      await new Promise((r) => setTimeout(r, 300));
      return await chrome.tabs.sendMessage(tabId, message);
    }
    throw err;
  }
}

// --- Extract ---
$("btn-extract").addEventListener("click", async () => {
  // Rate limiting: check cooldown
  if (await isOnCooldown()) {
    $("save-result").textContent = "Please wait a few seconds before extracting again.";
    $("save-result").className = "result failure";
    $("save-result").classList.remove("hidden");
    return;
  }

  const tab = await getCurrentTab();

  $("btn-extract").textContent = "Scrolling & Extracting...";
  $("btn-extract").disabled = true;

  try {
    const response = await sendToContentScript(tab.id, {
      action: "extractProfile",
    });

    if (!response || !response.success) {
      throw new Error(response?.error || "Extraction failed");
    }

    extractedData = response.data;

    // Start cooldown after successful extraction
    startCooldown();

    // Show preview
    $("preview-name").textContent = extractedData.name || "Unknown";
    $("preview-headline").textContent = extractedData.headline || "";
    $("preview-location").textContent = extractedData.location || "";
    $("preview-stats").textContent = [
      extractedData.experience?.length
        ? `${extractedData.experience.length} exp`
        : null,
      extractedData.education?.length
        ? `${extractedData.education.length} edu`
        : null,
      extractedData.skills?.length
        ? `${extractedData.skills.length} skills`
        : null,
      extractedData.certifications?.length
        ? `${extractedData.certifications.length} certs`
        : null,
      extractedData.volunteer?.length
        ? `${extractedData.volunteer.length} volunteer`
        : null,
      extractedData.projects?.length
        ? `${extractedData.projects.length} projects`
        : null,
    ]
      .filter(Boolean)
      .join(" \u00B7 ");

    // About snippet
    $("preview-about").textContent = extractedData.about
      ? extractedData.about.substring(0, 120) + (extractedData.about.length > 120 ? "..." : "")
      : "";
    $("preview-about").classList.toggle("hidden", !extractedData.about);

    // Open to Work badge
    $("preview-otw").classList.toggle("hidden", !extractedData.open_to_work);

    // Low quality warning
    if (extractedData._extraction_quality != null && extractedData._extraction_quality < 0.3) {
      $("save-result").textContent =
        `Warning: Low extraction quality (${Math.round(extractedData._extraction_quality * 100)}%). Some profile sections may not have loaded. Try scrolling down on the profile first.`;
      $("save-result").className = "result failure";
      $("save-result").classList.remove("hidden");
    } else {
      $("save-result").classList.add("hidden");
    }

    $("profile-preview").classList.remove("hidden");
    $("save-section").classList.remove("hidden");

    // Check if candidate already exists
    if (extractedData.linkedin_url) {
      const config = await getConfig();
      checkCandidateExists(config, extractedData.linkedin_url);
    }

    // Show debug info if present
    if (extractedData._debug) {
      $("debug-panel").classList.remove("hidden");
      $("debug-content").textContent = JSON.stringify(
        { ...extractedData._debug, _version: extractedData._version, _extraction_quality: extractedData._extraction_quality },
        null,
        2
      );
    }
  } catch (err) {
    $("save-result").textContent = "Extraction failed: " + err.message;
    $("save-result").className = "result failure";
    $("save-result").classList.remove("hidden");
  } finally {
    // Don't reset button text here — cooldown timer handles it
    if (!await isOnCooldown()) {
      $("btn-extract").textContent = "Extract Profile";
      $("btn-extract").disabled = false;
    }
  }
});

// --- Save to Winnow ---
$("btn-save").addEventListener("click", async () => {
  if (!extractedData) return;

  // Validate before sending
  const { valid, errors } = validateExtractedData(extractedData);
  if (!valid) {
    $("save-result").textContent = "Validation failed: " + errors.join(", ");
    $("save-result").className = "result failure";
    $("save-result").classList.remove("hidden");
    return;
  }

  const config = await getConfig();
  const jobId = $("job-select").value || undefined;

  $("btn-save").textContent = "Saving...";
  $("btn-save").disabled = true;

  try {
    const payload = { ...extractedData };
    delete payload._debug; // Strip debug info before saving

    // Map underscore fields to API-expected names
    if (payload._version) {
      payload.extraction_version = payload._version;
      delete payload._version;
    }
    if (payload._extraction_quality != null) {
      payload.extraction_quality = payload._extraction_quality;
      delete payload._extraction_quality;
    }

    if (jobId) payload.tag_job_id = parseInt(jobId, 10);

    const result = await apiFetch(
      config,
      "/api/career-intelligence/source/linkedin",
      { method: "POST", body: JSON.stringify(payload) }
    );

    let msg = `Saved! Profile ID: ${result.candidate_profile_id} (${result.status})`;
    if (result.pipeline_candidate_id) {
      msg += ` \u2014 Pipeline #${result.pipeline_candidate_id}`;
    }
    $("save-result").textContent = msg;
    $("save-result").className = "result success";
    $("save-result").classList.remove("hidden");
  } catch (err) {
    $("save-result").textContent = "Save failed: " + err.message;
    $("save-result").className = "result failure";
    $("save-result").classList.remove("hidden");
  } finally {
    $("btn-save").textContent = "Save to Winnow";
    $("btn-save").disabled = false;
  }
});

// --- Dev login link ---
$("btn-dev-login")?.addEventListener("click", (e) => {
  e.preventDefault();
  showManualAuth();
});

// --- Boot ---
init();
