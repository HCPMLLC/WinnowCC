"""Generate a PDF testing guide from the markdown file."""
import re
from fpdf import FPDF


class TestingGuidePDF(FPDF):
    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=20)

    def header(self):
        if self.page_no() > 1:
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(128, 128, 128)
            self.cell(0, 10, "Winnow Feature Testing Guide - March 2026", align="C")
            self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")

    def add_title(self, text):
        self.set_font("Helvetica", "B", 22)
        self.set_text_color(30, 58, 95)
        self.cell(0, 15, text, new_x="LMARGIN", new_y="NEXT")
        self.ln(3)

    def add_subtitle(self, text):
        self.set_font("Helvetica", "", 11)
        self.set_text_color(100, 100, 100)
        self.cell(0, 7, text, new_x="LMARGIN", new_y="NEXT")

    def add_h2(self, text):
        self.ln(5)
        self.set_font("Helvetica", "B", 16)
        self.set_text_color(30, 58, 95)
        self.cell(0, 10, text, new_x="LMARGIN", new_y="NEXT")
        # underline
        self.set_draw_color(30, 58, 95)
        self.set_line_width(0.5)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(4)

    def add_h3(self, text):
        self.ln(3)
        self.set_font("Helvetica", "B", 13)
        self.set_text_color(50, 80, 120)
        self.cell(0, 9, text, new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def add_paragraph(self, text):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(40, 40, 40)
        # Handle bold markers
        self.multi_cell(0, 5.5, text)
        self.ln(2)

    def add_step(self, number, text):
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(30, 58, 95)
        self.cell(8, 5.5, f"{number}.")
        self.set_font("Helvetica", "", 10)
        self.set_text_color(40, 40, 40)
        self.multi_cell(0, 5.5, text)
        self.ln(1)

    def add_code_block(self, text):
        self.set_font("Courier", "", 9)
        self.set_fill_color(240, 240, 240)
        self.set_text_color(50, 50, 50)
        x = self.get_x()
        self.set_x(x + 5)
        for line in text.split("\n"):
            if line.strip():
                self.cell(180, 5.5, "  " + line, fill=True, new_x="LMARGIN", new_y="NEXT")
                self.set_x(x + 5)
        self.ln(2)

    def add_note(self, text):
        self.set_font("Helvetica", "I", 9)
        self.set_text_color(100, 100, 100)
        self.multi_cell(0, 5, text)
        self.ln(2)

    def add_pass_if(self, text):
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(0, 128, 0)
        self.cell(18, 5.5, "PASS if: ")
        self.set_font("Helvetica", "", 10)
        self.set_text_color(40, 40, 40)
        self.multi_cell(0, 5.5, text)
        self.ln(2)

    def add_table_row(self, cells, header=False):
        if header:
            self.set_font("Helvetica", "B", 9)
            self.set_fill_color(30, 58, 95)
            self.set_text_color(255, 255, 255)
        else:
            self.set_font("Helvetica", "", 9)
            self.set_fill_color(250, 250, 250)
            self.set_text_color(40, 40, 40)

        col_widths = [10, 75, 25, 80]
        for i, cell_text in enumerate(cells):
            w = col_widths[i] if i < len(col_widths) else 40
            self.cell(w, 7, cell_text, border=1, fill=True)
        self.ln()


def clean_md(text):
    """Strip markdown formatting and replace unicode for latin-1 safe output."""
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"`(.*?)`", r"\1", text)
    text = text.replace("&mdash;", " -- ")
    # Replace unicode chars that latin-1 can't encode
    text = text.replace("\u2014", "--")   # em dash
    text = text.replace("\u2013", "-")    # en dash
    text = text.replace("\u2018", "'")    # left single quote
    text = text.replace("\u2019", "'")    # right single quote
    text = text.replace("\u201c", '"')    # left double quote
    text = text.replace("\u201d", '"')    # right double quote
    text = text.replace("\u2026", "...")  # ellipsis
    text = text.replace("\u2022", "-")    # bullet
    text = text.replace("\u00a0", " ")    # nbsp
    # Catch any remaining non-latin-1 chars
    text = text.encode("latin-1", errors="replace").decode("latin-1")
    return text.strip()


