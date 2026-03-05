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
      <p className="mb-8 text-sm text-slate-500">Last updated: March 2, 2026</p>

      {/* How to Opt In — clear CTA path for Telnyx 10DLC compliance */}
      <section className="mb-10 rounded-2xl border border-blue-200 bg-blue-50 p-6">
        <h2 className="mb-1 text-lg font-semibold text-slate-900">
          How to Opt In to Winnow SMS Notifications
        </h2>
        <p className="mb-4 text-sm text-slate-600">
          Follow these steps to receive text messages from Winnow:
        </p>

        <ol className="mb-5 list-inside list-decimal space-y-2 text-sm text-slate-700">
          <li>
            <Link href="/login" className="font-semibold underline hover:text-slate-900">
              Create a free Winnow account or sign in
            </Link>
          </li>
          <li>
            Go to your{" "}
            <Link href="/settings" className="font-semibold underline hover:text-slate-900">
              Account Settings
            </Link>{" "}
            page
          </li>
          <li>
            Scroll to <strong>&quot;Phone &amp; SMS Notifications&quot;</strong>
          </li>
          <li>Enter your mobile phone number</li>
          <li>
            Check the consent box and tap <strong>&quot;Save Changes&quot;</strong>
          </li>
        </ol>

        <div className="rounded-lg border border-blue-300 bg-white p-4 text-sm text-slate-700">
          <p className="mb-2 font-semibold text-slate-900">
            At the point of opt-in you will see and agree to the following:
          </p>
          <p className="italic text-slate-600">
            &quot;I agree to receive automated text messages from Winnow about job
            matches, application updates, and career alerts at the phone number
            provided. Message frequency varies. Standard Msg &amp; data rates may
            apply. Reply STOP to opt out or HELP for help. We will not share your
            mobile information with third parties for promotional or marketing
            purposes. See our{" "}
            <span className="font-semibold underline">Terms of Service</span> and{" "}
            <span className="font-semibold underline">Privacy Policy</span>. Consent
            is not required to use Winnow.&quot;
          </p>
        </div>

        <div className="mt-4 flex">
          <Link
            href="/login"
            className="inline-flex items-center gap-2 rounded-lg bg-slate-900 px-5 py-2.5 text-sm font-medium text-white hover:bg-slate-800"
          >
            Sign In to Opt In
          </Link>
        </div>
      </section>

      {/* Quick-reference disclosure box for reviewer */}
      <section className="mb-10 rounded-2xl border border-slate-300 bg-slate-50 p-6">
        <h2 className="mb-3 text-lg font-semibold text-slate-900">
          SMS Program Summary
        </h2>
        <table className="w-full text-sm text-slate-700">
          <tbody className="divide-y divide-slate-200">
            <tr><td className="py-2 pr-4 font-semibold text-slate-900 align-top whitespace-nowrap">Brand</td><td className="py-2">Winnow Career Concierge</td></tr>
            <tr><td className="py-2 pr-4 font-semibold text-slate-900 align-top whitespace-nowrap">Program</td><td className="py-2">Winnow Job Alerts &amp; Application Updates</td></tr>
            <tr><td className="py-2 pr-4 font-semibold text-slate-900 align-top whitespace-nowrap">Opt-in</td><td className="py-2"><Link href="/login" className="font-semibold underline hover:text-slate-900">Sign in</Link> &rarr; <Link href="/settings" className="font-semibold underline hover:text-slate-900">Settings</Link> &rarr; Phone &amp; SMS Notifications &rarr; check consent box &rarr; Save</td></tr>
            <tr><td className="py-2 pr-4 font-semibold text-slate-900 align-top whitespace-nowrap">Opt-out</td><td className="py-2">Reply <strong>STOP</strong> to any message, or disable in <Link href="/settings" className="font-semibold underline hover:text-slate-900">Account Settings</Link></td></tr>
            <tr><td className="py-2 pr-4 font-semibold text-slate-900 align-top whitespace-nowrap">Help</td><td className="py-2">Reply <strong>HELP</strong> to any message, or email <a href="mailto:support@winnowcc.ai" className="font-semibold underline hover:text-slate-900">support@winnowcc.ai</a></td></tr>
            <tr><td className="py-2 pr-4 font-semibold text-slate-900 align-top whitespace-nowrap">Frequency</td><td className="py-2">Message frequency varies; up to 10 messages per week</td></tr>
            <tr><td className="py-2 pr-4 font-semibold text-slate-900 align-top whitespace-nowrap">Rates</td><td className="py-2">Message and data rates may apply</td></tr>
            <tr><td className="py-2 pr-4 font-semibold text-slate-900 align-top whitespace-nowrap">Privacy</td><td className="py-2"><Link href="/privacy" className="font-semibold underline hover:text-slate-900">Privacy Policy</Link> &mdash; see <Link href="/privacy#sms---text-messaging" className="font-semibold underline hover:text-slate-900">SMS / Text Messaging</Link> section</td></tr>
            <tr><td className="py-2 pr-4 font-semibold text-slate-900 align-top whitespace-nowrap">Terms</td><td className="py-2"><Link href="/terms" className="font-semibold underline hover:text-slate-900">Terms of Service</Link> &mdash; see <Link href="/terms#sms---text-messaging" className="font-semibold underline hover:text-slate-900">SMS / Text Messaging</Link> section</td></tr>
          </tbody>
        </table>
      </section>

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
