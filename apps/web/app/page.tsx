"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import CompetitiveComparison from "./competitive/winnow-competitive-comparison";
import EmployerComparisonPage from "./competitive/employers/page";
import RecruiterComparisonPage from "./competitive/recruiters/page";

type Audience = "seeker" | "employer" | "recruiter";

const COLORS: Record<Audience, {
  bg: string; iconBg: string; iconText: string;
  accent: string; accentHover: string; accentText: string;
  border: string; label: string; heroCta: string; heroCtaHover: string;
}> = {
  seeker: {
    bg: "bg-amber-50", iconBg: "bg-amber-100", iconText: "text-amber-700",
    accent: "bg-amber-500", accentHover: "hover:bg-amber-400", accentText: "text-amber-600",
    border: "border-amber-500", label: "text-amber-400",
    heroCta: "bg-amber-500", heroCtaHover: "hover:bg-amber-400",
  },
  employer: {
    bg: "bg-blue-50", iconBg: "bg-blue-100", iconText: "text-blue-700",
    accent: "bg-blue-600", accentHover: "hover:bg-blue-500", accentText: "text-blue-600",
    border: "border-blue-500", label: "text-blue-400",
    heroCta: "bg-blue-600", heroCtaHover: "hover:bg-blue-500",
  },
  recruiter: {
    bg: "bg-emerald-50", iconBg: "bg-emerald-100", iconText: "text-emerald-700",
    accent: "bg-emerald-600", accentHover: "hover:bg-emerald-500", accentText: "text-emerald-600",
    border: "border-emerald-500", label: "text-emerald-400",
    heroCta: "bg-emerald-600", heroCtaHover: "hover:bg-emerald-500",
  },
};

// ---------------------------------------------------------------------------
// Audience-specific content
// ---------------------------------------------------------------------------

const HERO_CONTENT: Record<
  Audience,
  { headline: string; accent: string; sub: string; cta: string; ctaHref: string; secondary: string }
> = {
  seeker: {
    headline: "Separate the wheat",
    accent: "from the chaff",
    sub: "Stop spraying resumes into the void. Winnow matches you to jobs where you actually have a shot, then tailors your resume to land the interview.",
    cta: "Start Free",
    ctaHref: "/login?mode=signup",
    secondary: "No credit card required. Upload your resume and get matched in minutes.",
  },
  employer: {
    headline: "Find candidates who",
    accent: "actually fit",
    sub: "Post once, distribute everywhere. Winnow\u2019s AI scores every applicant against your requirements so you interview the right people first.",
    cta: "Post a Job Free",
    ctaHref: "/login?mode=signup&role=employer",
    secondary: "Free tier includes 1 active posting and 5 candidate views per month.",
  },
  recruiter: {
    headline: "Place faster with",
    accent: "AI-powered intel",
    sub: "Candidate briefs, salary intelligence, and CRM migration in one platform. Close more placements in less time.",
    cta: "Start 14-Day Free Trial",
    ctaHref: "/login?mode=signup&role=recruiter",
    secondary: "Full feature access for 14 days. No credit card required.",
  },
};

const FEATURES_CONTENT: Record<
  Audience,
  { heading: string; sub: string; items: { title: string; description: string }[] }
