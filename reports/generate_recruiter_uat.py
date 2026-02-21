"""Generate a UAT test script PDF for the Winnow Recruiter App."""

from datetime import datetime

from fpdf import FPDF


class UATReport(FPDF):
    """Custom PDF with header/footer for Winnow UAT."""

    def header(self):
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(100, 100, 100)
        self.cell(0, 6, "Winnow Recruiter App - UAT Test Script", align="L")
        self.cell(0, 6, f"Generated: {datetime.now().strftime('%Y-%m-%d')}", align="R", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(200, 200, 200)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")

    def section_title(self, num, title):
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(20, 60, 120)
        self.cell(0, 10, f"{num}. {title}", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(20, 60, 120)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(3)

    def subsection_title(self, title):
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(40, 40, 40)
        self.cell(0, 8, title, new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def test_case(self, tc_id, title, preconditions, steps, expected, priority="Medium"):
        # Check if we need a page break (estimate space needed)
        lines_needed = 3 + len(steps) + len(expected.split("\n")) + (2 if preconditions else 0)
        if self.get_y() + (lines_needed * 5) > 265:
            self.add_page()

        # ID + Title row
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(0, 0, 0)
        self.set_fill_color(235, 240, 250)
        self.cell(25, 7, f"  {tc_id}", fill=True)
        self.cell(130, 7, f"  {title}", fill=True)

        # Priority badge
        colors = {"High": (220, 50, 50), "Medium": (230, 160, 0), "Low": (80, 160, 80)}
        r, g, b = colors.get(priority, (100, 100, 100))
        self.set_text_color(r, g, b)
        self.set_font("Helvetica", "B", 9)
        self.cell(20, 7, f"  [{priority}]", fill=True)

        # Pass/Fail checkbox
        self.set_text_color(100, 100, 100)
        self.set_font("Helvetica", "", 9)
        self.cell(0, 7, "  Pass [ ]  Fail [ ]", fill=True, new_x="LMARGIN", new_y="NEXT")

        # Preconditions
        if preconditions:
            self.set_font("Helvetica", "I", 9)
            self.set_text_color(100, 100, 100)
            self.cell(0, 5, f"    Preconditions: {preconditions}", new_x="LMARGIN", new_y="NEXT")

        # Steps
        self.set_font("Helvetica", "", 9)
        self.set_text_color(30, 30, 30)
        for i, step in enumerate(steps, 1):
            self.cell(0, 5, f"    {i}. {step}", new_x="LMARGIN", new_y="NEXT")

        # Expected
        self.set_font("Helvetica", "I", 9)
        self.set_text_color(0, 100, 0)
        for line in expected.split("\n"):
            self.cell(0, 5, f"    -> {line.strip()}", new_x="LMARGIN", new_y="NEXT")

        self.ln(4)


def build_pdf():
    pdf = UATReport()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    # ── COVER PAGE ──────────────────────────────────────────────────────
    pdf.ln(30)
    pdf.set_font("Helvetica", "B", 28)
    pdf.set_text_color(20, 60, 120)
    pdf.cell(0, 15, "Winnow Recruiter App", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 20)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(0, 12, "User Acceptance Test Script", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(10)
    pdf.set_draw_color(20, 60, 120)
    pdf.line(60, pdf.get_y(), 150, pdf.get_y())
    pdf.ln(10)

    meta = [
        ("Document Version", "1.0"),
        ("Date", datetime.now().strftime("%B %d, %Y")),
        ("Application", "Winnow Recruiter Module"),
        ("Environment", "Staging / localhost:3000"),
        ("Total Test Cases", "75"),
        ("Prepared By", "QA Automation"),
    ]
    pdf.set_font("Helvetica", "", 11)
    for label, value in meta:
        pdf.set_text_color(100, 100, 100)
        pdf.cell(60, 7, f"  {label}:", align="R")
        pdf.set_text_color(30, 30, 30)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 7, f"  {value}", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 11)

    pdf.ln(15)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(80, 80, 80)
    pdf.multi_cell(0, 5,
        "This document contains step-by-step test cases for user acceptance testing "
        "of the Winnow Recruiter application. Each test case includes preconditions, "
        "test steps, and expected results. Testers should mark each case as Pass or Fail "
        "and note any defects discovered during execution.",
        align="C",
    )

    # ── TABLE OF CONTENTS ───────────────────────────────────────────────
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(20, 60, 120)
    pdf.cell(0, 10, "Table of Contents", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    toc_items = [
        ("1", "Onboarding & Registration", "5 test cases"),
        ("2", "Dashboard", "6 test cases"),
        ("3", "Pipeline Management", "8 test cases"),
        ("4", "Client Management", "8 test cases"),
        ("5", "Job Management", "10 test cases"),
        ("6", "Candidate Sourcing", "4 test cases"),
        ("7", "Intelligence Tools", "9 test cases"),
        ("8", "Sieve AI Concierge", "5 test cases"),
        ("9", "Team & Settings", "7 test cases"),
        ("10", "CRM Data Migration", "5 test cases"),
        ("11", "Billing & Tier Enforcement", "8 test cases"),
    ]
    pdf.set_font("Helvetica", "", 11)
    for num, title, desc in toc_items:
        pdf.set_text_color(30, 30, 30)
        pdf.cell(8, 7, num + ".")
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(90, 7, title)
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(120, 120, 120)
        leader = "." * 40
        pdf.cell(0, 7, f"  {leader}  {desc}", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 11)

    # =====================================================================
    # 1. ONBOARDING & REGISTRATION
    # =====================================================================
    pdf.add_page()
    pdf.section_title("1", "Onboarding & Registration")
    pdf.subsection_title("URL: /recruiter/onboarding")

    pdf.test_case("OB-01", "Successful recruiter registration",
        "User is logged in with role='recruiter', no existing recruiter profile",
        [
            "Navigate to /recruiter/onboarding",
            "Enter 'Test Staffing Agency' in Company Name",
            "Select 'Staffing Agency' from Company Type dropdown",
            "Enter 'https://teststaffing.com' in Website",
            "Enter 'Technology, Healthcare' in Specializations",
            "Click 'Start Free Trial'",
        ],
        "Redirects to /recruiter/dashboard\n14-day trial is activated\nDashboard shows company name 'Test Staffing Agency'",
        "High",
    )

    pdf.test_case("OB-02", "Registration requires company name",
        "User is on onboarding page",
        [
            "Leave Company Name field empty",
            "Click 'Start Free Trial'",
        ],
        "Validation error shown for Company Name\nForm does not submit",
        "High",
    )

    pdf.test_case("OB-03", "Duplicate profile prevented",
        "User already has a recruiter profile",
        [
            "Navigate to /recruiter/onboarding",
            "Fill in all fields with valid data",
            "Click 'Start Free Trial'",
        ],
        "Error message: 'Recruiter profile already exists'\nUser is not redirected",
        "Medium",
    )

    pdf.test_case("OB-04", "Non-recruiter role blocked",
        "User has role='candidate' (not recruiter)",
        [
            "Navigate to /recruiter/onboarding",
            "Attempt to submit registration form",
        ],
        "403 error or redirect away from recruiter area\nProfile is not created",
        "High",
    )

    pdf.test_case("OB-05", "Trial period starts correctly",
        "Just completed onboarding (OB-01)",
        [
            "Navigate to /recruiter/dashboard",
            "Check the trial banner at the top",
            "Navigate to /recruiter/settings",
            "Check billing section",
        ],
        "Dashboard shows 'X days remaining in your free trial'\nSettings shows 'trial' as current plan\nAll features are accessible during trial",
        "High",
    )

    # =====================================================================
    # 2. DASHBOARD
    # =====================================================================
    pdf.add_page()
    pdf.section_title("2", "Dashboard")
    pdf.subsection_title("URL: /recruiter/dashboard")

    pdf.test_case("DB-01", "Dashboard loads with correct stats",
        "Recruiter profile exists with data (jobs, clients, pipeline candidates)",
        [
            "Navigate to /recruiter/dashboard",
            "Observe the four stat cards",
            "Check the pipeline-by-stage chart",
            "Check the recent activities section",
        ],
        "Active Jobs count matches actual active jobs\nPipeline count matches total pipeline candidates\nClients count matches total clients\nPlacements count matches placed candidates\nPipeline chart shows correct distribution across stages",
        "High",
    )

    pdf.test_case("DB-02", "Dashboard empty state (new user)",
        "New recruiter with no data",
        [
            "Navigate to /recruiter/dashboard",
            "Check all stat cards",
        ],
        "All stat cards show 0\nAction buttons (Source Candidates, View Pipeline, Manage Clients) are visible\nNo errors displayed",
        "Medium",
    )

    pdf.test_case("DB-03", "Trial banner displays correctly",
        "Recruiter is on a trial plan",
        [
            "Navigate to /recruiter/dashboard",
            "Observe the trial banner",
        ],
        "Banner shows 'You have X days remaining in your free trial'\n'View Plans' link is visible and navigates to /recruiter/pricing",
        "Medium",
    )

    pdf.test_case("DB-04", "Quick action buttons navigate correctly",
        "Recruiter is on dashboard",
        [
            "Click 'Source Candidates' button",
            "Navigate back to dashboard",
            "Click 'View Pipeline' button",
            "Navigate back to dashboard",
            "Click 'Manage Clients' button",
        ],
        "'Source Candidates' navigates to /recruiter/candidates\n'View Pipeline' navigates to /recruiter/pipeline\n'Manage Clients' navigates to /recruiter/clients",
        "Low",
    )

    pdf.test_case("DB-05", "Recent activity feed shows latest entries",
        "Recruiter has logged activities (calls, emails, stage changes)",
        [
            "Navigate to /recruiter/dashboard",
            "Scroll to Recent Activity section",
        ],
        "Most recent activities are shown with timestamps\nActivity type and subject are displayed\nActivities are in reverse chronological order",
        "Medium",
    )

    pdf.test_case("DB-06", "Sidebar navigation works on all pages",
        "Recruiter is logged in",
        [
            "Click each nav item: Dashboard, Jobs, Clients, Candidates, Pipeline, Intelligence, Sieve AI, Migrate, Settings",
            "Verify each page loads correctly",
        ],
        "Each page loads without errors\nActive nav item is highlighted\nSidebar is visible on all pages except /recruiter/onboarding",
        "High",
    )

    # =====================================================================
    # 3. PIPELINE MANAGEMENT
    # =====================================================================
    pdf.add_page()
    pdf.section_title("3", "Pipeline Management")
    pdf.subsection_title("URL: /recruiter/pipeline")

    pdf.test_case("PL-01", "Add external candidate to pipeline",
        "Recruiter is on pipeline page",
        [
            "Click '+ Add to Pipeline' button",
            "Enter 'Jane Smith' as Name",
            "Enter 'jane@example.com' as Email",
            "Select 'LinkedIn' as Source",
            "Enter notes: 'Strong Python background'",
            "Select 'sourced' as Stage",
            "Click 'Add to Pipeline'",
        ],
        "Candidate appears in the pipeline list\nName, email, source, and stage are correct\nForm resets after submission",
        "High",
    )

    pdf.test_case("PL-02", "Change candidate stage",
        "Pipeline has at least one candidate",
        [
            "Locate a candidate in the list",
            "Click the stage dropdown on the candidate card",
            "Change stage from 'sourced' to 'screening'",
        ],
        "Stage updates immediately in the UI\nCandidate appears under 'screening' filter\nStage change is persisted on page reload",
        "High",
    )

    pdf.test_case("PL-03", "Filter pipeline by stage",
        "Pipeline has candidates in multiple stages",
        [
            "Click 'sourced' stage filter pill",
            "Verify only sourced candidates show",
            "Click 'interviewing' stage filter pill",
            "Click 'All' filter pill",
        ],
        "Each filter shows only candidates in that stage\n'All' shows all candidates\nCounts per stage are accurate",
        "Medium",
    )

    pdf.test_case("PL-04", "Remove candidate from pipeline",
        "Pipeline has at least one candidate",
        [
            "Locate a candidate in the list",
            "Click the X (remove) button on the candidate card",
        ],
        "Candidate is removed from the list\nPipeline count decreases by 1\nRemoval persists on page reload",
        "Medium",
    )

    pdf.test_case("PL-05", "Pipeline with match score display",
        "Pipeline has a candidate with a match score",
        [
            "Navigate to /recruiter/pipeline",
            "Find a candidate with a match score",
        ],
        "Match score badge is visible (e.g., '85%')\nScore is color-coded (green for high, yellow for medium)",
        "Low",
    )

    pdf.test_case("PL-06", "Add candidate without required name",
        "Recruiter is on pipeline page with add form open",
        [
            "Leave Name field empty",
            "Attempt to submit the form",
        ],
        "Form validation prevents submission\nError message indicates name is required",
        "Medium",
    )

    pdf.test_case("PL-07", "Pipeline pagination works",
        "Pipeline has more than 50 candidates",
        [
            "Navigate to /recruiter/pipeline",
            "Scroll through the candidate list",
        ],
        "First 100 candidates are loaded\nAll candidates are accessible",
        "Low",
    )

    pdf.test_case("PL-08", "Stage transition from sourced to placed (full flow)",
        "Pipeline has a candidate in 'sourced' stage",
        [
            "Change stage: sourced -> contacted",
            "Change stage: contacted -> screening",
            "Change stage: screening -> interviewing",
            "Change stage: interviewing -> offered",
            "Change stage: offered -> placed",
        ],
        "Each stage transition succeeds\nCandidate reaches 'placed' stage\nDashboard placements count increases",
        "High",
    )

    # =====================================================================
    # 4. CLIENT MANAGEMENT
    # =====================================================================
    pdf.add_page()
    pdf.section_title("4", "Client Management")
    pdf.subsection_title("URL: /recruiter/clients, /recruiter/clients/[id]")

    pdf.test_case("CL-01", "Create a new client",
        "Recruiter is on clients page",
        [
            "Click '+ Add Client'",
            "Enter 'Acme Corporation' as Company Name",
            "Enter 'Technology' as Industry",
            "Enter 'John Doe' as Contact Name",
            "Enter 'john@acme.com' as Contact Email",
            "Select 'Contingency' as Contract Type",
            "Enter '20' as Fee %",
            "Click 'Create Client'",
        ],
        "Client appears in the client list\nAll fields are saved correctly\nClient status defaults to 'active'",
        "High",
    )

    pdf.test_case("CL-02", "View client detail page",
        "At least one client exists",
        [
            "Click on a client card in the list",
            "Review the client detail page",
        ],
        "Client detail page shows all information\nContact details, contract type, fee %, notes are displayed\nRecent activities section is visible",
        "Medium",
    )

    pdf.test_case("CL-03", "Edit client information",
        "On client detail page",
        [
            "Click 'Edit' button",
            "Change company name to 'Acme Corp International'",
            "Update fee % to 25",
            "Click 'Save'",
        ],
        "Changes are saved and reflected in the UI\nUpdated values persist on page reload\nEdit mode toggles off after save",
        "High",
    )

    pdf.test_case("CL-04", "Delete a client",
        "On client detail page",
        [
            "Click 'Delete' button",
            "Confirm the deletion in the dialog",
        ],
        "Client is removed\nRedirects to clients list\nClient no longer appears in the list",
        "Medium",
    )

    pdf.test_case("CL-05", "Filter clients by status",
        "Clients exist with different statuses (active, inactive, prospect)",
        [
            "Click 'active' filter pill",
            "Click 'prospect' filter pill",
            "Click 'All' filter pill",
        ],
        "Each filter shows only matching clients\n'All' shows all clients\nCounts are accurate",
        "Medium",
    )

    pdf.test_case("CL-06", "Client requires company name",
        "On add client form",
        [
            "Leave Company Name field empty",
            "Fill in other fields",
            "Click 'Create Client'",
        ],
        "Validation error for Company Name\nForm does not submit",
        "Medium",
    )

    pdf.test_case("CL-07", "Client activity log shows entries",
        "Client has associated activities",
        [
            "Navigate to client detail page",
            "Scroll to activity section",
        ],
        "Activities specific to this client are shown\nActivities include type, subject, and timestamp",
        "Low",
    )

    pdf.test_case("CL-08", "Client job count displays correctly",
        "Client has jobs linked to it",
        [
            "Navigate to /recruiter/clients",
            "Check job count on client cards",
        ],
        "Job count badge shows correct number of linked jobs\nClients with no jobs show 0",
        "Low",
    )

    # =====================================================================
    # 5. JOB MANAGEMENT
    # =====================================================================
    pdf.add_page()
    pdf.section_title("5", "Job Management")
    pdf.subsection_title("URL: /recruiter/jobs, /recruiter/jobs/[id]")

    pdf.test_case("JB-01", "Create a draft job posting",
        "Recruiter is on jobs page",
        [
            "Click '+ Create Job'",
            "Enter 'Senior Python Developer' as Title",
            "Enter job description (min 10 characters)",
            "Enter requirements",
            "Select a client from dropdown",
            "Set location to 'Remote'",
            "Set salary range: $120,000 - $180,000",
            "Leave status as 'Draft'",
            "Click 'Create Job'",
        ],
        "Job appears in the jobs list with 'Draft' badge\nAll fields are saved correctly\nJob is not visible to candidates",
        "High",
    )

    pdf.test_case("JB-02", "Publish a draft job",
        "A draft job exists",
        [
            "Click on the draft job to view details",
            "Click 'Publish' button",
        ],
        "Job status changes to 'Active'\nPosted date is set to current time\nStatus badge updates to 'Active'",
        "High",
    )

    pdf.test_case("JB-03", "Upload job documents",
        "Recruiter is on jobs page",
        [
            "Click 'Upload Documents'",
            "Drag and drop a .docx job description file into the drop zone",
            "Wait for upload and parsing to complete",
        ],
        "Upload progress bar shows percentage\nParsing indicator appears after upload\nParsed job appears as a draft with extracted title and description\nSuccess message is displayed",
        "High",
    )

    pdf.test_case("JB-04", "Filter jobs by status",
        "Jobs exist in multiple statuses (draft, active, paused, closed)",
        [
            "Select 'Active' from status filter",
            "Select 'Draft' from status filter",
            "Select 'All'",
        ],
        "Each filter shows only matching jobs\nCounts match actual job statuses",
        "Medium",
    )

    pdf.test_case("JB-05", "View matched candidates for a job",
        "An active job has matched candidates",
        [
            "Navigate to job detail page",
            "Scroll to 'Matched Candidates' section",
        ],
        "Candidate list shows name, headline, match score, matched skills\nCandidates are sorted by match score (descending)\nTotal cached count is displayed",
        "High",
    )

    pdf.test_case("JB-06", "Refresh candidate matches",
        "On job detail page for an active job",
        [
            "Click 'Refresh Matches' button",
        ],
        "Confirmation message: 'Candidate refresh queued'\nNew candidates may appear after background processing",
        "Medium",
    )

    pdf.test_case("JB-07", "Pause an active job",
        "Active job exists",
        [
            "Navigate to job detail page",
            "Click 'Pause' button",
        ],
        "Job status changes to 'Paused'\nStatus badge updates\nJob is no longer matching new candidates",
        "Medium",
    )

    pdf.test_case("JB-08", "Close a job",
        "Active or paused job exists",
        [
            "Navigate to job detail page",
            "Click 'Close' button",
        ],
        "Job status changes to 'Closed'\nJob no longer appears in active filters",
        "Medium",
    )

    pdf.test_case("JB-09", "Delete a job",
        "A job exists (any status)",
        [
            "Navigate to job detail page",
            "Click 'Delete' button",
            "Confirm deletion",
        ],
        "Job is removed\nRedirects to jobs list\nJob no longer appears in the list",
        "Medium",
    )

    pdf.test_case("JB-10", "Reject unsupported file types in upload",
        "On job upload form",
        [
            "Attempt to upload a .jpg or .mp3 file",
        ],
        "File is rejected with 'Unsupported file type' error\nOnly .doc, .docx, .pdf, .txt are accepted",
        "Medium",
    )

    # =====================================================================
    # 6. CANDIDATE SOURCING
    # =====================================================================
    pdf.add_page()
    pdf.section_title("6", "Candidate Sourcing")
    pdf.subsection_title("URL: /recruiter/candidates")

    pdf.test_case("CS-01", "View sourced candidates list",
        "Candidates have been sourced (via Chrome extension or manual)",
        [
            "Navigate to /recruiter/candidates",
            "Review the candidate cards grid",
        ],
        "Candidate cards show name, headline, location, skills\nLinkedIn badge appears for extension-sourced candidates\nTotal count is displayed in header",
        "Medium",
    )

    pdf.test_case("CS-02", "Search candidates by keyword",
        "Multiple candidates exist with different skills",
        [
            "Enter 'Python' in the search box",
            "Observe filtered results",
            "Clear search and enter a candidate name",
        ],
        "Results filter to candidates matching the search term\nSearch works on name, headline, and skills\nClearing search shows all candidates",
        "Medium",
    )

    pdf.test_case("CS-03", "View candidate LinkedIn profile",
        "A candidate has a LinkedIn URL",
        [
            "Find a candidate with a LinkedIn badge",
            "Click 'View LinkedIn' button",
        ],
        "Opens LinkedIn profile in a new tab\nLink is correct for the candidate",
        "Low",
    )

    pdf.test_case("CS-04", "Empty state when no candidates sourced",
        "No candidates have been sourced yet",
        [
            "Navigate to /recruiter/candidates",
        ],
        "Empty state message is shown (e.g., 'No candidates sourced yet')\nNo errors displayed",
        "Low",
    )

    # =====================================================================
    # 7. INTELLIGENCE TOOLS
    # =====================================================================
    pdf.add_page()
    pdf.section_title("7", "Intelligence Tools")
    pdf.subsection_title("URL: /recruiter/intelligence")

    pdf.test_case("IN-01", "Salary intelligence lookup",
        "Recruiter is on Intelligence page, Salary tab",
        [
            "Enter 'Software Engineer' as role title",
            "Enter 'San Francisco, CA' as location",
            "Click 'Look Up'",
        ],
        "Salary percentiles displayed: P10, P25, P50, P75, P90\nP50 is highlighted\nRole and location are shown in results\nSample size is indicated",
        "High",
    )

    pdf.test_case("IN-02", "Salary lookup without location",
        "On Salary Intelligence tab",
        [
            "Enter 'Data Scientist' as role title",
            "Leave location empty",
            "Click 'Look Up'",
        ],
        "National/average salary data is returned\nResults display correctly without location",
        "Medium",
    )

    pdf.test_case("IN-03", "Generate a general candidate brief",
        "On Candidate Briefs tab",
        [
            "Enter a valid candidate profile ID",
            "Select 'General' brief type",
            "Click 'Generate Brief'",
        ],
        "Brief displays: headline, elevator pitch, strengths, concerns\nRecommended action badge is shown\nFull brief text is available in expandable section",
        "High",
    )

    pdf.test_case("IN-04", "Generate a job-specific brief",
        "On Candidate Briefs tab",
        [
            "Enter a valid candidate profile ID",
            "Select 'Job Specific' brief type",
            "Enter a valid job ID",
            "Click 'Generate Brief'",
        ],
        "Brief includes fit rationale for the specific job\nStrengths/concerns are job-relevant\nUsage counter increments by 1",
        "High",
    )

    pdf.test_case("IN-05", "Generate a client submittal brief",
        "On Candidate Briefs tab",
        [
            "Enter a valid candidate profile ID",
            "Select 'Client Submittal' brief type",
            "Click 'Generate Brief'",
        ],
        "Submittal-format brief is generated\nSuitable for sending to hiring managers",
        "Medium",
    )

    pdf.test_case("IN-06", "Career trajectory prediction",
        "On Career Trajectory tab",
        [
            "Enter a valid candidate profile ID",
            "Click 'Predict'",
        ],
        "Current level is displayed\nCareer velocity indicator (accelerating/steady/plateauing)\n6-month and 12-month projections shown\nGrowth areas and recommended skills listed",
        "Medium",
    )

    pdf.test_case("IN-07", "Usage counter displays and updates",
        "On Intelligence page header",
        [
            "Note current briefs and salary lookup counts",
            "Perform a salary lookup",
            "Check usage counter again",
        ],
        "Usage display shows 'X/Y briefs used' and 'X/Y salary lookups'\nCounters increment after each operation\nLimits match the current plan tier",
        "High",
    )

    pdf.test_case("IN-08", "Brief limit enforcement (solo tier)",
        "Recruiter on solo plan, at brief limit (20/20 used)",
        [
            "Attempt to generate another brief",
        ],
        "429 error: 'Monthly limit reached'\nUpgrade message is displayed\nBrief is not generated",
        "High",
    )

    pdf.test_case("IN-09", "Salary lookup limit enforcement (solo tier)",
        "Recruiter on solo plan, at salary limit (5/5 used)",
        [
            "Attempt another salary lookup",
        ],
        "429 error: 'Monthly limit reached'\nUpgrade message is displayed",
        "High",
    )

    # =====================================================================
    # 8. SIEVE AI CONCIERGE
    # =====================================================================
    pdf.add_page()
    pdf.section_title("8", "Sieve AI Concierge")
    pdf.subsection_title("URL: /recruiter/sieve")

    pdf.test_case("SV-01", "Initial empty state with suggestions",
        "First visit to Sieve AI page",
        [
            "Navigate to /recruiter/sieve",
            "Review the empty state",
        ],
        "Sieve AI branding and intro text displayed\nSuggested action buttons are visible\n'I can help with pipeline strategy, client submittals...' message shown",
        "Medium",
    )

    pdf.test_case("SV-02", "Send a message and receive response",
        "On Sieve AI page",
        [
            "Type 'How should I prioritize my pipeline this week?' in the input",
            "Click Send or press Enter",
            "Wait for response",
        ],
        "User message appears right-aligned in blue\nLoading indicator shows while waiting\nAI response appears left-aligned in gray\nResponse is recruiter-contextual (mentions pipeline, candidates, etc.)",
        "High",
    )

    pdf.test_case("SV-03", "Use a suggested action prompt",
        "On Sieve AI page with suggestions visible",
        [
            "Click a suggested action button (e.g., 'Help me write a client submittal')",
        ],
        "Suggestion text is sent as a message\nAI responds with relevant recruiter advice\nSuggestion buttons disappear after first message",
        "Medium",
    )

    pdf.test_case("SV-04", "Clear conversation history",
        "At least one message has been sent",
        [
            "Click 'Clear history' button in the header",
        ],
        "All messages are removed\nEmpty state returns\nHistory is cleared on reload (not just visually)",
        "Medium",
    )

    pdf.test_case("SV-05", "Conversation history persists across visits",
        "Messages have been sent in a previous visit",
        [
            "Navigate away from Sieve AI page",
            "Navigate back to /recruiter/sieve",
        ],
        "Previous messages are loaded and displayed\nConversation context is maintained for follow-up questions",
        "Medium",
    )

    # =====================================================================
    # 9. TEAM & SETTINGS
    # =====================================================================
    pdf.add_page()
    pdf.section_title("9", "Team & Settings")
    pdf.subsection_title("URL: /recruiter/settings")

    pdf.test_case("ST-01", "Update company profile",
        "On Settings page",
        [
            "Change Company Name to 'Updated Agency Name'",
            "Select a different Company Type",
            "Enter a new website URL",
            "Click 'Save'",
        ],
        "Changes are saved successfully\nUpdated values persist on page reload\nDashboard reflects the new company name",
        "High",
    )

    pdf.test_case("ST-02", "Invite a team member",
        "On Settings page, team plan or higher",
        [
            "Enter 'newmember@example.com' in the invite email field",
            "Select 'Member' role",
            "Click 'Invite'",
        ],
        "Team member appears in the list with 'Pending' status\nSeats used counter increases\nInvite email is sent (if email service configured)",
        "High",
    )

    pdf.test_case("ST-03", "Remove a team member",
        "Team has at least one invited member",
        [
            "Click 'Remove' button next to a team member",
            "Confirm removal",
        ],
        "Member is removed from the list\nSeats used counter decreases\nRemoval persists on reload",
        "Medium",
    )

    pdf.test_case("ST-04", "Seat limit enforcement",
        "On solo plan (1 seat) or team plan at capacity",
        [
            "Attempt to invite more members than seats allow",
        ],
        "Error: 'Seat limit reached or user not found'\nInvite is not created",
        "High",
    )

    pdf.test_case("ST-05", "View billing information",
        "On Settings page",
        [
            "Scroll to Billing section",
            "Check current plan display",
        ],
        "Current plan tier is displayed (Trial/Solo/Team/Agency)\nSubscription status shown if applicable\nUpgrade or choose plan link is visible",
        "Medium",
    )

    pdf.test_case("ST-06", "Navigate to pricing from settings",
        "On Settings page",
        [
            "Click 'Choose a Plan' or 'Upgrade Plan' link in billing section",
        ],
        "Navigates to /recruiter/pricing\nPricing page shows all recruiter tiers\nCurrent tier is indicated",
        "Low",
    )

    pdf.test_case("ST-07", "Seats display shows correct counts",
        "On Settings page with team members",
        [
            "Check 'Seats: X / Y' display",
        ],
        "X = number of active team members (including owner)\nY = seats purchased for the plan\nNumbers match actual data",
        "Medium",
    )

    # =====================================================================
    # 10. CRM DATA MIGRATION
    # =====================================================================
    pdf.add_page()
    pdf.section_title("10", "CRM Data Migration")
    pdf.subsection_title("URL: /recruiter/migrate")

    pdf.test_case("MG-01", "Upload CRM export file",
        "On Migration page (Step 1: Upload)",
        [
            "Drag and drop a .csv CRM export file into the drop zone",
            "Wait for upload to complete",
        ],
        "Upload progress bar shows percentage\nFile is processed and platform is auto-detected\nAdvances to Step 2 (Detection)",
        "High",
    )

    pdf.test_case("MG-02", "Platform detection review",
        "File uploaded successfully (Step 2: Detection)",
        [
            "Review detected platform name and confidence %",
            "Review row count",
            "Review evidence list",
        ],
        "Platform name is displayed (e.g., 'Bullhorn', 'Recruit CRM')\nConfidence percentage is shown\nRow count matches the data file\nDetection evidence criteria are listed",
        "Medium",
    )

    pdf.test_case("MG-03", "Start and complete import",
        "On Step 2 with detection results",
        [
            "Click 'Start Import'",
            "Monitor progress bar (Step 3)",
            "Wait for completion (Step 4)",
        ],
        "Progress bar advances with percentage\nRow count shows processed/total\nStats grid shows imported/merged/skipped/errors\nSummary page shows final results",
        "High",
    )

    pdf.test_case("MG-04", "Rollback a completed migration",
        "Migration has completed successfully (Step 4)",
        [
            "Click 'Rollback' button",
            "Confirm the rollback",
        ],
        "Rollback confirmation dialog appears\nImported data is removed\nSuccess message: migration rolled back",
        "Medium",
    )

    pdf.test_case("MG-05", "Start a new migration after completion",
        "On summary page (Step 4)",
        [
            "Click 'New Migration' button",
        ],
        "Returns to Step 1 (Upload)\nDrop zone is empty and ready for new file",
        "Low",
    )

    # =====================================================================
    # 11. BILLING & TIER ENFORCEMENT
    # =====================================================================
    pdf.add_page()
    pdf.section_title("11", "Billing & Tier Enforcement")
    pdf.subsection_title("Cross-feature tier enforcement tests")

    pdf.test_case("BL-01", "Trial tier has full access",
        "Recruiter is on 14-day trial",
        [
            "Access all features: pipeline, clients, jobs, intelligence, sieve",
            "Verify no feature is blocked",
        ],
        "All features are accessible during trial\nNo limit-related errors\nTrial banner shows remaining days",
        "High",
    )

    pdf.test_case("BL-02", "Solo tier client limit (max 5)",
        "Recruiter on solo plan with 5 existing clients",
        [
            "Attempt to create a 6th client",
        ],
        "429 error: 'Client limit reached (5 on solo plan)'\nUpgrade message displayed",
        "High",
    )

    pdf.test_case("BL-03", "Solo tier pipeline limit (max 100)",
        "Recruiter on solo plan with 100 pipeline candidates",
        [
            "Attempt to add a 101st pipeline candidate",
        ],
        "429 error: 'Pipeline limit reached (100 on solo plan)'\nUpgrade message displayed",
        "High",
    )

    pdf.test_case("BL-04", "Solo tier active job limit (max 10)",
        "Recruiter on solo plan with 10 active jobs",
        [
            "Attempt to create an 11th active job",
        ],
        "429 error: 'Active job limit reached (10 on solo plan)'\nDraft jobs do not count toward this limit",
        "High",
    )

    pdf.test_case("BL-05", "Solo tier blocks bulk outreach",
        "Recruiter on solo plan",
        [
            "Attempt to send bulk outreach to multiple candidates",
        ],
        "403 error: 'Bulk outreach requires a Team or Agency plan'",
        "Medium",
    )

    pdf.test_case("BL-06", "Team/Agency tier allows bulk outreach",
        "Recruiter on team plan",
        [
            "Send bulk outreach to 5 pipeline candidates",
        ],
        "Outreach is queued for all 5 candidates\nResponse shows queued/failed counts",
        "Medium",
    )

    pdf.test_case("BL-07", "Monthly counter reset",
        "Recruiter has used some briefs/salary lookups, it is a new calendar month",
        [
            "Navigate to Intelligence page",
            "Check usage counters",
        ],
        "Counters reset to 0 at the start of a new month\nFull monthly allowance is available again",
        "Medium",
    )

    pdf.test_case("BL-08", "Pricing page shows all tiers correctly",
        "Navigate to /recruiter/pricing",
        [
            "Review all 4 pricing tiers",
            "Check monthly and annual pricing",
            "Verify feature lists for each tier",
        ],
        "Trial: $0, 14-day full access, 1 seat\nSolo: $29/mo or $249/yr, 1 seat, 20 briefs, 5 salary lookups\nTeam: $69/user/mo or $599/yr, 10 seats, 100 briefs, 50 lookups\nAgency: $99/user/mo or $899/yr, unlimited seats/lookups",
        "Medium",
    )

    # ── NOTES PAGE ──────────────────────────────────────────────────────
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(20, 60, 120)
    pdf.cell(0, 10, "Test Execution Notes", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(60, 60, 60)
    notes = [
        "Tester Name: ___________________________________    Date: _______________",
        "",
        "Environment: ___________________________________    Browser: ____________",
        "",
        "Overall Result:   [ ] PASS    [ ] PASS WITH ISSUES    [ ] FAIL",
        "",
        "Total Passed: _____  /  75        Total Failed: _____  /  75",
        "",
        "",
        "Defects Found:",
        "___________________________________________________________________________",
        "___________________________________________________________________________",
        "___________________________________________________________________________",
        "___________________________________________________________________________",
        "___________________________________________________________________________",
        "___________________________________________________________________________",
        "___________________________________________________________________________",
        "___________________________________________________________________________",
        "",
        "",
        "Additional Notes:",
        "___________________________________________________________________________",
        "___________________________________________________________________________",
        "___________________________________________________________________________",
        "___________________________________________________________________________",
        "___________________________________________________________________________",
        "___________________________________________________________________________",
        "___________________________________________________________________________",
        "___________________________________________________________________________",
        "",
        "",
        "Sign-off:",
        "",
        "Tester Signature: _________________________    Date: _______________",
        "",
        "Product Owner:    _________________________    Date: _______________",
    ]
    for line in notes:
        pdf.cell(0, 6, f"  {line}", new_x="LMARGIN", new_y="NEXT")

    # ── SAVE ────────────────────────────────────────────────────────────
    output_path = "reports/Winnow_Recruiter_UAT_Test_Script.pdf"
    pdf.output(output_path)
    print(f"PDF generated: {output_path}")
    return output_path


if __name__ == "__main__":
    build_pdf()
