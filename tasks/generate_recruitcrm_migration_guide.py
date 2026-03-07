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
        "Source: Recruit CRM (CSV + Attachments Export)",
        "Version: Complete -- CRM Data + Resume Attachments",
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
        "in your new recruiter workspace. Covers CRM data (Companies, Contacts, "
        "Jobs, Candidates, Assignments) and resume attachments import."
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
        ("5", "Resume Attachments Import", "Phase 2: import resumes and enable matching"),
        ("6", "Verify Your Data", "Post-import checklist"),
        ("7", "Your Recruiter Workflow", "Using Winnow day-to-day after migration"),
        ("8", "Troubleshooting", "Common issues and how to resolve them"),
        ("9", "FAQ", "Frequently asked questions"),
        ("10", "Ask Sieve for Help", "Your AI concierge knows migration inside out"),
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

    pdf.bullet("(Phase 2) The attachments-data-export ZIP from Recruit CRM "
               "(contains candidate resumes, typically 1-2 GB)")

    pdf.sub_heading("What to Expect")
    pdf.body(
        "The migration has two phases. Phase 1 imports five entity types from "
        "your CSV export in dependency order: Companies, Contacts, Jobs, "
        "Candidates, and Assignments. This completes in under 30 seconds. "
        "Phase 2 imports resume attachments and matches them to the candidates "
        "from Phase 1, enabling Winnow's match scoring engine."
    )

    pdf.table(
        ["Phase", "Entity", "Winnow Destination"],
        [
            ["1 (CSV)", "Companies (~430)", "Clients"],
            ["1 (CSV)", "Contacts (~387)", "Client contacts (merged)"],
            ["1 (CSV)", "Jobs (~413)", "Recruiter Jobs"],
            ["1 (CSV)", "Candidates (~8,800+)", "Pipeline Candidates"],
            ["1 (CSV)", "Assignments (~11,000+)", "Candidate-Job links"],
            ["2 (Attach.)", "Resumes (~8,900)", "CandidateProfile + matching"],
        ],
        col_widths=[30, 65, 95],
    )

    pdf.tip_box(
        "TIP: Timing",
        "Phase 1 (CSV) runs synchronously -- results appear in seconds. "
        "Phase 2 (attachments) runs in the background because of the large "
        "file size. You can close the browser and come back later."
    )

    pdf.sub_heading("What Is NOT Yet Imported")
    pdf.body("The following data will be imported in a future update:")
    pdf.bullet("Skills and tags")
    pdf.bullet("Work history and education history")
    pdf.bullet("Notes and activity logs")

    # ===== SECTION 2: EXPORT FROM RECRUIT CRM ============================
    pdf.add_page()
    pdf.section_title("2.  Export from Recruit CRM")

    pdf.sub_heading("Export 1: CSV Data Export (Phase 1)")
    pdf.step(1, "Log in to Recruit CRM as an administrator.")
    pdf.step(2, 'Navigate to Settings (gear icon) then select "Data Export" '
                'from the left sidebar.')
    pdf.step(3, 'Select "CSV Data Export".')
    pdf.step(4, 'Click "Export All Data". Recruit CRM will package all your '
                "entities into a single ZIP file.")
    pdf.step(5, "Wait for the export to complete. You will receive an email "
                "with a download link, or it may download directly.")
    pdf.step(6, "Save the ZIP file to your computer. The filename is usually "
                "csv-data-export-<date-time>.zip.")

    pdf.sub_heading("Export 2: Attachments Export (Phase 2)")
    pdf.step(7, 'In the same Data Export page, select "Attachments Data Export".')
    pdf.step(8, 'Click "Export All Attachments". This is a much larger file '
                "(typically 1-2 GB) and may take several minutes to prepare.")
    pdf.step(9, "Download the ZIP file. The filename is usually "
                "attachments-data-export-<date-time>.zip.")

    pdf.warn_box(
        "IMPORTANT: Do Not Unzip Either File",
        "Upload both ZIP files directly to Winnow. Do not extract them first. "
        "Winnow's migration wizard reads the files from inside "
        "the ZIP automatically."
    )
    pdf.tip_box(
        "TIP: Order Matters",
        "Always import the CSV data export first (Phase 1), then the "
        "attachments export (Phase 2). The attachments import needs the "
        "candidate records from Phase 1 to match resumes correctly."
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
    pdf.section_title("3.  Upload CSV Data to Winnow (Phase 1)")

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
    pdf.section_title("4.  What Gets Imported (Phase 1)")

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

    # ===== SECTION 5: RESUME ATTACHMENTS IMPORT ==========================
    pdf.add_page()
    pdf.section_title("5.  Resume Attachments Import (Phase 2)")

    pdf.sub_heading("Why This Step Matters")
    pdf.body(
        "After Phase 1, your candidates are imported as contact-info shells -- "
        "names, emails, and phone numbers. Without parsed resumes, Winnow's "
        "matching engine cannot compute Interview Probability Scores (IPS) "
        "between candidates and jobs. Phase 2 imports the actual resume files "
        "and links them to the candidates you already imported."
    )

    pdf.sub_heading("Prerequisites")
    pdf.bullet("Phase 1 (CSV import) must be completed first")
    pdf.bullet("The attachments-data-export ZIP from Recruit CRM "
               "(downloaded in Section 2)")
    pdf.bullet("A stable internet connection (the file is 1-2 GB)")

    pdf.sub_heading("Step-by-Step Import")
    pdf.step(1, "Go to Migration (/recruiter/migrate) in Winnow.")
    pdf.step(2, "Upload the attachments-data-export ZIP file. Winnow detects "
                'it as "Recruit CRM Resume Attachments" and shows the number '
                "of candidate resumes found (typically ~8,900).")
    pdf.step(3, 'Review the detection summary. You should see an info box '
                'explaining that resumes will be matched by slug to your '
                'previously imported candidates.')
    pdf.step(4, 'Click "Start Resume Attachment Import".')
    pdf.step(5, "The import begins in the background. A progress bar shows "
                "how many files have been processed. You can safely close the "
                "browser and come back later.")
    pdf.step(6, "When complete, the summary shows succeeded/failed/total. "
                "Navigate to any job to see matched candidates with IPS scores.")

    pdf.sub_heading("How It Works (Behind the Scenes)")
    pdf.body(
        "The attachments ZIP has a nested structure: an outer ZIP containing "
        "an inner ZIP, which contains folders for each candidate organized by "
        "slug. Winnow extracts each candidate's resume from the resumefilename/ "
        "subfolder, matches it to the pipeline candidate using the same slug "
        "from Phase 1, parses the resume into structured data, and creates a "
        "CandidateProfile. This enables the match scoring engine."
    )

    pdf.table(
        ["Step", "What Happens"],
        [
            ["Extract", "Inner ZIP extracted to temp (avoids 1.4GB in RAM)"],
            ["Match", "Each Candidates/{slug}/resumefilename/ matched by slug"],
            ["Parse", "PDF/DOCX text extracted and parsed into profile data"],
            ["Link", "CandidateProfile linked to pipeline candidate"],
            ["Score", "Candidate now eligible for IPS match scoring"],
        ],
        col_widths=[35, 155],
    )

    pdf.warn_box(
        "IMPORTANT: Processing Time",
        "With ~8,900 resumes, Phase 2 takes approximately 3-6 hours to "
        "complete (each resume is individually parsed). The import runs in "
        "the background -- you do not need to keep the browser open. Check "
        "the progress at any time by visiting the Migration page."
    )

    pdf.tip_box(
        "TIP: Multiple Files per Candidate",
        "Some candidates may have multiple files in their folder (cover "
        "letters, certifications, etc.). Winnow picks the largest file in "
        "the resumefilename/ subfolder, which is typically the most "
        "complete resume."
    )

    # ===== SECTION 6: VERIFY YOUR DATA ===================================
    pdf.add_page()
    pdf.section_title("6.  Verify Your Data")

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
        ("Resumes", "(After Phase 2) Open a candidate and verify their "
         "profile shows parsed resume data. Check that the experience, "
         "skills, and education sections are populated."),
        ("Match Scores", "(After Phase 2) Go to a job and check the Matched "
         "Candidates tab. Candidates with parsed resumes should now show "
         "IPS scores. If scores are missing, the resume may have failed "
         "to parse -- check the migration summary for failed files."),
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

    # ===== SECTION 7: RECRUITER WORKFLOW ==================================
    pdf.add_page()
    pdf.section_title("7.  Your Recruiter Workflow After Migration")

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

    # ===== SECTION 8: TROUBLESHOOTING ====================================
    pdf.add_page()
    pdf.section_title("8.  Troubleshooting")

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
        ('"Import CSV data first" error on attachments upload',
         "Phase 2 (attachments) requires Phase 1 (CSV) to be completed "
         "first. Upload the csv-data-export ZIP and complete that import "
         "before uploading the attachments ZIP."),
        ("Attachments import stuck or stale",
         "The attachments import runs in the background. If the progress "
         "bar has not moved for 10+ minutes, the background worker may "
         "need restarting. Cancel the migration from the progress page "
         "and try again. If the problem persists, contact support."),
        ("Most resumes show as 'unmatched'",
         "Resumes are matched by candidate slug. If a slug mismatch occurs "
         "(e.g., the CSV and attachments exports were done at very different "
         "times), some candidates may not be found. Re-export both files "
         "from Recruit CRM at the same time to ensure slug consistency."),
        ("Candidates still show no match scores after Phase 2",
         "Match scores require both a parsed resume (CandidateProfile) and "
         "a linked job. Verify the candidate has a profile by clicking on "
         "them in the pipeline. If the resume failed to parse, the file may "
         "be corrupted or in an unsupported format. Try manually uploading "
         "the resume for that candidate."),
    ]
    for title, desc in issues:
        pdf.sub_sub_heading(title)
        pdf.body(desc)

    # ===== SECTION 9: FAQ ================================================
    pdf.add_page()
    pdf.section_title("9.  Frequently Asked Questions")

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
         "Upload the attachments-data-export.zip from Recruit CRM as Phase 2 "
         "(see Section 5). Winnow automatically matches resumes to the "
         "candidates imported in Phase 1, parses them, and enables match "
         "scoring. Processing ~8,900 resumes takes approximately 3-6 hours "
         "in the background."),
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

    # Add Phase 2 FAQs
    phase2_faqs = [
        ("How long does the attachments import take?",
         "For ~8,900 resumes, expect 3-6 hours. Each resume is individually "
         "parsed and scored. The import runs in the background -- you can "
         "close the browser and check back later."),
        ("Do I need the CSV import before the attachments import?",
         "Yes. Phase 1 (CSV) must complete first. The attachments import "
         "matches resumes to candidates using slugs from the CSV import. "
         "If you try to upload attachments first, you will see an error "
         "message asking you to complete the CSV import first."),
        ("What file formats are supported for resumes?",
         "PDF, DOCX, and DOC files. Other attachment types (images, "
         "spreadsheets, etc.) are skipped. Winnow picks the largest "
         "resume file per candidate for the best parsing results."),
        ("Can I ask Sieve for help during the migration?",
         "Absolutely! Sieve (the AI concierge) knows every step of the "
         "migration process. Click the Sieve chat icon and ask anything: "
         "'How do I export from Recruit CRM?', 'Why are my candidates not "
         "showing match scores?', or 'What should I do after the import?'"),
    ]
    for q, a in phase2_faqs:
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*NAVY)
        pdf.multi_cell(0, 5.5, "Q: " + q)
        pdf.ln(1)
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(*DARK)
        pdf.multi_cell(0, 5.5, a)
        pdf.ln(4)

    # ===== SECTION 10: ASK SIEVE FOR HELP ================================
    pdf.add_page()
    pdf.section_title("10.  Ask Sieve for Help")

    pdf.body(
        "Sieve is Winnow's AI concierge, and she knows the entire migration "
        "process inside and out. You can ask her for help at any point -- "
        "before, during, or after your migration."
    )

    pdf.sub_heading("What Sieve Can Help With")
    pdf.bullet("Walking you through the export steps in Recruit CRM")
    pdf.bullet("Explaining what gets imported and what to expect")
    pdf.bullet("Troubleshooting errors during import")
    pdf.bullet("Diagnosing why candidates aren't showing match scores")
    pdf.bullet("Suggesting next steps after migration completes")
    pdf.bullet("Explaining Phase 2 (attachments) and when to do it")
    pdf.bullet("Answering any platform question about Winnow")

    pdf.sub_heading("How to Access Sieve")
    pdf.step(1, "Click the Sieve chat icon in the bottom-right corner of "
                "any page in Winnow, or go to /recruiter/sieve.")
    pdf.step(2, "Type your question naturally. Examples:")
    pdf.ln(1)
    pdf.bullet('"How do I export my data from Recruit CRM?"', indent=9)
    pdf.bullet('"I uploaded the CSV but where are my candidates?"', indent=9)
    pdf.bullet('"Why are there no match scores for my candidates?"', indent=9)
    pdf.bullet('"How do I import my resume attachments?"', indent=9)
    pdf.bullet('"My attachments import seems stuck -- what do I do?"', indent=9)
    pdf.bullet('"What should I do now that migration is complete?"', indent=9)

    pdf.tip_box(
        "TIP: Sieve Knows Your Data",
        "Sieve can see your current migration state, pipeline counts, and "
        "plan details. She will give personalized advice based on where "
        "you are in the process. For example, if you have candidates "
        "without resumes, she'll proactively suggest the attachments import."
    )

    # ===== OUTPUT =========================================================
    output_path = "tasks/Recruit_CRM_Migration_Guide.pdf"
    pdf.output(output_path)
    print(f"PDF generated: {output_path}")


if __name__ == "__main__":
    build_pdf()