> = {
  seeker: {
    heading: "Everything you need to land the right job",
    sub: "Winnow replaces the spray-and-pray approach with a precision campaign built on data.",
    items: [
      {
        title: "Interview Probability Score\u2122",
        description: "Every job match comes with an IPS\u2122 \u2014 a single number combining resume fit, timing, referral potential, and more.",
      },
      {
        title: "Tailored Resumes",
        description: "For every job you pursue, Winnow generates a custom resume variant optimized for that specific role.",
      },
      {
        title: "Smart Job Matching",
        description: "We aggregate jobs from dozens of sources and score each one against your profile. You see only the roles worth your time.",
      },
      {
        title: "One Resume Upload",
        description: "Upload your resume once. Winnow parses it, builds your profile, and continuously matches you as new jobs appear.",
      },
      {
        title: "Cover Letter Generator",
        description: "For every application, Winnow generates a personalized cover letter that complements your tailored resume.",
      },
      {
        title: "Sieve AI Concierge",
        description: "Your personal career coach answers questions, suggests strategy, and helps you prioritize opportunities.",
      },
    ],
  },
  employer: {
    heading: "Hire smarter, faster, fairer",
    sub: "AI-powered tools that help you find the best candidates while reducing bias.",
    items: [
      {
        title: "AI Candidate Scoring",
        description: "Every applicant is scored against your job requirements. See who really fits before you spend time on interviews.",
      },
      {
        title: "Multi-Board Distribution",
        description: "Post once to Google Jobs, Indeed, ZipRecruiter, and more. Manage all applications in one dashboard.",
      },
      {
        title: "Bias Detection",
        description: "Our AI flags potentially biased language in your job postings and helps you write more inclusive descriptions.",
      },
      {
        title: "Compliance & Analytics",
        description: "Track EEOC compliance, cross-board performance, and time-to-hire metrics across all your postings.",
      },
      {
        title: "Salary Intelligence",
        description: "Market benchmarks by role, location, and experience level help you write competitive offers.",
      },
      {
        title: "Sieve AI Concierge",
        description: "Your AI hiring advisor helps optimize job descriptions, screen candidates, and plan interviews.",
      },
    ],
  },
  recruiter: {
    heading: "Close placements faster",
    sub: "Purpose-built tools for independent recruiters and staffing agencies.",
    items: [
      {
        title: "AI Candidate Briefs",
        description: "Generate comprehensive candidate summaries instantly. Present polished briefs to clients in seconds, not hours.",
      },
      {
        title: "Chrome Extension",
        description: "Source candidates from LinkedIn and job boards directly into your Winnow pipeline with one click.",
      },
      {
        title: "CRM Migration Toolkit",
        description: "Import your existing candidate database from Bullhorn, Recruit CRM, or any other platform seamlessly.",
      },
      {
        title: "Sieve AI Concierge",
        description: "Your AI assistant that helps match candidates to open reqs, draft outreach emails, and manage your pipeline.",
      },
      {
        title: "Multi-Board Distribution",
        description: "Post jobs to Google Jobs, Indeed, ZipRecruiter, and more from a single dashboard.",
      },
      {
        title: "Pipeline CRM",
        description: "Track candidates across stages, manage client relationships, and close placements faster.",
      },
    ],
  },
};

const STEPS_CONTENT: Record<Audience, { heading: string; steps: { title: string; description: string }[] }> = {
  seeker: {
    heading: "From upload to interview in four steps",
    steps: [
      { title: "Upload your resume", description: "Drop in your PDF or DOCX. Winnow extracts your skills, experience, and preferences automatically." },
      { title: "Get matched", description: "Our algorithms scan thousands of live job postings and score each one against your profile." },
      { title: "Review your IPS", description: "See your Interview Probability Score\u2122 for every match. Focus on jobs where you have the best odds." },
      { title: "Apply with a tailored resume", description: "Choose a role and Winnow generates a custom resume and cover letter optimized for that job." },
    ],
  },
  employer: {
    heading: "From posting to hire in four steps",
    steps: [
      { title: "Post your job", description: "Enter your job details or paste a URL. Our AI parses requirements, skills, and qualifications automatically." },
      { title: "Candidates are scored", description: "Every applicant is matched and scored against your requirements. See the best fits first." },
      { title: "Interview top matches", description: "Review AI-generated candidate summaries and schedule interviews with your best matches." },
      { title: "Make the hire", description: "Track your hiring pipeline from application through offer with built-in compliance logging." },
    ],
  },
  recruiter: {
    heading: "From sourcing to placement in four steps",
    steps: [
      { title: "Import your database", description: "Migrate candidates from your current CRM or start sourcing with our Chrome extension." },
      { title: "Source & match", description: "Our AI matches your candidate pool against open reqs. Find the right fit for every role instantly." },
      { title: "Submit candidates", description: "Generate polished candidate briefs and submit to clients with salary intelligence and market context." },
      { title: "Close the placement", description: "Track submissions, interviews, and offers. Manage your entire pipeline in one place." },
    ],
  },
};

