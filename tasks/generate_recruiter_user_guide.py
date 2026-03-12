"""Generate the Winnow Recruiter User Guide PDF.

Covers every feature by tier (Trial / Solo / Team / Agency), includes a
workflow lifecycle diagram, and is designed to be Sieve-aware so the AI
concierge can reference it directly.

Run:
    cd services/api && .venv/Scripts/python.exe -m tasks.generate_recruiter_user_guide

Or from repo root:
    python tasks/generate_recruiter_user_guide.py
"""

import os
import sys
from fpdf import FPDF

# ---------------------------------------------------------------------------
# Brand colours (matches gold-standard template)
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
BG_FLOW = (230, 238, 250)


class RecruiterGuidePDF(FPDF):
    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=22)

    def header(self):
        if self.page_no() > 1:
            self.set_font("Helvetica", "I", 7.5)
            self.set_text_color(*GRAY)
            self.cell(95, 8, "Winnow Recruiter User Guide", align="L")
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
        x = self.get_x()
        y = self.get_y()
        self.set_fill_color(*ACCENT)
        self.set_draw_color(*ACCENT)
        self.ellipse(x, y, 6, 6, style="F")
        self.set_font("Helvetica", "B", 8)
        self.set_text_color(*WHITE)
        self.set_xy(x, y + 0.3)
        self.cell(6, 5.5, str(number), align="C")
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
        self.set_font("Helvetica", "B", 9)
        self.set_fill_color(*NAVY)
        self.set_text_color(*WHITE)
        for i, h in enumerate(headers):
            self.cell(col_widths[i], 7, h, border=1, fill=True, align="C")
        self.ln()
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

    def flow_box(self, text, x, y, w=32, h=12):
        """Draw a rounded workflow box."""
        self.set_fill_color(*BG_FLOW)
        self.set_draw_color(*NAVY)
        self.set_line_width(0.4)
        self.rect(x, y, w, h, style="FD")
        self.set_font("Helvetica", "B", 7)
        self.set_text_color(*NAVY)
        self.set_xy(x, y + 1)
        self.multi_cell(w, 3.5, text, align="C")

    def flow_arrow(self, x1, y1, x2, y2):
        """Draw an arrow between two points."""
        self.set_draw_color(*ACCENT)
        self.set_line_width(0.5)
        self.line(x1, y1, x2, y2)
        # Arrowhead
        self.set_fill_color(*ACCENT)
        self.polygon(
            [(x2, y2), (x2 - 1.5, y2 - 2.5), (x2 + 1.5, y2 - 2.5)],
            style="F",
        )


