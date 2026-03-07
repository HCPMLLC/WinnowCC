"""Generate a PDF user guide for the Bulk Attach Resumes feature."""

from fpdf import FPDF


class GuidePDF(FPDF):
    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=20)

    def header(self):
        if self.page_no() > 1:
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(128, 128, 128)
            self.cell(0, 10, "Winnow -- Bulk Attach Resumes User Guide", align="C")
            self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")

    def add_title(self, text):
        self.set_font("Helvetica", "B", 24)
        self.set_text_color(30, 58, 95)
        self.cell(0, 15, text, new_x="LMARGIN", new_y="NEXT")
        self.ln(3)

    def add_subtitle(self, text):
        self.set_font("Helvetica", "", 11)
        self.set_text_color(100, 100, 100)
        self.cell(0, 7, text, new_x="LMARGIN", new_y="NEXT")

    def add_h2(self, text):
        self.ln(6)
        self.set_font("Helvetica", "B", 16)
        self.set_text_color(30, 58, 95)
        self.cell(0, 10, text, new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(30, 58, 95)
        self.set_line_width(0.5)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(5)

    def add_h3(self, text):
        self.ln(4)
        self.set_font("Helvetica", "B", 13)
        self.set_text_color(50, 80, 120)
        self.cell(0, 9, text, new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def add_paragraph(self, text):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(40, 40, 40)
        self.multi_cell(0, 5.5, text)
        self.ln(2)

    def add_step(self, number, text):
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(30, 58, 95)
        self.cell(8, 5.5, f"{number}.")
        self.set_font("Helvetica", "", 10)
        self.set_text_color(40, 40, 40)
        self.multi_cell(0, 5.5, text)
        self.ln(1.5)

    def add_bullet(self, text, indent=0):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(40, 40, 40)
        x = self.get_x() + indent
        self.set_x(x)
        self.cell(5, 5.5, "-")
        self.multi_cell(0, 5.5, " " + text)
        self.ln(1)

    def add_example_filename(self, filename, description):
        self.set_font("Courier", "B", 10)
        self.set_text_color(30, 58, 95)
        x = self.get_x()
        self.set_x(x + 5)
        self.cell(65, 6, filename)
        self.set_font("Helvetica", "", 10)
        self.set_text_color(80, 80, 80)
        self.cell(0, 6, description, new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def add_tip(self, text):
        self.set_fill_color(235, 245, 255)
        self.set_draw_color(30, 58, 95)
        self.set_line_width(0.3)
        y = self.get_y()
        self.rect(10, y, 190, 14, style="DF")
        self.set_xy(14, y + 2)
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(30, 58, 95)
        self.cell(10, 5, "TIP: ")
        self.set_font("Helvetica", "", 9)
        self.set_text_color(40, 40, 40)
        self.multi_cell(170, 5, text)
        self.set_y(y + 16)

    def add_warning(self, text):
        self.set_fill_color(255, 245, 235)
        self.set_draw_color(200, 120, 30)
        self.set_line_width(0.3)
        y = self.get_y()
        self.rect(10, y, 190, 14, style="DF")
        self.set_xy(14, y + 2)
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(200, 120, 30)
        self.cell(15, 5, "NOTE: ")
        self.set_font("Helvetica", "", 9)
        self.set_text_color(40, 40, 40)
        self.multi_cell(165, 5, text)
        self.set_y(y + 16)

    def add_table_header(self, cells, widths):
        self.set_font("Helvetica", "B", 9)
        self.set_fill_color(30, 58, 95)
        self.set_text_color(255, 255, 255)
        for i, cell_text in enumerate(cells):
            self.cell(widths[i], 8, cell_text, border=1, fill=True, align="C")
        self.ln()

    def add_table_row(self, cells, widths):
        self.set_font("Helvetica", "", 9)
        self.set_fill_color(250, 250, 250)
        self.set_text_color(40, 40, 40)
        for i, cell_text in enumerate(cells):
            self.cell(widths[i], 7, cell_text, border=1, fill=True)
        self.ln()

    def add_divider(self):
        self.ln(3)
        self.set_draw_color(200, 200, 200)
        self.set_line_width(0.3)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(5)


def main():
    pdf = GuidePDF()
    pdf.alias_nb_pages()

    # =====================================================================
    # PAGE 1: Title page
    # =====================================================================
    pdf.add_page()
    pdf.ln(30)
    pdf.add_title("Bulk Attach Resumes")
    pdf.ln(3)
    pdf.set_font("Helvetica", "", 14)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(0, 8, "User Guide for Recruiters", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(10)

    pdf.add_divider()
    pdf.ln(5)

    pdf.add_subtitle("Product: Winnow (winnowcc.ai)")
    pdf.add_subtitle("Feature: PROMPT80 -- Resume Bulk Attach")
    pdf.add_subtitle("Date: March 2026")
    pdf.add_subtitle("Audience: Recruiters on any subscription tier")

    pdf.ln(15)
    pdf.add_paragraph(
        "This guide explains how to use the Bulk Attach Resumes feature. "
        "If you imported candidates via CSV or CRM migration, those candidates "
        "may not have resumes attached. This feature lets you upload a ZIP file "
        "of resumes that Winnow automatically matches to your existing pipeline "
        "candidates, then parses and attaches them."
    )

    # =====================================================================
    # PAGE 2: What you need before starting
    # =====================================================================
    pdf.add_page()

    pdf.add_h2("What You Need Before Starting")

    pdf.add_paragraph(
        "Before using Bulk Attach, make sure you have the following:"
    )

    pdf.add_step("1", "A Winnow recruiter account (any tier: Trial, Solo, Team, or Agency)")
    pdf.add_step("2", "Pipeline candidates already imported (via CSV import, CRM migration, "
                       "or manual entry)")
    pdf.add_step("3", "A ZIP file containing PDF or DOCX resume files")
    pdf.add_step("4", "Resume files named to match your candidates (see naming rules below)")

    pdf.ln(3)
    pdf.add_warning(
        "You must have pipeline candidates in your account first. "
        "If you have no candidates, import them before using this feature."
    )

    # =====================================================================
    # How to name your resume files
    # =====================================================================
    pdf.add_h2("How to Name Your Resume Files")

    pdf.add_paragraph(
        "Winnow matches resume files to your pipeline candidates based on the "
        "filename. There are three ways a file can be matched. You can mix and "
        "match all three styles in the same ZIP file."
    )

    pdf.add_h3("Option 1: Name by Email Address (Best)")

    pdf.add_paragraph(
        "Name the file exactly as the candidate's email address. This is the "
        "most reliable method because emails are unique."
    )
    pdf.add_example_filename("jane.doe@gmail.com.pdf", "Matches candidate with that email")
    pdf.add_example_filename("bob_smith@acme.co.docx", "Also works with DOCX files")

    pdf.ln(2)
    pdf.add_tip(
        "The email in the filename is matched against the candidate's "
        "email in your pipeline. Make sure it matches exactly."
    )

    pdf.add_h3("Option 2: Name by Candidate ID")

    pdf.add_paragraph(
        "Use the candidate's pipeline ID number as the filename. "
        "You can also prefix it with 'candidate_' or 'id_'."
    )
    pdf.add_example_filename("42.pdf", "Matches pipeline candidate #42")
    pdf.add_example_filename("candidate_42.pdf", "Same -- matches candidate #42")
    pdf.add_example_filename("id_108.docx", "Matches pipeline candidate #108")

    pdf.add_h3("Option 3: Name by Candidate Name")

    pdf.add_paragraph(
        "Use the candidate's full name as the filename, with underscores, "
        "hyphens, or spaces separating first and last name."
    )
    pdf.add_example_filename("John_Smith.pdf", "Matches candidate named John Smith")
    pdf.add_example_filename("Jane-Doe.docx", "Matches candidate named Jane Doe")
    pdf.add_example_filename("Bob Wilson.pdf", "Spaces work too")

    pdf.ln(2)
    pdf.add_warning(
        "Name matching compares against the candidate's full name in "
        "your pipeline. If two candidates share the same name, the match may "
        "be ambiguous. Use email or ID matching for those cases."
    )

    # =====================================================================
    # Confidence levels
    # =====================================================================
    pdf.add_h2("Match Confidence Levels")

    pdf.add_paragraph(
        "Each match is assigned a confidence level so you can review before confirming:"
    )
    pdf.ln(2)

    widths = [50, 50, 90]
    pdf.add_table_header(["Match Method", "Confidence", "When to Use"], widths)
    pdf.add_table_row(["Email", "High", "Best -- unique, reliable matches"], widths)
    pdf.add_table_row(["Candidate ID", "High", "When you know the pipeline ID"], widths)
    pdf.add_table_row(["Name", "Medium", "Convenient but verify if names overlap"], widths)

    pdf.ln(3)
    pdf.add_paragraph(
        "High confidence means the match is very likely correct. Medium "
        "confidence means you should double-check the match in the preview "
        "step before confirming."
    )

    # =====================================================================
    # Step-by-step walkthrough
    # =====================================================================
    pdf.add_page()

    pdf.add_h2("Step-by-Step Walkthrough")

    # Step 1
    pdf.add_h3("Step 1: Open Bulk Attach")

    pdf.add_step("1", 'Log in to Winnow and go to the Recruiter section.')
    pdf.add_step("2", 'Click "Candidates" in the left sidebar to open your candidate list.')
    pdf.add_step("3", 'Click the "Attach Resumes" button near the top-right of the page.')
    pdf.add_step("4", 'You will see the Bulk Attach Resumes page with a file upload area.')

    # Step 2
    pdf.add_h3("Step 2: Upload Your ZIP File")

    pdf.add_step("1", "Drag and drop your ZIP file onto the upload area, or click "
                       '"Select ZIP File" to browse your computer.')
    pdf.add_step("2", "Winnow will upload the ZIP and analyze the files inside.")
    pdf.add_step("3", "Wait for the analysis to complete. This usually takes a few seconds.")

    pdf.ln(2)
    pdf.add_paragraph("Supported file types inside the ZIP:")
    pdf.add_bullet("PDF files (.pdf)")
    pdf.add_bullet("Word documents (.docx)")

    pdf.ln(2)
    pdf.add_paragraph("Limits:")
    pdf.add_bullet("Maximum 500 resume files per ZIP")
    pdf.add_bullet("Maximum 200 MB total ZIP size")
    pdf.add_bullet("Individual files up to 10 MB each")

    # Step 3
    pdf.add_h3("Step 3: Review the Match Preview")

    pdf.add_paragraph(
        "After uploading, Winnow shows you a preview of how each resume file "
        "matched to your pipeline candidates. You will see:"
    )
    pdf.add_bullet("A summary bar showing Total Files, Matched, and Unmatched counts")
    pdf.add_bullet("A list of every file with its match result")
    pdf.add_bullet("For matched files: the candidate name, email, match method, "
                   "and confidence badge")
    pdf.add_bullet("Checkboxes to select or deselect individual matches")

    pdf.ln(2)
    pdf.add_paragraph("What to do in this step:")
    pdf.add_step("1", "Review the matches. All matched files are selected by default.")
    pdf.add_step("2", "Uncheck any matches that look wrong.")
    pdf.add_step("3", 'Use the "Select all" checkbox to quickly select or deselect all '
                       "matched files.")
    pdf.add_step("4", 'Unmatched files (shown grayed out) cannot be selected -- you will '
                       "need to rename them and re-upload if you want to attach them.")

    pdf.ln(2)
    pdf.add_tip(
        "If many files are unmatched, check that the filenames follow "
        "the naming rules described earlier. Rename the files and try again."
    )

    # Step 4
    pdf.add_h3("Step 4: Confirm and Process")

    pdf.add_step("1", 'Click the "Attach X Resumes" button (where X is the number you selected).')
    pdf.add_step("2", "Winnow will begin processing the selected resumes in the background.")
    pdf.add_step("3", "You will see a progress bar showing how many files have been processed.")
    pdf.add_step("4", "You can stay on the page or navigate away -- processing continues "
                       "in the background.")

    pdf.ln(2)
    pdf.add_paragraph("For each resume, Winnow will:")
    pdf.add_bullet("Parse the resume to extract text and structured data")
    pdf.add_bullet("Create a candidate profile linked to the resume")
    pdf.add_bullet("Attach the profile to the matched pipeline candidate")
    pdf.add_bullet("Queue an AI-powered deep parse for richer data extraction")

    # Step 5
    pdf.add_h3("Step 5: Review Results")

    pdf.add_paragraph(
        "When processing is complete, you will see a summary screen showing:"
    )
    pdf.add_bullet("Total files processed")
    pdf.add_bullet("Number successfully attached (in green)")
    pdf.add_bullet("Number that failed (in red), if any")

    pdf.add_step("1", 'Click "Back to Candidates" to return to your candidate list.')
    pdf.add_step("2", "Open any candidate to see their newly attached resume and parsed profile.")

    # =====================================================================
    # Troubleshooting
    # =====================================================================
    pdf.add_page()

    pdf.add_h2("Troubleshooting")

    pdf.add_h3('"No pipeline candidates found"')
    pdf.add_paragraph(
        "You need to import candidates before using Bulk Attach. "
        "Go to Candidates and use CSV Import, CRM Migration, or add candidates "
        "manually first."
    )

    pdf.add_h3('"ZIP contains no PDF or DOCX resume files"')
    pdf.add_paragraph(
        "The ZIP file must contain at least one .pdf or .docx file. "
        "Other file types (images, text files, spreadsheets) are ignored. "
        "Check that your files have the correct extensions."
    )

    pdf.add_h3("Most files show as Unmatched")
    pdf.add_paragraph(
        "This means the filenames do not match any candidate in your pipeline. "
        "Check these common issues:"
    )
    pdf.add_bullet("Email filenames must match exactly (case-insensitive)")
    pdf.add_bullet("Name filenames must match the full name in your pipeline")
    pdf.add_bullet("ID filenames must use the exact pipeline candidate ID number")
    pdf.add_bullet("Files inside folders in the ZIP are supported -- only the "
                   "filename (not the folder path) is used for matching")

    pdf.add_h3("A file failed during processing")
    pdf.add_paragraph(
        "Individual files can fail if the resume text cannot be extracted "
        "(e.g., a scanned image PDF without OCR, or a corrupted file). "
        "The rest of the batch will continue processing. You can re-upload "
        "just the failed files in a new batch."
    )

    pdf.add_h3("Resume import limit reached")
    pdf.add_paragraph(
        "Each recruiter tier has a monthly limit on resume imports. If you "
        "hit your limit, you can upgrade your plan or wait until the next "
        "billing period."
    )

    # =====================================================================
    # FAQ
    # =====================================================================
    pdf.add_h2("Frequently Asked Questions")

    pdf.add_h3("Can I attach resumes to candidates who already have one?")
    pdf.add_paragraph(
        "Yes. If a pipeline candidate already has a resume, Bulk Attach will "
        "update it with the new resume. The old resume is not deleted -- the "
        "profile is updated to reference the new document."
    )

    pdf.add_h3("What happens after the resume is attached?")
    pdf.add_paragraph(
        "Winnow first does a quick text extraction to create a basic profile. "
        "Then it queues an AI-powered deep parse that runs in the background, "
        "extracting skills, experience, education, and more. The deep parse "
        "usually completes within a few minutes."
    )

    pdf.add_h3("Can I undo a bulk attach?")
    pdf.add_paragraph(
        "There is no one-click undo. If you attached the wrong resume to a "
        "candidate, you can open that candidate's profile and upload the "
        "correct resume individually."
    )

    pdf.add_h3("What file formats are supported?")
    pdf.add_paragraph("PDF (.pdf) and Microsoft Word (.docx) files only.")

    pdf.add_h3("Is there a limit on how many files I can attach at once?")
    pdf.add_paragraph(
        "Each ZIP can contain up to 500 resume files and be up to 200 MB in "
        "total size. Individual files can be up to 10 MB each."
    )

    # =====================================================================
    # Quick reference
    # =====================================================================
    pdf.add_page()

    pdf.add_h2("Quick Reference Card")

    pdf.add_paragraph("Keep this page handy for a fast reminder of the process.")

    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(30, 58, 95)
    pdf.cell(0, 8, "The 5-Step Process:", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    steps = [
        ("1", "PREPARE", "Name your resume files by email, ID, or candidate name. "
                         "Put them all in one ZIP file."),
        ("2", "UPLOAD", "Go to Candidates > Attach Resumes. Drag and drop your ZIP "
                        "or click to browse."),
        ("3", "REVIEW", "Check the match preview. Uncheck any incorrect matches. "
                        "Verify medium-confidence name matches."),
        ("4", "CONFIRM", 'Click "Attach Resumes" to start processing. '
                         "A progress bar shows the status."),
        ("5", "VERIFY", "When complete, open candidates to confirm resumes are attached "
                        "and profiles are populated."),
    ]

    for num, title, desc in steps:
        self = pdf
        self.set_fill_color(30, 58, 95)
        self.set_text_color(255, 255, 255)
        self.set_font("Helvetica", "B", 12)
        y = self.get_y()
        self.rect(10, y, 10, 10, style="DF")
        self.set_xy(10, y)
        self.cell(10, 10, num, align="C")
        self.set_xy(24, y)
        self.set_text_color(30, 58, 95)
        self.cell(30, 10, title)
        self.set_xy(50, y)
        self.set_font("Helvetica", "", 10)
        self.set_text_color(40, 40, 40)
        self.multi_cell(150, 5, desc)
        self.ln(3)

    pdf.ln(5)
    pdf.add_divider()
    pdf.ln(3)

    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(30, 58, 95)
    pdf.cell(0, 8, "File Naming Cheat Sheet:", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(2)

    widths2 = [55, 60, 75]
    pdf.add_table_header(["Filename", "Matches By", "Example Candidate"], widths2)
    pdf.add_table_row(["jane@acme.com.pdf", "Email (high)", "jane@acme.com in pipeline"], widths2)
    pdf.add_table_row(["42.pdf", "ID (high)", "Pipeline candidate #42"], widths2)
    pdf.add_table_row(["candidate_108.docx", "ID (high)", "Pipeline candidate #108"], widths2)
    pdf.add_table_row(["John_Smith.pdf", "Name (medium)", "John Smith in pipeline"], widths2)
    pdf.add_table_row(["Jane-Doe.docx", "Name (medium)", "Jane Doe in pipeline"], widths2)

    pdf.ln(8)

    pdf.set_font("Helvetica", "I", 9)
    pdf.set_text_color(128, 128, 128)
    pdf.cell(0, 6, "Winnow -- winnowcc.ai", align="C", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, "For support, contact support@winnowcc.ai", align="C")

    # Output
    output_path = "tasks/Bulk_Attach_Resumes_User_Guide.pdf"
    pdf.output(output_path)
    print(f"PDF generated: {output_path}")


if __name__ == "__main__":
    main()