const CTA_CONTENT: Record<Audience, { heading: string; sub: string; cta: string; ctaHref: string }> = {
  seeker: {
    heading: "Ready to find gold in your job search?",
    sub: "Join Winnow and stop wasting time on jobs that won\u2019t call you back.",
    cta: "Get Started Free",
    ctaHref: "/login?mode=signup",
  },
  employer: {
    heading: "Ready to hire the right candidates?",
    sub: "Post your first job free and see AI-powered matching in action.",
    cta: "Post a Job Free",
    ctaHref: "/login?mode=signup&role=employer",
  },
  recruiter: {
    heading: "Ready to place faster?",
    sub: "Start your 14-day free trial with full access to every feature.",
    cta: "Start Free Trial",
    ctaHref: "/login?mode=signup&role=recruiter",
  },
};

// ---------------------------------------------------------------------------
// Pricing data per audience
// ---------------------------------------------------------------------------

const PRICING_CONTENT: Record<
  Audience,
  { heading: string; sub: string; tiers: { name: string; price: string; interval: string; annual?: string; desc: string; features: string[]; cta: string; href: string; highlight: boolean }[] }
> = {
  seeker: {
    heading: "Start free. Upgrade when you\u2019re ready.",
    sub: "No credit card required. Get matched to your first jobs today.",
    tiers: [
      {
        name: "Free", price: "$0", interval: "/mo", desc: "For getting started",
        features: ["5 job matches", "Interview Probability Score\u2122", "1 tailored resume per month", "1 cover letter per month", "3 Sieve AI messages per day"],
        cta: "Get Started", href: "/login?mode=signup", highlight: false,
      },
      {
        name: "Starter", price: "$9", interval: "/mo", annual: "or $79/year (save 27%)", desc: "For active job seekers",
        features: ["25 job matches", "Interview Probability Score\u2122", "5 tailored resumes per month", "5 cover letters per month", "50 Sieve AI messages per day", "Full match explainability", "CSV data export"],
        cta: "Get Started", href: "/login?mode=signup", highlight: false,
      },
      {
        name: "Pro", price: "$19", interval: "/mo", annual: "or $149/year (save 35%)", desc: "For serious job seekers",
        features: ["Unlimited job matches", "Interview Probability Score\u2122", "30 tailored resumes per month", "30 cover letters per month", "Unlimited Sieve AI", "Gap analysis & coaching", "Full data export"],
        cta: "Get Started", href: "/login?mode=signup", highlight: true,
      },
    ],
  },
  employer: {
    heading: "Plans that grow with your team.",
    sub: "Start free with one posting. Scale up as you hire.",
    tiers: [
      {
        name: "Free", price: "$0", interval: "/mo", desc: "Try with a single posting",
        features: ["1 active job posting", "5 candidate views per month", "1 AI job parse", "Google Jobs distribution"],
        cta: "Get Started", href: "/login?mode=signup&role=employer", highlight: false,
      },
      {
        name: "Starter", price: "$49", interval: "/mo", annual: "or $399/year (save 32%)", desc: "For growing companies",
        features: ["5 active job postings", "50 candidate views per month", "10 AI job parses", "3 job boards", "Basic analytics & bias detection"],
        cta: "Get Started", href: "/login?mode=signup&role=employer", highlight: false,
      },
      {
        name: "Pro", price: "$149", interval: "/mo", annual: "or $1,199/year (save 33%)", desc: "For hiring teams",
        features: ["25 active job postings", "200 candidate views per month", "Unlimited AI parsing", "All job boards", "Full analytics & intelligence", "Full bias detection"],
        cta: "Get Started", href: "/login?mode=signup&role=employer", highlight: true,
      },
    ],
  },
  recruiter: {
    heading: "Built for recruiters. Priced to scale.",
    sub: "Start with a free 14-day trial. Every feature, no limits.",
    tiers: [
      {
        name: "Solo", price: "$29", interval: "/mo", annual: "or $249/year (save 28%)", desc: "For independent recruiters",
        features: ["1 seat", "20 candidate briefs per month", "Chrome extension", "5 salary lookups per month", "Full migration toolkit"],
        cta: "Get Started", href: "/login?mode=signup&role=recruiter", highlight: false,
      },
      {
        name: "Team", price: "$69", interval: "/user/mo", annual: "or $599/user/year (save 28%)", desc: "For recruiting teams",
        features: ["Up to 10 seats", "100 candidate briefs per month", "Chrome extension", "50 salary lookups per month", "Full migration toolkit", "Full client CRM"],
        cta: "Get Started", href: "/login?mode=signup&role=recruiter", highlight: true,
      },
      {
        name: "Agency", price: "$99", interval: "/user/mo", annual: "or $899/user/year (save 24%)", desc: "For staffing agencies",
        features: ["Unlimited seats", "500 candidate briefs per month", "Chrome extension", "Unlimited salary lookups", "Full migration toolkit", "Full client CRM"],
        cta: "Contact Sales", href: "mailto:sales@winnow.careers", highlight: false,
      },
    ],
  },
};

