export const metadata = {
  title: 'Privacy Policy — Winnow',
  description: 'Winnow privacy policy',
};

export default function PrivacyPage() {
  return (
    <main style={{ maxWidth: 800, margin: '0 auto', padding: '40px 20px', fontFamily: 'system-ui' }}>
      <h1>Privacy Policy</h1>
      <p><strong>Last updated:</strong> February 2026</p>
      <p><strong>Winnow</strong> (&quot;we&quot;, &quot;our&quot;, &quot;us&quot;) operates the Winnow mobile application and web platform (winnowcc.ai). This policy explains how we collect, use, and protect your information.</p>

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
        <li><strong>Anthropic (Claude AI):</strong> For resume parsing, job matching, and tailored resume generation. Your resume content is sent to Claude&apos;s API for processing.</li>
        <li><strong>Stripe:</strong> For payment processing. We do not store your credit card information.</li>
        <li><strong>Sentry:</strong> For error tracking. Personal data is scrubbed from error reports.</li>
        <li><strong>Posthog:</strong> For product analytics. Usage patterns are collected anonymously.</li>
      </ul>

      <h2>Data Retention and Deletion</h2>
      <p>Your data is retained as long as your account is active. You can export all your data or permanently delete your account at any time from Settings. Account deletion removes all stored data including resumes, profiles, matches, and tailored resumes within 30 days.</p>

      <h2>Your Rights</h2>
      <p>You have the right to: access your data (via data export), correct your data (via profile editing), delete your data (via account deletion), and opt out of analytics tracking.</p>

      <h2>Children&apos;s Privacy</h2>
      <p>Winnow is not intended for users under 16. We do not knowingly collect data from children.</p>

      <h2>Changes to This Policy</h2>
      <p>We may update this policy. Changes will be posted on this page with an updated date.</p>

      <h2>Contact</h2>
      <p>Questions about this policy? Contact us at <a href="mailto:privacy@winnowcc.ai">privacy@winnowcc.ai</a>.</p>
    </main>
  );
}
