# PROMPT59_TOS_n_PP.md

Read SPEC.md, ARCHITECTURE.md, CLAUDE.md, and PROMPT27 (App Store Submission) before making changes.

## Purpose

Replace the plain, unstyled Privacy Policy and Terms of Service pages with professionally branded, fully styled versions that match Winnow's visual identity. The new pages include a dark gradient header banner, sticky sidebar table of contents, a clean card layout, a third-party services table, and a highlighted contact box. Content has been expanded to be more legally complete — covering AI-generated content disclaimers, CCPA/GDPR rights references, governing law (Texas), and limitation of liability language.

---

## Triggers — When to Use This Prompt

- The existing Privacy Policy or Terms of Service pages look plain or "unprofessional"
- You are preparing for App Store submission and need polished legal pages at live URLs
- You want to improve trust signals for candidates, employers, or recruiters visiting the site
- The legal content needs to be updated or expanded

---

## What Already Exists (DO NOT recreate)

1. **Privacy Policy page:** `apps/web/app/privacy/page.tsx` — exists but uses plain inline styles with no branding
2. **Terms of Service page:** `apps/web/app/terms/page.tsx` — exists but uses plain inline styles with no branding
3. **Routes are already registered** — `/privacy` and `/terms` are live once the web app is running

---

## What You Will Build

| File | Action | Description |
|------|--------|-------------|
| `apps/web/app/privacy/page.tsx` | **REPLACE** | Fully styled Privacy Policy with sidebar TOC, services table, branded header |
| `apps/web/app/terms/page.tsx` | **REPLACE** | Fully styled Terms of Service with sidebar TOC, expanded legal sections, branded header |

No new routes, no new dependencies, no database changes required.

---

# PART 1 — PRIVACY POLICY PAGE

### 1.1 Replace the Privacy Policy file

**File to edit:**
```
apps/web/app/privacy/page.tsx
```

**How to open it in Cursor:**
1. Open Cursor
2. In the left sidebar file tree, click: `apps` → `web` → `app` → `privacy` → `page.tsx`
3. Press `Ctrl+A` to select all existing content
4. Delete it and paste the full replacement below

**Full file content — paste this exactly:**