// ---------------------------------------------------------------------------
// Feature icons (shared)
// ---------------------------------------------------------------------------

const FEATURE_ICONS = [
  <svg key="0" className="h-7 w-7" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z" /></svg>,
  <svg key="1" className="h-7 w-7" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m0 12.75h7.5m-7.5 3H12M10.5 2.25H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" /></svg>,
  <svg key="2" className="h-7 w-7" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456z" /></svg>,
  <svg key="3" className="h-7 w-7" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" /></svg>,
  <svg key="4" className="h-7 w-7" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M21.75 6.75v10.5a2.25 2.25 0 01-2.25 2.25h-15a2.25 2.25 0 01-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25m19.5 0v.243a2.25 2.25 0 01-1.07 1.916l-7.5 4.615a2.25 2.25 0 01-2.36 0L3.32 8.91a2.25 2.25 0 01-1.07-1.916V6.75" /></svg>,
  <svg key="5" className="h-7 w-7" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.129.166 2.27.293 3.423.379.35.026.67.21.865.501L12 21l2.755-4.133a1.14 1.14 0 01.865-.501 48.172 48.172 0 003.423-.379c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0012 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018z" /></svg>,
];

// ---------------------------------------------------------------------------
// Audience Toggle
// ---------------------------------------------------------------------------