def main():
    with open("tasks/testing-guide-last-5-days.md", encoding="utf-8") as f:
        md = f.read()

    pdf = TestingGuidePDF()
    pdf.alias_nb_pages()
    pdf.add_page()

    # Title page
    pdf.ln(20)
    pdf.add_title("Winnow Feature Testing Guide")
    pdf.ln(5)
    pdf.add_subtitle("Tester: rlevi@hcpm.llc")
    pdf.add_subtitle("Date: March 4, 2026")
    pdf.add_subtitle("Scope: All features delivered in the last 5 days")
    pdf.add_subtitle("Method: ADMIN_TEST_EMAILS billing bypass (PROMPT79)")
    pdf.ln(10)

    # Divider
    pdf.set_draw_color(200, 200, 200)
    pdf.set_line_width(0.3)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(10)

    pdf.add_paragraph(
        "This guide walks you through testing every feature delivered in the last 5 days. "
        "Each test includes step-by-step instructions written so anyone can follow them. "
        "The ADMIN_TEST_EMAILS feature (PROMPT79) bypasses billing limits so you can test "
        "Pro-tier features without a Stripe subscription."
    )

    # Parse sections
    sections = md.split("\n---\n")
    # Skip the header metadata, process everything after the first ---
    content = "\n---\n".join(sections[1:]) if len(sections) > 1 else md

    lines = content.split("\n")
    i = 0
    in_code_block = False
    code_buffer = []

    while i < len(lines):
        line = lines[i]

        # Code block toggle
        if line.strip().startswith("```"):
            if in_code_block:
                pdf.add_code_block("\n".join(code_buffer))
                code_buffer = []
                in_code_block = False
            else:
                in_code_block = True
            i += 1
            continue

        if in_code_block:
            code_buffer.append(line)
            i += 1
            continue

        stripped = line.strip()

        # Skip empty lines
        if not stripped:
            i += 1
            continue

        # H2
        if stripped.startswith("## "):
            text = clean_md(stripped[3:])
            pdf.add_h2(text)
            i += 1
            continue

        # H3
        if stripped.startswith("### "):
            text = clean_md(stripped[4:])
            pdf.add_h3(text)
            i += 1
            continue

        # Numbered steps
        step_match = re.match(r"^(\d+)\.\s+(.*)", stripped)
        if step_match:
            num = step_match.group(1)
            text = clean_md(step_match.group(2))
            pdf.add_step(num, text)
            i += 1
            continue

        # Bullet points
        if stripped.startswith("- "):
            text = clean_md(stripped[2:])
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(40, 40, 40)
            x = pdf.get_x()
            pdf.cell(5, 5.5, "-")  # bullet
            pdf.multi_cell(0, 5.5, " " + text)
            pdf.ln(1)
            i += 1
            continue

        # Pass if lines
        if stripped.startswith("**Pass if:**"):
            text = clean_md(stripped.replace("**Pass if:**", "").strip())
            pdf.add_pass_if(text)
            i += 1
            continue

        # Note lines
        if stripped.startswith("**Note:**"):
            text = clean_md(stripped.replace("**Note:**", "Note:").strip())
            pdf.add_note(text)
            i += 1
            continue

        # Table rows
        if stripped.startswith("|"):
            cells = [clean_md(c.strip()) for c in stripped.split("|")[1:-1]]
            if all(c.replace("-", "").strip() == "" for c in cells):
                i += 1
                continue  # skip separator row
            is_header = i > 0 and i + 1 < len(lines) and lines[i + 1].strip().startswith("|") and "---" in lines[i + 1]
            pdf.add_table_row(cells, header=is_header)
            i += 1
            continue

        # Regular paragraph
        text = clean_md(stripped)
        if text:
            pdf.add_paragraph(text)
        i += 1

    # Output
    output_path = "tasks/Winnow_Testing_Guide_March_2026.pdf"
    pdf.output(output_path)
    print(f"PDF generated: {output_path}")


if __name__ == "__main__":
    main()
