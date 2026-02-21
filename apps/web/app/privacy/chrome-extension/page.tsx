export const metadata = {
  title: 'Chrome Extension Privacy Policy — Winnow',
  description: 'Privacy policy for the Winnow LinkedIn Sourcing Chrome extension',
};

export default function ChromeExtensionPrivacyPage() {
  return (
    <main style={{ maxWidth: 800, margin: '0 auto', padding: '40px 20px', fontFamily: 'system-ui' }}>
      <h1>Chrome Extension Privacy Policy</h1>
      <p><strong>Winnow LinkedIn Sourcing</strong></p>
      <p><strong>Last updated:</strong> February 2026</p>

      <p>This privacy policy describes how the Winnow LinkedIn Sourcing Chrome extension (&quot;the Extension&quot;) collects, uses, and protects information. The Extension is published by Winnow (&quot;we&quot;, &quot;our&quot;, &quot;us&quot;). By using the Extension you agree to the practices described here and in our <a href="/privacy">main Privacy Policy</a>.</p>

      <h2>What the Extension Does</h2>
      <p>The Extension allows recruiters and hiring managers to extract publicly visible profile information from LinkedIn profile pages and import it into their Winnow employer account for candidate sourcing and job matching.</p>

      <h2>Data We Collect</h2>
      <p>When you use the Extension to extract a LinkedIn profile, the following data is read from the page and transmitted to the Winnow API:</p>
      <ul style={{ paddingLeft: 20 }}>
        <li><strong>Name and headline:</strong> The candidate&apos;s display name and professional headline.</li>
        <li><strong>Location:</strong> City/region as displayed on the profile.</li>
        <li><strong>LinkedIn URL:</strong> The public URL of the profile page.</li>
        <li><strong>Profile photo URL:</strong> The URL of the profile picture (not the image itself).</li>
        <li><strong>Current company:</strong> The company listed in the profile header.</li>
        <li><strong>Experience:</strong> Job titles, company names, and date ranges from the experience section.</li>
        <li><strong>Education:</strong> School names and degrees from the education section.</li>
        <li><strong>Skills:</strong> Skill names from the skills section.</li>
      </ul>
      <p>The Extension does <strong>not</strong> collect browsing history, keystrokes, form inputs on other sites, or any data outside of LinkedIn profile pages you explicitly choose to extract.</p>

      <h2>How Data Is Transmitted</h2>
      <p>Extracted profile data is sent over HTTPS to the Winnow API. No data is sent to any third party other than the Winnow platform. Data is transmitted only when you click &quot;Save to Winnow&quot; — extraction alone does not transmit data.</p>

      <h2>Authentication</h2>
      <p>The Extension uses OAuth 2.0 (via Auth0) to authenticate your Winnow account. Your credentials are handled entirely by the Auth0 authentication service and are never stored by the Extension. A session token (JWT) is stored locally in Chrome&apos;s extension storage to maintain your session. You can sign out at any time to clear this token.</p>

      <h2>Permissions Used</h2>
      <ul style={{ paddingLeft: 20 }}>
        <li><strong>activeTab:</strong> Required to read the current LinkedIn profile page when you click &quot;Extract Profile&quot;. Only activates on the tab you are viewing.</li>
        <li><strong>storage:</strong> Stores your authentication session token and API configuration locally in the browser.</li>
        <li><strong>identity:</strong> Powers the &quot;Sign in with Winnow&quot; OAuth flow using Chrome&apos;s built-in authentication support.</li>
        <li><strong>host_permissions (linkedin.com):</strong> Required to inject the content script that reads profile data from LinkedIn pages.</li>
        <li><strong>host_permissions (api.winnowcc.ai):</strong> Required to communicate with the Winnow API to save extracted profiles.</li>
      </ul>

      <h2>Data Storage and Retention</h2>
      <p>Profile data saved through the Extension is stored in the Winnow platform and is subject to the <a href="/privacy">Winnow Privacy Policy</a>. Data is retained as long as the employer&apos;s account is active. Employers can delete imported candidate profiles at any time from their Winnow dashboard.</p>

      <h2>Third-Party Services</h2>
      <ul style={{ paddingLeft: 20 }}>
        <li><strong>Auth0:</strong> Handles OAuth authentication. See <a href="https://auth0.com/privacy" target="_blank" rel="noopener noreferrer">Auth0 Privacy Policy</a>.</li>
        <li><strong>Winnow API:</strong> Receives and stores extracted profile data. See <a href="/privacy">Winnow Privacy Policy</a>.</li>
      </ul>

      <h2>Your Rights</h2>
      <p>You can sign out of the Extension at any time to clear your session. You can uninstall the Extension at any time to remove all locally stored data. Candidates whose profiles have been imported can request deletion by contacting us or through the main Winnow platform&apos;s data deletion processes.</p>

      <h2>Changes to This Policy</h2>
      <p>We may update this policy when the Extension is updated. Changes will be posted on this page with an updated date.</p>

      <h2>Contact</h2>
      <p>Questions about this policy? Contact us at <a href="mailto:privacy@winnowcc.ai">privacy@winnowcc.ai</a>.</p>
    </main>
  );
}