```tsx
export const metadata = {
  title: 'Privacy Policy – Winnow Career Concierge',
  description: 'How Winnow collects, uses, and protects your personal information.',
};

const sections = [
  'Information We Collect',
  'How We Use Your Information',
  'Data Storage & Security',
  'Third-Party Services',
  'Data Retention & Deletion',
  'Your Rights',
  "Children's Privacy",
  'Changes to This Policy',
  'Contact Us',
];

export default function PrivacyPage() {
  return (
    <div style={{ fontFamily: 'Inter, system-ui, sans-serif', color: '#1a1a2e', background: '#f8f9fc', minHeight: '100vh' }}>
      {/* Header Banner */}
      <div style={{ background: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 100%)', padding: '60px 20px', textAlign: 'center' }}>
        <p style={{ color: '#a78bfa', fontSize: 14, fontWeight: 600, letterSpacing: 2, textTransform: 'uppercase', marginBottom: 12 }}>Legal</p>
        <h1 style={{ color: '#ffffff', fontSize: 40, fontWeight: 700, margin: '0 0 16px' }}>Privacy Policy</h1>
        <p style={{ color: '#94a3b8', fontSize: 16, margin: 0 }}>Last updated: February 2026 &nbsp;·&nbsp; Effective: February 2026</p>
      </div>

      <div style={{ maxWidth: 1100, margin: '0 auto', padding: '60px 20px', display: 'flex', gap: 60, alignItems: 'flex-start' }}>
        {/* Sidebar TOC */}
        <nav style={{ width: 220, flexShrink: 0, position: 'sticky', top: 40 }}>
          <p style={{ fontSize: 11, fontWeight: 700, letterSpacing: 2, textTransform: 'uppercase', color: '#94a3b8', marginBottom: 16 }}>On This Page</p>
          <ul style={{ listStyle: 'none', margin: 0, padding: 0 }}>
            {sections.map((s) => (
              <li key={s} style={{ marginBottom: 10 }}>
                <a
                  href={`#${s.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`}
                  style={{ fontSize: 14, color: '#6366f1', textDecoration: 'none', lineHeight: 1.5 }}
                >
                  {s}
                </a>
              </li>
            ))}
          </ul>
          <div style={{ marginTop: 32, padding: '20px', background: '#fff', borderRadius: 12, border: '1px solid #e2e8f0' }}>
            <p style={{ fontSize: 13, fontWeight: 600, margin: '0 0 8px', color: '#1a1a2e' }}>Questions?</p>
            <p style={{ fontSize: 13, color: '#64748b', margin: '0 0 12px' }}>We're happy to explain anything.</p>
            <a href="mailto:privacy@winnowcc.ai" style={{ fontSize: 13, color: '#6366f1', fontWeight: 600 }}>
              privacy@winnowcc.ai
            </a>
          </div>
        </nav>

        {/* Main Content */}
        <main style={{ flex: 1, maxWidth: 720 }}>
          <div style={{ background: '#fff', borderRadius: 16, border: '1px solid #e2e8f0', padding: '48px 56px' }}>
            <p style={{ fontSize: 16, color: '#475569', lineHeight: 1.8, marginTop: 0 }}>
              <strong>Winnow Career Concierge</strong> ("we", "our", "us") operates the Winnow platform at{' '}
              <a href="https://winnowcc.ai" style={{ color: '#6366f1' }}>winnowcc.ai</a> and our mobile app.
              This policy explains what data we collect, why we collect it, and how we protect it.
            </p>

            <Section id="information-we-collect" title="Information We Collect">
              <p><strong>Account information:</strong> Your name, email address, and password when you register.</p>
              <p><strong>Resume &amp; profile data:</strong> Resume files you upload (PDF/DOCX) and the professional data extracted from them — work experience, education, skills, and contact details.</p>
              <p><strong>Job preferences:</strong> Target roles, preferred locations, salary expectations, and remote work preferences.</p>
              <p><strong>Usage data:</strong> Pages visited, features used, and interaction patterns — used to improve the platform.</p>
              <p><strong>Device information:</strong> Device type, OS, and app version for troubleshooting.</p>
            </Section>

            <Section id="how-we-use-your-information" title="How We Use Your Information">
              <ul>
                <li>Match you with relevant job opportunities using our AI scoring engine</li>
                <li>Generate tailored, ATS-optimized resumes and cover letters</li>
                <li>Provide Interview Probability Scores and dashboard analytics</li>
                <li>Improve our matching algorithms and platform quality</li>
                <li>Send transactional emails (job alerts, account notices) — never spam</li>
              </ul>
            </Section>

            <Section id="data-storage-&-security" title="Data Storage & Security">
              <p>
                Your data is stored on <strong>Google Cloud Platform</strong> with encryption at rest (AES-256)
                and in transit (TLS 1.2+). Resume files are stored in Google Cloud Storage with restricted
                access controls. We never log raw resume text in application logs.
              </p>
            </Section>

            <Section id="third-party-services" title="Third-Party Services">
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
                <thead>
                  <tr style={{ background: '#f8f9fc' }}>
                    <th style={{ padding: '10px 16px', textAlign: 'left', border: '1px solid #e2e8f0', color: '#475569' }}>Service</th>
                    <th style={{ padding: '10px 16px', textAlign: 'left', border: '1px solid #e2e8f0', color: '#475569' }}>Purpose</th>
                  </tr>
                </thead>
                <tbody>
                  {[
                    ['Anthropic (Claude AI)', 'Resume parsing, job matching, and resume generation'],
                    ['Stripe', 'Payment processing — we never store card details'],
                    ['Auth0', 'Secure authentication and OAuth login'],
                    ['Google Cloud Platform', 'Infrastructure, storage, and compute'],
                    ['Sentry', 'Error tracking — personal data is scrubbed'],
                    ['PostHog', 'Anonymous product analytics'],
                  ].map(([name, purpose]) => (
                    <tr key={name}>
                      <td style={{ padding: '10px 16px', border: '1px solid #e2e8f0', fontWeight: 600 }}>{name}</td>
                      <td style={{ padding: '10px 16px', border: '1px solid #e2e8f0', color: '#475569' }}>{purpose}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </Section>

            <Section id="data-retention-&-deletion" title="Data Retention & Deletion">
              <p>
                Your data is retained while your account is active. You may export all your data or permanently
                delete your account at any time from <strong>Settings → Account</strong>. Account deletion removes
                all stored data — resumes, profiles, matches, and generated content — within 30 days.
              </p>
            </Section>

            <Section id="your-rights" title="Your Rights">
              <p>
                You have the right to <strong>access</strong> your data (via data export), <strong>correct</strong> it
                (via profile editing), <strong>delete</strong> it (via account deletion), and <strong>opt out</strong> of
                analytics tracking. California residents may have additional rights under CCPA. EU residents may have
                rights under GDPR. Contact us to exercise any of these rights.
              </p>
            </Section>

            <Section id="children's-privacy" title="Children's Privacy">
              <p>
                Winnow is not intended for users under 16. We do not knowingly collect data from minors.
                If you believe a minor has provided us data, please contact us immediately.
              </p>
            </Section>

            <Section id="changes-to-this-policy" title="Changes to This Policy">
              <p>
                We may update this policy as the platform evolves. When we make material changes, we'll notify
                you by email or an in-app notice. The "Last updated" date at the top will always reflect the
                current version.
              </p>
            </Section>

            <Section id="contact-us" title="Contact Us">
              <div style={{ background: '#f0f0ff', borderRadius: 12, padding: 24, border: '1px solid #c7d2fe' }}>
                <p style={{ margin: '0 0 8px' }}><strong>Winnow Career Concierge</strong></p>
                <p style={{ margin: '0 0 4px', color: '#475569' }}>
                  Privacy inquiries:{' '}
                  <a href="mailto:privacy@winnowcc.ai" style={{ color: '#6366f1' }}>privacy@winnowcc.ai</a>
                </p>
                <p style={{ margin: 0, color: '#475569' }}>
                  General:{' '}
                  <a href="mailto:hello@winnowcc.ai" style={{ color: '#6366f1' }}>hello@winnowcc.ai</a>
                </p>
              </div>
            </Section>
          </div>
        </main>
      </div>
    </div>
  );
}

function Section({ id, title, children }: { id: string; title: string; children: React.ReactNode }) {
  return (
    <section id={id} style={{ marginTop: 48 }}>
      <h2
        style={{
          fontSize: 22,
          fontWeight: 700,
          color: '#1a1a2e',
          borderBottom: '2px solid #e2e8f0',
          paddingBottom: 12,
          marginBottom: 20,
        }}
      >
        {title}
      </h2>
      <div style={{ fontSize: 15, color: '#475569', lineHeight: 1.85 }}>{children}</div>
    </section>
  );
}
```

Save the file with `Ctrl+S`.

---

# PART 2 — TERMS OF SERVICE PAGE

### 2.1 Replace the Terms of Service file

**File to edit:**
```
apps/web/app/terms/page.tsx
```

**How to open it in Cursor:**
1. In the Cursor left sidebar, click: `apps` → `web` → `app` → `terms` → `page.tsx`
2. Press `Ctrl+A` to select all existing content
3. Delete it and paste the full replacement below

**Full file content — paste this exactly:**

```tsx
export const metadata = {
  title: 'Terms of Service – Winnow Career Concierge',
  description: 'Terms and conditions for using the Winnow platform.',
};

const sections = [
  'Acceptance of Terms',
  'Service Description',
  'Account Responsibilities',
  'Acceptable Use',
  'Content Ownership',
  'Subscription & Billing',
  'AI-Generated Content',
  'Disclaimer of Warranties',
  'Limitation of Liability',
  'Termination',
  'Governing Law',
  'Contact Us',
];

export default function TermsPage() {
  return (
    <div style={{ fontFamily: 'Inter, system-ui, sans-serif', color: '#1a1a2e', background: '#f8f9fc', minHeight: '100vh' }}>
      {/* Header Banner */}
      <div style={{ background: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 100%)', padding: '60px 20px', textAlign: 'center' }}>
        <p style={{ color: '#a78bfa', fontSize: 14, fontWeight: 600, letterSpacing: 2, textTransform: 'uppercase', marginBottom: 12 }}>Legal</p>
        <h1 style={{ color: '#ffffff', fontSize: 40, fontWeight: 700, margin: '0 0 16px' }}>Terms of Service</h1>
        <p style={{ color: '#94a3b8', fontSize: 16, margin: 0 }}>Last updated: February 2026 &nbsp;·&nbsp; Effective: February 2026</p>
      </div>

      <div style={{ maxWidth: 1100, margin: '0 auto', padding: '60px 20px', display: 'flex', gap: 60, alignItems: 'flex-start' }}>
        {/* Sidebar TOC */}
        <nav style={{ width: 220, flexShrink: 0, position: 'sticky', top: 40 }}>
          <p style={{ fontSize: 11, fontWeight: 700, letterSpacing: 2, textTransform: 'uppercase', color: '#94a3b8', marginBottom: 16 }}>On This Page</p>
          <ul style={{ listStyle: 'none', margin: 0, padding: 0 }}>
            {sections.map((s) => (
              <li key={s} style={{ marginBottom: 10 }}>
                <a
                  href={`#${s.toLowerCase().replace(/[^a-z0-9]+/g, '-')}`}
                  style={{ fontSize: 14, color: '#6366f1', textDecoration: 'none', lineHeight: 1.5 }}
                >
                  {s}
                </a>
              </li>
            ))}
          </ul>
          <div style={{ marginTop: 32, padding: '20px', background: '#fff', borderRadius: 12, border: '1px solid #e2e8f0' }}>
            <p style={{ fontSize: 13, fontWeight: 600, margin: '0 0 8px', color: '#1a1a2e' }}>Questions?</p>
            <p style={{ fontSize: 13, color: '#64748b', margin: '0 0 12px' }}>We're here to help.</p>
            <a href="mailto:hello@winnowcc.ai" style={{ fontSize: 13, color: '#6366f1', fontWeight: 600 }}>
              hello@winnowcc.ai
            </a>
          </div>
        </nav>

        {/* Main Content */}
        <main style={{ flex: 1, maxWidth: 720 }}>
          <div style={{ background: '#fff', borderRadius: 16, border: '1px solid #e2e8f0', padding: '48px 56px' }}>
            <p style={{ fontSize: 16, color: '#475569', lineHeight: 1.8, marginTop: 0 }}>
              Please read these Terms of Service carefully before using the Winnow Career Concierge platform.
              By creating an account or using any part of our service, you agree to be bound by these terms.
            </p>

            <Section id="acceptance-of-terms" title="Acceptance of Terms">
              <p>
                By accessing or using Winnow at{' '}
                <a href="https://winnowcc.ai" style={{ color: '#6366f1' }}>winnowcc.ai</a> or our mobile
                applications, you confirm that you are at least 16 years old and agree to these Terms. If you
                are using Winnow on behalf of an organization, you represent that you have authority to bind
                that organization.
              </p>
            </Section>

            <Section id="service-description" title="Service Description">
              <p>Winnow is an AI-powered career concierge platform that analyzes your resume, matches you with relevant job opportunities, and generates tailored ATS-optimized application materials. We serve three types of users:</p>
              <ul>
                <li><strong>Job seekers</strong> — resume parsing, job matching, tailored resumes, and Interview Probability Scoring</li>
                <li><strong>Employers</strong> — job posting, candidate search, and hiring analytics</li>
                <li><strong>Recruiters</strong> — CRM pipeline management, client coordination, and candidate sourcing</li>
              </ul>
              <p><strong>We do not guarantee employment outcomes.</strong> Winnow improves your visibility and application quality but cannot guarantee interviews or job offers.</p>
            </Section>

            <Section id="account-responsibilities" title="Account Responsibilities">
              <p>
                You are responsible for maintaining the confidentiality of your login credentials and for all
                activity that occurs under your account. You must provide accurate, current information in your
                profile and resume. Notify us immediately at{' '}
                <a href="mailto:hello@winnowcc.ai" style={{ color: '#6366f1' }}>hello@winnowcc.ai</a> if you
                suspect unauthorized access.
              </p>
            </Section>

            <Section id="acceptable-use" title="Acceptable Use">
              <p>You agree <strong>not</strong> to:</p>
              <ul>
                <li>Upload false, misleading, or fraudulent resume information</li>
                <li>Use the platform to spam employers or misrepresent your qualifications</li>
                <li>Attempt to circumvent subscription limits or access restricted features</li>
                <li>Reverse-engineer, scrape, or copy our matching algorithms or platform code</li>
                <li>Use Winnow to facilitate illegal discrimination in hiring</li>
                <li>Upload content that violates third-party intellectual property rights</li>
              </ul>
              <p>Violations may result in immediate account suspension without refund.</p>
            </Section>

            <Section id="content-ownership" title="Content Ownership">
              <p>
                You retain full ownership of your resume, profile data, and any content you upload. By uploading
                content, you grant Winnow a limited, non-exclusive license to process, store, and use that content
                solely to provide our services to you. We do not sell your content or use it to train AI models
                without explicit consent.
              </p>
            </Section>

            <Section id="subscription-&-billing" title="Subscription & Billing">
              <p>
                Winnow offers free and paid subscription tiers. Paid subscriptions are processed securely by{' '}
                <strong>Stripe</strong>. By subscribing, you authorize recurring charges at the frequency shown
                at checkout.
              </p>
              <p>
                You may cancel at any time through the Stripe Customer Portal — cancellations take effect at the
                end of the current billing period. Refunds are handled per Stripe's standard refund policies. We
                reserve the right to change pricing with 30 days' notice.
              </p>
            </Section>

            <Section id="ai-generated-content" title="AI-Generated Content">
              <p>
                Winnow uses AI (Claude by Anthropic) to generate tailored resumes, cover letters, and
                recommendations. All AI-generated content is based exclusively on the information you provide —
                we do not fabricate credentials or experience.{' '}
                <strong>
                  You are responsible for reviewing all AI-generated materials before submitting them to employers.
                </strong>{' '}
                Winnow is not liable for inaccuracies in AI-generated content that you choose to submit.
              </p>
            </Section>

            <Section id="disclaimer-of-warranties" title="Disclaimer of Warranties">
              <p>
                Winnow is provided "as is" and "as available" without warranties of any kind, express or implied.
                We do not warrant that the platform will be uninterrupted, error-free, or that job matches will
                result in interviews or employment.
              </p>
            </Section>

            <Section id="limitation-of-liability" title="Limitation of Liability">
              <p>
                To the maximum extent permitted by law, Winnow's total liability for any claims arising from your
                use of the platform shall not exceed the amount you paid us in the 12 months prior to the claim.
                We are not liable for indirect, incidental, or consequential damages.
              </p>
            </Section>

            <Section id="termination" title="Termination">
              <p>
                You may delete your account at any time from Settings. We may suspend or terminate accounts that
                violate these Terms, with or without prior notice depending on the severity of the violation. Upon
                termination, your right to use the platform ends immediately, and we will delete your data per our
                Privacy Policy.
              </p>
            </Section>

            <Section id="governing-law" title="Governing Law">
              <p>
                These Terms are governed by the laws of the State of Texas, United States, without regard to
                conflict of law principles. Any disputes shall be resolved in the courts of Bexar County, Texas.
              </p>
            </Section>

            <Section id="contact-us" title="Contact Us">
              <div style={{ background: '#f0f0ff', borderRadius: 12, padding: 24, border: '1px solid #c7d2fe' }}>
                <p style={{ margin: '0 0 8px' }}><strong>Winnow Career Concierge</strong></p>
                <p style={{ margin: '0 0 4px', color: '#475569' }}>
                  Legal inquiries:{' '}
                  <a href="mailto:hello@winnowcc.ai" style={{ color: '#6366f1' }}>hello@winnowcc.ai</a>
                </p>
                <p style={{ margin: 0, color: '#475569' }}>San Antonio, Texas, USA</p>
              </div>
            </Section>
          </div>
        </main>
      </div>
    </div>
  );
}

function Section({ id, title, children }: { id: string; title: string; children: React.ReactNode }) {
  return (
    <section id={id} style={{ marginTop: 48 }}>
      <h2
        style={{
          fontSize: 22,
          fontWeight: 700,
          color: '#1a1a2e',
          borderBottom: '2px solid #e2e8f0',
          paddingBottom: 12,
          marginBottom: 20,
        }}
      >
        {title}
      </h2>
      <div style={{ fontSize: 15, color: '#475569', lineHeight: 1.85 }}>{children}</div>
    </section>
  );
}
```

Save the file with `Ctrl+S`.

---

# PART 3 — VERIFY YOUR CHANGES

### 3.1 Start the web app (if not already running)

Open a terminal in Cursor: **Terminal → New Terminal**, then run:

```powershell
cd C:\Users\ronle\Documents\resumematch\apps\web
npm run dev
```

### 3.2 Check both pages in your browser

Visit each URL and confirm the page looks correct:

| Page | URL |
|------|-----|
| Privacy Policy | http://localhost:3000/privacy |
| Terms of Service | http://localhost:3000/terms |

**What you should see on each page:**
- Dark gradient header banner with "Legal" label and page title
- Sticky sidebar on the left with clickable section links
- White card containing all the policy content
- Lavender contact box at the bottom
- Clean section dividers between each topic

### 3.3 Test the sidebar links

Click each link in the "On This Page" sidebar and confirm the page scrolls to the correct section.

---

# PART 4 — AFTER DEPLOYMENT

Once you deploy to production (see PROMPT41 for GCP deployment), verify the live pages load correctly:

- `https://winnowcc.ai/privacy`
- `https://winnowcc.ai/terms`

These URLs are required for:
- Apple App Store submission (PROMPT27)
- Google Play Store submission (PROMPT27)
- Auth0 application settings
- Stripe account compliance settings

---

## Summary of Changes

| File | Change |
|------|--------|
| `apps/web/app/privacy/page.tsx` | Full replacement — branded, styled, expanded content |
| `apps/web/app/terms/page.tsx` | Full replacement — branded, styled, expanded content |

No backend changes. No new packages. No database migrations. No environment variables added.

---

## Legal Note

These pages provide a reasonable baseline for a SaaS platform but are not a substitute for legal counsel. Before launching to the public, consider having an attorney review both documents — especially the Limitation of Liability, Governing Law, and CCPA/GDPR sections.
