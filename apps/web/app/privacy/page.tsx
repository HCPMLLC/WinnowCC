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
  'California Privacy Rights (CCPA)',
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
            <p style={{ fontSize: 13, color: '#64748b', margin: '0 0 12px' }}>We&apos;re happy to explain anything.</p>
            <a href="mailto:privacy@winnowcc.ai" style={{ fontSize: 13, color: '#6366f1', fontWeight: 600 }}>
              privacy@winnowcc.ai
            </a>
          </div>
        </nav>

        {/* Main Content */}
        <main style={{ flex: 1, maxWidth: 720 }}>
          <div style={{ background: '#fff', borderRadius: 16, border: '1px solid #e2e8f0', padding: '48px 56px' }}>
            <p style={{ fontSize: 16, color: '#475569', lineHeight: 1.8, marginTop: 0 }}>
              <strong>Winnow Career Concierge</strong> (&quot;we&quot;, &quot;our&quot;, &quot;us&quot;) operates the Winnow platform at{' '}
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
              <p>
                Winnow does not store credit card numbers or payment credentials. All payment
                processing is handled by <strong>Stripe</strong>, a PCI DSS Level 1 certified
                processor. Card data never touches Winnow&apos;s servers.
              </p>
            </Section>

            <Section id="third-party-services" title="Third-Party Services">
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 14 }}>
                <thead>
                  <tr style={{ background: '#f8f9fc' }}>
                    <th style={{ padding: '10px 16px', textAlign: 'left', border: '1px solid #e2e8f0', color: '#475569' }}>Service</th>
                    <th style={{ padding: '10px 16px', textAlign: 'left', border: '1px solid #e2e8f0', color: '#475569' }}>Purpose</th>
                    <th style={{ padding: '10px 16px', textAlign: 'left', border: '1px solid #e2e8f0', color: '#475569' }}>Privacy / DPA</th>
                  </tr>
                </thead>
                <tbody>
                  {([
                    ['Anthropic (Claude AI)', 'Resume parsing, job matching, and resume generation', 'https://www.anthropic.com/privacy'],
                    ['Stripe', 'Payment processing — we never store card details', 'https://stripe.com/privacy'],
                    ['Auth0', 'Secure authentication and OAuth login', 'https://www.okta.com/privacy-policy/'],
                    ['Google Cloud Platform', 'Infrastructure, storage, and compute', 'https://cloud.google.com/terms/data-processing-addendum'],
                    ['Sentry', 'Error tracking — personal data is scrubbed', 'https://sentry.io/privacy/'],
                    ['PostHog', 'Anonymous product analytics', 'https://posthog.com/privacy'],
                  ] as [string, string, string][]).map(([name, purpose, dpaUrl]) => (
                    <tr key={name}>
                      <td style={{ padding: '10px 16px', border: '1px solid #e2e8f0', fontWeight: 600 }}>{name}</td>
                      <td style={{ padding: '10px 16px', border: '1px solid #e2e8f0', color: '#475569' }}>{purpose}</td>
                      <td style={{ padding: '10px 16px', border: '1px solid #e2e8f0' }}>
                        <a href={dpaUrl} target="_blank" rel="noopener noreferrer" style={{ color: '#6366f1', fontSize: 13 }}>View</a>
                      </td>
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
              <p>
                To opt out of analytics tracking, reject non-essential cookies via the cookie consent
                banner on your first visit. You can also enable your browser&apos;s Do Not Track setting
                or clear your cookies from Settings. PostHog respects the Do Not Track header when enabled.
              </p>
            </Section>

            <Section id="california-privacy-rights-(ccpa)" title="California Privacy Rights (CCPA)">
              <p>
                If you are a California resident, the California Consumer Privacy Act (CCPA) provides
                you with additional rights regarding your personal information:
              </p>
              <ul>
                <li><strong>Right to Know:</strong> You may request details about the categories and specific pieces of personal information we collect.</li>
                <li><strong>Right to Delete:</strong> You may request deletion of your personal information (available via Settings &gt; Delete Account).</li>
                <li><strong>Right to Opt-Out of Sale:</strong> Winnow does <strong>not</strong> sell your personal information to third parties. We do not share personal information for cross-context behavioral advertising.</li>
                <li><strong>Right to Non-Discrimination:</strong> We will not discriminate against you for exercising any of your CCPA rights.</li>
              </ul>
              <p>
                To exercise these rights, email{' '}
                <a href="mailto:hello@winnowcc.ai" style={{ color: '#6366f1' }}>hello@winnowcc.ai</a>{' '}
                with the subject line &quot;CCPA Request&quot; or use the data export and account deletion
                features in your Settings.
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
                We may update this policy as the platform evolves. When we make material changes, we&apos;ll notify
                you by email or an in-app notice. The &quot;Last updated&quot; date at the top will always reflect the
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
