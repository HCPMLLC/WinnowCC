import Link from "next/link";

export const metadata = {
  title: "SMS Consent & Disclosure | Winnow",
  description:
    "Winnow SMS messaging program details, opt-in, opt-out, and privacy information.",
};

export default function SmsConsentPage() {
  return (
    <main className="mx-auto max-w-3xl px-6 py-16">
      <h1 className="mb-2 text-3xl font-bold text-slate-900">
        SMS Messaging Terms &amp; Consent
      </h1>
      <p className="mb-8 text-sm text-slate-500">Last updated: March 12, 2026</p>

      {/* ─── Opt-In Form ─── */}
      <section className="mb-10 rounded-2xl border border-blue-200 bg-blue-50 p-6">
        <h2 className="mb-1 text-lg font-semibold text-slate-900">
          Opt In to Winnow SMS Notifications
        </h2>
        <p className="mb-5 text-sm text-slate-600">
          Enter your phone number and agree to the terms below to receive text
          message notifications from Winnow.
        </p>

        {/* Visible opt-in form with phone number field and consent language */}
        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <label className="mb-4 flex flex-col gap-1.5 text-sm font-medium text-slate-700">
            Phone Number
            <input
              type="tel"
              placeholder="(210) 555-1234"
              className="max-w-xs rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700"
            />
          </label>

          <label className="mb-5 flex items-start gap-3 text-sm">
            <input type="checkbox" className="mt-1" />
            <span className="text-slate-700">
              By providing your phone number, you agree to receive SMS job match
              alerts, application updates, and career notifications from Winnow
              Career Concierge. Message frequency may vary. Standard Message and
              Data Rates may apply. Reply STOP to opt out. Reply HELP for help.
              We will not share mobile information with third parties for
              promotional or marketing purposes. See our{" "}
              <Link href="/terms" className="font-semibold underline hover:text-slate-900">
                Terms of Service
              </Link>{" "}
              and{" "}
              <Link href="/privacy" className="font-semibold underline hover:text-slate-900">
                Privacy Policy
              </Link>
              . Consent is not required to use Winnow.
            </span>
          </label>

          <Link
            href="/login?redirect=/settings"
            className="inline-flex items-center gap-2 rounded-lg bg-slate-900 px-5 py-2.5 text-sm font-medium text-white hover:bg-slate-800"
          >
            Subscribe to SMS Alerts
          </Link>
          <p className="mt-2 text-xs text-slate-400">
            You will be asked to create an account or sign in to complete your
            opt-in. The same form is also available in{" "}
            <Link href="/settings" className="underline hover:text-slate-600">
              Account Settings → Phone &amp; SMS Notifications
            </Link>
            .
          </p>
        </div>
      </section>

      {/* ─── Opt-In Workflow ─── */}
      <section className="mb-10 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="mb-3 text-lg font-semibold text-slate-900">
          Opt-In Workflow
        </h2>
        <p className="mb-4 text-sm text-slate-600">
          The same opt-in form shown above is displayed in two locations:
        </p>
        <ol className="list-inside list-decimal space-y-3 text-sm text-slate-700">
          <li>
            <strong>This page</strong> (winnowcc.ai/sms-consent) — the opt-in
            form is shown above. The user enters their phone number, checks the
            consent checkbox with the full SMS disclosure language, and clicks
            &quot;Subscribe to SMS Alerts.&quot; They are then prompted to create
            an account or sign in to finalize opt-in.
          </li>
          <li>
            <strong>Account Settings</strong> (winnowcc.ai/settings) — under the
            &quot;Phone &amp; SMS Notifications&quot; section. The user enters
            their phone number, checks the consent checkbox with the same full
            disclosure language, and clicks &quot;Save Changes.&quot;
          </li>
        </ol>
        <p className="mt-4 text-sm text-slate-600">
          In both cases, the user must:
        </p>
        <ul className="mt-2 list-inside list-disc space-y-1 text-sm text-slate-600">
          <li>Enter their mobile phone number in the phone number field</li>
          <li>Check the consent checkbox with the full SMS opt-in disclosure</li>
          <li>Complete opt-in by saving their preferences</li>
        </ul>
        <p className="mt-4 text-sm text-slate-600">
          Upon opt-in, the user receives an automatic confirmation SMS:
        </p>
        <div className="mt-2 rounded-lg border border-green-200 bg-green-50 px-4 py-3 text-sm italic text-slate-700">
          &quot;Winnow: Thanks for subscribing to job match alerts and application
          updates! Reply HELP for help. Message frequency may vary. Msg&amp;data
          rates may apply. Consent is not a condition of purchase. Reply STOP to
          opt out.&quot;
        </div>
      </section>

      {/* ─── Sample Messages ─── */}
      <section className="mb-10 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <h2 className="mb-3 text-lg font-semibold text-slate-900">
          Sample Messages
        </h2>
        <p className="mb-4 text-sm text-slate-600">
          Below are example messages for each use case in this campaign:
        </p>
        <div className="space-y-4">
          <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
            <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
              Job Match Alert
            </p>
            <p className="text-sm text-slate-700">
              &quot;Winnow: New match! &apos;Senior Product Designer&apos; at Acme Corp
              scores 92% for your profile. View details in your dashboard:
              https://winnowcc.ai/matches. Reply STOP to opt out.&quot;
            </p>
          </div>
          <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
            <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
              Application Status Update
            </p>
            <p className="text-sm text-slate-700">
              &quot;Winnow: Your application for &apos;Frontend Engineer&apos; at Globex
              Inc. has been viewed by the hiring team. Check your dashboard for
              details: https://winnowcc.ai/matches. Reply STOP to opt out.&quot;
            </p>
          </div>
          <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
            <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
              Career Alert
            </p>
            <p className="text-sm text-slate-700">
              &quot;Winnow: 5 new jobs matching your skills were posted this week.
              See your latest matches: https://winnowcc.ai/matches. Reply STOP
              to opt out.&quot;
            </p>
          </div>
          <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
            <p className="mb-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
              Account Verification (OTP)
            </p>
            <p className="text-sm text-slate-700">
              &quot;Your Winnow verification code is: 482913. It expires in 10
              minutes. Do not share this code with anyone.&quot;
            </p>
          </div>
        </div>
      </section>

      {/* ─── Program Summary Table ─── */}
      <section className="mb-10 rounded-2xl border border-slate-300 bg-slate-50 p-6">
        <h2 className="mb-3 text-lg font-semibold text-slate-900">
          SMS Program Summary
        </h2>
        <table className="w-full text-sm text-slate-700">
          <tbody className="divide-y divide-slate-200">
            <tr><td className="py-2 pr-4 font-semibold text-slate-900 align-top whitespace-nowrap">Brand</td><td className="py-2">Winnow Career Concierge</td></tr>
            <tr><td className="py-2 pr-4 font-semibold text-slate-900 align-top whitespace-nowrap">Program</td><td className="py-2">Winnow Job Alerts &amp; Application Updates</td></tr>
            <tr><td className="py-2 pr-4 font-semibold text-slate-900 align-top whitespace-nowrap">Opt-in</td><td className="py-2">Enter phone number + check consent box on this page or in <Link href="/settings" className="font-semibold underline hover:text-slate-900">Account Settings</Link></td></tr>
            <tr><td className="py-2 pr-4 font-semibold text-slate-900 align-top whitespace-nowrap">Opt-out</td><td className="py-2">Reply <strong>STOP</strong> to any message, or disable in <Link href="/settings" className="font-semibold underline hover:text-slate-900">Account Settings</Link></td></tr>
            <tr><td className="py-2 pr-4 font-semibold text-slate-900 align-top whitespace-nowrap">Help</td><td className="py-2">Reply <strong>HELP</strong> to any message, or email <a href="mailto:support@winnowcc.ai" className="font-semibold underline hover:text-slate-900">support@winnowcc.ai</a></td></tr>
            <tr><td className="py-2 pr-4 font-semibold text-slate-900 align-top whitespace-nowrap">Frequency</td><td className="py-2">Message frequency varies; up to 10 messages per week</td></tr>
            <tr><td className="py-2 pr-4 font-semibold text-slate-900 align-top whitespace-nowrap">Rates</td><td className="py-2">Message and data rates may apply</td></tr>
            <tr><td className="py-2 pr-4 font-semibold text-slate-900 align-top whitespace-nowrap">Privacy</td><td className="py-2"><Link href="/privacy" className="font-semibold underline hover:text-slate-900">Privacy Policy</Link> &mdash; see <Link href="/privacy#sms---text-messaging" className="font-semibold underline hover:text-slate-900">SMS / Text Messaging</Link> section</td></tr>
            <tr><td className="py-2 pr-4 font-semibold text-slate-900 align-top whitespace-nowrap">Terms</td><td className="py-2"><Link href="/terms" className="font-semibold underline hover:text-slate-900">Terms of Service</Link> &mdash; see <Link href="/terms#sms---text-messaging" className="font-semibold underline hover:text-slate-900">SMS / Text Messaging</Link> section</td></tr>
          </tbody>
        </table>
      </section>

      {/* ─── Detailed Disclosures ─── */}
      <div className="space-y-8 text-sm leading-relaxed text-slate-700">
        <section>
          <h2 className="mb-2 text-lg font-semibold text-slate-900">Program Name</h2>
          <p>Winnow Job Alerts &amp; Application Updates</p>
        </section>

        <section>
          <h2 className="mb-2 text-lg font-semibold text-slate-900">
            What Messages Will I Receive?
          </h2>
          <p>
            When you opt in to SMS notifications from Winnow, you may receive automated
            text messages including:
          </p>
          <ul className="mt-2 list-inside list-disc space-y-1 text-slate-600">
            <li>New job match alerts based on your preferences</li>
            <li>Application status updates (submitted, viewed, interview scheduled)</li>
            <li>Career alerts and recommendations</li>
            <li>Account security notifications (e.g., verification codes)</li>
          </ul>
        </section>

        <section>
          <h2 className="mb-2 text-lg font-semibold text-slate-900">Message Frequency</h2>
          <p>
            Message frequency varies based on your job matching activity. You may receive
            up to 10 messages per week depending on new matches and application activity.
            Some weeks you may receive fewer or no messages.
          </p>
        </section>

        <section>
          <h2 className="mb-2 text-lg font-semibold text-slate-900">
            Message &amp; Data Rates
          </h2>
          <p>
            Message and data rates may apply. Check with your mobile carrier for details
            about your text messaging plan.
          </p>
        </section>

        <section>
          <h2 className="mb-2 text-lg font-semibold text-slate-900">How to Opt Out</h2>
          <p>
            You can stop receiving SMS messages at any time by replying <strong>STOP</strong> to
            any message you receive from Winnow. You will receive a confirmation message
            and no further texts will be sent. You can also disable SMS notifications in
            your{" "}
            <Link href="/settings" className="font-semibold underline hover:text-slate-900">
              Account Settings
            </Link>
            .
          </p>
        </section>

        <section>
          <h2 className="mb-2 text-lg font-semibold text-slate-900">How to Get Help</h2>
          <p>
            Reply <strong>HELP</strong> to any message for assistance, or contact us at{" "}
            <a
              href="mailto:support@winnowcc.ai"
              className="font-semibold underline hover:text-slate-900"
            >
              support@winnowcc.ai
            </a>
            .
          </p>
        </section>

        <section>
          <h2 className="mb-2 text-lg font-semibold text-slate-900">
            Consent Is Not Required
          </h2>
          <p>
            Your consent to receive SMS messages is not a condition of purchasing any goods
            or services from Winnow. You may use all features of the Winnow platform
            without opting in to SMS notifications.
          </p>
        </section>

        <section>
          <h2 className="mb-2 text-lg font-semibold text-slate-900">
            Supported Carriers
          </h2>
          <p>
            SMS messaging is supported on all major US carriers including AT&amp;T,
            T-Mobile, Verizon, and others. Carriers are not liable for delayed or
            undelivered messages.
          </p>
        </section>

        <section>
          <h2 className="mb-2 text-lg font-semibold text-slate-900">Privacy</h2>
          <p>
            Your phone number and messaging preferences are handled in accordance with our{" "}
            <Link
              href="/privacy"
              className="font-semibold underline hover:text-slate-900"
            >
              Privacy Policy
            </Link>
            . We do not sell, rent, or share your phone number with third parties for
            marketing purposes. Text messaging originator opt-in data and consent will not
            be shared with any third parties. For full details, please review our{" "}
            <Link
              href="/terms"
              className="font-semibold underline hover:text-slate-900"
            >
              Terms of Service
            </Link>
            .
          </p>
        </section>
      </div>
    </main>
  );
}