def build_pdf():
    pdf = RecruiterGuidePDF()
    pdf.alias_nb_pages()

    # ===== COVER PAGE =====================================================
    pdf.add_page()
    pdf.ln(35)
    pdf.set_fill_color(*NAVY)
    pdf.rect(0, 0, 210, 6, style="F")
    pdf.set_font("Helvetica", "B", 28)
    pdf.set_text_color(*NAVY)
    pdf.cell(0, 16, "Winnow Recruiter", align="C",
             new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 20)
    pdf.set_text_color(*BLUE)
    pdf.cell(0, 12, "Complete User Guide", align="C",
             new_x="LMARGIN", new_y="NEXT")
    pdf.ln(10)
    pdf.set_draw_color(*NAVY)
    pdf.set_line_width(0.8)
    pdf.line(60, pdf.get_y(), 150, pdf.get_y())
    pdf.ln(10)
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(*GRAY)
    for line in [
        "Platform: Winnow (winnowcc.ai)",
        "Audience: Recruiters -- All Tiers",
        "Version: Complete Feature Reference",
        "Date: March 2026",
    ]:
        pdf.cell(0, 7, line, align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(20)
    pdf.set_fill_color(*BG_LIGHT)
    pdf.rect(25, pdf.get_y(), 160, 48, style="F")
    y0 = pdf.get_y()
    pdf.set_xy(35, y0 + 5)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(*NAVY)
    pdf.cell(0, 6, "What This Guide Covers", new_x="LMARGIN", new_y="NEXT")
    pdf.set_x(35)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(*DARK)
    pdf.multi_cell(140, 5.5,
        "Every Winnow recruiter feature organized by tier, with step-by-step "
        "workflows for the complete recruiting lifecycle: uploading and migrating "
        "resumes, managing job matches, selecting top candidates, building and "
        "sending client submittal packages, and candidate follow-up. Includes a "
        "visual workflow diagram and tier comparison matrix."
    )
    pdf.set_y(y0 + 52)

    # ===== TABLE OF CONTENTS ==============================================
    pdf.add_page()
    pdf.section_title("Table of Contents")
    pdf.ln(2)
    toc = [
        ("1", "Getting Started", "Account setup, onboarding, and trial overview"),
        ("2", "Tier Comparison", "Feature matrix across Trial, Solo, Team, and Agency"),
        ("3", "Workflow Lifecycle Diagram", "Visual map from resume upload to placement"),
        ("4", "Uploading & Importing Resumes", "Bulk upload, Chrome extension, and migration"),
        ("5", "Managing Jobs & Matches", "Creating jobs, matching candidates, Smart Job Parsing"),
        ("6", "Pipeline Management", "CRM pipeline, stages, tags, automation rules"),
        ("7", "Intelligence & Briefs", "AI briefs, salary intelligence, market position"),
        ("8", "Client Submittal Packages", "Build, review, and send PDF packages to clients"),
        ("9", "Client Management", "CRM clients, contacts, hierarchy, contracts"),
        ("10", "Outreach Sequences", "Automated email campaigns for candidate engagement"),
        ("11", "Career Pages", "Branded job portals with Sieve AI application flow"),
        ("12", "Analytics & Reporting", "Funnel, time-to-hire, conversions, source effectiveness"),
        ("13", "Team Collaboration", "Seats, @mentions, notifications, activity logging"),
        ("14", "Candidate Export", "CSV and XLSX export of sourced candidates"),
        ("15", "Chrome Extension", "LinkedIn sourcing directly into Winnow"),
        ("16", "Sieve AI Concierge", "Your AI assistant for platform questions and strategy"),
        ("17", "Settings & Billing", "Plan management, team settings, account controls"),
        ("18", "Troubleshooting & FAQ", "Common issues and answers"),
    ]
    for num, title, desc in toc:
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(*NAVY)
        pdf.cell(10, 7, num + ".")
        pdf.cell(65, 7, title)
        pdf.set_font("Helvetica", "", 10)
        pdf.set_text_color(*GRAY)
        pdf.cell(0, 7, desc, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(5)

    # ===== SECTION 1: GETTING STARTED =====================================
    pdf.add_page()
    pdf.section_title("1.  Getting Started")

    pdf.sub_heading("Create Your Recruiter Account")
    pdf.step(1, "Go to winnowcc.ai and click Sign Up.")
    pdf.step(2, "Choose 'Recruiter' as your role during registration.")
    pdf.step(3, "Complete the onboarding form: company name, specializations, "
                "and preferences.")
    pdf.step(4, "Your 14-day free trial begins automatically with full "
                "access to all features.")

    pdf.tip_box(
        "TIP: Trial Access",
        "Your 14-day trial gives you Agency-level access (999 limits on "
        "most features). Use this time to import your data, test matching, "
        "and explore every feature before choosing a paid plan."
    )

    pdf.sub_heading("Your Dashboard")
    pdf.body(
        "After onboarding, you land on the Recruiter Dashboard. This shows "
        "your pipeline summary, recent activity, daily action queue, and "
        "quick-action buttons. The left sidebar gives you access to every "
        "feature: Jobs, Clients, Candidates, Pipeline, Intelligence, "
        "Sequences, Migration, Career Pages, Analytics, and Settings."
    )

    pdf.sub_heading("Daily Action Queue")
    pdf.body(
        "Winnow automatically generates a prioritized to-do list on your "
        "dashboard:"
    )
    pdf.bullet("Follow-up reminders for stale pipeline candidates (7+ days inactive)")
    pdf.bullet("Draft jobs awaiting publication")
    pdf.bullet("Idle clients needing attention (14+ days no activity)")
    pdf.body("Actions can be dismissed or snoozed (minimum 4 hours).")

    # ===== SECTION 2: TIER COMPARISON =====================================
    pdf.add_page()
    pdf.section_title("2.  Tier Comparison")

    pdf.body(
        "Winnow offers four recruiter tiers. Each tier is designed for a "
        "different stage of your recruiting business."
    )

    pdf.sub_heading("Pricing")
    pdf.table(
        ["Feature", "Trial (14 days)", "Solo $39/mo", "Team $89/user", "Agency $129/user"],
        [
            ["Seats", "1", "1", "Up to 10", "Unlimited"],
            ["Active Job Orders", "999", "10", "50", "999"],
            ["Pipeline Candidates", "999", "100", "500", "999"],
            ["Clients", "999", "5", "25", "999"],
            ["CRM Level", "Full", "Basic", "Full", "Full"],
        ],
        col_widths=[35, 38, 38, 40, 39],
    )

    pdf.sub_heading("Intelligence & Automation")
    pdf.table(
        ["Feature", "Trial", "Solo", "Team", "Agency"],
        [
            ["AI Candidate Briefs/mo", "999", "20", "100", "500"],
            ["Salary Lookups/mo", "999", "5", "50", "999"],
            ["Smart Job Parsing/mo", "10", "0", "10", "999"],
            ["Sieve Messages/day", "30", "30", "75", "150"],
            ["Outreach Sequences", "No", "No", "Yes (3)", "Yes (10)"],
            ["Enrollments/mo", "0", "0", "50", "200"],
            ["Intro Requests/mo", "999", "20", "75", "999"],
        ],
        col_widths=[45, 36, 36, 36, 37],
    )

    pdf.sub_heading("Import & Migration")
    pdf.table(
        ["Feature", "Trial", "Solo", "Team", "Agency"],
        [
            ["Resume Imports/mo", "50", "25", "200", "999"],
            ["Import Batch Size", "10", "10", "25", "50"],
            ["Migration Toolkit", "Full", "Full", "Full", "Full"],
            ["Bulk Resume Archive", "Yes", "Yes", "Yes", "Yes"],
        ],
        col_widths=[45, 36, 36, 36, 37],
    )

    pdf.sub_heading("Advanced Features")
    pdf.table(
        ["Feature", "Trial", "Solo", "Team", "Agency"],
        [
            ["Client Hierarchy", "Yes", "No", "Yes", "Yes"],
            ["Contract Vehicles", "Yes", "No", "Yes", "Yes"],
            ["Cross-Vendor Dupe Check", "Yes", "No", "Yes", "Yes"],
            ["Submission Analytics", "Yes", "No", "Yes", "Yes"],
            ["Career Pages", "1", "1", "5", "999"],
            ["Custom Domain", "No", "No", "Yes", "Yes"],
            ["Per-Client Branding", "No", "No", "Yes", "Yes"],
            ["White-Label Sieve", "No", "No", "No", "Yes"],
            ["Activity History", "All", "7 days", "All", "All"],
        ],
        col_widths=[45, 36, 36, 36, 37],
    )

    pdf.warn_box(
        "SOLO PLAN NOTE",
        "Solo uses a Basic CRM (7-day activity history, no client hierarchy "
        "or contract vehicles). If you need full CRM features, consider Team. "
        "Smart Job Parsing is not available on Solo."
    )

    # ===== SECTION 3: WORKFLOW LIFECYCLE DIAGRAM ==========================
    pdf.add_page()
    pdf.section_title("3.  Workflow Lifecycle Diagram")

    pdf.body(
        "This diagram shows the complete recruiting lifecycle on Winnow, "
        "from getting candidates into the system through placement and "
        "follow-up."
    )

    # --- Row 1: Sources ---
    y_start = pdf.get_y() + 5
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*ACCENT)
    pdf.set_xy(10, y_start - 5)
    pdf.cell(190, 5, "PHASE 1: SOURCE CANDIDATES", align="C",
             new_x="LMARGIN", new_y="NEXT")

    boxes_r1 = [
        (15, y_start + 2, "Upload\nResumes"),
        (55, y_start + 2, "Chrome Ext.\n(LinkedIn)"),
        (95, y_start + 2, "CRM\nMigration"),
        (135, y_start + 2, "Winnow\nIntroductions"),
    ]
    for (bx, by, bt) in boxes_r1:
        pdf.flow_box(bt, bx, by, w=32, h=14)

    # Arrows down from row 1 to row 2 center
    y_r2 = y_start + 26
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*ACCENT)
    pdf.set_xy(10, y_r2 - 5)
    pdf.cell(190, 5, "PHASE 2: MATCH & EVALUATE", align="C",
             new_x="LMARGIN", new_y="NEXT")

    for (bx, by, _) in boxes_r1:
        cx = bx + 16
        pdf.set_draw_color(*ACCENT)
        pdf.set_line_width(0.4)
        pdf.line(cx, by + 14, cx, y_r2 + 2)

    boxes_r2 = [
        (15, y_r2 + 2, "Candidate\nDatabase"),
        (55, y_r2 + 2, "Job Order\nMatching"),
        (95, y_r2 + 2, "IPS Score\n& Ranking"),
        (135, y_r2 + 2, "AI Candidate\nBriefs"),
    ]
    for (bx, by, bt) in boxes_r2:
        pdf.flow_box(bt, bx, by, w=32, h=14)

    # Horizontal arrows in row 2
    for i in range(len(boxes_r2) - 1):
        x1 = boxes_r2[i][0] + 32
        x2 = boxes_r2[i + 1][0]
        cy = boxes_r2[i][1] + 7
        pdf.set_draw_color(*ACCENT)
        pdf.set_line_width(0.4)
        pdf.line(x1, cy, x2, cy)
        pdf.set_fill_color(*ACCENT)
        pdf.polygon(
            [(x2, cy), (x2 - 2, cy - 1.2), (x2 - 2, cy + 1.2)],
            style="F",
        )

    # --- Row 3: Pipeline ---
    y_r3 = y_r2 + 26
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*ACCENT)
    pdf.set_xy(10, y_r3 - 5)
    pdf.cell(190, 5, "PHASE 3: PIPELINE & SELECTION", align="C",
             new_x="LMARGIN", new_y="NEXT")

    # Arrow from row 2 to row 3
    pdf.set_draw_color(*ACCENT)
    pdf.set_line_width(0.4)
    pdf.line(100, y_r2 + 16, 100, y_r3 + 2)

    stages = [
        (10, y_r3 + 2, "Sourced"),
        (40, y_r3 + 2, "Screening"),
        (70, y_r3 + 2, "Submitted"),
        (100, y_r3 + 2, "Interview"),
        (130, y_r3 + 2, "Offer"),
        (160, y_r3 + 2, "Placed"),
    ]
    for (bx, by, bt) in stages:
        pdf.flow_box(bt, bx, by, w=26, h=12)

    # Horizontal arrows between stages
    for i in range(len(stages) - 1):
        x1 = stages[i][0] + 26
        x2 = stages[i + 1][0]
        cy = stages[i][1] + 6
        pdf.set_draw_color(*ACCENT)
        pdf.set_line_width(0.4)
        pdf.line(x1, cy, x2, cy)
        pdf.set_fill_color(*ACCENT)
        pdf.polygon(
            [(x2, cy), (x2 - 2, cy - 1.2), (x2 - 2, cy + 1.2)],
            style="F",
        )

    # --- Row 4: Client Communication ---
    y_r4 = y_r3 + 24
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(*ACCENT)
    pdf.set_xy(10, y_r4 - 5)
    pdf.cell(190, 5, "PHASE 4: CLIENT PRESENTATION & FOLLOW-UP",
             align="C", new_x="LMARGIN", new_y="NEXT")

    # Arrow from "Submitted" down to row 4
    pdf.set_draw_color(*ACCENT)
    pdf.set_line_width(0.4)
    pdf.line(83, y_r3 + 14, 83, y_r4 + 2)

    boxes_r4 = [
        (10, y_r4 + 2, "Submittal\nBrief"),
        (48, y_r4 + 2, "Build PDF\nPackage"),
        (86, y_r4 + 2, "Send to\nClient"),
        (124, y_r4 + 2, "Client\nFeedback"),
        (162, y_r4 + 2, "Candidate\nFollow-up"),
    ]
    for (bx, by, bt) in boxes_r4:
        pdf.flow_box(bt, bx, by, w=32, h=14)

    for i in range(len(boxes_r4) - 1):
        x1 = boxes_r4[i][0] + 32
        x2 = boxes_r4[i + 1][0]
        cy = boxes_r4[i][1] + 7
        pdf.set_draw_color(*ACCENT)
        pdf.set_line_width(0.4)
        pdf.line(x1, cy, x2, cy)
        pdf.set_fill_color(*ACCENT)
        pdf.polygon(
            [(x2, cy), (x2 - 2, cy - 1.2), (x2 - 2, cy + 1.2)],
            style="F",
        )

    pdf.set_y(y_r4 + 22)
    pdf.ln(5)

    # Legend
    pdf.sub_sub_heading("Lifecycle Summary")
    pdf.body(
        "1. SOURCE: Get candidates into Winnow via resume upload, Chrome "
        "extension (LinkedIn), CRM migration (Bullhorn, Recruit CRM, "
        "CATSOne, Zoho), or Winnow introductions.\n"
        "2. MATCH: Create job orders, run AI matching to score candidates "
        "with IPS (Interview Probability Score), generate AI briefs.\n"
        "3. PIPELINE: Move top candidates through stages (Sourced > "
        "Screening > Submitted > Interview > Offer > Placed). Use tags, "
        "automation rules, and team @mentions.\n"
        "4. PRESENT: Build a submittal brief, assemble a PDF package of "
        "top candidates, email it to your client, gather feedback, and "
        "follow up with candidates on next steps."
    )

    # ===== SECTION 4: UPLOADING & IMPORTING RESUMES ======================
    pdf.add_page()
    pdf.section_title("4.  Uploading & Importing Resumes")

    pdf.sub_heading("Bulk Resume Upload")
    pdf.body(
        "Upload multiple candidate resumes at once to build your database quickly."
    )
    pdf.step(1, "Go to Candidates in the left sidebar.")
    pdf.step(2, "Click 'Upload Resumes' and select up to your batch limit "
                "(Solo: 10, Team: 25, Agency: 50 files per batch).")
    pdf.step(3, "Winnow parses each resume automatically, extracting name, "
                "contact info, skills, experience, and education.")
    pdf.step(4, "Parsed candidates appear in your Candidates list with "
                "full profiles ready for matching.")

    pdf.tip_box(
        "TIP: Auto-Populate Pipeline",
        "Enable 'Auto-populate pipeline' in Settings to automatically add "
        "newly sourced candidates to your pipeline. This saves you from "
        "manually adding each candidate after upload."
    )

    pdf.sub_heading("CRM Migration Toolkit")
    pdf.body(
        "Winnow supports full data migration from major recruiting platforms:"
    )
    pdf.table(
        ["Platform", "Import Method", "Entities Imported"],
        [
            ["Bullhorn", "Full CRM export", "Candidates, Jobs, Companies, Contacts"],
            ["Recruit CRM", "CSV + Attachments ZIP", "Candidates, Jobs, Companies, Contacts, Assignments"],
            ["CATSOne", "Full CRM export", "Candidates, Jobs, Companies, Contacts"],
            ["Zoho Recruit", "Full CRM export", "Candidates, Jobs, Companies, Contacts"],
            ["Generic CSV", "Flexible column mapping", "Candidates (custom fields)"],
            ["Resume Archive", "ZIP of resumes", "Candidate profiles (Agency tier)"],
        ],
        col_widths=[35, 55, 100],
    )

    pdf.sub_sub_heading("Migration Steps")
    pdf.step(1, "Go to Migration in the left sidebar.")
    pdf.step(2, "Upload your export file (ZIP or CSV). Winnow auto-detects "
                "the platform.")
    pdf.step(3, "Review the preview showing entity counts and field mappings.")
    pdf.step(4, "Click Start Import. CRM data imports in seconds.")
    pdf.step(5, "For resume attachments (Phase 2), upload the attachments "
                "ZIP separately after Phase 1 completes.")
    pdf.step(6, "Verify your data: check Clients, Jobs, and Pipeline counts.")

    pdf.warn_box(
        "IMPORTANT: Phase Order",
        "Always import CRM data (Phase 1) before resume attachments "
        "(Phase 2). The attachments import matches resumes to candidates "
        "by slug from the CRM import. Rollback is available if anything "
        "looks wrong."
    )

    pdf.sub_heading("Chrome Extension (LinkedIn Sourcing)")
    pdf.body(
        "The Winnow Chrome Extension lets you source candidates directly "
        "from LinkedIn profiles:"
    )
    pdf.step(1, "Install the Winnow Chrome Extension from the Chrome Web Store.")
    pdf.step(2, "Navigate to any LinkedIn profile.")
    pdf.step(3, "Click the Winnow icon to capture the candidate's profile data.")
    pdf.step(4, "The candidate is added to your Candidates database "
                "automatically. Available on all tiers.")

    # ===== SECTION 5: MANAGING JOBS & MATCHES =============================
    pdf.add_page()
    pdf.section_title("5.  Managing Jobs & Matches")

    pdf.sub_heading("Creating Job Orders")
    pdf.step(1, "Go to Jobs in the left sidebar and click 'New Job'.")
    pdf.step(2, "Fill in: title, description, requirements, nice-to-haves, "
                "location, remote policy, salary range, employment type.")
    pdf.step(3, "Link the job to a client (optional but recommended for "
                "submittal tracking).")
    pdf.step(4, "Set priority (low/normal/high/urgent) and positions to fill.")
    pdf.step(5, "Save as Draft or Publish immediately. Published jobs are "
                "visible to Pro candidates on the Winnow marketplace.")

    pdf.tip_box(
        "TIP: Smart Job Parsing",
        "Have a job description PDF or DOCX? Use Smart Job Parsing "
        "(Team/Agency) to upload the document and auto-fill all job fields. "
        "Team: 10 parses/month. Agency: unlimited."
    )

    pdf.sub_heading("Matching Candidates to Jobs")
    pdf.body(
        "Once a job is published, Winnow's AI matching engine scores every "
        "eligible candidate against the job requirements."
    )
    pdf.step(1, "Open a job and click 'Refresh Matches'.")
    pdf.step(2, "Winnow computes an IPS (Interview Probability Score) for "
                "each candidate. A progress bar shows real-time scoring.")
    pdf.step(3, "Matched candidates are listed with their score (0-100%), "
                "matched skills, and missing skills.")
    pdf.step(4, "Click 'Add to Pipeline' on any candidate to move them "
                "into your recruiting pipeline for that job.")

    pdf.sub_heading("Marketplace Jobs")
    pdf.body(
        "Browse jobs ingested from external sources (Remotive, The Muse, etc.) "
        "on the Marketplace. Match your candidates against these jobs to "
        "find new placement opportunities. Use 'Refresh Candidates' to "
        "re-score matches in real time."
    )

    # ===== SECTION 6: PIPELINE MANAGEMENT =================================
    pdf.add_page()
    pdf.section_title("6.  Pipeline Management")

    pdf.sub_heading("Pipeline Stages")
    pdf.body(
        "Your CRM pipeline uses six stages to track candidate progress:"
    )
    pdf.table(
        ["Stage", "Description", "Typical Actions"],
        [
            ["Sourced", "Candidate identified, not yet contacted", "Review profile, add tags"],
            ["Screening", "Initial outreach or phone screen", "Schedule call, add notes"],
            ["Submitted", "Candidate presented to client", "Generate submittal brief"],
            ["Interview", "Client is interviewing candidate", "Prep candidate, track feedback"],
            ["Offer", "Offer extended to candidate", "Negotiate terms, confirm acceptance"],
            ["Placed", "Candidate accepted and started", "Close the placement, celebrate!"],
        ],
        col_widths=[28, 75, 87],
    )

    pdf.sub_heading("Pipeline Operations")
    pdf.bullet("Drag-and-drop candidates between stages on the kanban board")
    pdf.bullet("Bulk operations: select multiple candidates to batch-delete "
               "or batch-update stage (up to 100 at a time)")
    pdf.bullet("Filter by stage, rating (1-5 stars), tags, source, or "
               "job order")
    pdf.bullet("Sort by name, score, date added, or last activity")

    pdf.sub_heading("Tags & Hotlists")
    pdf.body(
        "Organize candidates with custom tags like 'hot lead', "
        "'Java senior', or 'client-A shortlist'. Tags autocomplete "
        "from your history. Filter the pipeline by tags to create "
        "instant hotlists for specific searches."
    )

    pdf.sub_heading("Automated Stage Rules")
    pdf.body(
        "Set rules to auto-advance candidates between stages based on "
        "conditions:"
    )
    pdf.bullet("Match score above a threshold (e.g., score > 80 = auto-qualify)")
    pdf.bullet("Rating above a value (e.g., 4+ stars = fast-track)")
    pdf.bullet("Days in a stage (e.g., 5+ days in Sourced = auto-advance)")
    pdf.bullet("Specific tag present (e.g., tag 'pre-screened' = skip Screening)")
    pdf.body(
        "Rules can apply to all jobs or a specific job order. Run them "
        "manually or let them trigger automatically."
    )

    pdf.sub_heading("Pipeline Notes & @Mentions")
    pdf.body(
        "Add timestamped notes on any pipeline candidate. Use @mentions to "
        "tag teammates -- mentioned team members receive a notification. "
        "Available on Team and Agency plans."
    )

    # ===== SECTION 7: INTELLIGENCE & BRIEFS ===============================
    pdf.add_page()
    pdf.section_title("7.  Intelligence & Briefs")

    pdf.sub_heading("AI Candidate Briefs")
    pdf.body(
        "Winnow's Intelligence page offers three types of AI-generated "
        "candidate analysis:"
    )

    pdf.sub_sub_heading("General Brief")
    pdf.body(
        "A comprehensive candidate assessment: strengths, experience "
        "summary, and potential fit areas. Great for initial screening."
    )

    pdf.sub_sub_heading("Job-Specific Brief")
    pdf.body(
        "Detailed match analysis against a specific job order: skill "
        "alignment, gaps, fit score, and recommendation."
    )

    pdf.sub_sub_heading("Client Submittal Brief")
    pdf.body(
        "A professional, client-ready document including: candidate "
        "summary, relevant experience highlights, skill match to job "
        "requirements, salary expectations, availability, and your "
        "recruiter recommendation. This is the foundation of your "
        "submittal package."
    )

    pdf.sub_heading("How to Generate a Brief")
    pdf.step(1, "Go to Intelligence in the left sidebar.")
    pdf.step(2, "Select a candidate from the dropdown (searchable by "
                "name, title, or skill).")
    pdf.step(3, "Choose the brief type: General, Job Specific, or "
                "Client Submittal.")
    pdf.step(4, "For Job Specific or Submittal: select the target job order.")
    pdf.step(5, "Click 'Generate Brief' -- takes 10-20 seconds.")

    pdf.tip_box(
        "TIP: Brief Limits",
        "Trial: 999/mo | Solo: 20/mo | Team: 100/mo | Agency: 500/mo. "
        "Use Client Submittal briefs for your top candidates to maximize value."
    )

    pdf.sub_heading("Salary Intelligence")
    pdf.body(
        "Enter a role title and optional location to get salary percentiles "
        "(P10 through P90). Use this to validate compensation ranges, "
        "negotiate offers, or advise clients on market rates."
    )

    pdf.sub_heading("Market Position & Career Trajectory")
    pdf.body(
        "See how a candidate ranks against other matches for a specific "
        "job. Career Trajectory predicts likely next career moves based "
        "on their experience pattern."
    )

    # ===== SECTION 8: CLIENT SUBMITTAL PACKAGES ===========================
    pdf.add_page()
    pdf.section_title("8.  Client Submittal Packages")

    pdf.body(
        "Winnow's submittal package feature lets you build professional "
        "PDF presentations of your top candidates and email them directly "
        "to clients -- all without leaving the platform."
    )

    pdf.sub_heading("Building a Submittal Package")
    pdf.step(1, "Open a job order and go to its Matched Candidates tab.")
    pdf.step(2, "Select the candidates you want to present to your client "
                "(check the boxes next to their names).")
    pdf.step(3, "Click 'Build Submittal Package'.")
    pdf.step(4, "Choose the target client and recipient (name + email).")
    pdf.step(5, "Optionally customize the cover email subject and body.")
    pdf.step(6, "Click 'Build Package'. Winnow generates AI submittal "
                "briefs for each candidate and merges everything into a "
                "single, branded PDF.")
    pdf.step(7, "The package status shows 'building' while the AI works "
                "(typically 1-2 minutes for 3-5 candidates).")

    pdf.sub_heading("Reviewing the Package")
    pdf.body(
        "Once the package is ready (status: 'ready'), you can:"
    )
    pdf.bullet("Preview the merged PDF directly in your browser")
    pdf.bullet("Download the PDF for offline review or editing")
    pdf.bullet("Check individual candidate briefs within the package")

    pdf.sub_heading("Sending to Your Client")
    pdf.step(1, "Click 'Send to Client' on a ready package.")
    pdf.step(2, "Winnow emails the PDF to the recipient with your "
                "customized cover email.")
    pdf.step(3, "The package status updates to 'sent' with a timestamp.")
    pdf.step(4, "Follow up with your client based on their feedback.")

    pdf.tip_box(
        "TIP: Submittal Workflow",
        "The ideal flow: Match candidates to a job > generate AI briefs > "
        "build a submittal package > send to client > track feedback in "
        "pipeline notes > advance candidates to Interview stage."
    )

    pdf.sub_heading("After Sending: Client Communication & Follow-up")
    pdf.body(
        "After sending a submittal package:"
    )
    pdf.bullet("Track client responses using pipeline notes on each "
               "candidate (add notes about client feedback).")
    pdf.bullet("Advance accepted candidates from 'Submitted' to "
               "'Interview' stage.")
    pdf.bullet("Move rejected candidates back to 'Sourced' or archive "
               "them for future opportunities.")
    pdf.bullet("Use the Activity Log to record all client communications "
               "(calls, emails, meetings).")
    pdf.bullet("If the client requests more candidates, build a new "
               "submittal package with additional selections.")

    pdf.warn_box(
        "DUPLICATE SUBMISSION WARNING",
        "Before submitting a candidate, Winnow checks if they were already "
        "submitted by another recruiter. You'll see who submitted first "
        "and when. You can still proceed, but with full visibility to "
        "protect first-submitter rights."
    )

    # ===== SECTION 9: CLIENT MANAGEMENT ===================================
    pdf.add_page()
    pdf.section_title("9.  Client Management")

    pdf.sub_heading("Managing Clients")
    pdf.step(1, "Go to Clients in the left sidebar.")
    pdf.step(2, "Click 'New Client' to add a company. Fill in: company name, "
                "industry, size, website, and status (active/inactive/prospect).")
    pdf.step(3, "Add contacts under each client: first name, last name, "
                "email, phone, and role.")
    pdf.step(4, "Link clients to job orders for submittal tracking.")

    pdf.sub_heading("Advanced Client Features (Team & Agency)")
    pdf.bullet("Client Hierarchy: set parent-child relationships between "
               "clients (e.g., a staffing agency's sub-clients).")
    pdf.bullet("Contract Vehicle Management: track contract types "
               "(contingency, retained, RPO, contract staffing) with "
               "fee percentages and flat fees.")
    pdf.bullet("Contract dates and renewal tracking.")

    pdf.sub_heading("Client Job Summary")
    pdf.body(
        "View a summary of all job orders for a client (including child "
        "clients in hierarchies). See active, paused, closed, and filled "
        "positions at a glance."
    )

    # ===== SECTION 10: OUTREACH SEQUENCES =================================
    pdf.add_page()
    pdf.section_title("10.  Outreach Sequences")

    pdf.body(
        "Automated multi-step email campaigns to engage candidates at "
        "scale. Available on Team and Agency plans."
    )

    pdf.sub_heading("Creating a Sequence")
    pdf.step(1, "Go to Sequences in the left sidebar.")
    pdf.step(2, "Click 'New Sequence' and name it (e.g., 'Initial Outreach', "
                "'Follow-up Cadence').")
    pdf.step(3, "Add steps: write email template + set wait duration between "
                "steps (max 10 steps per sequence).")
    pdf.step(4, "Use merge fields for personalization: {{candidate_name}}, "
                "{{job_title}}, {{job_location}}, {{recruiter_name}}, "
                "{{recruiter_company}}.")
    pdf.step(5, "Save and activate the sequence.")

    pdf.sub_heading("Enrolling Candidates")
    pdf.step(1, "From any pipeline candidate, click 'Enroll in Sequence'.")
    pdf.step(2, "Select an active sequence.")
    pdf.step(3, "Emails are sent automatically on schedule (processed "
                "every 15 minutes).")
    pdf.step(4, "Track enrollment status: active, completed, paused, "
                "unenrolled, bounced.")

    pdf.tip_box(
        "TIP: Best Practices",
        "Keep sequences to 3-5 steps. Wait 2-3 days between emails for a "
        "natural cadence. Personalize the first email; follow-ups can be "
        "shorter. Unenroll candidates who respond. Sequences auto-advance "
        "candidates from 'sourced' to 'contacted' on first email send."
    )

    pdf.table(
        ["Tier", "Active Sequences", "Enrollments/Month"],
        [
            ["Solo", "Not available", "Not available"],
            ["Team", "3", "50"],
            ["Agency", "10", "200"],
        ],
        col_widths=[50, 70, 70],
    )

    # ===== SECTION 11: CAREER PAGES =======================================
    pdf.add_page()
    pdf.section_title("11.  Career Pages")

    pdf.body(
        "Branded job portals hosted on Winnow with an AI-powered "
        "application experience via Sieve."
    )

    pdf.sub_heading("Setting Up a Career Page")
    pdf.step(1, "Go to Career Pages in the left sidebar and click "
                "'Create Career Page'.")
    pdf.step(2, "Enter a name (auto-generates a URL slug at "
                "winnowcc.ai/careers/your-slug).")
    pdf.step(3, "Use the visual builder to customize branding: colors, "
                "logo, fonts, hero style, job display layout.")
    pdf.step(4, "Enable Sieve AI and customize her welcome message and "
                "tone (professional/casual/enthusiastic).")
    pdf.step(5, "Publish to go live. Share the URL or embed on your website.")

    pdf.sub_heading("Sieve-Guided Application Flow")
    pdf.body(
        "When candidates visit your career page:"
    )
    pdf.bullet("Sieve greets them with your custom welcome message.")
    pdf.bullet("Candidate uploads their resume -- Sieve parses it instantly.")
    pdf.bullet("Sieve asks follow-up questions conversationally to fill "
               "missing profile fields.")
    pdf.bullet("A completeness score tracks progress (submit at 70%+).")
    pdf.bullet("Sieve shows cross-job recommendations before submitting.")
    pdf.bullet("On submission, IPS is calculated and the application enters "
               "your pipeline.")

    pdf.sub_heading("Custom Screening Questions")
    pdf.body(
        "Add custom questions to any job (text, select, boolean, number, "
        "date). Sieve asks these naturally during conversation -- not as "
        "a rigid form. Candidate answers are extracted with confidence scoring."
    )

    pdf.sub_heading("Embeddable Widget")
    pdf.body(
        "Generate a JavaScript snippet to embed your career page on any "
        "external website. Manage API keys with CORS whitelist and rate "
        "limiting."
    )

    pdf.sub_heading("Custom Domains (Team & Agency)")
    pdf.body(
        "Connect your own domain (e.g., careers.youragency.com). Winnow "
        "provides a CNAME target -- add it in your DNS provider. SSL is "
        "provisioned automatically after verification."
    )

    pdf.table(
        ["Tier", "Career Pages", "Custom Domain", "Per-Client Branding"],
        [
            ["Trial", "1", "No", "No"],
            ["Solo", "1", "No", "No"],
            ["Team", "5", "Yes", "Yes"],
            ["Agency", "Unlimited", "Yes", "Yes"],
        ],
        col_widths=[40, 50, 50, 50],
    )

    # ===== SECTION 12: ANALYTICS & REPORTING ==============================
    pdf.add_page()
    pdf.section_title("12.  Analytics & Reporting")

    pdf.body(
        "Data-driven insights into your recruiting performance, "
        "available at Analytics in the left sidebar."
    )

    pdf.sub_heading("Pipeline Funnel")
    pdf.body(
        "See candidate counts at each pipeline stage. Identify where "
        "candidates accumulate or drop off."
    )

    pdf.sub_heading("Time-to-Hire")
    pdf.body(
        "Average, median, and 75th-percentile days from pipeline entry "
        "to placement. Track hiring speed trends."
    )

    pdf.sub_heading("Conversion Rates")
    pdf.body(
        "Stage-to-stage conversion percentages. Find your bottleneck: "
        "if Screening-to-Submitted is low, improve your submittal "
        "selection. If Interview-to-Offer is low, prep candidates better."
    )

    pdf.sub_heading("Source Effectiveness")
    pdf.body(
        "Which sourcing channels produce the most hires? Compare LinkedIn, "
        "referral, job board, migration, and other sources."
    )

    # ===== SECTION 13: TEAM COLLABORATION =================================
    pdf.add_page()
    pdf.section_title("13.  Team Collaboration")

    pdf.sub_heading("Team Management")
    pdf.body(
        "Invite recruiters to your team from Settings. Manage roles "
        "(admin, recruiter, viewer)."
    )
    pdf.table(
        ["Tier", "Seats"],
        [
            ["Solo", "1 (just you)"],
            ["Team", "Up to 10"],
            ["Agency", "Unlimited"],
        ],
        col_widths=[50, 140],
    )

    pdf.sub_heading("@Mentions & Notifications")
    pdf.body(
        "Add notes on pipeline candidates with @mentions to tag teammates. "
        "Mentioned team members receive notifications in their inbox. "
        "Use the notification bell to see unread mentions and team activity."
    )

    pdf.sub_heading("Activity Logging")
    pdf.body(
        "Log calls, emails, and meetings on any pipeline candidate. "
        "All recruiter touchpoints are tracked in a chronological feed."
    )
    pdf.warn_box(
        "SOLO PLAN NOTE",
        "Solo plan shows only 7 days of activity history. Team and Agency "
        "plans have unlimited activity history."
    )

    # ===== SECTION 14: CANDIDATE EXPORT ===================================
    pdf.section_title("14.  Candidate Export")

    pdf.body(
        "Export your sourced candidates to CSV or formatted XLSX from "
        "the Candidates page. Exports include: name, email, phone, "
        "LinkedIn, current company, current title, location, skills, "
        "source, created date, and match score."
    )

    # ===== SECTION 15: CHROME EXTENSION ===================================
    pdf.section_title("15.  Chrome Extension")

    pdf.body(
        "Source candidates directly from LinkedIn profiles into your "
        "Winnow candidate database. Available on all tiers."
    )
    pdf.step(1, "Install from the Chrome Web Store.")
    pdf.step(2, "Navigate to a LinkedIn profile.")
    pdf.step(3, "Click the Winnow icon to capture profile data.")
    pdf.step(4, "Candidate appears in your Candidates list automatically.")

    # ===== SECTION 16: SIEVE AI CONCIERGE =================================
    pdf.add_page()
    pdf.section_title("16.  Sieve AI Concierge")

    pdf.body(
        "Sieve is your AI assistant built into Winnow. She knows every "
        "recruiter feature, your current pipeline state, and can help "
        "with strategy, workflows, and platform questions."
    )

    pdf.sub_heading("What Sieve Can Help With")
    pdf.bullet("Platform navigation: 'How do I create a job order?'")
    pdf.bullet("Strategy: 'How should I improve my placement rate?'")
    pdf.bullet("Troubleshooting: 'Why aren't candidates showing match scores?'")
    pdf.bullet("Workflow guidance: 'Walk me through building a submittal package.'")
    pdf.bullet("Tier questions: 'What does Team unlock vs Solo?'")
    pdf.bullet("Migration help: 'How do I import from Recruit CRM?'")

    pdf.sub_heading("Sieve Message Limits")
    pdf.table(
        ["Tier", "Messages per Day"],
        [
            ["Trial", "30"],
            ["Solo", "30"],
            ["Team", "75"],
            ["Agency", "150"],
        ],
        col_widths=[70, 120],
    )

    pdf.tip_box(
        "TIP: Ask Sieve Anything",
        "Sieve is context-aware -- she knows your pipeline counts, job "
        "statuses, usage limits, and migration state. Ask specific "
        "questions for the most helpful answers."
    )

    # ===== SECTION 17: SETTINGS & BILLING =================================
    pdf.section_title("17.  Settings & Billing")

    pdf.sub_heading("Plan Management")
    pdf.body(
        "View your current plan, usage, and limits at Settings > Billing. "
        "Upgrade or downgrade at any time. Changes take effect immediately."
    )

    pdf.sub_heading("Key Settings")
    pdf.bullet("Auto-populate pipeline: automatically add sourced "
               "candidates to your pipeline")
    pdf.bullet("Team invitations and seat management")
    pdf.bullet("Notification preferences")
    pdf.bullet("Profile: company name, specializations, contact info")

    # ===== SECTION 18: TROUBLESHOOTING & FAQ ==============================
    pdf.add_page()
    pdf.section_title("18.  Troubleshooting & FAQ")

    pdf.sub_heading("Common Issues")

    pdf.sub_sub_heading("Candidates don't show match scores")
    pdf.body(
        "Most likely cause: missing resumes. Candidates without parsed "
        "resumes can't be scored. Upload resumes via bulk upload or "
        "complete Phase 2 of your CRM migration (attachments import)."
    )

    pdf.sub_sub_heading("Migration import is stuck")
    pdf.body(
        "Go to Migration page and click Cancel on the stuck import. "
        "Then re-upload and try again. If the worker seems stale, "
        "the cancel will reset the job. Contact support if it persists."
    )

    pdf.sub_sub_heading("Sequence emails aren't sending")
    pdf.body(
        "Sequences are processed every 15 minutes. If emails still "
        "aren't sending after 30 minutes, check: (1) the sequence is "
        "active, (2) the enrolled candidate has a valid email, and "
        "(3) the candidate hasn't been unenrolled or bounced."
    )

    pdf.sub_sub_heading("Can't see a feature described in this guide")
    pdf.body(
        "Some features are tier-gated. Check the tier comparison table "
        "in Section 2 to see which plan unlocks the feature you need."
    )

    pdf.sub_heading("FAQ")

    pdf.sub_sub_heading("How long is the free trial?")
    pdf.body("14 days with full access to all features at Agency-level limits.")

    pdf.sub_sub_heading("Can I migrate from multiple CRMs?")
    pdf.body(
        "Yes. Run separate migrations for each platform. Data is merged "
        "into your single Winnow workspace."
    )

    pdf.sub_sub_heading("Do candidates see my job orders?")
    pdf.body(
        "Published recruiter jobs appear on the Winnow marketplace with "
        "a 'Recruiter' badge and are visible to Pro-tier candidates."
    )

    pdf.sub_sub_heading("What happens when my trial ends?")
    pdf.body(
        "Your data is preserved. You'll be prompted to choose a paid "
        "plan. Features above your chosen tier's limits become gated "
        "until you upgrade."
    )

    pdf.sub_sub_heading("How do I get help?")
    pdf.body(
        "Ask Sieve (the AI concierge) anytime from the Sieve AI page. "
        "For issues Sieve can't resolve, email support@winnow.app."
    )

    pdf.sub_sub_heading("Is my candidate data secure?")
    pdf.body(
        "Yes. Winnow uses encrypted connections (TLS), secure "
        "authentication (JWT + HttpOnly cookies), and GDPR-compliant "
        "data handling. Candidate consent is tracked through the "
        "Trust & Verification system."
    )

    return pdf


def main():
    pdf = build_pdf()

    # Determine output path
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_dir = os.path.join(repo_root, "apps", "web", "public", "docs")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "winnow-recruiter-user-guide.pdf")

    pdf.output(out_path)
    print(f"PDF generated: {out_path}")
    print(f"Pages: {pdf.pages_count}")


if __name__ == "__main__":
    main()