function AudienceToggle({
  audience,
  onChange,
}: {
  audience: Audience;
  onChange: (a: Audience) => void;
}) {
  const options: { key: Audience; label: string }[] = [
    { key: "seeker", label: "Job Seekers" },
    { key: "employer", label: "Employers" },
    { key: "recruiter", label: "Recruiters" },
  ];

  return (
    <div className="inline-flex rounded-full bg-slate-800/60 p-1 backdrop-blur">
      {options.map((opt) => (
        <button
          key={opt.key}
          onClick={() => onChange(opt.key)}
          className={`rounded-full px-5 py-2 text-sm font-semibold transition-all ${
            audience === opt.key
              ? `${COLORS[opt.key].accent} text-white shadow`
              : "text-white/70 hover:text-white"
          }`}
        >
          {opt.label}
        </button>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Components
// ---------------------------------------------------------------------------

function NavBar({ audience }: { audience: Audience }) {
  const [scrolled, setScrolled] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 40);
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const ctaLabel =
    audience === "employer"
      ? "Post a Job Free"
      : audience === "recruiter"
        ? "Start Free Trial"
        : "Get Started Free";

  const ctaHref =
    audience === "employer"
      ? "/login?mode=signup&role=employer"
      : audience === "recruiter"
        ? "/login?mode=signup&role=recruiter"
        : "/login?mode=signup";

  return (
    <nav
      className={`fixed inset-x-0 top-0 z-50 transition-colors duration-300 ${
        scrolled ? "bg-slate-900/90 backdrop-blur" : "bg-transparent"
      }`}
    >
      <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4 lg:px-8">
        <Link href="/" className="flex items-center gap-2">
          <img
            src="/Winnow CC Masthead TBGC.png"
            alt="Winnow"
            className="h-[72px] w-auto"
          />
        </Link>

        <div className="hidden items-center gap-8 md:flex">
          <a href="#features" className="text-sm font-medium text-white/80 transition-colors hover:text-white">Features</a>
          <a href="#how-it-works" className="text-sm font-medium text-white/80 transition-colors hover:text-white">How It Works</a>
          <a href="#compare" className="text-sm font-medium text-white/80 transition-colors hover:text-white">Compare</a>
          <a href="#pricing" className="text-sm font-medium text-white/80 transition-colors hover:text-white">Pricing</a>
          <Link href="/login" className="text-sm font-medium text-white/80 transition-colors hover:text-white">Sign In</Link>
          <Link
            href={ctaHref}
            className="rounded-lg bg-white px-4 py-2 text-sm font-semibold text-slate-900 transition-colors hover:bg-slate-100"
          >
            {ctaLabel}
          </Link>
        </div>

        <button
          onClick={() => setMenuOpen(!menuOpen)}
          className="flex h-10 w-10 items-center justify-center rounded-lg text-white md:hidden"
          aria-label="Toggle menu"
        >
          <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            {menuOpen ? (
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            ) : (
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            )}
          </svg>
        </button>
      </div>

      {menuOpen && (
        <div className="border-t border-white/10 bg-slate-900/95 backdrop-blur md:hidden">
          <div className="flex flex-col gap-1 px-6 py-4">
            <a href="#features" onClick={() => setMenuOpen(false)} className="rounded-lg px-3 py-2 text-sm font-medium text-white/80 hover:bg-white/10 hover:text-white">Features</a>
            <a href="#how-it-works" onClick={() => setMenuOpen(false)} className="rounded-lg px-3 py-2 text-sm font-medium text-white/80 hover:bg-white/10 hover:text-white">How It Works</a>
            <a href="#compare" onClick={() => setMenuOpen(false)} className="rounded-lg px-3 py-2 text-sm font-medium text-white/80 hover:bg-white/10 hover:text-white">Compare</a>
            <a href="#pricing" onClick={() => setMenuOpen(false)} className="rounded-lg px-3 py-2 text-sm font-medium text-white/80 hover:bg-white/10 hover:text-white">Pricing</a>
            <Link href="/login" className="rounded-lg px-3 py-2 text-sm font-medium text-white/80 hover:bg-white/10 hover:text-white">Sign In</Link>
            <Link
              href={ctaHref}
              className="mt-2 rounded-lg bg-white px-3 py-2 text-center text-sm font-semibold text-slate-900 hover:bg-slate-100"
            >
              {ctaLabel}
            </Link>
          </div>
        </div>
      )}
    </nav>
  );
}

function HeroSection({
  audience,
  onAudienceChange,
}: {
  audience: Audience;
  onAudienceChange: (a: Audience) => void;
}) {
  const content = HERO_CONTENT[audience];

  return (
    <section className="relative flex min-h-screen items-center justify-center overflow-hidden">
      <video autoPlay muted loop playsInline className="absolute inset-0 h-full w-full object-cover">
        <source src="/Winnow Vid AI Gend.mp4" type="video/mp4" />
      </video>
      <div className="absolute inset-0 bg-gradient-to-b from-slate-900/70 via-slate-900/50 to-slate-900/80" />

      <div className="relative z-10 mx-auto max-w-4xl px-6 py-32 text-center lg:px-8">
        {/* Audience toggle */}
        <div className="mb-10">
          <AudienceToggle audience={audience} onChange={onAudienceChange} />
        </div>

        <h1 className="text-4xl font-bold tracking-tight text-white sm:text-5xl lg:text-6xl">
          {content.headline}
          <br />
          <span className={COLORS[audience].label}>{content.accent}</span>
        </h1>
        <p className="mx-auto mt-6 max-w-2xl text-lg leading-relaxed text-slate-300 sm:text-xl">
          {content.sub}
        </p>
        <div className="mt-10 flex flex-col items-center justify-center gap-4 sm:flex-row">
          <Link
            href={content.ctaHref}
            className={`w-full rounded-xl ${COLORS[audience].heroCta} px-8 py-3.5 text-base font-semibold text-white shadow-lg transition-colors ${COLORS[audience].heroCtaHover} sm:w-auto`}
          >
            {content.cta}
          </Link>
          <a
            href="#how-it-works"
            className="w-full rounded-xl border border-white/30 bg-white/10 px-8 py-3.5 text-base font-semibold text-white backdrop-blur transition-colors hover:bg-white/20 sm:w-auto"
          >
            See How It Works
          </a>
        </div>
        <p className="mt-6 text-sm text-slate-400">{content.secondary}</p>
      </div>

      <div className="absolute bottom-8 left-1/2 z-10 -translate-x-1/2 animate-bounce">
        <svg className="h-6 w-6 text-white/60" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 14l-7 7m0 0l-7-7m7 7V3" />
        </svg>
      </div>
    </section>
  );
}

function FeaturesSection({ audience }: { audience: Audience }) {
  const content = FEATURES_CONTENT[audience];

  return (
    <section id="features" className={`${COLORS[audience].bg} py-24`}>
      <div className="mx-auto max-w-7xl px-6 lg:px-8">
        <div className="mx-auto max-w-2xl text-center">
          <p className={`text-sm font-semibold uppercase tracking-widest ${COLORS[audience].accentText}`}>Features</p>
          <h2 className="mt-2 text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl">
            {content.heading}
          </h2>
          <p className="mt-4 text-lg text-slate-600">{content.sub}</p>
        </div>
        <div className="mx-auto mt-16 grid max-w-5xl gap-8 sm:grid-cols-2 lg:grid-cols-3">
          {content.items.map((feature, i) => (
            <div
              key={feature.title}
              className="rounded-2xl border border-slate-200 bg-slate-50 p-8 transition-shadow hover:shadow-md"
            >
              <div className={`flex h-12 w-12 items-center justify-center rounded-xl ${COLORS[audience].iconBg} ${COLORS[audience].iconText}`}>
                {FEATURE_ICONS[i % FEATURE_ICONS.length]}
              </div>
              <h3 className="mt-5 text-lg font-semibold text-slate-900">{feature.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-slate-600">{feature.description}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function HowItWorksSection({ audience }: { audience: Audience }) {
  const content = STEPS_CONTENT[audience];

  return (
    <section id="how-it-works" className="bg-slate-900 py-24">
      <div className="mx-auto max-w-7xl px-6 lg:px-8">
        <div className="mx-auto max-w-2xl text-center">
          <p className={`text-sm font-semibold uppercase tracking-widest ${COLORS[audience].label}`}>How It Works</p>
          <h2 className="mt-2 text-3xl font-bold tracking-tight text-white sm:text-4xl">
            {content.heading}
          </h2>
        </div>
        <div className="mx-auto mt-16 grid max-w-4xl gap-8 sm:grid-cols-2 lg:grid-cols-4">
          {content.steps.map((item, i) => (
            <div key={i} className="text-center">
              <div className={`mx-auto flex h-14 w-14 items-center justify-center rounded-full ${COLORS[audience].accent} text-xl font-bold text-white`}>
                {i + 1}
              </div>
              <h3 className="mt-4 text-base font-semibold text-white">{item.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-slate-400">{item.description}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function CompareSection({ audience }: { audience: Audience }) {
  return (
    <section id="compare">
      {audience === "seeker" ? (
        <CompetitiveComparison />
      ) : audience === "employer" ? (
        <EmployerComparisonPage />
      ) : (
        <RecruiterComparisonPage />
      )}
    </section>
  );
}

function PricingSection({ audience }: { audience: Audience }) {
  const content = PRICING_CONTENT[audience];

  return (
    <section id="pricing" className="bg-white py-24">
      <div className="mx-auto max-w-7xl px-6 lg:px-8">
        <div className="mx-auto max-w-2xl text-center">
          <p className={`text-sm font-semibold uppercase tracking-widest ${COLORS[audience].accentText}`}>Pricing</p>
          <h2 className="mt-2 text-3xl font-bold tracking-tight text-slate-900 sm:text-4xl">
            {content.heading}
          </h2>
          <p className="mt-4 text-lg text-slate-600">{content.sub}</p>
        </div>
        <div className={`mx-auto mt-16 grid max-w-4xl gap-8 lg:grid-cols-3`}>
          {content.tiers.map((tier) => (
            <div
              key={tier.name}
              className={`relative rounded-2xl bg-white p-8 ${
                tier.highlight
                  ? `border-2 ${COLORS[audience].border} shadow-lg`
                  : "border border-slate-200"
              }`}
            >
              {tier.highlight && (
                <div className={`absolute -top-3 left-1/2 -translate-x-1/2 rounded-full ${COLORS[audience].accent} px-3 py-0.5 text-xs font-semibold text-white`}>
                  Popular
                </div>
              )}
              <h3 className="text-lg font-semibold text-slate-900">{tier.name}</h3>
              <p className="mt-1 text-sm text-slate-500">{tier.desc}</p>
              <p className="mt-6">
                <span className="text-4xl font-bold text-slate-900">{tier.price}</span>
                <span className="text-sm text-slate-500">{tier.interval}</span>
              </p>
              {tier.annual && <p className="text-xs text-slate-400">{tier.annual}</p>}
              <ul className="mt-8 space-y-3 text-sm text-slate-600">
                {tier.features.map((f) => (
                  <li key={f} className="flex gap-2">
                    <span className="text-emerald-500">&#10003;</span> {f}
                  </li>
                ))}
              </ul>
              <Link
                href={tier.href}
                className={`mt-8 block rounded-xl py-2.5 text-center text-sm font-semibold transition-colors ${
                  tier.highlight
                    ? `${COLORS[audience].accent} text-white ${COLORS[audience].accentHover}`
                    : "border border-slate-300 text-slate-700 hover:bg-slate-50"
                }`}
              >
                {tier.cta}
              </Link>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function CtaBanner({ audience }: { audience: Audience }) {
  const content = CTA_CONTENT[audience];

  return (
    <section className="relative overflow-hidden bg-slate-900 py-20">
      <div className="absolute inset-0 opacity-20">
        <video autoPlay muted loop playsInline className="h-full w-full object-cover">
          <source src="/Winnow Vid AI Gend.mp4" type="video/mp4" />
        </video>
      </div>
      <div className="relative z-10 mx-auto max-w-3xl px-6 text-center lg:px-8">
        <h2 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">
          {content.heading}
        </h2>
        <p className="mt-4 text-lg text-slate-300">{content.sub}</p>
        <Link
          href={content.ctaHref}
          className={`mt-8 inline-block rounded-xl ${COLORS[audience].heroCta} px-8 py-3.5 text-base font-semibold text-white shadow-lg transition-colors ${COLORS[audience].heroCtaHover}`}
        >
          {content.cta}
        </Link>
      </div>
    </section>
  );
}

function Footer() {
  return (
    <footer className="border-t border-slate-200 bg-white">
      <div className="mx-auto flex max-w-7xl flex-col items-center gap-4 px-6 py-8 sm:flex-row sm:justify-between lg:px-8">
        <div className="flex items-center gap-6 text-sm text-slate-500">
          <Link href="/privacy" className="transition-colors hover:text-slate-700">Privacy</Link>
          <Link href="/terms" className="transition-colors hover:text-slate-700">Terms</Link>
          <a href="mailto:support@winnow.careers" className="transition-colors hover:text-slate-700">Support</a>
        </div>
        <p className="text-sm text-slate-400">
          &copy; {new Date().getFullYear()} Winnow. All rights reserved.
        </p>
      </div>
    </footer>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function HomePage() {
  const [audience, setAudience] = useState<Audience>("seeker");

  return (
    <main className="bg-white">
      <NavBar audience={audience} />
      <HeroSection audience={audience} onAudienceChange={setAudience} />
      <FeaturesSection audience={audience} />
      <HowItWorksSection audience={audience} />
      <CompareSection audience={audience} />
      <PricingSection audience={audience} />
      <CtaBanner audience={audience} />
      <Footer />
    </main>
  );
}
