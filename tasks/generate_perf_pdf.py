"""Generate performance analysis PDF."""
from fpdf import FPDF

pdf = FPDF()
pdf.set_auto_page_break(auto=True, margin=15)


def heading(text, size=16):
    pdf.set_font("Helvetica", "B", size)
    pdf.multi_cell(0, size * 0.6, text)
    pdf.ln(2)


def subheading(text, size=12):
    pdf.set_font("Helvetica", "B", size)
    pdf.multi_cell(0, size * 0.55, text)
    pdf.ln(1)


def body(text, size=10):
    pdf.set_font("Helvetica", "", size)
    pdf.multi_cell(0, size * 0.5, text)
    pdf.ln(1)


def code(text, size=8):
    pdf.set_font("Courier", "", size)
    pdf.set_fill_color(240, 240, 240)
    pdf.multi_cell(0, size * 0.55, text, fill=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.ln(1)


def separator():
    pdf.set_draw_color(180, 180, 180)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(4)


# ---- Title Page ----
pdf.add_page()
pdf.ln(60)
pdf.set_font("Helvetica", "B", 28)
pdf.cell(0, 15, "Winnow Performance &", new_x="LMARGIN", new_y="NEXT", align="C")
pdf.cell(0, 15, "Optimization Analysis", new_x="LMARGIN", new_y="NEXT", align="C")
pdf.ln(10)
pdf.set_font("Helvetica", "", 14)
pdf.cell(
    0,
    8,
    "Application Performance, Efficiency, Throughput,",
    new_x="LMARGIN",
    new_y="NEXT",
    align="C",
)
pdf.cell(
    0,
    8,
    "Response Time & User Experience",
    new_x="LMARGIN",
    new_y="NEXT",
    align="C",
)
pdf.ln(20)
pdf.set_font("Helvetica", "", 11)
pdf.cell(0, 6, "March 2026", new_x="LMARGIN", new_y="NEXT", align="C")

# ---- CRITICAL ----
pdf.add_page()
heading("CRITICAL (Biggest Impact)")
separator()

subheading("1. Resume parsing blocks the user request")
code("services/api/app/routers/resume.py:163")
body(
    "When someone uploads a resume, the server parses it synchronously "
    "(10-120 seconds of waiting). This should be queued as a background job "
    "so the user gets an instant response."
)
pdf.ln(2)

subheading("2. N+1 database queries in admin pages")
code(
    "admin_candidates.py:134-151  (2+ queries per user = 200+ for 100 users)\n"
    "admin_support.py:258-327    (6 queries per user = 600+ for 100 users)"
)
body(
    "These should batch-fetch all related data in 2-3 queries total "
    "instead of looping per user."
)
pdf.ln(2)

subheading("3. Missing database indexes on hot paths")
body(
    'Match(user_id, created_at) - Every "show my matches" request does a '
    "full table scan.\n"
    "Job(source, source_job_id) - Job ingestion dedup scans the whole table.\n"
    "Job(is_active) - Filtering active jobs has no index.\n\n"
    "A single Alembic migration adding these indexes could dramatically "
    "speed up core features."
)
pdf.ln(2)

subheading("4. Sieve chat loads ALL jobs into memory")
code("sieve_chat.py:92-110")
body(
    "Loads every active job to compute skill matches in Python. With "
    "thousands of jobs, this risks out-of-memory crashes and slow responses."
)

# ---- HIGH ----
pdf.add_page()
heading("HIGH (Strong User-Facing Improvements)")
separator()

subheading("5. No LLM streaming anywhere")
body(
    "All 21 Anthropic API calls use blocking mode - the user stares at a "
    "spinner until the full response is ready. Sieve chat especially should "
    "stream responses (like ChatGPT does) for a much snappier feel."
)
pdf.ln(2)

subheading("6. No retry logic on Anthropic API calls")
code("cover_letter_generator.py, sieve_chat.py, career_intelligence.py")
body(
    "If the LLM has a brief hiccup, the user gets an immediate error. "
    "Adding retry with backoff would make these reliable."
)
pdf.ln(2)

subheading("7. Password reset email sent synchronously")
code("routers/auth.py:374")
body("If Resend is slow (3-5s), the user waits. Should use a background task.")
pdf.ln(2)

subheading("8. Undersized database connection pool")
code("db/session.py:23-26  (pool_size=3, max_overflow=7)")
body(
    "API pool is only 3 connections (max 10 with overflow). Under moderate "
    "load, requests will queue waiting for a connection."
)
pdf.ln(2)

subheading("9. Frontend: sequential data fetches")
code("dashboard/page.tsx:65-93")
body(
    "Dashboard makes API calls one after another instead of in parallel. "
    "Using Promise.all() would cut load time roughly in half."
)
pdf.ln(2)

subheading("10. No data-fetching library (SWR / React Query)")
body(
    "The entire frontend uses raw fetch() + useState. This means no "
    "automatic caching, no background revalidation, and no request "
    "deduplication. Adding TanStack Query or SWR would significantly "
    "improve perceived speed."
)

# ---- MEDIUM ----
pdf.add_page()
heading("MEDIUM (Quality & Efficiency)")
separator()

subheading("11. Landing page bundles unused components")
code("page.tsx:6-8")
body(
    "All three comparison components are imported upfront but only one "
    "shows at a time. Dynamic imports would shrink the initial bundle."
)
pdf.ln(2)

subheading("12. Videos autoplay without lazy loading")
code("page.tsx:449, 634")
body(
    "Two <video autoPlay> elements block the critical rendering path on "
    "the landing page."
)
pdf.ln(2)

subheading("13. Billing tier checked via DB on every request")
body(
    "get_plan_tier() queries the Candidate table on every gated endpoint "
    "(~20 routers). Caching the tier in Redis or a request-scoped variable "
    "would eliminate 1-3 DB hits per request."
)
pdf.ln(2)

subheading("14. Over-using expensive LLM models")
body(
    "Sieve chat, salary coach, and interview prep all use Claude Sonnet "
    "when Claude Haiku would suffice - could save 30-50% on API costs."
)
pdf.ln(2)

subheading("15. No prompt caching")
body(
    "Resume parser sends the same ~4KB system prompt on every call. "
    "Anthropic prompt caching would reduce token costs."
)
pdf.ln(2)

subheading("16. No skeleton loaders on key pages")
body(
    "Matches, profile, upload pages show nothing while loading. Adding "
    "skeleton placeholders prevents layout shift and makes the app feel faster."
)
pdf.ln(2)

subheading("17. No job timeouts on queue workers")
code("worker.py:56-58")
body(
    "If a job hangs (e.g., LLM never responds), it blocks the worker "
    "forever. Adding job_timeout prevents this."
)
pdf.ln(2)

subheading("18. No form validation feedback during editing")
code("JobForm.tsx:183")
body(
    "Forms only show errors after submission, not as-you-type. Adding "
    "inline validation improves the form experience."
)
pdf.ln(2)

subheading("19. Accessibility gaps")
body(
    "- Almost no aria-label attributes across the app\n"
    '- Modals lack focus traps and role="dialog"\n'
    "- Color-only status indicators (no text for colorblind users)\n"
    '- No "skip to content" link'
)

# ---- LOW ----
pdf.add_page()
heading("LOW (Good Housekeeping)")
separator()

body(
    "- Fixed retry intervals in queue (queue.py:14-19) risk thundering "
    "herd - add jitter\n"
    "- Temp files can leak if LLM parsing fails (resume_parse_job.py:32)\n"
    "- No upload rate limiting (abuse via rapid 10MB uploads)\n"
    "- next.config.js disables TypeScript and ESLint checks during builds\n"
    "- No request tracing / Sentry context on LLM calls\n"
    "- SMS OTP polling has a hardcoded 2-second sleep() blocking thread"
)

# ---- PRIORITY TABLE ----
pdf.add_page()
heading("Recommended Implementation Priority")
separator()

# Table header
pdf.set_font("Helvetica", "B", 9)
col_w = [8, 70, 22, 80]
headers = ["#", "Change", "Effort", "Impact"]
for i, h in enumerate(headers):
    pdf.cell(col_w[i], 7, h, border=1, align="C")
pdf.ln()

# Table rows
pdf.set_font("Helvetica", "", 9)
rows = [
    ("1", "Add DB indexes (match, job)", "Low", "Huge - speeds up core pages"),
    ("2", "Queue resume parsing", "Low", "Huge - unblocks uploads"),
    ("3", "Stream Sieve chat responses", "Medium", "High - much better chat UX"),
    ("4", "Add retry logic to LLM calls", "Low", "High - fewer random errors"),
    ("5", "Parallel dashboard fetches", "Low", "Medium - faster dashboard"),
    ("6", "Fix N+1 queries in admin", "Medium", "High - admin pages usable"),
    ("7", "Dynamic imports on landing page", "Low", "Medium - faster first load"),
    ("8", "Background password reset email", "Low", "Medium - snappier login flow"),
    ("9", "Add skeleton loaders", "Medium", "Medium - better perceived speed"),
    ("10", "Adopt TanStack Query / SWR", "High", "High - systemic frontend fix"),
]
for row in rows:
    for i, val in enumerate(row):
        pdf.cell(col_w[i], 7, val, border=1)
    pdf.ln()

import os

output_path = os.path.join(os.path.dirname(__file__), "performance-analysis.pdf")
pdf.output(output_path)
print(f"PDF saved to {output_path}")
