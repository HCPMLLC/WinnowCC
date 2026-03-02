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
            . We do not share your phone number with third parties for marketing purposes.
            For full details, please review our{" "}
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
