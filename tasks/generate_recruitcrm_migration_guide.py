"""Generate a professional PDF guide for migrating from Recruit CRM to Winnow."""

from fpdf import FPDF


# ---------------------------------------------------------------------------
# Brand colours
# ---------------------------------------------------------------------------
NAVY = (30, 58, 95)
BLUE = (50, 80, 120)
DARK = (40, 40, 40)
GRAY = (100, 100, 100)
LIGHT_GRAY = (200, 200, 200)
WHITE = (255, 255, 255)
GREEN = (16, 120, 60)
AMBER = (160, 100, 10)
BG_LIGHT = (245, 247, 250)
BG_CODE = (240, 240, 240)
BG_TIP = (235, 245, 235)
BG_WARN = (255, 248, 235)
ACCENT = (37, 99, 235)


class MigrationGuidePDF(FPDF):
    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=22)

    def header(self):
        if self.page_no() > 1:
            self.set_font("Helvetica", "I", 7.5)
            self.set_text_color(*GRAY)
            self.cell(95, 8, "Recruit CRM to Winnow -- Migration Guide", align="L")
            self.cell(95, 8, "winnowcc.ai", align="R")
            self.ln(4)
            self.set_draw_color(*LIGHT_GRAY)
            self.set_line_width(0.3)
            self.line(10, self.get_y(), 200, self.get_y())
            self.ln(4)

    def footer(self):
        self.set_y(-15)
        self.set_draw_color(*LIGHT_GRAY)
        self.set_line_width(0.2)
        self.line(10, self.get_y(), 200, self.get_y())
        self.set_font("Helvetica", "", 7.5)
        self.set_text_color(*GRAY)
        self.cell(95, 10, "Confidential", align="L")
        self.cell(95, 10, f"Page {self.page_no()}/{{nb}}", align="R")

    # -- Primitives ----------------------------------------------------------

    def section_title(self, text):
        self.ln(6)
        self.set_font("Helvetica", "B", 17)
        self.set_text_color(*NAVY)
        self.cell(0, 11, text, new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(*NAVY)
        self.set_line_width(0.6)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(5)

    def sub_heading(self, text):
        self.ln(3)
        self.set_font("Helvetica", "B", 13)
        self.set_text_color(*BLUE)
        self.cell(0, 9, text, new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def sub_sub_heading(self, text):
        self.ln(2)
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(*NAVY)
        self.cell(0, 7, text, new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def body(self, text):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(*DARK)
        self.multi_cell(0, 5.5, text)
        self.ln(2)

    def bold_body(self, text):
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(*DARK)
        self.multi_cell(0, 5.5, text)
        self.ln(2)

    def step(self, number, text):
        # Circled step number
        x = self.get_x()
        y = self.get_y()
        self.set_fill_color(*ACCENT)
        self.set_draw_color(*ACCENT)
        self.ellipse(x, y, 6, 6, style="F")
        self.set_font("Helvetica", "B", 8)
        self.set_text_color(*WHITE)
        self.set_xy(x, y + 0.3)
        self.cell(6, 5.5, str(number), align="C")
        # Step text
        self.set_xy(x + 9, y)
        self.set_font("Helvetica", "", 10)
        self.set_text_color(*DARK)
        self.multi_cell(0, 5.5, text)
        self.ln(1.5)

    def bullet(self, text, indent=0):
        x = self.get_x() + indent
        self.set_x(x)
        self.set_font("Helvetica", "", 10)
        self.set_text_color(*DARK)
        self.cell(5, 5.5, "-")
        self.multi_cell(0, 5.5, text)
        self.ln(1)

    def tip_box(self, title, text):
        self.ln(1)
        x = self.get_x()
        w = 190
        self.set_fill_color(*BG_TIP)
        self.set_draw_color(16, 120, 60)
        # Estimate height
        self.set_font("Helvetica", "", 9.5)
        lines = self.multi_cell(w - 14, 5, text, dry_run=True, output="LINES")
        h = max(20, 10 + len(lines) * 5 + 6)
        self.rect(x, self.get_y(), w, h, style="F")
        self.set_line_width(0.5)
        self.line(x, self.get_y(), x, self.get_y() + h)
        y0 = self.get_y()
        self.set_xy(x + 7, y0 + 3)
        self.set_font("Helvetica", "B", 9.5)
        self.set_text_color(*GREEN)
        self.cell(0, 5, title, new_x="LMARGIN", new_y="NEXT")
        self.set_x(x + 7)
        self.set_font("Helvetica", "", 9.5)
        self.set_text_color(*DARK)
        self.multi_cell(w - 14, 5, text)
        self.set_y(y0 + h + 2)
        self.ln(1)

    def warn_box(self, title, text):
        self.ln(1)
        x = self.get_x()
        w = 190
        self.set_fill_color(*BG_WARN)
        self.set_draw_color(*AMBER)
        self.set_font("Helvetica", "", 9.5)
        lines = self.multi_cell(w - 14, 5, text, dry_run=True, output="LINES")
        h = max(20, 10 + len(lines) * 5 + 6)
        self.rect(x, self.get_y(), w, h, style="F")
        self.set_line_width(0.5)
        self.line(x, self.get_y(), x, self.get_y() + h)
        y0 = self.get_y()
        self.set_xy(x + 7, y0 + 3)
        self.set_font("Helvetica", "B", 9.5)
        self.set_text_color(*AMBER)
        self.cell(0, 5, title, new_x="LMARGIN", new_y="NEXT")
        self.set_x(x + 7)
        self.set_font("Helvetica", "", 9.5)
        self.set_text_color(*DARK)
        self.multi_cell(w - 14, 5, text)
        self.set_y(y0 + h + 2)
        self.ln(1)

    def table(self, headers, rows, col_widths=None):
        if col_widths is None:
            n = len(headers)
            col_widths = [190 / n] * n
        # Header row
        self.set_font("Helvetica", "B", 9)
        self.set_fill_color(*NAVY)
        self.set_text_color(*WHITE)
        for i, h in enumerate(headers):
            self.cell(col_widths[i], 7, h, border=1, fill=True, align="C")
        self.ln()
        # Data rows
        self.set_font("Helvetica", "", 9)
        self.set_text_color(*DARK)
        alt = False
        for row in rows:
            if alt:
                self.set_fill_color(*BG_LIGHT)
            else:
                self.set_fill_color(*WHITE)
            alt = not alt
            for i, cell in enumerate(row):
                self.cell(col_widths[i], 7, cell, border=1, fill=True)
            self.ln()
        self.ln(3)

    def code(self, text):
        self.set_font("Courier", "", 9)
        self.set_fill_color(*BG_CODE)
        self.set_text_color(50, 50, 50)
        x = self.get_x() + 5
        for line in text.strip().split("\n"):
            self.set_x(x)
            self.cell(
                180, 5.5, "  " + line,
                fill=True, new_x="LMARGIN", new_y="NEXT",
            )
        self.ln(2)


def build_pdf():
    pdf = MigrationGuidePDF()
    pdf.alias_nb_pages()

    # ===== COVER PAGE =====================================================
    pdf.add_page()
    pdf.ln(35)
    # Top accent bar
    pdf.set_fill_color(*NAVY)
    pdf.rect(0, 0, 210, 6, style="F")
    # Title
    pdf.set_font("Helvetica", "B", 28)
    pdf.set_text_color(*NAVY)
    pdf.cell(0, 16, "Recruit CRM to Winnow", align="C",
             new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 20)
    pdf.set_text_color(*BLUE)
    pdf.cell(0, 12, "Migration Guide", align="C",
             new_x="LMARGIN", new_y="NEXT")
    pdf.ln(10)
    # Divider
    pdf.set_draw_color(*NAVY)
    pdf.set_line_width(0.8)
    pdf.line(60, pdf.get_y(), 150, pdf.get_y())
    pdf.ln(10)
    # Metadata
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(*GRAY)
    for line in [
        "Platform: Winnow (winnowcc.ai)",
        "Source: Recruit CRM (CSV Data Export)",
        "Version: Phase 1 -- Core Entity Import",
        "Date: March 2026",
    ]:
        pdf.cell(0, 7, line, align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(20)
    # Scope summary box
    pdf.set_fill_color(*BG_LIGHT)
    pdf.rect(25, pdf.get_y(), 160, 40, style="F")
    y0 = pdf.get_y()
    pdf.set_xy(35, y0 + 5)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(*NAVY)
    pdf.cell(0, 6, "What This Guide Covers", new_x="LMARGIN", new_y="NEXT")
    pdf.set_x(35)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*DARK)
    pdf.multi_cell(140, 5.5,
        "Step-by-step instructions for exporting your data from Recruit CRM, "
        "uploading it to Winnow, verifying the import, and getting productive "
        "in your new recruiter workspace. Covers Companies, Contacts, Jobs, "
        "Candidates, and Assignments."
    )
    pdf.set_y(y0 + 44)

    # ===== TABLE OF CONTENTS ==============================================
    pdf.add_page()
    pdf.section_title("Table of Contents")
    pdf.ln(2)
    toc = [
        ("1", "Before You Begin", "Prerequisites and what to expect"),
        ("2", "Export from Recruit CRM", "How to download your CSV data export"),
        ("3", "Upload to Winnow", "The migration wizard step by step"),
        ("4", "What Gets Imported", "Entity mapping and data details"),
        ("5", "Verify Your Data", "Post-import checklist"),
        ("6", "Your Recruiter Workflow", "Using Winnow day-to-day after migration"),
        ("7", "Troubleshooting", "Common issues and how to resolve them"),
        ("8", "FAQ", "Frequently asked questions"),
    ]
    for num, title, desc in toc:
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(*NAVY)
        pdf.cell(10, 7, num + ".")
        pdf.cell(70, 7, title)
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(*GRAY)
        pdf.cell(0, 7, desc, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    # ===== SECTION 1: BEFORE YOU BEGIN ====================================
    pdf.add_page()
    pdf.section_title("1.  Before You Begin")

    pdf.sub_heading("Prerequisites")
    pdf.bullet("An active Winnow recruiter account (any tier: Trial, Solo, "
               "Team, or Agency)")
    pdf.bullet("Admin access to your Recruit CRM workspace (to export data)")
    pdf.bullet("The CSV data export ZIP file from Recruit CRM "
               "(usually named csv-data-export-<date>.zip)")
    pdf.bullet("A modern web browser (Chrome, Edge, Firefox, or Safari)")

    pdf.sub_heading("What to Expect")
    pdf.body(
        "The migration imports five entity types from your Recruit CRM export "
        "in dependency order: Companies, Contacts, Jobs, Candidates, and "
        "Assignments. The entire process typically completes in under 30 "
        "seconds for most datasets."
    )

    pdf.table(
        ["Entity", "Approx. Count", "Winnow Destination"],
        [
            ["Companies", "~430", "Clients"],
            ["Contacts", "~387", "Client contacts (merged)"],
            ["Jobs", "~413", "Recruiter Jobs"],
            ["Candidates", "~8,800+", "Pipeline Candidates"],
            ["Assignments", "~11,000+", "Candidate-Job links + stages"],
        ],
        col_widths=[45, 40, 105],
    )

    pdf.tip_box(
        "TIP: Timing",
        "The import runs synchronously -- you will see results immediately "
        "after clicking Start Import. No background processing is needed for "
        "CRM data exports."
    )

    pdf.sub_heading("What Is NOT Imported (Phase 1)")
    pdf.body("The following data will be imported in a future update:")
    pdf.bullet("Skills and tags")
    pdf.bullet("Work history and education history")
    pdf.bullet("Notes and activity logs")
    pdf.bullet("Resume file attachments (requires the separate "
               "attachments-data-export.zip)")

    # ===== SECTION 2: EXPORT FROM RECRUIT CRM ============================
    pdf.add_page()
    pdf.section_title("2.  Export from Recruit CRM")

    pdf.sub_heading("Step-by-Step Export")
    pdf.step(1, "Log in to Recruit CRM as an administrator.")
    pdf.step(2, 'Navigate to Settings (gear icon) then select "Data Export" '
                'from the left sidebar.')
    pdf.step(3, 'Select "CSV Data Export" (not the attachments export -- '
                "that's a separate step for Phase 2).")
    pdf.step(4, 'Click "Export All Data". Recruit CRM will package all your '
                "entities into a single ZIP file.")
    pdf.step(5, "Wait for the export to complete. You will receive an email "
                "with a download link, or it may download directly.")
    pdf.step(6, "Save the ZIP file to your computer. The filename is usually "
                "csv-data-export-<date-time>.zip.")

    pdf.warn_box(
        "IMPORTANT: Do Not Unzip",
        "Upload the ZIP file directly to Winnow. Do not extract it first. "
        "Winnow's migration wizard reads all five CSV files from inside "
        "the ZIP automatically."
    )

    pdf.sub_heading("What's Inside the ZIP")
    pdf.body("The Recruit CRM CSV export contains these files:")
    pdf.table(
        ["Filename", "Contents", "Typical Row Count"],
        [
            ["candidate_data.csv", "All candidates with contact info", "~8,800"],
            ["company_data.csv", "Client companies", "~430"],
            ["contact_data.csv", "Contacts linked to companies", "~387"],
            ["job_data.csv", "Job openings", "~413"],
            ["assignment_data.csv", "Candidate-to-job assignments", "~11,000"],
        ],
        col_widths=[55, 85, 50],
    )

    # ===== SECTION 3: UPLOAD TO WINNOW ===================================
    pdf.add_page()
    pdf.section_title("3.  Upload to Winnow")

    pdf.sub_heading("Navigate to the Migration Wizard")
    pdf.step(1, "Log in to Winnow at winnowcc.ai with your recruiter account.")
    pdf.step(2, "From the left sidebar, click Migrate (or navigate directly "
                "to /recruiter/migrate).")
    pdf.ln(2)

    pdf.sub_heading("Step 1: Upload Your File")
    pdf.step(3, "Drag and drop your csv-data-export ZIP file onto the upload "
                "area, or click Browse Files to select it.")
    pdf.step(4, "Click Upload & Detect Platform. A progress bar shows the "
                "upload status.")
    pdf.ln(2)

    pdf.sub_heading("Step 2: Review Detection Results")
    pdf.body(
        "Winnow automatically identifies the file as a Recruit CRM export. "
        "You will see:"
    )
    pdf.bullet('Platform: "Recruit CRM" with a high confidence score '
               "(typically 90%+)")
    pdf.bullet("A summary of detected entity types: Companies, Contacts, "
               "Jobs, Candidates, Assignments")
    pdf.bullet("The total number of rows across all CSV files")

    pdf.tip_box(
        "TIP: Multi-Entity Detection",
        "Unlike single-CSV imports, the Recruit CRM ZIP import shows all "
        "five entity types it will process. This is normal -- all entities "
        "are imported in one operation."
    )

    pdf.step(5, "Review the detection summary. Confirm it shows the correct "
                "entity types and row counts.")
    pdf.step(6, "Click Start Import.")
    pdf.ln(2)

    pdf.sub_heading("Step 3: Import Completes")
    pdf.body(
        "The import processes all entities in seconds. When complete, you "
        "will see a summary table showing per-entity results:"
    )
    pdf.table(
        ["Entity", "Imported", "Merged", "Skipped", "Errors"],
        [
            ["Companies", "430", "0", "0", "0"],
            ["Contacts", "85", "302", "0", "0"],
            ["Jobs", "413", "0", "0", "0"],
            ["Candidates", "8,864", "0", "0", "0"],
            ["Assignments", "7,230", "0", "3,848", "0"],
        ],
        col_widths=[45, 35, 35, 35, 35],
    )
    pdf.set_font("Helvetica", "I", 9)
    pdf.set_text_color(*GRAY)
    pdf.cell(0, 5, "(Example numbers -- your actual counts will vary)",
             align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    pdf.body(
        '"Merged" means the entity was matched to an existing record (e.g., '
        "contacts merged into their parent company). "
        '"Skipped" means the assignment referenced a candidate or job not '
        "found in the export."
    )

    # ===== SECTION 4: WHAT GETS IMPORTED =================================
    pdf.add_page()
    pdf.section_title("4.  What Gets Imported")

    pdf.sub_heading("Companies -> Clients")
    pdf.body(
        "Each company from Recruit CRM becomes a Client in Winnow's "
        "recruiter workspace. Fields mapped:"
    )
    pdf.table(
        ["Recruit CRM Field", "Winnow Field"],
        [
            ["Company (name)", "Company Name"],
            ["Industry", "Industry"],
            ["Website", "Website"],
            ["Parent Company Slug", "(reserved for future hierarchy)"],
        ],
        col_widths=[80, 110],
    )
    pdf.body("De-duplication: Companies are matched by name (case-insensitive) "
             "within your recruiter account.")

    pdf.sub_heading("Contacts -> Client Contact Records")
    pdf.body(
        "Contacts are merged into their parent company's Client record. Each "
        "contact is appended to the client's contacts list, and the first "
        "contact's details populate the primary contact fields."
    )
    pdf.table(
        ["Recruit CRM Field", "Winnow Field"],
        [
            ["First Name + Last Name", "Contact Name"],
            ["Email", "Contact Email"],
            ["Contact Number", "Contact Phone"],
            ["Designation", "Contact Title"],
            ["Company Slug", "(links to parent Client)"],
        ],
        col_widths=[80, 110],
    )

    pdf.sub_heading("Jobs -> Recruiter Jobs")
    pdf.body("Each job opening becomes a Recruiter Job linked to its client.")
    pdf.table(
        ["Recruit CRM Field", "Winnow Field"],
        [
            ["Name", "Title"],
            ["Job Status", "Status (Open->active, Closed->closed)"],
            ["Job Type", "Employment Type"],
            ["Min/Max Annual Salary", "Salary Range"],
            ["City, State, Country", "Location"],
            ["Company Slug", "Client (linked by slug)"],
        ],
        col_widths=[65, 125],
    )

    pdf.sub_heading("Candidates -> Pipeline Candidates")
    pdf.body(
        "Each candidate becomes a Pipeline Candidate in your recruiter CRM."
    )
    pdf.table(
        ["Recruit CRM Field", "Winnow Field"],
        [
            ["First Name + Last Name", "Name"],
            ["Email", "Email"],
            ["Contact Number", "Phone"],
            ["Profile Linkedin", "LinkedIn URL"],
            ["Source", "Source"],
        ],
        col_widths=[65, 125],
    )
    pdf.body("De-duplication: Candidates are matched by email address "
             "(case-insensitive) within your recruiter account.")

    pdf.sub_heading("Assignments -> Candidate-Job Links + Stages")
    pdf.body(
        "Assignments connect candidates to jobs and set their pipeline stage. "
        "When a candidate has multiple assignments to the same job, the most "
        "recent one (by Stage Date) is used."
    )
    pdf.ln(1)
    pdf.sub_sub_heading("Stage Mapping")
    pdf.table(
        ["Recruit CRM Status", "Winnow Stage"],
        [
            ["Applied / Assigned / Invited to Apply", "Sourced"],
            ["Demographics Requested / Submittal Forms Sent", "Contacted"],
            ["Submittal Forms Received / Submitted to Prime", "Screening"],
            ["Interviewing", "Interviewing"],
            ["Selected", "Placed"],
            ["Did Not Join / Insufficient Exp. / Non-Resident / "
             "Not in Consideration", "Rejected"],
        ],
        col_widths=[105, 85],
    )

    # ===== SECTION 5: VERIFY YOUR DATA ===================================
    pdf.add_page()
    pdf.section_title("5.  Verify Your Data")

    pdf.sub_heading("Post-Import Checklist")
    pdf.body("After the import completes, walk through these checks to "
             "confirm everything looks right:")
    pdf.ln(1)

    checks = [
        ("Clients", "Go to Clients in the sidebar. Verify the total count "
         "matches. Spot-check 3-5 companies: correct name, industry, and "
         "website. Open a client and confirm contacts are listed."),
        ("Jobs", "Go to Jobs. Verify the total count. Check that job titles, "
         "statuses (active/closed), salary ranges, and client links are "
         "correct."),
        ("Pipeline", "Go to Pipeline or Candidates. Verify the total count "
         "of candidates. Spot-check names, emails, phone numbers, and "
         "LinkedIn URLs."),
        ("Assignments", "Open a job and verify candidates are linked to it. "
         "Check that pipeline stages (Sourced, Contacted, Screening, etc.) "
         "match what you expect from Recruit CRM."),
        ("Rollback", "If anything looks wrong, use the Rollback button on "
         "the migration summary page. This cleanly removes all imported "
         "entities so you can start fresh."),
    ]
    for i, (title, desc) in enumerate(checks, 1):
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*NAVY)
        pdf.cell(6, 5.5, f"{i}.")
        pdf.cell(25, 5.5, title)
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(*DARK)
        pdf.multi_cell(0, 5.5, desc)
        pdf.ln(2)

    pdf.warn_box(
        "IMPORTANT: Rollback Is Available",
        "The migration summary page includes a Rollback button. Clicking it "
        "will delete all entities created by this import (clients, jobs, "
        "candidates, and their links). Use this if you spot data issues and "
        "want to re-import after fixing your export. Rollback does not affect "
        "any data you created manually in Winnow."
    )

    # ===== SECTION 6: RECRUITER WORKFLOW ==================================
    pdf.add_page()
    pdf.section_title("6.  Your Recruiter Workflow After Migration")

    pdf.body(
        "Once your data is imported, here is how to use Winnow day-to-day "
        "as your primary recruiter CRM."
    )

    pdf.sub_heading("Client Management")
    pdf.step(1, "Navigate to Clients from the sidebar to see all imported "
                "companies.")
    pdf.step(2, "Click any client to view their details, contacts, and "
                "associated jobs.")
    pdf.step(3, "Edit client records to add contract terms (fee percentage, "
                "flat fee, contract dates) that were not part of the "
                "Recruit CRM export.")
    pdf.step(4, "Add new clients directly in Winnow as you win new business.")
    pdf.ln(2)

    pdf.sub_heading("Job Pipeline")
    pdf.step(1, "Go to Jobs to see all imported and new job openings.")
    pdf.step(2, "Each job shows its linked client, status, salary range, "
                "and assigned candidates.")
    pdf.step(3, "Create new jobs by clicking New Job. Winnow will suggest "
                "matching candidates from your pipeline automatically.")
    pdf.step(4, 'Use the status filters (Active, Closed, Paused) to focus '
                "on current openings.")
    pdf.ln(2)

    pdf.sub_heading("Candidate Pipeline")
    pdf.step(1, "Go to Pipeline to view all candidates. Use the stage "
                "filters (Sourced, Contacted, Screening, Interviewing, "
                "Offered, Placed) to track progress.")
    pdf.step(2, "Click a candidate to view their profile, linked job, "
                "stage history, and contact details.")
    pdf.step(3, "Move candidates between stages by updating their stage "
                "from the candidate detail page or the pipeline board view.")
    pdf.step(4, "Add notes, ratings, and tags to candidates for easy "
                "filtering later.")
    pdf.ln(2)

    pdf.sub_heading("Winnow-Exclusive Features")
    pdf.body("Now that your data is in Winnow, you can take advantage of "
             "features not available in Recruit CRM:")
    pdf.bullet("AI Match Scoring -- Winnow automatically scores candidates "
               "against jobs using Interview Probability Scores (IPS).")
    pdf.bullet("Sieve AI Concierge -- Ask Sieve to find candidates matching "
               "specific criteria, draft outreach messages, or summarize "
               "pipeline status.")
    pdf.bullet("Resume Parsing -- Upload candidate resumes and Winnow "
               "extracts structured data automatically.")
    pdf.bullet("Tailored Resumes -- Generate client-specific resume versions "
               "highlighting relevant experience.")
    pdf.bullet("Multi-Board Distribution -- Post jobs to multiple boards "
               "simultaneously.")
    pdf.bullet("Fraud Detection -- Winnow flags suspicious job postings "
               "with its 14-signal fraud detector.")

    # ===== SECTION 7: TROUBLESHOOTING ====================================
    pdf.add_page()
    pdf.section_title("7.  Troubleshooting")

    issues = [
        ('"Unknown platform" after upload',
         "This means the ZIP file does not contain the expected CSV filenames. "
         "Verify you exported CSV Data (not attachments or a filtered subset). "
         "The ZIP should contain candidate_data.csv, company_data.csv, "
         "contact_data.csv, job_data.csv, and assignment_data.csv."),
        ("Low confidence score",
         "If the confidence is below 50%, the file may be missing some CSVs. "
         "Check that at least 3 of the 5 expected files are present. You can "
         "still proceed with the import if the entity types look correct."),
        ("Import fails with errors",
         "Check the error log on the summary page. Common causes: corrupted "
         "CSV rows, encoding issues (non-UTF-8 characters), or extremely "
         "long field values. Try re-exporting from Recruit CRM."),
        ("Duplicate candidates after import",
         "Winnow de-duplicates by email address. If some candidates in "
         "Recruit CRM have no email, they will be imported as new records "
         "even if they already exist. You can merge duplicates manually "
         "from the candidate detail page."),
        ("Contacts not linked to companies",
         "This happens when a contact's Company Slug does not match any "
         "company in the export. These contacts are created as standalone "
         "client records. You can merge them manually."),
        ("Assignments skipped",
         "Assignments are skipped when the referenced candidate or job slug "
         "is not found in the import. This can happen if Recruit CRM "
         "exported a partial dataset. The skipped count is shown in the "
         "summary."),
    ]
    for title, desc in issues:
        pdf.sub_sub_heading(title)
        pdf.body(desc)

    # ===== SECTION 8: FAQ ================================================
    pdf.add_page()
    pdf.section_title("8.  Frequently Asked Questions")

    faqs = [
        ("Can I run the migration more than once?",
         "Yes. Each upload creates a separate migration job. If you roll back "
         "the first import and re-upload, you get a clean slate. You can also "
         "import additional files without rolling back -- Winnow will merge "
         "duplicates by email and company name."),
        ("Does migration count against my plan limits?",
         "No. The migration import does not consume any daily usage limits "
         "(matches, Sieve messages, etc.). It's a one-time data operation."),
        ("How long does the import take?",
         "For most Recruit CRM exports (up to ~20,000 total rows), the "
         "import completes in under 30 seconds. It runs synchronously -- "
         "you see results immediately."),
        ("What about my resume files?",
         "Resume file attachments (the attachments-data-export.zip) will be "
         "supported in Phase 2. For now, you can manually upload resumes for "
         "individual candidates or use the bulk resume upload feature on the "
         "Agency plan."),
        ("Can I import from multiple CRM platforms?",
         "Yes. Winnow supports Bullhorn, CATSOne, Zoho Recruit, and generic "
         "CSV exports in addition to Recruit CRM. Each import is tracked as "
         "a separate migration job."),
        ("What if I add data in Winnow before migrating?",
         "No problem. The import de-duplicates against your existing data. "
         "Candidates with matching emails and companies with matching names "
         "will be merged, not duplicated."),
        ("Is there a way to undo the migration?",
         "Yes. The Rollback button on the migration summary page removes all "
         "entities created by that specific import. It does not affect "
         "manually-created records or data from other imports."),
    ]
    for q, a in faqs:
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*NAVY)
        pdf.multi_cell(0, 5.5, "Q: " + q)
        pdf.ln(1)
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(*DARK)
        pdf.multi_cell(0, 5.5, a)
        pdf.ln(4)

    # ===== OUTPUT =========================================================
    output_path = "tasks/Recruit_CRM_Migration_Guide.pdf"
    pdf.output(output_path)
    print(f"PDF generated: {output_path}")


if __name__ == "__main__":
    build_pdf()
