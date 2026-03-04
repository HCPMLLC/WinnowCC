"""
Generate comprehensive test scripts for Winnow platform.
- Web Platform Test Script (all segments/tiers, no duplication)
- Mobile App Test Script (mobile-specific)
Export to PDF.
"""

from fpdf import FPDF

class TestScriptPDF(FPDF):
    def __init__(self, title_text):
        super().__init__()
        self.title_text = title_text
        self.set_auto_page_break(auto=True, margin=15)

    def header(self):
        self.set_font("Helvetica", "B", 8)
        self.set_text_color(100, 100, 100)
        self.cell(0, 5, self.title_text, align="L")
        self.cell(0, 5, f"Page {self.page_no()}/{{nb}}", align="R", new_x="LMARGIN", new_y="NEXT")
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(2)

    def footer(self):
        self.set_y(-10)
        self.set_font("Helvetica", "I", 7)
        self.set_text_color(130, 130, 130)
        self.cell(0, 5, "Winnow QA | Confidential", align="C")

    def add_cover(self, title, subtitle, tester_email):
        self.add_page()
        self.ln(40)
        self.set_font("Helvetica", "B", 28)
        self.set_text_color(30, 30, 30)
        self.cell(0, 14, title, align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(4)
        self.set_font("Helvetica", "", 14)
        self.set_text_color(80, 80, 80)
        self.cell(0, 8, subtitle, align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(10)
        self.set_font("Helvetica", "", 11)
        self.cell(0, 7, f"Tester: {tester_email}", align="C", new_x="LMARGIN", new_y="NEXT")
        self.cell(0, 7, "Date: _____________", align="C", new_x="LMARGIN", new_y="NEXT")
        self.cell(0, 7, "Environment: _____________", align="C", new_x="LMARGIN", new_y="NEXT")
        self.ln(10)
        self.set_font("Helvetica", "I", 9)
        self.set_text_color(100, 100, 100)
        self.multi_cell(0, 5,
            "Instructions: For each test case, record Pass/Fail/Skip in the Result column. "
            "Add notes for any failures or unexpected behavior. "
            "Tier-gating tests verify that limits are enforced -- test with appropriate tier account.",
            align="C")

    def section_header(self, num, title):
        self.set_font("Helvetica", "B", 13)
        self.set_text_color(20, 60, 120)
        self.cell(0, 7, f"{num}. {title}", new_x="LMARGIN", new_y="NEXT")
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(2)

    def subsection(self, num, title):
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(40, 40, 40)
        self.cell(0, 6, f"  {num} {title}", new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def test_table(self, rows):
        """rows = list of (id, test_case, expected_result)"""
        col_w = [14, 100, 56, 20]  # ID, Test Case, Expected, Result
        self.set_font("Helvetica", "B", 7.5)
        self.set_fill_color(230, 235, 245)
        self.set_text_color(30, 30, 30)
        self.cell(col_w[0], 5, "ID", border=1, fill=True, align="C")
        self.cell(col_w[1], 5, "Test Case", border=1, fill=True)
        self.cell(col_w[2], 5, "Expected Result", border=1, fill=True)
        self.cell(col_w[3], 5, "P/F/S", border=1, fill=True, align="C",
                  new_x="LMARGIN", new_y="NEXT")

        self.set_font("Helvetica", "", 7)
        self.set_text_color(20, 20, 20)
        for i, (tid, tc, er) in enumerate(rows):
            fill = i % 2 == 1
            if fill:
                self.set_fill_color(245, 247, 252)
            # Calculate row height based on content
            tc_lines = self.multi_cell(col_w[1], 4, tc, split_only=True)
            er_lines = self.multi_cell(col_w[2], 4, er, split_only=True)
            max_lines = max(len(tc_lines), len(er_lines), 1)
            row_h = max_lines * 4

            # Check page break
            if self.get_y() + row_h > 280:
                self.add_page()
                self.set_font("Helvetica", "B", 7.5)
                self.set_fill_color(230, 235, 245)
                self.cell(col_w[0], 5, "ID", border=1, fill=True, align="C")
                self.cell(col_w[1], 5, "Test Case", border=1, fill=True)
                self.cell(col_w[2], 5, "Expected Result", border=1, fill=True)
                self.cell(col_w[3], 5, "P/F/S", border=1, fill=True, align="C",
                          new_x="LMARGIN", new_y="NEXT")
                self.set_font("Helvetica", "", 7)
                self.set_text_color(20, 20, 20)
                if fill:
                    self.set_fill_color(245, 247, 252)

            y0 = self.get_y()
            self.cell(col_w[0], row_h, tid, border=1, fill=fill, align="C")
            x_tc = self.get_x()
            self.multi_cell(col_w[1], 4, tc, border=0)
            y_after_tc = self.get_y()
            self.set_xy(x_tc + col_w[1], y0)
            self.multi_cell(col_w[2], 4, er, border=0)
            y_after_er = self.get_y()
            self.set_xy(x_tc + col_w[1] + col_w[2], y0)
            self.cell(col_w[3], row_h, "", border=1, fill=fill, align="C")
            # Draw borders for tc and er columns
            self.rect(x_tc, y0, col_w[1], row_h)
            self.rect(x_tc + col_w[1], y0, col_w[2], row_h)
            self.set_xy(10, y0 + row_h)
        self.ln(2)

    def tier_gate_table(self, rows):
        """rows = list of (id, feature, tier_values_dict, test_action)
        tier_values_dict maps tier name to expected value"""
        tiers = list(rows[0][2].keys()) if rows else []
        tier_w = max(18, int(50 / max(len(tiers), 1)))
        col_w = [12, 52] + [tier_w] * len(tiers) + [50, 16]

        self.set_font("Helvetica", "B", 6.5)
        self.set_fill_color(230, 235, 245)
        self.set_text_color(30, 30, 30)
        self.cell(col_w[0], 5, "ID", border=1, fill=True, align="C")
        self.cell(col_w[1], 5, "Feature / Limit", border=1, fill=True)
        for i, t in enumerate(tiers):
            self.cell(col_w[2 + i], 5, t, border=1, fill=True, align="C")
        self.cell(col_w[-2], 5, "How to Test", border=1, fill=True)
        self.cell(col_w[-1], 5, "P/F/S", border=1, fill=True, align="C",
                  new_x="LMARGIN", new_y="NEXT")

        self.set_font("Helvetica", "", 6.5)
        self.set_text_color(20, 20, 20)
        total_w = sum(col_w)
        for i, (tid, feat, tier_vals, how) in enumerate(rows):
            fill = i % 2 == 1
            if fill:
                self.set_fill_color(245, 247, 252)

            feat_lines = self.multi_cell(col_w[1], 3.5, feat, split_only=True)
            how_lines = self.multi_cell(col_w[-2], 3.5, how, split_only=True)
            max_lines = max(len(feat_lines), len(how_lines), 1)
            row_h = max(max_lines * 3.5, 5)

            if self.get_y() + row_h > 280:
                self.add_page()
                self.set_font("Helvetica", "B", 6.5)
                self.set_fill_color(230, 235, 245)
                self.cell(col_w[0], 5, "ID", border=1, fill=True, align="C")
                self.cell(col_w[1], 5, "Feature / Limit", border=1, fill=True)
                for j, t in enumerate(tiers):
                    self.cell(col_w[2 + j], 5, t, border=1, fill=True, align="C")
                self.cell(col_w[-2], 5, "How to Test", border=1, fill=True)
                self.cell(col_w[-1], 5, "P/F/S", border=1, fill=True, align="C",
                          new_x="LMARGIN", new_y="NEXT")
                self.set_font("Helvetica", "", 6.5)
                self.set_text_color(20, 20, 20)
                if fill:
                    self.set_fill_color(245, 247, 252)

            y0 = self.get_y()
            self.cell(col_w[0], row_h, tid, border=1, fill=fill, align="C")
            x1 = self.get_x()
            self.multi_cell(col_w[1], 3.5, feat, border=0)
            self.set_xy(x1 + col_w[1], y0)
            for j, t in enumerate(tiers):
                val = str(tier_vals.get(t, ""))
                self.cell(col_w[2 + j], row_h, val, border=1, fill=fill, align="C")
            x_how = self.get_x()
            self.multi_cell(col_w[-2], 3.5, how, border=0)
            self.set_xy(x_how + col_w[-2], y0)
            self.cell(col_w[-1], row_h, "", border=1, fill=fill, align="C")
            # borders
            self.rect(x1, y0, col_w[1], row_h)
            self.rect(x_how, y0, col_w[-2], row_h)
            self.set_xy(10, y0 + row_h)
        self.ln(2)


def build_web_script():
    pdf = TestScriptPDF("Winnow Web Platform - Comprehensive Test Script")
    pdf.alias_nb_pages()
    pdf.add_cover(
        "Winnow Web Platform",
        "Comprehensive Test Script - All Segments & Tiers",
        "rlevi@hcpm.llc"
    )

    # =========================================================================
    # SECTION 1: SHARED FEATURES
    # =========================================================================
    pdf.add_page()
    pdf.section_header("1", "SHARED FEATURES (All Segments)")

    pdf.subsection("1.1", "Authentication")
    pdf.test_table([
        ("A-01", "Sign up with email/password as new candidate", "Account created, redirected to onboarding"),
        ("A-02", "Sign up with email/password as new employer", "Account created, redirected to employer onboarding"),
        ("A-03", "Sign up with email/password as new recruiter", "Account created, 14-day trial starts"),
        ("A-04", "Log in with valid credentials", "JWT cookie set, redirected to dashboard"),
        ("A-05", "Log in with invalid password", "Error message, no session created"),
        ("A-06", "Log in with unregistered email", "Error message displayed"),
        ("A-07", "OAuth login via Auth0 (Google/social)", "Auth0 redirect, account created/linked"),
        ("A-08", "Email verification flow", "Verification email sent, link activates account"),
        ("A-09", "Forgot password - request reset email", "Reset email sent with valid link"),
        ("A-10", "Reset password using email link", "Password updated, can log in with new password"),
        ("A-11", "Log out", "Session cookie cleared, redirected to login"),
        ("A-12", "Session persistence across browser tabs", "Same session active in all tabs"),
        ("A-13", "Session expiry after token timeout", "Redirected to login after token expires"),
    ])

    pdf.subsection("1.2", "Sieve AI Concierge")
    pdf.test_table([
        ("S-01", "Open Sieve chat interface", "Chat UI loads with welcome message"),
        ("S-02", "Send a message and receive AI response", "Streaming response appears in chat"),
        ("S-03", "Rate limit: send 11+ messages in 1 minute", "429 error after 10th message in 1 min"),
        ("S-04", "Verify conversation history persists across page reload", "Previous messages load on return"),
        ("S-05", "Proactive triggers/nudges display", "Contextual suggestions appear based on profile gaps"),
        ("S-06", "Clear chat history", "History cleared, fresh conversation starts"),
        ("S-07", "Escalate to live support agent", "WebSocket connection, live agent joins chat"),
        ("S-08", "Candidate context: ask career/resume question", "Response references candidate profile data"),
        ("S-09", "Employer context: ask hiring/JD question", "Response uses employer hiring context"),
        ("S-10", "Recruiter context: ask placement question", "Response uses recruiter CRM context"),
    ])

    pdf.subsection("1.3", "Billing & Subscription")
    pdf.test_table([
        ("B-01", "View public pricing page for candidates", "Free/Starter/Pro tiers shown with features"),
        ("B-02", "View public pricing page for employers", "Starter/Pro/Enterprise tiers shown"),
        ("B-03", "View public pricing page for recruiters", "Solo/Team/Agency tiers shown"),
        ("B-04", "Initiate Stripe checkout for plan upgrade", "Redirected to Stripe checkout page"),
        ("B-05", "Complete Stripe checkout successfully", "Plan tier updated, features unlocked"),
        ("B-06", "Access Stripe customer portal", "Portal opens with subscription management"),
        ("B-07", "View billing status with usage/limits", "Current plan, usage counts, limits displayed"),
        ("B-08", "Stripe webhook processes subscription change", "Tier updated in real-time after webhook"),
        ("B-09", "Downgrade plan tier", "Features restricted to new tier limits"),
        ("B-10", "Cancel subscription", "Reverts to free tier at period end"),
    ])

    pdf.subsection("1.4", "Account Management")
    pdf.test_table([
        ("AC-01", "Request GDPR data export (Starter+ tier)", "ZIP file generated with all user data"),
        ("AC-02", "Preview data export contents", "Summary of exportable data shown"),
        ("AC-03", "Data export blocked on free tier", "402 error, upgrade prompt shown"),
        ("AC-04", "Request account deletion", "Confirmation prompt, account + all data removed"),
        ("AC-05", "Verify cascade delete removes all related records", "No orphaned data in DB after deletion"),
    ])

    pdf.subsection("1.5", "Landing Page & Navigation")
    pdf.test_table([
        ("L-01", "Landing page loads with candidate (seeker) view", "Hero, features, pricing for job seekers"),
        ("L-02", "Toggle to employer audience", "Employer hero, features, pricing, ATS comparisons"),
        ("L-03", "Toggle to recruiter audience", "Recruiter hero, features, pricing, CRM comparisons"),
        ("L-04", "Competitive comparison pages load", "vs Greenhouse/Lever/Workable (employers), vs Bullhorn/CATSOne (recruiters)"),
        ("L-05", "Trust & Safety page accessible", "Trust documentation displayed"),
        ("L-06", "Privacy policy and Terms of Service pages", "Legal pages load correctly"),
    ])

    # =========================================================================
    # SECTION 2: CANDIDATE FEATURES
    # =========================================================================
    pdf.section_header("2", "CANDIDATE FEATURES")

    pdf.subsection("2.1", "Onboarding")
    pdf.test_table([
        ("C-01", "Complete candidate onboarding flow", "Profile created with preferences, redirected to dashboard"),
        ("C-02", "Set job preferences (titles, locations, remote, salary)", "Preferences saved and reflected in matches"),
        ("C-03", "Accept Terms of Service and Privacy Policy", "Consent recorded, onboarding completes"),
    ])

    pdf.subsection("2.2", "Resume Upload & Parsing")
    pdf.test_table([
        ("C-04", "Upload PDF resume (< 10MB)", "File accepted, parsing job queued"),
        ("C-05", "Upload DOCX resume", "File accepted, parsing job queued"),
        ("C-06", "Reject oversized file (> 10MB)", "Error message, upload blocked"),
        ("C-07", "Reject unsupported file type (e.g., .jpg)", "Error message shown"),
        ("C-08", "Resume parsing completes successfully", "Profile populated with extracted data"),
        ("C-09", "View parsing status (pending/processing/complete)", "Status updates shown during processing"),
    ])

    pdf.subsection("2.3", "Profile Management")
    pdf.test_table([
        ("C-10", "View candidate profile", "All parsed data displayed (skills, experience, education)"),
        ("C-11", "Edit profile fields", "Changes saved and reflected"),
        ("C-12", "View profile completeness score", "Percentage shown with improvement suggestions"),
        ("C-13", "Add/edit/delete professional references", "References CRUD works correctly"),
        ("C-14", "View enhancement suggestions", "AI suggestions for profile improvement displayed"),
    ])

    pdf.subsection("2.4", "Job Matches & IPS")
    pdf.test_table([
        ("C-15", "View job matches list", "Matches displayed sorted by score"),
        ("C-16", "View match detail with IPS breakdown", "Score components shown (skills, experience, etc.)"),
        ("C-17", "View matched/missing skills for a job", "Skills comparison displayed with icons"),
        ("C-18", "Refresh matches", "New matches computed, counter incremented"),
        ("C-19", "Update match status (saved/applied/interviewing/offer/rejected)", "Status updated, reflected in applications"),
        ("C-20", "Record job application", "Application tracked with timestamp"),
        ("C-21", "Filter matches by IPS score", "Only matches above threshold shown"),
    ])

    pdf.subsection("2.5", "Tailored Resumes & Cover Letters")
    pdf.test_table([
        ("C-22", "Request tailored resume for a job match", "Job queued, tailored resume generated"),
        ("C-23", "Download tailored resume (DOCX)", "Document downloads with job-specific content"),
        ("C-24", "Request cover letter for a job match", "Cover letter generated for specific job"),
        ("C-25", "View all generated documents", "Document list with job, date, download links"),
    ])

    pdf.subsection("2.6", "Interview Prep & AI Features")
    pdf.test_table([
        ("C-26", "Generate interview prep content", "Questions, tips, company research provided"),
        ("C-27", "Retry failed interview prep generation", "Regeneration succeeds"),
        ("C-28", "View gap recommendations for a job", "Skill gaps identified with learning suggestions"),
        ("C-29", "View rejection feedback (after rejection)", "Analysis of why application was rejected"),
        ("C-30", "Draft email to employer/recruiter", "AI-generated email draft with context"),
        ("C-31", "View status prediction for application", "ML prediction of interview probability"),
    ])

    pdf.subsection("2.7", "Career Intelligence (Pro Only)")
    pdf.test_table([
        ("C-32", "View market position for a job", "Percentile rank among applicants shown"),
        ("C-33", "View salary intelligence by role/location", "Salary percentiles (p10-p90) displayed"),
        ("C-34", "View career trajectory (6/12 month prediction)", "Projected roles, salary, growth areas shown"),
        ("C-35", "Salary negotiation coaching", "Negotiation guidance and talking points provided"),
        ("C-36", "Career intelligence blocked on Free/Starter", "402 error, upgrade prompt displayed"),
    ])

    pdf.subsection("2.8", "Dashboard & Applications")
    pdf.test_table([
        ("C-37", "View candidate dashboard", "Metrics, recommendations, weekly digest shown"),
        ("C-38", "View application history", "All applications listed with status filters"),
        ("C-39", "Dashboard recommendations update based on activity", "Relevant suggestions shown"),
    ])

    # =========================================================================
    # SECTION 3: CANDIDATE TIER-GATING
    # =========================================================================
    pdf.section_header("3", "CANDIDATE TIER-GATING VERIFICATION")

    pdf.tier_gate_table([
        ("CT-01", "Matches visible", {"Free": "5", "Starter": "25", "Pro": "Unlim"},
         "List matches, verify count cap"),
        ("CT-02", "Match refreshes/mo", {"Free": "10", "Starter": "50", "Pro": "Unlim"},
         "Refresh matches, verify counter"),
        ("CT-03", "Tailored resumes/mo", {"Free": "1", "Starter": "10", "Pro": "Unlim"},
         "Generate tailored resumes until blocked"),
        ("CT-04", "Cover letters/mo", {"Free": "1", "Starter": "10", "Pro": "Unlim"},
         "Generate cover letters until blocked"),
        ("CT-05", "Interview preps/mo", {"Free": "0", "Starter": "3", "Pro": "Unlim"},
         "Request interview prep, verify access"),
        ("CT-06", "Sieve messages/day", {"Free": "3", "Starter": "50", "Pro": "Unlim"},
         "Send messages until daily limit hit"),
        ("CT-07", "Semantic searches/day", {"Free": "0", "Starter": "5", "Pro": "Unlim"},
         "Run semantic search, verify counter"),
        ("CT-08", "Gap recs/day", {"Free": "3", "Starter": "15", "Pro": "Unlim"},
         "Request gap recs until daily limit"),
        ("CT-09", "Email drafts/day", {"Free": "3", "Starter": "15", "Pro": "Unlim"},
         "Draft emails until daily limit"),
        ("CT-10", "Data export", {"Free": "No", "Starter": "Yes", "Pro": "Yes"},
         "Request export on each tier"),
        ("CT-11", "Career intelligence", {"Free": "No", "Starter": "No", "Pro": "Yes"},
         "Access /insights on each tier"),
        ("CT-12", "Salary negotiation", {"Free": "No", "Starter": "No", "Pro": "Yes"},
         "Access salary coach on each tier"),
        ("CT-13", "IPS detail level", {"Free": "Basic", "Starter": "Basic", "Pro": "Full+Coach"},
         "View match detail, check IPS depth"),
        ("CT-14", "Submission details", {"Free": "Basic", "Starter": "Std", "Pro": "Full"},
         "Check submission info visibility"),
        ("CT-15", "Submission notifications", {"Free": "No", "Starter": "Yes", "Pro": "Yes"},
         "Verify notification delivery by tier"),
        ("CT-16", "Job sources", {"Free": "Board", "Starter": "Brd+Emp", "Pro": "All"},
         "Check job sources in match results"),
    ])

    # =========================================================================
    # SECTION 4: EMPLOYER FEATURES
    # =========================================================================
    pdf.section_header("4", "EMPLOYER FEATURES")

    pdf.subsection("4.1", "Onboarding & Profile")
    pdf.test_table([
        ("E-01", "Complete employer onboarding", "Company workspace created"),
        ("E-02", "Create/update company profile (name, logo, website)", "Profile saved and displayed"),
        ("E-03", "View employer dashboard metrics", "Active jobs, views, applications, saved candidates"),
    ])

    pdf.subsection("4.2", "Job Posting & Management")
    pdf.test_table([
        ("E-04", "Create new job posting", "Job created in draft status"),
        ("E-05", "Edit job posting details", "Changes saved"),
        ("E-06", "Publish/activate job posting", "Job visible to candidates"),
        ("E-07", "Pause job posting", "Job hidden from candidates, distribution paused"),
        ("E-08", "Close job posting", "Job removed from boards, marked closed"),
        ("E-09", "Upload application form for a job", "Form attached to job posting"),
        ("E-10", "View submissions/applicants for a job", "Applicant list with match scores"),
        ("E-11", "AI job parsing (paste JD text)", "Job fields auto-populated from text"),
    ])

    pdf.subsection("4.3", "Candidate Search & Pipeline")
    pdf.test_table([
        ("E-12", "Search candidates with filters (skills, location, title)", "Matching candidates returned with scores"),
        ("E-13", "View candidate profile detail", "Full profile with match details"),
        ("E-14", "Save candidate to favorites", "Candidate added to saved list"),
        ("E-15", "Add candidate to talent pipeline", "Pipeline entry created with stage"),
        ("E-16", "Update pipeline stage/notes", "Stage and notes updated"),
        ("E-17", "Send introduction request to candidate", "Intro request sent, counter incremented"),
        ("E-18", "View introduction request status", "Sent/accepted/declined status shown"),
    ])

    pdf.subsection("4.4", "Multi-Board Distribution")
    pdf.test_table([
        ("E-19", "Add job board connection (Indeed, ZipRecruiter)", "Board credentials saved"),
        ("E-20", "List connected boards", "All connections shown with status"),
        ("E-21", "Distribute job to multiple boards", "Job posted to selected boards"),
        ("E-22", "View distribution status per board", "Success/failure per board shown"),
    ])

    pdf.subsection("4.5", "Analytics & Intelligence")
    pdf.test_table([
        ("E-23", "View analytics overview dashboard", "Applications, time-to-hire metrics"),
        ("E-24", "View pipeline funnel by board (Starter+)", "Funnel visualization by source"),
        ("E-25", "View cost-per-hire by channel (Pro+)", "Cost breakdown by board/source"),
        ("E-26", "View AI hiring recommendations", "Actionable suggestions displayed"),
        ("E-27", "Bias detection in job posting (Starter+)", "Language bias flagged with suggestions"),
        ("E-28", "Salary intelligence for role (Pro+)", "Market salary data shown"),
        ("E-29", "Market intelligence dashboard", "Hiring trends, competitor activity"),
    ])

    pdf.subsection("4.6", "Compliance & Workspace")
    pdf.test_table([
        ("E-30", "EEOC compliance reporting", "Aggregate demographics report generated"),
        ("E-31", "View audit log", "Access/action trail displayed"),
        ("E-32", "Hiring workspace collaboration", "Multiple team members can collaborate on job"),
    ])

    # =========================================================================
    # SECTION 5: EMPLOYER TIER-GATING
    # =========================================================================
    pdf.section_header("5", "EMPLOYER TIER-GATING VERIFICATION")

    pdf.tier_gate_table([
        ("ET-01", "Active jobs", {"Free": "1", "Starter": "5", "Pro": "25", "Ent": "Unlim"},
         "Create jobs until limit reached"),
        ("ET-02", "Candidate views/mo", {"Free": "5", "Starter": "50", "Pro": "200", "Ent": "Unlim"},
         "View candidate profiles, verify counter"),
        ("ET-03", "AI job parsing/mo", {"Free": "1", "Starter": "10", "Pro": "Unlim", "Ent": "Unlim"},
         "Parse JDs until limit hit"),
        ("ET-04", "Intro requests/mo", {"Free": "2", "Starter": "15", "Pro": "50", "Ent": "Unlim"},
         "Send intro requests until blocked"),
        ("ET-05", "Distribution boards", {"Free": "Google", "Starter": "+Indeed+Zip", "Pro": "All", "Ent": "All"},
         "Attempt distribution to each board"),
        ("ET-06", "Cross-board analytics", {"Free": "No", "Starter": "Basic", "Pro": "Full", "Ent": "Full"},
         "Access analytics dashboard"),
        ("ET-07", "Bias detection", {"Free": "No", "Starter": "Basic", "Pro": "Full", "Ent": "Full"},
         "Submit JD for bias scan"),
        ("ET-08", "Salary intelligence", {"Free": "No", "Starter": "No", "Pro": "Yes", "Ent": "Yes"},
         "Access salary data"),
        ("ET-09", "Submission view depth", {"Free": "Basic", "Starter": "Std", "Pro": "Full", "Ent": "Full"},
         "View candidate submission details"),
        ("ET-10", "Duplicate highlighting", {"Free": "No", "Starter": "Yes", "Pro": "Yes", "Ent": "Yes"},
         "Check duplicate candidate flags"),
        ("ET-11", "Sieve messages/day", {"Free": "10", "Starter": "30", "Pro": "100", "Ent": "Unlim"},
         "Send Sieve messages until limit"),
    ])

    # =========================================================================
    # SECTION 6: RECRUITER FEATURES
    # =========================================================================
    pdf.section_header("6", "RECRUITER FEATURES")

    pdf.subsection("6.1", "Onboarding & Profile")
    pdf.test_table([
        ("R-01", "Complete recruiter onboarding", "Workspace created, 14-day trial activated"),
        ("R-02", "Verify 14-day trial countdown", "Trial end date shown, features accessible"),
        ("R-03", "Create/update recruiter profile", "Profile info saved"),
        ("R-04", "View current plan and limits", "Tier, limits, CRM level displayed"),
    ])

    pdf.subsection("6.2", "Team Management")
    pdf.test_table([
        ("R-05", "Invite team member", "Invitation sent, member appears in list"),
        ("R-06", "List team members with permissions", "All members and roles shown"),
        ("R-07", "Update team member role", "Role/permissions changed"),
        ("R-08", "Verify seat limit enforcement", "Cannot add members beyond seat limit"),
    ])

    pdf.subsection("6.3", "Client CRM")
    pdf.test_table([
        ("R-09", "Create client company", "Client added with contact info"),
        ("R-10", "List all clients", "Client list with active job counts"),
        ("R-11", "View client detail (jobs, placements)", "Full client profile with history"),
        ("R-12", "Update client information", "Changes saved"),
        ("R-13", "Create job order for client", "Job order linked to client"),
        ("R-14", "Verify CRM level: basic vs full", "Solo=basic (limited), Team/Agency=full features"),
    ])

    pdf.subsection("6.4", "Pipeline & Candidates")
    pdf.test_table([
        ("R-15", "Add candidate to pipeline", "Candidate added with initial stage"),
        ("R-16", "View pipeline with stage filters", "Filtered by Lead/Contacted/Screening/etc."),
        ("R-17", "Update pipeline stage and notes", "Stage transition recorded"),
        ("R-18", "View candidate database (imported + discovered)", "All candidates listed"),
        ("R-19", "View candidate profile detail", "Full profile with brief"),
        ("R-20", "Log activity (call, email, meeting, submission)", "Activity recorded in timeline"),
        ("R-21", "View activity history", "Chronological activity log"),
        ("R-22", "View prioritized daily action queue", "Actions ranked by priority"),
    ])

    pdf.subsection("6.5", "Briefs & Intelligence")
    pdf.test_table([
        ("R-23", "Generate AI candidate brief", "Summary, strengths, gaps, placement likelihood"),
        ("R-24", "Salary intelligence lookup", "Market rates by role/location"),
        ("R-25", "Market intelligence dashboard", "Hiring trends, competitor data"),
    ])

    pdf.subsection("6.6", "Outreach Sequences (Team/Agency)")
    pdf.test_table([
        ("R-26", "Create email outreach sequence", "Sequence created with steps/templates"),
        ("R-27", "Edit sequence steps and timing", "Changes saved"),
        ("R-28", "Enroll candidates in sequence", "Candidates added, emails scheduled"),
        ("R-29", "Unenroll candidate from sequence", "Candidate removed, emails stopped"),
        ("R-30", "View enrollment history and open rates", "Stats displayed per candidate"),
        ("R-31", "Verify sequences blocked on Solo tier", "Feature unavailable, upgrade prompt"),
    ])

    pdf.subsection("6.7", "Bulk Upload & Migration")
    pdf.test_table([
        ("R-32", "Bulk import candidates (resume batch)", "Resumes parsed, candidates added"),
        ("R-33", "Verify batch size limit enforcement", "Exceeding batch limit shows error"),
        ("R-34", "ATS/CRM data migration (Bullhorn/Recruit CRM/CATSone/Zoho)", "Data imported with mapping"),
        ("R-35", "View migration status", "Progress and completion shown"),
    ])

    pdf.subsection("6.8", "Introduction Requests & Settings")
    pdf.test_table([
        ("R-36", "Send introduction request to candidate", "Request sent, counter incremented"),
        ("R-37", "View intro request usage vs monthly limit", "Usage count and limit shown"),
        ("R-38", "Recruiter settings (email signature, templates)", "Settings saved"),
    ])

    # =========================================================================
    # SECTION 7: RECRUITER TIER-GATING
    # =========================================================================
    pdf.section_header("7", "RECRUITER TIER-GATING VERIFICATION")

    pdf.tier_gate_table([
        ("RT-01", "Seats", {"Trial": "1", "Solo": "1", "Team": "10", "Agency": "Unlim"},
         "Add team members until limit"),
        ("RT-02", "Candidate briefs/mo", {"Trial": "Unlim", "Solo": "20", "Team": "100", "Agency": "500"},
         "Generate briefs until limit"),
        ("RT-03", "Salary lookups/mo", {"Trial": "Unlim", "Solo": "5", "Team": "50", "Agency": "Unlim"},
         "Run salary lookups until limit"),
        ("RT-04", "Smart job parsing/mo", {"Trial": "10", "Solo": "0", "Team": "10", "Agency": "Unlim"},
         "Parse job descriptions"),
        ("RT-05", "Active job orders", {"Trial": "Unlim", "Solo": "10", "Team": "50", "Agency": "Unlim"},
         "Create job orders until limit"),
        ("RT-06", "Pipeline candidates", {"Trial": "Unlim", "Solo": "100", "Team": "500", "Agency": "Unlim"},
         "Add candidates until limit"),
        ("RT-07", "Clients", {"Trial": "Unlim", "Solo": "5", "Team": "25", "Agency": "Unlim"},
         "Create clients until limit"),
        ("RT-08", "Intro requests/mo", {"Trial": "Unlim", "Solo": "20", "Team": "75", "Agency": "Unlim"},
         "Send intros until limit"),
        ("RT-09", "Resume imports/mo", {"Trial": "50", "Solo": "25", "Team": "200", "Agency": "Unlim"},
         "Import resumes until limit"),
        ("RT-10", "Resume imports/batch", {"Trial": "10", "Solo": "10", "Team": "25", "Agency": "50"},
         "Upload batch exceeding limit"),
        ("RT-11", "Outreach sequences", {"Trial": "No", "Solo": "No", "Team": "Yes(3)", "Agency": "Yes(10)"},
         "Create sequences on each tier"),
        ("RT-12", "Enrollments/mo", {"Trial": "0", "Solo": "0", "Team": "50", "Agency": "200"},
         "Enroll candidates until limit"),
        ("RT-13", "Cross-vendor dedup", {"Trial": "Yes", "Solo": "No", "Team": "Yes", "Agency": "Yes"},
         "Check duplicate detection"),
        ("RT-14", "Contract vehicle mgmt", {"Trial": "Yes", "Solo": "No", "Team": "Yes", "Agency": "Yes"},
         "Access contract management"),
        ("RT-15", "Client hierarchy", {"Trial": "Yes", "Solo": "No", "Team": "Yes", "Agency": "Yes"},
         "Access hierarchy features"),
        ("RT-16", "Submission analytics", {"Trial": "Yes", "Solo": "No", "Team": "Yes", "Agency": "Yes"},
         "Access submission analytics"),
        ("RT-17", "CRM level", {"Trial": "Full", "Solo": "Basic", "Team": "Full", "Agency": "Full"},
         "Verify CRM features by tier"),
        ("RT-18", "Sieve messages/day", {"Trial": "30", "Solo": "30", "Team": "30", "Agency": "30"},
         "Send messages, verify daily cap"),
    ])

    # =========================================================================
    # SECTION 8: ADMIN FEATURES
    # =========================================================================
    pdf.section_header("8", "ADMIN FEATURES")
    pdf.test_table([
        ("AD-01", "Admin: search/view candidates", "Candidate list with filters"),
        ("AD-02", "Admin: manage employers", "Employer list with actions"),
        ("AD-03", "Admin: manage recruiters", "Recruiter list with actions"),
        ("AD-04", "Admin: moderate job postings", "Job review/approve/reject"),
        ("AD-05", "Admin: override user plan tier", "Tier changed via admin token"),
        ("AD-06", "Admin: view support tickets", "Ticket list with status"),
        ("AD-07", "Admin: user lookup and billing debug", "User details and billing info shown"),
        ("AD-08", "Admin: view audit logs", "Full audit trail accessible"),
        ("AD-09", "Admin: KPI dashboard", "Key metrics displayed"),
        ("AD-10", "Admin: trust/consent override", "Consent status modified"),
        ("AD-11", "Admin: job quality review", "Quality scoring dashboard"),
        ("AD-12", "Admin: scheduler management", "Job scheduler status and controls"),
    ])

    # =========================================================================
    # SECTION 9: INTEGRATION & EDGE CASES
    # =========================================================================
    pdf.section_header("9", "INTEGRATION & EDGE CASES")
    pdf.test_table([
        ("I-01", "Stripe webhook: subscription created", "User tier updated immediately"),
        ("I-02", "Stripe webhook: payment failed", "Grace period, user notified"),
        ("I-03", "Stripe webhook: subscription canceled", "Reverts to free at period end"),
        ("I-04", "Daily counter resets at midnight", "New day = fresh daily limits"),
        ("I-05", "Monthly counter resets at billing cycle", "New month = fresh monthly limits"),
        ("I-06", "Queue worker processes jobs (matching, parsing, tailoring)", "Jobs complete within timeout"),
        ("I-07", "Job fraud detection (14-signal check)", "Fraudulent jobs flagged/blocked"),
        ("I-08", "Job deduplication", "Duplicate jobs identified and merged"),
        ("I-09", "Email delivery (Resend): welcome, reset, digest", "Emails delivered successfully"),
        ("I-10", "SMS OTP delivery (Telnyx)", "SMS received with valid code"),
        ("I-11", "Concurrent users on same account", "No session conflicts"),
        ("I-12", "Chrome extension: LinkedIn sourcing", "Extension captures candidate data"),
        ("I-13", "Error tracking (Sentry) captures exceptions", "Errors logged with context"),
    ])

    # Sign-off
    pdf.ln(5)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, "SIGN-OFF", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(95, 7, "Tester Signature: ________________________")
    pdf.cell(95, 7, "Date: ________________________", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(95, 7, "Total Pass: ____  Fail: ____  Skip: ____")
    pdf.cell(95, 7, "Approved By: ________________________", new_x="LMARGIN", new_y="NEXT")

    return pdf


def build_mobile_script():
    pdf = TestScriptPDF("Winnow Mobile App - Test Script")
    pdf.alias_nb_pages()
    pdf.add_cover(
        "Winnow Mobile App",
        "Comprehensive Test Script (iOS & Android)",
        "rlevi@hcpm.llc"
    )

    # =========================================================================
    # SECTION 1: INSTALLATION & LAUNCH
    # =========================================================================
    pdf.add_page()
    pdf.section_header("1", "INSTALLATION & LAUNCH")
    pdf.test_table([
        ("M-01", "Install app from TestFlight (iOS) / Play Store (Android)", "App installs without errors"),
        ("M-02", "Launch app - splash screen displays", "Logo and branding shown"),
        ("M-03", "OTA update check on launch", "If update available, prompt to restart shown"),
        ("M-04", "App opens on login screen for new install", "Login/signup options visible"),
    ])

    # =========================================================================
    # SECTION 2: AUTHENTICATION
    # =========================================================================
    pdf.section_header("2", "MOBILE AUTHENTICATION")
    pdf.test_table([
        ("M-05", "Sign up with email/password + role selection", "Account created, role-specific onboarding starts"),
        ("M-06", "Log in with valid credentials", "JWT stored securely, redirected to dashboard"),
        ("M-07", "Log in with invalid password", "Error shown, no session created"),
        ("M-08", "Forgot password - request reset email", "Reset email sent"),
        ("M-09", "Reset password via deep link", "Password updated, can log in"),
        ("M-10", "MFA: email OTP verification", "OTP email received, code accepted"),
        ("M-11", "MFA: SMS OTP verification", "OTP SMS received, code accepted"),
        ("M-12", "MFA: switch between email and SMS delivery", "Delivery method changed, new code sent"),
        ("M-13", "MFA: resend OTP code", "New code sent"),
        ("M-14", "Session persistence after app close/reopen", "User stays logged in"),
        ("M-15", "Session recovery on app restart", "Token validated, auto-redirects to dashboard"),
        ("M-16", "401 response triggers automatic logout", "User redirected to login"),
        ("M-17", "Log out clears secure storage", "Token removed, login screen shown"),
    ])

    # =========================================================================
    # SECTION 3: CANDIDATE MOBILE FEATURES
    # =========================================================================
    pdf.section_header("3", "CANDIDATE MOBILE FEATURES")

    pdf.subsection("3.1", "Onboarding (3-Step Flow)")
    pdf.test_table([
        ("M-18", "Step 1: Enter personal info (name, phone, location, experience)", "Fields validated, progress dots update"),
        ("M-19", "Step 2: Set job preferences (titles, locations, remote, salary)", "Preferences saved"),
        ("M-20", "Step 3: Accept TOS and Privacy Policy", "Consent recorded, links to winnowcc.ai work"),
        ("M-21", "Complete onboarding, redirect to dashboard", "Dashboard loads with empty state"),
    ])

    pdf.subsection("3.2", "Dashboard Tab")
    pdf.test_table([
        ("M-22", "View dashboard metrics (completeness, jobs, applications, interviews)", "All metric cards display correctly"),
        ("M-23", "'View Matches' CTA navigates to matches tab", "Matches tab selected"),
    ])

    pdf.subsection("3.3", "Matches Tab")
    pdf.test_table([
        ("M-24", "View match list with score, company, location, remote flag", "Match cards render correctly"),
        ("M-25", "Match cards show matched skills tags", "Skill tags visible on cards"),
        ("M-26", "Pull-to-refresh match list", "List refreshes with latest data"),
        ("M-27", "Empty state with resume upload prompt", "Prompt shown when no matches"),
        ("M-28", "Tap match card to open detail view", "Full match detail screen opens"),
    ])

    pdf.subsection("3.4", "Match Detail Screen")
    pdf.test_table([
        ("M-29", "View job title, company, location, salary", "All job info displayed"),
        ("M-30", "View match score and interview probability badges", "Score badges render"),
        ("M-31", "View matched vs missing skills with icons", "Skills comparison shown"),
        ("M-32", "View skill gap recommendations card", "Gap recs display with suggestions"),
        ("M-33", "View culture fit summary card", "Culture analysis displayed"),
        ("M-34", "Change application status (Saved/Applied/Interviewing/Offer/Rejected)", "Status updates optimistically"),
        ("M-35", "View status prediction card (when Applied)", "ML prediction shown"),
        ("M-36", "View interview prep panel (when Interviewing/Offer)", "Prep content displayed"),
        ("M-37", "View rejection feedback card (when Rejected)", "Feedback analysis shown"),
        ("M-38", "Generate ATS-tailored resume with download", "Resume generated, download works"),
        ("M-39", "Draft email modal", "AI email draft opens in modal"),
        ("M-40", "Salary coach modal (when Offer received)", "Negotiation guidance shown"),
        ("M-41", "Link to view original job posting", "External link opens correctly"),
    ])

    pdf.subsection("3.5", "Applications Tab")
    pdf.test_table([
        ("M-42", "View applications with status filter chips", "All/Saved/Applied/Interviewing/Offer/Rejected"),
        ("M-43", "Status badges show count indicators", "Counts accurate per status"),
        ("M-44", "Update application status from list", "Status updates with optimistic UI"),
        ("M-45", "Empty state when no applications", "Prompt to browse matches"),
    ])

    pdf.subsection("3.6", "Profile Tab")
    pdf.test_table([
        ("M-46", "View profile summary (name, skills, experience, education)", "Profile data renders"),
        ("M-47", "View top 8 skills display", "Skills shown as tags"),
        ("M-48", "View profile completeness with progress bar", "Percentage and bar shown"),
        ("M-49", "View enhancement suggestions card", "AI improvement tips displayed"),
        ("M-50", "Edit job preferences inline (titles, locations, remote, salary, type)", "Preferences saved on submit"),
        ("M-51", "'Full editing on web' notice displayed", "Notice with winnowcc.ai link shown"),
    ])

    pdf.subsection("3.7", "Profile Submenu Screens")
    pdf.test_table([
        ("M-52", "Resume upload: pick PDF/DOCX (max 10MB)", "Document picker opens, file accepted"),
        ("M-53", "Resume upload: reject oversized or wrong format", "Error message shown"),
        ("M-54", "Resume parsing progress (polling 20 attempts)", "Status updates shown during parsing"),
        ("M-55", "Resume parsing success redirects to profile", "Profile updated with parsed data"),
        ("M-56", "Documents screen: list tailored resumes/cover letters", "Documents listed by job"),
        ("M-57", "Documents: download and share functionality", "File downloads, share sheet opens"),
        ("M-58", "References: add new reference", "Modal form, reference saved"),
        ("M-59", "References: edit existing reference", "Fields update, changes saved"),
        ("M-60", "References: delete reference", "Reference removed from list"),
        ("M-61", "References: toggle active/inactive", "Status toggled"),
        ("M-62", "Career insights: trajectory analysis (Pro only)", "Career level, velocity, projections shown"),
        ("M-63", "Career insights: salary intelligence (Pro only)", "Role/location salary ranges displayed"),
        ("M-64", "Career insights: blocked on non-Pro tier", "402 error, upgrade prompt"),
        ("M-65", "Settings: request data export", "Export initiated (Starter+ tier)"),
        ("M-66", "Settings: request account deletion", "Confirmation, account removed"),
    ])

    # =========================================================================
    # SECTION 4: EMPLOYER MOBILE FEATURES
    # =========================================================================
    pdf.section_header("4", "EMPLOYER MOBILE FEATURES")

    pdf.subsection("4.1", "Onboarding & Dashboard")
    pdf.test_table([
        ("M-67", "Complete employer onboarding (company name, size, industry, location)", "Workspace created, dashboard loads"),
        ("M-68", "Dashboard: view metric cards (active jobs, views, applications, saved)", "Metrics render correctly"),
        ("M-69", "Quick actions: Post Job, Search Candidates, Analytics, Saved, Pipeline", "Each action navigates correctly"),
    ])

    pdf.subsection("4.2", "Jobs Tab")
    pdf.test_table([
        ("M-70", "View jobs list with status filter (All/Draft/Active/Paused/Closed)", "Jobs filtered by status"),
        ("M-71", "Job cards show title, status badge, location, views, applications", "Card info renders"),
        ("M-72", "Tap job to view detail / edit", "Job detail screen opens"),
        ("M-73", "FAB to create new job posting", "New job form opens"),
        ("M-74", "Empty state with CTA to post first job", "Prompt shown when no jobs"),
    ])

    pdf.subsection("4.3", "Candidates Tab & Pipeline")
    pdf.test_table([
        ("M-75", "Search candidates by skills, location, job titles", "Results returned with pagination"),
        ("M-76", "Candidate cards show name, headline, location, experience, skills", "Card renders correctly"),
        ("M-77", "Save candidate from search results", "Candidate added to saved list"),
        ("M-78", "View candidate profile detail", "Full profile displayed"),
        ("M-79", "Pipeline tab: manage hiring pipeline stages", "Stage cards and candidates shown"),
        ("M-80", "Navigate to saved candidates screen", "Saved candidates list loads"),
    ])

    pdf.subsection("4.4", "Employer Analytics & Other")
    pdf.test_table([
        ("M-81", "Analytics screen: job performance metrics", "Charts and metrics render"),
        ("M-82", "Compliance screen: reporting interface", "Compliance data loads"),
        ("M-83", "Distribution screen: board connections", "Connected boards listed"),
    ])

    # =========================================================================
    # SECTION 5: RECRUITER MOBILE FEATURES
    # =========================================================================
    pdf.section_header("5", "RECRUITER MOBILE FEATURES")

    pdf.subsection("5.1", "Onboarding & Dashboard")
    pdf.test_table([
        ("M-84", "Complete recruiter onboarding", "Workspace created, 14-day trial starts"),
        ("M-85", "Dashboard: stat cards (active jobs, pipeline, clients, placements)", "Metrics render"),
        ("M-86", "Dashboard: pipeline by stage breakdown", "Bar chart visualization shown"),
        ("M-87", "Dashboard: recent activity timeline", "Activities listed chronologically"),
        ("M-88", "Quick actions: Pipeline, Jobs, Client Management", "Navigation works"),
    ])

    pdf.subsection("5.2", "Pipeline Tab")
    pdf.test_table([
        ("M-89", "View pipeline with stage filter chips", "All/Lead/Contacted/Screening/Submitted/etc."),
        ("M-90", "Candidate cards show name, stage, score, last updated", "Cards render correctly"),
        ("M-91", "FAB: add candidate to pipeline", "Add candidate form opens"),
        ("M-92", "FAB: bulk upload candidates", "Bulk upload screen opens"),
        ("M-93", "Tap candidate to view pipeline detail", "Detail screen with stage management"),
        ("M-94", "Advance/move back/place/reject candidate", "Stage transitions work"),
        ("M-95", "View notes and communication history", "Activity log displayed"),
    ])

    pdf.subsection("5.3", "Jobs Tab (Recruiter)")
    pdf.test_table([
        ("M-96", "View job orders list", "Jobs listed with client, fee, status, candidates"),
        ("M-97", "Tap job order to view detail", "Job requirements, matched candidates shown"),
    ])

    pdf.subsection("5.4", "Clients Tab")
    pdf.test_table([
        ("M-98", "View client list with active job counts", "Client cards render"),
        ("M-99", "Add new client via form", "Client created with contact info"),
        ("M-100", "View client detail (jobs, placements, contacts)", "Client profile loads"),
    ])

    pdf.subsection("5.5", "Recruiter Screens")
    pdf.test_table([
        ("M-101", "Bulk upload screen: import multiple resumes", "Upload progress shown, candidates created"),
        ("M-102", "Sequences screen: list outreach sequences (Team/Agency)", "Sequences listed"),
        ("M-103", "Sequence detail: steps, templates, enrollments", "Sequence management works"),
        ("M-104", "CRM migration screen", "Migration interface accessible"),
    ])

    # =========================================================================
    # SECTION 6: SIEVE AI ON MOBILE
    # =========================================================================
    pdf.section_header("6", "SIEVE AI CONCIERGE (Mobile)")
    pdf.test_table([
        ("M-105", "Floating Sieve button visible on all main screens", "Gold FAB visible, tappable"),
        ("M-106", "Sieve button hidden on Sieve screen itself", "No duplicate button"),
        ("M-107", "Open Sieve full-screen chat", "Chat UI loads with history"),
        ("M-108", "Send message, receive streaming AI response", "Response streams in real-time"),
        ("M-109", "Conversation history loads on open", "Previous messages displayed"),
        ("M-110", "Clear chat history", "History cleared"),
        ("M-111", "Escalation phrases trigger live agent", "'Talk to a human' connects to support"),
        ("M-112", "WebSocket live agent connection", "Agent joins, real-time messaging works"),
        ("M-113", "Agent name and online badge display", "Agent identity shown"),
        ("M-114", "System messages styled (centered, italic)", "System messages distinguishable"),
        ("M-115", "Suggested actions / follow-up prompts", "Action chips displayed after response"),
        ("M-116", "Daily message limit enforcement by tier", "Limit hit shows upgrade prompt"),
    ])

    # =========================================================================
    # SECTION 7: ROLE SWITCHING
    # =========================================================================
    pdf.section_header("7", "ROLE SWITCHING & MULTI-ROLE")
    pdf.test_table([
        ("M-117", "'Both' user: switch from candidate to employer view", "Tab navigation switches to employer tabs"),
        ("M-118", "'Both' user: switch from employer to recruiter view", "Tab navigation switches to recruiter tabs"),
        ("M-119", "Role switcher banner on profile/dashboard", "Switch option visible and functional"),
        ("M-120", "Role-based routing after login", "Correct tabs shown for user role"),
    ])

    # =========================================================================
    # SECTION 8: FEATURE GATING ON MOBILE
    # =========================================================================
    pdf.section_header("8", "FEATURE GATING (Mobile-Specific)")
    pdf.test_table([
        ("M-121", "402 response: 'Feature Unavailable' alert with upgrade prompt", "Alert shown, not a crash"),
        ("M-122", "403 response: access denied handling", "User-friendly message displayed"),
        ("M-123", "429 response: rate limit handling", "Rate limit message shown"),
        ("M-124", "Pro-only features blocked on Free (career insights, salary coach)", "Upgrade prompt, not error"),
        ("M-125", "Starter+ features blocked on Free (data export)", "Upgrade prompt shown"),
        ("M-126", "Recruiter tier limits enforced on mobile", "Limits match web behavior"),
        ("M-127", "Employer tier limits enforced on mobile", "Limits match web behavior"),
    ])

    # =========================================================================
    # SECTION 9: MOBILE-SPECIFIC UX & PLATFORM
    # =========================================================================
    pdf.section_header("9", "MOBILE UX & PLATFORM")
    pdf.test_table([
        ("M-128", "iOS: app renders correctly on iPhone (various sizes)", "UI scales properly, no clipping"),
        ("M-129", "Android: app renders correctly (various sizes)", "UI scales properly"),
        ("M-130", "Pull-to-refresh on all list screens", "Data refreshes without errors"),
        ("M-131", "Loading spinners display during data fetch", "Spinners visible, not stuck"),
        ("M-132", "Error boundary catches component crashes", "Error screen shown, not blank"),
        ("M-133", "Network error handling (airplane mode)", "Offline message shown gracefully"),
        ("M-134", "Deep link from email/notification opens correct screen", "Correct screen loads"),
        ("M-135", "Push notification receipt (if configured)", "Notification appears in system tray"),
        ("M-136", "Secure storage for tokens (expo-secure-store)", "Tokens not in plain text storage"),
        ("M-137", "File download to cache directory", "File saved, accessible for sharing"),
        ("M-138", "Share sheet for documents (resume, cover letter)", "System share sheet opens"),
        ("M-139", "Keyboard handling on form screens", "Keyboard doesn't obscure inputs"),
        ("M-140", "Touch targets have adequate hitSlop", "Buttons/links easy to tap"),
        ("M-141", "Text truncation with numberOfLines", "Long text truncated with ellipsis"),
        ("M-142", "Back navigation works correctly on all screens", "Back button returns to previous screen"),
        ("M-143", "Tab navigation state preserved on tab switch", "Scroll position/data maintained"),
    ])

    # Sign-off
    pdf.ln(5)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, "SIGN-OFF", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(95, 7, "Tester Signature: ________________________")
    pdf.cell(95, 7, "Date: ________________________", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(95, 7, "Total Pass: ____  Fail: ____  Skip: ____")
    pdf.cell(95, 7, "Approved By: ________________________", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)
    pdf.set_font("Helvetica", "", 8)
    pdf.cell(0, 5, "iOS Device/Version: ________________________    Android Device/Version: ________________________",
             new_x="LMARGIN", new_y="NEXT")

    return pdf


if __name__ == "__main__":
    import os
    out_dir = os.path.dirname(os.path.abspath(__file__))

    print("Generating Web Platform Test Script...")
    web_pdf = build_web_script()
    web_path = os.path.join(out_dir, "winnow-web-test-script.pdf")
    web_pdf.output(web_path)
    print(f"  -> {web_path}")

    print("Generating Mobile App Test Script...")
    mobile_pdf = build_mobile_script()
    mobile_path = os.path.join(out_dir, "winnow-mobile-test-script.pdf")
    mobile_pdf.output(mobile_path)
    print(f"  -> {mobile_path}")

    print("Done!")
