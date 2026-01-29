import Link from "next/link";

export default function HomePage() {
  return (
    <main className="mx-auto flex min-h-screen max-w-5xl flex-col gap-10 px-6 py-16">
      <header className="flex items-center justify-between">
        <div className="text-lg font-semibold">ResumeMatch</div>
        <nav className="flex gap-4 text-sm text-slate-600">
          <Link href="/dashboard" className="hover:text-slate-900">
            Dashboard
          </Link>
        </nav>
      </header>

      <section className="rounded-3xl border border-slate-200 bg-white p-10 shadow-sm">
        <h1 className="text-4xl font-semibold tracking-tight">
          Match resumes to roles with confidence.
        </h1>
        <p className="mt-4 max-w-2xl text-base text-slate-600">
          A focused workspace for comparing candidates against job requirements.
          Upload resumes, track fit scores, and keep your hiring pipeline crisp.
        </p>
        <div className="mt-6 flex flex-wrap gap-3">
          <Link
            href="/dashboard"
            className="rounded-full bg-slate-900 px-5 py-2.5 text-sm font-semibold text-white"
          >
            Go to dashboard
          </Link>
          <button
            type="button"
            className="rounded-full border border-slate-300 px-5 py-2.5 text-sm font-semibold text-slate-700"
          >
            Learn more
          </button>
        </div>
      </section>

      <section className="grid gap-6 md:grid-cols-3">
        {["Fast onboarding", "Clear scoring", "Team-ready"].map((item) => (
          <div
            key={item}
            className="rounded-2xl border border-slate-200 bg-white p-6"
          >
            <h2 className="text-lg font-semibold">{item}</h2>
            <p className="mt-2 text-sm text-slate-600">
              Placeholder copy for upcoming product details.
            </p>
          </div>
        ))}
      </section>
    </main>
  );
}