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
