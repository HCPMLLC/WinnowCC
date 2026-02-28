"use client";

import { useState, useEffect } from "react";
import { usePathname } from "next/navigation";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";

const PUBLIC_PATHS = ["/", "/login", "/signup", "/terms", "/privacy"];

export default function CandidateDisclaimer() {
  const pathname = usePathname();
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [expanded, setExpanded] = useState(false);

  const isExcluded =
    PUBLIC_PATHS.includes(pathname) ||
    pathname.startsWith("/privacy/") ||
    pathname.startsWith("/employer") ||
    pathname.startsWith("/recruiter") ||
    pathname.startsWith("/admin");

  useEffect(() => {
    if (isExcluded) return;
    fetch(`${API_BASE}/api/auth/me`, { credentials: "include" })
      .then((res) => {
        if (res.ok) setIsAuthenticated(true);
      })
      .catch(() => {});
  }, [isExcluded]);

  if (!isAuthenticated || isExcluded) return null;

  return (
    <footer
      className="mt-auto border-t border-gray-200 bg-gray-50 px-6 py-4"
      role="contentinfo"
      aria-label="Service disclaimer"
    >
      <div className="max-w-5xl mx-auto">
        {/* Always-visible summary line */}
        <div className="flex items-start justify-between gap-4">
          <p className="text-xs text-gray-500 leading-relaxed">
            <span className="font-semibold text-gray-600">Our commitment to you:</span>{" "}
            Winnow provides intelligent job matching, resume tailoring, and career tools
            to help you focus on opportunities where you&apos;re most likely to succeed.
            While no platform can guarantee an interview invitation or offer of employment,
            we guarantee the quality and honesty of every tool we put in your hands.{" "}
            <button
              onClick={() => setExpanded(!expanded)}
              className="text-emerald-700 hover:text-emerald-800 underline underline-offset-2 font-medium"
              aria-expanded={expanded}
              aria-controls="disclaimer-details"
            >
              {expanded ? "Show less" : "Learn what we guarantee"}
            </button>
          </p>
        </div>

        {/* Expandable details */}
        {expanded && (
          <div
            id="disclaimer-details"
            className="mt-4 text-xs text-gray-500 leading-relaxed space-y-3 border-t border-gray-200 pt-4"
          >
            {/* What we cannot guarantee */}
            <div>
              <h4 className="font-semibold text-gray-600 mb-1">
                What hiring outcomes depend on
              </h4>
              <p>
                Interview invitations and employment offers depend on many factors
                beyond any platform&apos;s control, including employer hiring timelines,
                internal candidate pools, budget approvals, role changes, and
                individual interviewer preferences. Winnow&apos;s Interview Probability
                scores are heuristic estimates designed to help you prioritize your
                efforts — they are not predictions or promises of any specific
                outcome.
              </p>
            </div>

            {/* What we DO guarantee */}
            <div>
              <h4 className="font-semibold text-gray-600 mb-1">
                What Winnow guarantees
              </h4>
              <ul className="list-none space-y-1.5 ml-0">
                <li className="flex items-start gap-2">
                  <span className="text-emerald-600 mt-0.5">✓</span>
                  <span>
                    <strong>Honest matching.</strong> Every match score comes with
                    transparent, explainable reasons — what matched, what&apos;s missing,
                    and why. No black boxes.
                  </span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-emerald-600 mt-0.5">✓</span>
                  <span>
                    <strong>Grounded resume tailoring.</strong> Every tailored resume
                    is built from your real experience. Winnow will never invent
                    employers, titles, degrees, dates, or certifications that aren&apos;t
                    in your profile. Every change includes a source-grounded audit
                    trail.
                  </span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-emerald-600 mt-0.5">✓</span>
                  <span>
                    <strong>Quality over volume.</strong> We show you fewer, better
                    matches rather than flooding you with hundreds of poor fits.
                    Research consistently shows that targeted applications lead to
                    more interviews than mass-applying.
                  </span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-emerald-600 mt-0.5">✓</span>
                  <span>
                    <strong>Your data, your control.</strong> You can export your
                    complete profile and generated documents, or delete your account
                    and all associated data at any time. Your resume content is
                    encrypted and never used for purposes other than serving you.
                  </span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-emerald-600 mt-0.5">✓</span>
                  <span>
                    <strong>Continuous improvement.</strong> We regularly expand our
                    job sources, refine our matching algorithms, and improve our
                    tools based on real outcomes and user feedback.
                  </span>
                </li>
              </ul>
            </div>

            {/* Encouragement */}
            <p className="text-gray-400 italic">
              Job searching is hard. Winnow is here to make it smarter, not to make
              promises we can&apos;t keep. We&apos;re rooting for you.
            </p>
          </div>
        )}
      </div>
    </footer>
  );
}
