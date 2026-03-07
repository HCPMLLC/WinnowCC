# Winnow Feature Testing Guide

**Tester:** rlevi@hcpm.llc
**Date:** March 4, 2026
**Scope:** All features delivered in the last 5 days
**Method:** Using ADMIN_TEST_EMAILS billing bypass (PROMPT79)

---

## BEFORE YOU START: Setup (Do This Once)

### Step 1: Add Your Email to the Billing Bypass List

This makes your account act like a Pro subscriber (the highest tier) so you can test everything without paying.

**Method A — Using the .env file (requires restart):**
1. Open the file `services/api/.env` in your code editor (it should already be open)
2. Look for a line that starts with `ADMIN_TEST_EMAILS=`
3. If it exists, make sure your email is there: `ADMIN_TEST_EMAILS=rlevi@hcpm.llc`
4. If it does NOT exist, add this new line anywhere in the file: `ADMIN_TEST_EMAILS=rlevi@hcpm.llc`
5. Save the file
6. Restart the API server (close and re-run `start-dev.ps1`)

**Method B — Using the Admin Settings page (no restart needed):**
1. Open your web browser
2. Go to `http://localhost:3000/admin/settings`
3. Scroll down to the section called **"Admin Test Emails"**
4. In the text box, type: `rlevi@hcpm.llc`
5. Click the **Add** button
6. You should see your email appear in the list below
7. This takes effect immediately — no restart needed

### Step 2: Start the Dev Environment

1. Open **PowerShell** (click the Windows Start button, type "PowerShell", click it)
2. Type this command and press Enter:
   ```
   cd C:\Users\ronle\Documents\resumematch
   ```
3. Type this command and press Enter:
   ```
   .\start-dev.ps1
   ```
4. Wait about 30 seconds for everything to start up
5. Several windows will open — that's normal. Don't close them.

### Step 3: Open the App

1. Open your web browser (Chrome recommended)
2. Go to `http://localhost:3000`
3. Log in with your email `rlevi@hcpm.llc` and your password

---

## TEST 1: Admin Test Email UI (PROMPT79)

**What this is:** A page where admins can add or remove email addresses that bypass billing limits.

**Steps:**
1. In your browser, go to `http://localhost:3000/admin/settings`
2. Look for the section called **"Admin Test Emails"**
3. You should see:
   - A list of emails that currently bypass billing (your email should be here)
   - A text box to add new emails
   - A **Remove** button next to each email
4. **Test adding:** Type `testuser@example.com` in the text box and click **Add**
   - It should appear in the list immediately
5. **Test removing:** Click the red **Remove** button next to `testuser@example.com`
   - It should disappear from the list
6. **Test duplicate:** Try adding `rlevi@hcpm.llc` again — it should show an error saying the email already exists

**Pass if:** You can add and remove emails, duplicates are rejected, and the list updates without refreshing the page.

---

## TEST 2: "Why This Job?" Match Explanations

**What this is:** Every job match now shows a one-sentence explanation of why it matched you.

**Steps:**
1. In your browser, go to `http://localhost:3000/matches`
2. You should see a list of job matches
3. Look at any match card — there should be a short sentence in green/emerald text explaining WHY this job matched your profile
   - Example: "Matched because of your Python and AWS experience, plus this role offers remote flexibility"
4. Click on a match to open the details page
5. The explanation should also appear on the detail page

**Pass if:** Each match shows a personalized explanation sentence.

---

## TEST 3: Application Status Predictor

**What this is:** AI predicts the status of a job application you've submitted.

**Steps:**
1. Go to `http://localhost:3000/matches`
2. Click on any match to open it
3. Find the **Application Status** section on the match detail page
4. Change the status to **"Applied"** (if it isn't already)
5. Look for a button that says something like **"Predict Status"** or **"Get Prediction"**
6. Click it
7. Wait a few seconds — the AI will analyze your application and predict what's likely happening
8. You should see a prediction with suggested next steps

**Pass if:** Clicking the predict button returns an AI-generated status prediction with next steps.

---

## TEST 4: Gap Closure Recommendations

**What this is:** AI analyzes skill gaps between your profile and a job, then recommends courses/certifications to close the gaps.

**Steps:**
1. Go to `http://localhost:3000/matches`
2. Click on any match to open it
3. Look for a section or button that says **"Recommend Learning Path"** or **"Gap Recommendations"**
4. Click it
5. The first click may show "Processing..." or "Pending" — this is normal (it's being generated in the background)
6. Wait 5-10 seconds, then refresh the page or wait for it to update automatically
7. You should see:
   - Courses to take
   - Certifications to earn
   - Portfolio project ideas
   - Time estimates
   - Quick wins you can do right away

**Pass if:** Recommendations appear with actionable learning plans after a short wait.

---

## TEST 5: Rejection Feedback Interpreter

**What this is:** If you get rejected from a job, you can paste the rejection email and get AI-powered feedback.

**Steps:**
1. Go to `http://localhost:3000/matches`
2. Click on any match to open it
3. Change the application status to **"Rejected"**
4. A new section should appear — something like **"Interpret Rejection"** or **"Rejection Feedback"**
5. You'll see a text box where you can paste a rejection email
6. Paste this sample text:
   ```
   Thank you for your interest in the Software Engineer position. After careful consideration, we've decided to move forward with other candidates whose experience more closely aligns with our current needs. We encourage you to apply for future openings.
   ```
7. Click the submit/analyze button
8. Wait 5-10 seconds for processing
9. You should see:
   - An interpretation of what the rejection really means
   - Your strengths they likely noticed
   - Probable reasons for rejection
   - Suggested next steps
   - Encouragement
   - Similar roles to consider

**Pass if:** The AI provides a thoughtful analysis of the rejection with actionable next steps.

---

## TEST 6: Company Culture Summary

**What this is:** Each job listing now has an AI-generated summary of the company's culture.

**Steps:**
1. Go to `http://localhost:3000/matches`
2. Click on any match to open it
3. Look for an expandable section called **"Culture Summary"** or **"Company Culture"**
4. Click to expand it
5. You should see:
   - Work style (collaborative, independent, etc.)
   - Pace (fast-paced startup, steady corporate, etc.)
   - Remote culture info
   - Company values
   - Positive signals (green flags)
   - Things to watch for (yellow flags)

**Pass if:** The culture summary card appears and shows meaningful culture information from the job posting.

---

## TEST 7: Application Email Drafter

**What this is:** AI generates a professional introduction email you can send when applying.

**Steps:**
1. Go to `http://localhost:3000/matches`
2. Click on any match to open it
3. Look for a button that says **"Draft Introduction Email"** or **"Email Draft"**
4. Click it
5. A modal (popup window) should appear with a professionally written email
6. The email should reference your specific skills and the specific job
7. Look for a **Copy** button — click it to copy the email to your clipboard
8. Look for a **Regenerate** button — click it to get a different version

**Pass if:** A professional email is generated, the Copy button works, and Regenerate creates a new version.

---

## TEST 8: Salary Negotiation Coach

**What this is:** If you receive a job offer, AI gives you negotiation advice and counter-offer scripts.

**Steps:**
1. Go to `http://localhost:3000/matches`
2. Click on any match to open it
3. Change the application status to **"Offer"**
4. Look for a button that says **"Get Negotiation Advice"** or **"Salary Coach"**
5. Click it
6. You should see:
   - Negotiation strategies tailored to the offer
   - Counter-offer script suggestions
   - Alternative things to ask for (more PTO, signing bonus, remote days, etc.)
   - Analysis based on the salary range, your experience, and the market

**Note:** This is a **Pro-only** feature. Because your email is in ADMIN_TEST_EMAILS, you can access it. Without the bypass, free/starter users would see an upgrade prompt.

**Pass if:** Negotiation advice appears with specific strategies and scripts.

---

## TEST 9: Email-to-Job Upload (PROMPT78)

**What this is:** Employers can email a job description file and it automatically gets parsed and added as a draft job.

**Steps:**
1. You need to test this as an **employer**. Since there's no role-switcher in the app, you need a separate employer account.
   - Option A: If you already have an employer account, log in with that email
   - Option B: Open a **private/incognito browser window** (Ctrl+Shift+N in Chrome), go to `http://localhost:3000/login`, click **Sign Up**, choose **Employer** as your role, and complete onboarding
   - **Important:** If you create a new employer account, add that new email to the Admin Test Emails list (see Step 1 above) so it also bypasses billing
2. Create a simple Word document (.docx) with a job description (title, company, requirements, salary, etc.)
3. Send an email with that .docx file attached to: `upload@jobs.winnowcc.ai`
   - Send it FROM the email address you used for your employer account
4. Check your email inbox — you should receive:
   - First: An **acknowledgment email** saying your job is being processed
   - Then (after 30-60 seconds): A **completion email** saying your job was parsed successfully
5. Go to `http://localhost:3000/employer/jobs` — you should see a new **draft** job posting created from your email

**Note:** This only works if the SendGrid email integration is configured. If you're testing locally without SendGrid, you can skip this test.

**Pass if:** The emailed job file gets parsed and appears as a draft job in the employer dashboard.

---

## TEST 10: Cover Letter Billing Limits

**What this is:** Cover letter generation now has its own billing counter separate from tailored resumes.

**Steps:**
1. Log in as a candidate at `http://localhost:3000`
2. Go to `http://localhost:3000/matches`
3. Click on any match to open it
4. Look for buttons to **generate a tailored resume** and/or **generate a cover letter**
5. Click the button to generate both
6. Go to `http://localhost:3000/settings`
7. Look at the **Usage** section — you should see separate counters for:
   - Tailored resumes used
   - Cover letters used
8. Because your email is in ADMIN_TEST_EMAILS, both limits should show as very high (9,999) or unlimited

**Pass if:** Cover letters have their own usage counter separate from tailored resumes, and both show on the settings page.

---

## TEST 11: Bulk ZIP Upload (10K Scale)

**What this is:** Recruiters can now upload ZIP files with up to 10,000 resumes at once.

**Steps:**
1. You need to test this as a **recruiter**. Open a **private/incognito browser window**, go to `http://localhost:3000/login`, click **Sign Up**, choose **Recruiter** as your role, and complete onboarding
   - Add this new recruiter email to Admin Test Emails so it bypasses billing
2. Create a ZIP file with several PDF or DOCX resume files inside (even 3-5 files is enough to test the flow)
3. Navigate to the candidates upload page (look for **Candidates** in the recruiter nav bar, then find an **Upload** or **Import** button)
4. Select your ZIP file
5. You should see:
   - A progress bar showing upload status
   - Queue position information
   - Estimated start and finish times
   - Row counts (not individual file names)
6. Wait for processing to complete
7. The imported resumes should appear in your candidate list

**Pass if:** ZIP upload shows progress with queue position and time estimates, and resumes appear after processing.

---

## TEST 12: Admin MFA Toggle

**What this is:** Admins can turn MFA (multi-factor authentication) on or off for any user.

**Steps:**
1. Open the **Swagger API docs** at `http://localhost:8000/docs`
2. Scroll down to find the endpoint: **POST /api/auth/admin-set-mfa**
3. Click on it to expand it
4. Click the **Try it out** button
5. In the **X-Admin-Token** header field, enter: `dev-admin-token`
6. In the request body, enter:
   ```json
   {
     "email": "rlevi@hcpm.llc",
     "mfa_required": true
   }
   ```
7. Click **Execute**
8. You should get a **200 OK** response confirming MFA was enabled
9. Now test disabling it — change `"mfa_required": true` to `"mfa_required": false` and click **Execute** again
10. You should get a **200 OK** response confirming MFA was disabled

**Pass if:** The endpoint returns 200 for both enabling and disabling MFA, and changes take effect on next login.

---

## TEST 13: Queue Monitor Improvements

**What this is:** The admin queue monitor now groups errors by category and shows actual error messages.

**Steps:**
1. In your browser, go to `http://localhost:3000/admin/support/queues`
2. You should see a list of all job queues: default, parse, match, tailor, embed, ingest
3. Each queue should show:
   - Number of jobs waiting
   - Number of jobs being processed
   - Number of failed jobs
4. If there are any failed jobs, click on a queue to see the failures
5. Failed jobs should now be **grouped by error type** (instead of a flat list)
6. Each error group should show the **actual error message** (not just "failed")

**Pass if:** Queue page loads, shows all queues, and failed jobs are grouped by error category with real error messages.

---

## TEST 14: Skeleton Loaders (Performance)

**What this is:** Pages now show gray animated placeholder shapes while content loads, instead of a blank screen.

**Steps:**
1. Go to `http://localhost:3000/dashboard`
2. Press **Ctrl+Shift+R** (this does a hard refresh, clearing the cache)
3. Watch the page load — you should briefly see gray rectangular shapes that pulse/shimmer before the real content appears
4. Do the same for:
   - `http://localhost:3000/matches` (hard refresh)
   - `http://localhost:3000/profile` (hard refresh)
5. The gray shapes should match the layout of the real content (cards, text lines, etc.)

**Note:** If your internet and computer are fast, the skeleton loaders may appear for less than a second. Try throttling your network in Chrome DevTools (F12 > Network tab > change "No throttling" to "Slow 3G") to see them more clearly.

**Pass if:** Gray animated placeholder shapes appear briefly before real content loads on dashboard, matches, and profile pages.

---

## TEST 15: Sieve Chat Streaming

**What this is:** The AI chat assistant (Sieve) now streams responses word-by-word instead of waiting for the full answer.

**Steps:**
1. Go to any page in the app while logged in
2. Look for a **chat bubble icon** in the bottom-right corner of the screen
3. Click it to open the Sieve chat
4. Type a question like: "What jobs match my skills?" and press Enter
5. Watch the response — it should appear **word by word** (like watching someone type), not all at once
6. Try another question: "Tell me about my career trajectory"
7. Again, words should stream in gradually

**Pass if:** Sieve responses appear incrementally (word by word) instead of all at once after a delay.

---

## TEST 16: Faster Dashboard Loading

**What this is:** The dashboard now loads multiple data sections at the same time instead of one after another.

**Steps:**
1. Go to `http://localhost:3000/dashboard`
2. Press **Ctrl+Shift+R** to hard refresh
3. Watch how the page loads — all sections (match count, recent matches, recommendations, usage stats) should appear at roughly the same time
4. Previously, sections loaded one by one from top to bottom. Now they should all pop in together.

**Pass if:** Dashboard sections load in parallel (roughly at the same time) rather than sequentially.

---

## TEST 17: Rate Limiting (Security)

**What this is:** Login attempts are now rate-limited to prevent brute-force attacks.

**Steps:**
1. Go to `http://localhost:3000/login`
2. Enter your email: `rlevi@hcpm.llc`
3. Enter a WRONG password (e.g., "wrongpassword123")
4. Click **Log In** — you should see "Invalid email or password"
5. Repeat this 10-12 times quickly (wrong password each time)
6. After about 10 attempts, you should see a different error: **"Too many requests"** or a **429 error**
7. Wait about 1 minute, then try again with your correct password — it should work

**Pass if:** After 10+ failed login attempts, the system blocks further attempts with a "Too many requests" message.

---

## TEST 18: Security Headers

**What this is:** API responses now include security headers to protect against common web attacks.

**Steps:**
1. Open Chrome and go to `http://localhost:3000`
2. Press **F12** to open Developer Tools
3. Click the **Network** tab at the top of the Developer Tools panel
4. Refresh the page (press F5)
5. In the Network tab, you'll see a list of files being loaded. Click on any one that goes to `localhost:8000` (the API)
6. On the right side, click the **Headers** tab
7. Scroll down to **Response Headers** and look for:
   - `X-Content-Type-Options: nosniff` (should be present)
   - `X-Frame-Options: DENY` (should be present)
   - `X-XSS-Protection: 1; mode=block` (should be present)

**Pass if:** All three security headers are present in API responses.

---

## TEST 19: Mobile App — Candidate Match Features (9 new cards)

**What this is:** The mobile app now shows all the same AI features that the web app has for job matches.

**Steps:**
1. Open the **Expo Go** app on your phone
2. Scan the QR code shown in the terminal where `start-dev.ps1` is running (or enter the URL manually)
3. Log in with your `rlevi@hcpm.llc` account
4. Tap **Matches** in the bottom tab bar
5. Tap on any match to open the detail screen
6. Scroll down — you should see these new cards/sections:
   - **Match Explanation** — one-sentence "why this job" text
   - **Status Prediction** — AI prediction for applied jobs
   - **Interview Prep** — preparation tips panel
   - **Rejection Feedback** — available if status is "rejected"
   - **Culture Summary** — expandable company culture card
   - **Gap Recommendations** — learning path suggestions
   - **Enhancement Suggestions** — profile improvement tips
   - **Email Draft** — tap to generate introduction email
   - **Salary Coach** — tap to get negotiation advice (for "offer" status)
7. Tap on each card to make sure it expands/loads without crashing

**Pass if:** All 9 feature cards appear on the match detail screen and can be tapped without crashing.

---

## TEST 20: Mobile App — Employer Features

**What this is:** The mobile app now has compliance reporting, analytics, and distribution management for employers.

**Steps:**
1. You need an employer account on mobile. In the Expo Go app, log out and sign up as an **Employer** (or log in with an existing employer account)
2. After logging in, you should see the employer tab bar at the bottom: Dashboard, Jobs, Candidates, Pipeline, Settings
3. Look for these new screens (may be accessible from the dashboard or as tabs):
   - **Compliance Reporting** — shows compliance status and logs
   - **Analytics Funnel** — shows hiring funnel visualization
   - **Distribution Management** — manage where jobs are posted
4. Tap each one to verify it loads without crashing

**Pass if:** All three employer screens load and display content on mobile.

---

## TEST 21: Mobile App — Recruiter Features

**What this is:** The mobile app now has outreach sequence management and a CRM migration tool for recruiters.

**Steps:**
1. In the Expo Go app, log out and sign up as a **Recruiter** (or log in with an existing recruiter account)
2. After logging in, you should see the recruiter tab bar: Dashboard, Pipeline, Jobs, Clients, Settings
3. Look for these new screens:
   - **Outreach Sequences** — manage multi-step outreach campaigns
   - **CRM Migration** — tool to import data from other CRM systems
4. Tap each one to verify it loads without crashing

**Pass if:** Both recruiter screens load and display content on mobile.

---

## TEST 22: Alembic Migrations (Infrastructure)

**What this is:** A fix for a migration error that was blocking production deployments.

**Steps:**
1. Open **PowerShell**
2. Run these commands:
   ```
   cd C:\Users\ronle\Documents\resumematch\services\api
   .\.venv\Scripts\activate
   alembic upgrade head
   ```
3. The command should complete without errors
4. You should see messages like "Running upgrade..." for each migration
5. It should NOT show any "circular dependency" or "cycle" errors

**Pass if:** `alembic upgrade head` completes successfully with no errors.

---

## TEST 23: RQ Scheduler Auto-Start

**What this is:** The dev startup script now automatically starts the job scheduler (previously had to be started manually).

**Steps:**
1. Close all terminal windows
2. Open a fresh **PowerShell** window
3. Run:
   ```
   cd C:\Users\ronle\Documents\resumematch
   .\start-dev.ps1
   ```
4. Count the windows that open — you should see separate windows for:
   - Infrastructure (Docker)
   - API server
   - Worker
   - **Scheduler** (this is the new one)
   - Web app
5. The Scheduler window should show messages about starting up and listening for scheduled tasks

**Pass if:** The scheduler starts automatically as part of `start-dev.ps1` without needing a separate manual command.

---

## QUICK VERIFICATION: Is Billing Bypass Working?

If you're unsure whether ADMIN_TEST_EMAILS is working for your account:

1. Go to `http://localhost:3000/settings`
2. Look at your plan information — your usage limits should show very high numbers (9,999) or "Unlimited"
3. Or open `http://localhost:8000/docs`, find `GET /api/billing/status`, click **Try it out**, and click **Execute**
4. In the response, look for `"tier": "pro"` — this confirms the bypass is active

---

## RESULTS SUMMARY

| # | Feature | Pass / Fail | Notes |
|---|---------|-------------|-------|
| 1 | Admin Test Email UI (PROMPT79) | | |
| 2 | "Why This Job?" Explanations | | |
| 3 | Application Status Predictor | | |
| 4 | Gap Closure Recommendations | | |
| 5 | Rejection Feedback Interpreter | | |
| 6 | Company Culture Summary | | |
| 7 | Application Email Drafter | | |
| 8 | Salary Negotiation Coach | | |
| 9 | Email-to-Job Upload (PROMPT78) | | |
| 10 | Cover Letter Billing Limits | | |
| 11 | Bulk ZIP Upload (10K Scale) | | |
| 12 | Admin MFA Toggle | | |
| 13 | Queue Monitor Improvements | | |
| 14 | Skeleton Loaders | | |
| 15 | Sieve Chat Streaming | | |
| 16 | Faster Dashboard Loading | | |
| 17 | Rate Limiting | | |
| 18 | Security Headers | | |
| 19 | Mobile — Candidate Match Cards | | |
| 20 | Mobile — Employer Features | | |
| 21 | Mobile — Recruiter Features | | |
| 22 | Alembic Migrations | | |
| 23 | RQ Scheduler Auto-Start | | |

**Tester Signature:** ___________________________
**Date Completed:** ___________________________
