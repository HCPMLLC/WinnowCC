# PROMPT45: Employer Forms Handler — Parse, Fill, Associate & Generate Exact-Format Documents

Read SPEC.md, ARCHITECTURE.md, CLAUDE.md, PROMPT9_Resume_Parser.md, PROMPT10_Job_Parser.md, and PROMPT12_Tailored_ATS_Resume_Generation.md before making changes.

## Purpose

Implement a complete **Employer Forms Handler** that:

1. **Parses employer-provided forms** (qualification forms, reference forms, acknowledgement forms, skills matrices) from uploaded DOCX/PDF files and extracts their structure, fields, and formatting.
2. **Adds professional references** to the candidate profile as a first-class data type.
3. **Tracks years of experience per skill** in the candidate profile (parsed from resumes or manually entered by the candidate).
4. **Auto-fills employer forms** using candidate profile data — preserving the employer's exact formatting, tables, fonts, headers, and layout.
5. **Associates supplementary forms with jobs** — uploaded alongside the job posting or linked to an existing job later.
6. **Generates filled forms ONLY when the candidate applies** — never preemptively.
7. **Merges all documents** into a single PDF in the order specified by the employer (e.g., Qualification Form → Resume → Reference Form → Acknowledgement Form).

This prompt is based on real-world government staffing solicitations (e.g., Texas DIR ITSAC) where employers require specific forms submitted in exact format. Winnow must handle these seamlessly.

---

## Triggers — When to Use This Prompt

- Building or upgrading the employer forms ingestion pipeline.
- Adding references to the candidate profile.
- Adding years-per-skill tracking to the candidate profile or resume parser.
- Implementing form-filling logic for employer-provided templates.
- Product asks for "form filling," "employer forms," "supplementary documents," "reference forms," "qualification forms," or "document merge."
- Handling government staffing solicitations (DIR, SAM.gov, state contracts) that require specific submission formats.

---

## Real-World Example: What This Must Handle

An employer uploads a solicitation document (DOCX) that contains:

**Section: CANDIDATE QUALIFICATIONS (Table)**

| Actual Years Experience | Years Experience Needed | Required/Preferred | Skills/Experience |
|---|---|---|---|
| _(blank — candidate fills)_ | 8 | Required | Software and database engineering for law enforcement... |
| _(blank — candidate fills)_ | 8 | Required | Knowledge of DPS License to Carry system |
| _(blank — candidate fills)_ | 8 | Preferred | Knowledge of DPS License to Carry system |

**Section: CANDIDATE REFERENCE (3 copies of the same table)**

| Field | Value |
|---|---|
| Reference Name (Required): | _(blank)_ |
| Title: | _(blank)_ |
| Company Name (Required): | _(blank)_ |
| Phone Number (Required include area code): | _(blank)_ |
| E-mail Address: | _(blank)_ |
| Professional Relationship: | ☐ Peer ☐ Co-Worker ☐ Supervisor ☐ Customer ☐ End-User ☐ Subordinate |

**Section: CANDIDATE ACKNOWLEDGEMENT**

| Field | Value |
|---|---|
| Candidate Name: | _(blank)_ |
| Worker signature: | _(blank — not auto-filled)_ |
| Date: | _(blank — not auto-filled)_ |

**Required merge order:** Qualification Form → Resume → Reference Form → Acknowledgement Form → merged into one PDF.

Winnow must parse this structure, map fields to the candidate profile, auto-fill what it can, leave signature/date fields blank, and produce the output in the employer's exact format.

---

## Stage 1: Candidate Profile — Add References & Years-Per-Skill

### 1.1 Add `references` to the candidate profile schema

**File to modify:** `services/api/app/models/candidate_profile.py`

The `profile_json` field is a JSON column. Add a `references` section to the schema.

**New JSON structure inside `profile_json`:**

```json
{
  "references": [
    {
      "id": "ref-uuid-1",
      "name": "Jane Smith",
      "title": "VP of Engineering",
      "company": "Acme Corp",
      "phone": "512-555-1234",
      "email": "jane.smith@acme.com",
      "relationship": "Supervisor",
      "years_known": 5,
      "notes": "Direct supervisor at Acme Corp 2019-2024",
      "is_active": true
    },
    {
      "id": "ref-uuid-2",
      "name": "Bob Jones",
      "title": "Senior PM",
      "company": "State Agency",
      "phone": "512-555-5678",
      "email": "bob.jones@state.gov",
      "relationship": "Peer",
      "years_known": 3,
      "notes": "",
      "is_active": true
    }
  ]
}
```

**Relationship enum values:** `Peer`, `Co-Worker`, `Supervisor`, `Customer`, `End-User`, `Subordinate`, `Manager`, `Mentor`, `Direct Report`, `Other`

### 1.2 Add `years_experience` per skill

**File to modify:** `services/api/app/models/candidate_profile.py`

Update the skills section of `profile_json` to include years of experience per skill:

```json
{
  "skills": {
    "technical_skills": [
      {
        "name": "Python",
        "category": "Programming Language",
        "proficiency_indicator": "Expert",
        "years_experience": 8,
        "years_experience_source": "parsed"
      },
      {
        "name": "ServiceNow",
        "category": "Platform",
        "proficiency_indicator": "Proficient",
        "years_experience": 5,
        "years_experience_source": "manual"
      }
    ]
  }
}
```

**`years_experience_source` values:**
- `parsed` — computed from work history dates where this skill was used.
- `manual` — entered directly by the candidate in the profile editor.
- `inferred` — estimated from total career span and context (lower confidence).

### 1.3 Alembic migration: add `references_complete` flag

Create a migration to add a convenience column to the `candidate_profiles` table:

**New column on `candidate_profiles`:**

| Column | Type | Description |
|---|---|---|
| has_references | bool default false | True if profile_json.references has ≥ 3 entries |

This is a computed convenience flag updated on profile save. Not strictly required but useful for UI indicators ("Add references before applying to government jobs").

### 1.4 API endpoints for references

**File to create:** `services/api/app/routers/references.py`

| Method | Path | Description |
|---|---|---|
| GET | `/api/profile/references` | List all references from profile |
| POST | `/api/profile/references` | Add a new reference |
| PUT | `/api/profile/references/{ref_id}` | Update a reference |
| DELETE | `/api/profile/references/{ref_id}` | Soft-delete a reference (set is_active=false) |

Each endpoint reads/writes the `profile_json.references` array and bumps `profile_version`.

**File to create:** `services/api/app/schemas/references.py`

```python
class ReferenceCreate(BaseModel):
    name: str
    title: str | None = None
    company: str
    phone: str
    email: str | None = None
    relationship: str  # enum validated
    years_known: int | None = None
    notes: str | None = None

class ReferenceResponse(BaseModel):
    id: str
    name: str
    title: str | None
    company: str
    phone: str
    email: str | None
    relationship: str
    years_known: int | None
    notes: str | None
    is_active: bool
```

### 1.5 API endpoint for years-per-skill editing

**File to modify:** `services/api/app/routers/profile.py` (or wherever profile updates are handled)

Add a sub-endpoint or include in the existing PUT /api/profile:

| Method | Path | Description |
|---|---|---|
| PATCH | `/api/profile/skills/{skill_name}/years` | Update years_experience for a specific skill |

**Request body:**
```json
{
  "years_experience": 8,
  "years_experience_source": "manual"
}
```

### 1.6 Frontend: References management page

**File to create:** `apps/web/app/profile/references/page.tsx`

UI for managing references:
- List existing references (name, title, company, phone, email, relationship).
- "Add Reference" button → inline form or modal.
- Edit/Delete buttons per reference.
- Show count indicator: "3 of 3 references added ✓" or "1 of 3 — add more references."
- Note: "Many government and staffing solicitations require 3 professional references."

### 1.7 Frontend: Years-per-skill editing

**File to modify:** `apps/web/app/profile/page.tsx` (or wherever skills are edited)

For each skill in the skills editor:
- Show a `years_experience` field (numeric input, 0–50).
- Show source badge: "Parsed" (gray) or "Manual" (blue).
- If parsed, show tooltip: "Computed from your work history. Edit to override."
- On edit, change `years_experience_source` to `manual`.

---

## Stage 2: Resume Parser Enhancement — Extract Years Per Skill

### 2.1 Modify resume parser to compute years per skill

**File to modify:** `services/api/app/services/resume_parser.py` (or the service that handles PROMPT9 logic)

After extracting work experience and skills, add a post-processing step:

**Algorithm: Compute years per skill from work history**

```
For each skill S found in the candidate's profile:
    total_months = 0
    For each work_experience entry E where S appears in:
        - E.technologies_used (name matches S)
        - E.duties or E.accomplishments (text mentions S)
        - E.environments_supported (matches S)
        - E.domain_skills (matches S)
    Calculate:
        months = (E.end_date - E.start_date) in months
        (use current date if end_date is "Present")
        total_months += months
    Deduplicate overlapping date ranges (if candidate had concurrent roles using the same skill, don't double-count).
    S.years_experience = round(total_months / 12)
    S.years_experience_source = "parsed"
```

**Important rules:**
- Handle "Present" or null end dates as current date.
- Handle date formats: "Jan 2019", "2019", "01/2019", "January 2019".
- When work entries overlap in time (concurrent roles), merge the date ranges before summing.
- Round to nearest integer year.
- If a skill is mentioned only in a skills section (not in any work entry), set `years_experience = null` and `years_experience_source = "inferred"`.

---

## Stage 3: Employer Form Parser Service

### File to create: `services/api/app/services/form_parser.py`

This service takes an uploaded DOCX (or PDF) employer form and extracts its structure.

### 3.1 Form detection

When a document is uploaded alongside a job (or linked to a job), determine if it contains fillable forms by looking for:

- Tables with empty cells adjacent to label cells.
- Blank lines after field labels (e.g., "Candidate Name: ___________").
- Checkbox patterns (☐, ☑, [ ], [x]).
- Signature lines ("signature: ___", "sign here", "authorized signature").
- Known section headers: "CANDIDATE QUALIFICATIONS", "CANDIDATE REFERENCE", "CANDIDATE ACKNOWLEDGEMENT", "SKILLS MATRIX", "RIGHT TO REPRESENT".

### 3.2 Form structure extraction

Parse the document and produce a structured representation:

```json
{
  "form_id": "form-uuid",
  "source_filename": "26R999999_DPS_PEdigoStaffingServices_CLEAN.docx",
  "job_id": "job-uuid",
  "detected_sections": [
    {
      "section_id": "sec-1",
      "section_name": "CANDIDATE QUALIFICATIONS",
      "section_type": "skills_matrix",
      "table_index": 3,
      "fields": [
        {
          "field_id": "field-1",
          "field_label": "Actual Years Experience",
          "field_type": "numeric",
          "is_fillable": true,
          "maps_to_profile": "skills.technical_skills[].years_experience",
          "context_skill": "Software and database engineering for law enforcement...",
          "context_required_years": 8,
          "context_required_or_preferred": "Required",
          "row_index": 2,
          "col_index": 0
        }
      ]
    },
    {
      "section_id": "sec-2",
      "section_name": "CANDIDATE REFERENCE",
      "section_type": "reference_form",
      "table_index": 5,
      "repeat_count": 3,
      "fields": [
        {
          "field_id": "field-10",
          "field_label": "Reference Name (Required)",
          "field_type": "text",
          "is_fillable": true,
          "maps_to_profile": "references[0].name"
        },
        {
          "field_id": "field-11",
          "field_label": "Title",
          "field_type": "text",
          "is_fillable": true,
          "maps_to_profile": "references[0].title"
        },
        {
          "field_id": "field-12",
          "field_label": "Company Name (Required)",
          "field_type": "text",
          "is_fillable": true,
          "maps_to_profile": "references[0].company"
        },
        {
          "field_id": "field-13",
          "field_label": "Phone Number (Required include area code)",
          "field_type": "phone",
          "is_fillable": true,
          "maps_to_profile": "references[0].phone"
        },
        {
          "field_id": "field-14",
          "field_label": "E-mail Address",
          "field_type": "email",
          "is_fillable": true,
          "maps_to_profile": "references[0].email"
        },
        {
          "field_id": "field-15",
          "field_label": "Professional Relationship",
          "field_type": "checkbox_group",
          "is_fillable": true,
          "maps_to_profile": "references[0].relationship",
          "options": ["Peer", "Co-Worker", "Supervisor", "Customer", "End-User", "Subordinate"]
        }
      ]
    },
    {
      "section_id": "sec-3",
      "section_name": "CANDIDATE ACKNOWLEDGEMENT",
      "section_type": "acknowledgement",
      "table_index": 15,
      "fields": [
        {
          "field_id": "field-20",
          "field_label": "Candidate Name",
          "field_type": "text",
          "is_fillable": true,
          "maps_to_profile": "contact_information.full_name"
        },
        {
          "field_id": "field-21",
          "field_label": "Worker signature",
          "field_type": "signature",
          "is_fillable": false,
          "auto_fill": false,
          "reason": "Signatures must be provided by the candidate manually"
        },
        {
          "field_id": "field-22",
          "field_label": "Date",
          "field_type": "date",
          "is_fillable": false,
          "auto_fill": false,
          "reason": "Date must be entered by candidate at time of signing"
        }
      ]
    }
  ],
  "merge_order": [
    "CANDIDATE QUALIFICATIONS",
    "CANDIDATE RESUME",
    "CANDIDATE REFERENCE",
    "CANDIDATE ACKNOWLEDGEMENT"
  ],
  "output_format": "PDF",
  "naming_convention": "{solicitation_number}_{vendor_name}_{candidate_name}.pdf"
}
```

### 3.3 Field-to-profile mapping rules

The parser uses these rules to determine which profile field each form field maps to:

| Form Field Pattern | Maps To |
|---|---|
| "Candidate Name", "Worker Name", "Name" | `profile_json.contact_information.full_name` |
| "Email", "E-mail" | `profile_json.contact_information.email` |
| "Phone", "Telephone" | `profile_json.contact_information.phone` |
| "Address", "City", "State", "Zip" | `profile_json.contact_information.location.*` |
| "Reference Name" (in reference table) | `profile_json.references[N].name` |
| "Title" (in reference table) | `profile_json.references[N].title` |
| "Company Name" (in reference table) | `profile_json.references[N].company` |
| "Phone Number" (in reference table) | `profile_json.references[N].phone` |
| "E-mail Address" (in reference table) | `profile_json.references[N].email` |
| "Professional Relationship" (checkboxes) | `profile_json.references[N].relationship` |
| "Actual Years Experience" (in skills matrix) | `profile_json.skills.technical_skills[matched].years_experience` |
| "Signature", "Sign", "Authorized" | **NEVER AUTO-FILL** — leave blank |
| "Date" (next to signature line) | **NEVER AUTO-FILL** — leave blank |
| "Hourly Rate", "Rate", "Bill Rate" | **NEVER AUTO-FILL** — leave blank (vendor/recruiter fills) |
| "Vendor", "Staffing Company", "Agency" | **NEVER AUTO-FILL** — leave blank (vendor fills) |

### 3.4 Skills matching for qualification forms

When the form has a skills matrix (like the DIR example), match each row's skill description to the candidate's skills:

```
For each row in the skills matrix:
    skill_description = row["Skills/Experience"]
    required_years = row["Years Experience Needed"]

    Find the best matching skill in candidate.skills.technical_skills:
        - Exact name match (highest confidence)
        - Keyword overlap between skill_description and candidate skill names/categories
        - Check candidate.work_experience duties/accomplishments for matching text

    If match found:
        Fill "Actual Years Experience" = matched_skill.years_experience
        If matched_skill.years_experience < required_years:
            Flag as gap: "Candidate has {X} years, {Y} required"
    If no match found:
        Leave "Actual Years Experience" blank
        Flag as gap: "No matching skill found in candidate profile"
```

---

## Stage 4: Database Model for Employer Forms

### 4.1 New table: `job_forms`

Create an Alembic migration.

**Table: `job_forms`**

| Column | Type | Description |
|---|---|---|
| id | uuid PK | Auto-generated |
| job_id | int FK jobs.id | The job this form belongs to |
| uploaded_by_user_id | int FK users.id | Who uploaded it |
| original_filename | string | Original filename as uploaded |
| storage_url | string | Path to stored file (local or GCS) |
| file_type | string enum | docx, pdf |
| form_type | string enum | qualification, reference, acknowledgement, skills_matrix, right_to_represent, other |
| parsed_structure | jsonb nullable | The extracted form structure (from Stage 3) |
| is_parsed | bool default false | Whether parsing has been completed |
| created_at | timestamp | Upload time |
| updated_at | timestamp | Last update |

### 4.2 New table: `filled_forms`

| Column | Type | Description |
|---|---|---|
| id | uuid PK | Auto-generated |
| job_form_id | uuid FK job_forms.id | Which template form was filled |
| user_id | int FK users.id | Which candidate |
| job_id | int FK jobs.id | Which job (redundant but useful for queries) |
| match_id | int FK matches.id nullable | The match record this is for |
| filled_data | jsonb | The field values used to fill the form |
| unfilled_fields | jsonb | Array of fields left blank and why |
| gaps_detected | jsonb | Skills/years gaps found during filling |
| output_storage_url | string nullable | Path to the generated filled document |
| output_format | string enum | docx, pdf |
| status | string enum | pending, generated, reviewed, submitted |
| generated_at | timestamp nullable | When the filled form was created |
| created_at | timestamp | Record creation |

### 4.3 New table: `merged_packets`

| Column | Type | Description |
|---|---|---|
| id | uuid PK | Auto-generated |
| user_id | int FK users.id | Which candidate |
| job_id | int FK jobs.id | Which job |
| match_id | int FK matches.id nullable | The match record |
| document_order | jsonb | Array of document IDs/types in merge order |
| merged_pdf_url | string nullable | Path to final merged PDF |
| naming_convention | string nullable | Filename pattern used |
| status | string enum | pending, generated, reviewed |
| generated_at | timestamp nullable | When merge completed |
| created_at | timestamp | Record creation |

---

## Stage 5: Form Filling Service

### File to create: `services/api/app/services/form_filler.py`

This service takes a parsed form structure + candidate profile and produces a filled document.

### 5.1 Core principle: EXACT FORMAT PRESERVATION

**This is the single most important requirement.** The output document must be visually identical to the employer's template, with only the fillable fields populated. Specifically:

- **Tables** must retain exact column widths, row heights, borders, and cell shading.
- **Fonts** must match the original (font family, size, weight, color).
- **Headers, footers, logos** must be preserved exactly.
- **Page breaks** must be in the same positions.
- **Margins** must be identical.
- **Checkbox appearance** must match the original style.
- **Text alignment** within cells must match.

### 5.2 DOCX form filling approach

Use `python-docx` to:

1. **Open the original DOCX template** (never modify the original — always work on a copy).
2. **Locate each fillable field** by table index + row index + column index (from the parsed structure).
3. **Insert values** into the correct cells:
   - For text fields: set the cell's paragraph text, preserving the cell's existing paragraph formatting (font, size, alignment).
   - For numeric fields: insert the number as text in the correct cell.
   - For checkbox fields: replace the empty checkbox character (☐) with a checked character (☑) for the matching option, leave others unchecked.
   - For signature/date fields: **leave blank** — do not modify.
4. **Save the filled copy** to the output directory.

### 5.3 Formatting preservation implementation

```python
def fill_cell_preserving_format(cell, value):
    """
    Fill a table cell with a value while preserving ALL formatting.
    """
    # Get the first paragraph in the cell
    paragraph = cell.paragraphs[0]

    # Capture existing formatting
    existing_runs = paragraph.runs
    if existing_runs:
        # Copy formatting from the first existing run
        font_name = existing_runs[0].font.name
        font_size = existing_runs[0].font.size
        font_bold = existing_runs[0].font.bold
        font_color = existing_runs[0].font.color.rgb if existing_runs[0].font.color.rgb else None
    else:
        font_name = None
        font_size = None
        font_bold = None
        font_color = None

    # Clear existing text (only in fillable cells — never clear label cells)
    paragraph.clear()

    # Add new run with preserved formatting
    run = paragraph.add_run(str(value))
    if font_name:
        run.font.name = font_name
    if font_size:
        run.font.size = font_size
    if font_bold is not None:
        run.font.bold = font_bold
    if font_color:
        run.font.color.rgb = font_color
```

### 5.4 Reference form filling

For forms that have repeated reference tables (like the DIR example with 3 reference blocks):

```
For i in range(number_of_reference_blocks):
    if i < len(candidate.references):
        ref = candidate.references[i]
        Fill "Reference Name" → ref.name
        Fill "Title" → ref.title
        Fill "Company Name" → ref.company
        Fill "Phone Number" → ref.phone
        Fill "E-mail Address" → ref.email
        Fill "Professional Relationship" → check the matching checkbox for ref.relationship
    else:
        Leave all fields blank
        Add to unfilled_fields: "Reference {i+1}: Not enough references in profile"
```

### 5.5 Skills matrix filling

```
For each row in the skills matrix:
    matched_skill = find_matching_skill(row.skill_description, candidate.skills)
    if matched_skill and matched_skill.years_experience is not None:
        Fill "Actual Years Experience" → matched_skill.years_experience
    else:
        Leave blank
        Add to gaps_detected: {
            "skill": row.skill_description,
            "required_years": row.required_years,
            "candidate_years": matched_skill.years_experience if matched_skill else null,
            "status": "gap" or "not_found"
        }
```

---

## Stage 6: Form Association & Upload

### 6.1 API endpoints for form management

**File to create:** `services/api/app/routers/job_forms.py`

| Method | Path | Description |
|---|---|---|
| POST | `/api/jobs/{job_id}/forms` | Upload a form and associate with a job |
| GET | `/api/jobs/{job_id}/forms` | List all forms for a job |
| GET | `/api/jobs/{job_id}/forms/{form_id}` | Get form details + parsed structure |
| DELETE | `/api/jobs/{job_id}/forms/{form_id}` | Remove a form association |
| POST | `/api/jobs/{job_id}/forms/{form_id}/reparse` | Re-parse a form (after parser improvements) |
| POST | `/api/jobs/{job_id}/forms/upload-with-job` | Upload job posting + forms together |

### 6.2 Upload flow: Form + Job together

When a user uploads a multi-section document (like the DIR solicitation) that contains BOTH the job description AND forms:

1. Parse the entire document.
2. Detect which sections are job description vs. forms.
3. Create the job record from the job description sections.
4. Create separate `job_forms` records for each detected form section.
5. Link all forms to the job via `job_id`.

**Section detection signals:**

| Section Header Pattern | Classification |
|---|---|
| "DESCRIPTION OF SERVICES", "SCOPE OF WORK", "JOB DESCRIPTION" | Job description |
| "CANDIDATE SKILLS AND QUALIFICATIONS", "REQUIREMENTS" | Job requirements (part of job record) |
| "TERMS OF SERVICE", "WORK HOURS", "LOCATION" | Job metadata (part of job record) |
| "CANDIDATE QUALIFICATIONS" (with fillable table) | Qualification form |
| "CANDIDATE REFERENCE" (with fillable table) | Reference form |
| "CANDIDATE ACKNOWLEDGEMENT" (with signature lines) | Acknowledgement form |
| "RIGHT TO REPRESENT" | Authorization form |
| "RESPONSE FORMAT", "INSTRUCTIONS" | Submission instructions (metadata, not a form) |

### 6.3 Upload flow: Form linked to existing job

When a user uploads a form separately and wants to link it to an existing job:

1. Show a job picker/search in the UI.
2. User selects the job.
3. Upload the form file.
4. Parse the form.
5. Create `job_forms` record linked to the selected job.

### 6.4 Form upload storage

Store uploaded forms at:
- **Local dev:** `services/api/generated/forms/{job_id}/{form_id}/original.docx`
- **Production:** GCS bucket under `forms/{job_id}/{form_id}/original.docx`

Store filled forms at:
- **Local dev:** `services/api/generated/forms/{job_id}/{form_id}/filled_{user_id}.docx`
- **Production:** GCS bucket under `forms/{job_id}/{form_id}/filled_{user_id}.docx`

---

## Stage 7: Generate-on-Apply — Trigger Logic

### 7.1 When forms are generated

Forms are ONLY generated when the candidate takes an apply action. This means:

- When the candidate clicks "Apply" or "Mark as Applied" on a match.
- When the candidate clicks "Generate Application Packet" on a match that has associated forms.

Forms are NEVER pre-generated during matching or browsing.

### 7.2 Apply flow with forms

**File to modify:** `services/api/app/routers/matches.py` (the status update endpoint)

When a candidate updates a match status to `applied`:

1. Check if the job has any associated forms: `SELECT * FROM job_forms WHERE job_id = {job_id}`.
2. If no forms → standard behavior (just update status, generate tailored resume if requested).
3. If forms exist:
   a. For each form, run the form filler (Stage 5) to produce filled documents.
   b. Generate the tailored resume (existing PROMPT12 logic).
   c. If a merge order is specified, merge all documents into a single PDF (Stage 8).
   d. Store all outputs.
   e. Return download links for individual documents AND the merged packet.

### 7.3 Pre-apply readiness check

Before generating, check the candidate's profile completeness:

```json
{
  "ready_to_apply": true,
  "missing_data": [],
  "warnings": [
    "Reference 3 has no email address — some employers require email",
    "Skill 'DPS License to Carry system' not found in your profile — you have 0 of 8 required years"
  ],
  "form_coverage": {
    "qualification_form": {
      "fillable_fields": 6,
      "auto_filled": 4,
      "left_blank": 2,
      "gaps": ["DPS License to Carry system: 0 of 8 years"]
    },
    "reference_form": {
      "fillable_fields": 18,
      "auto_filled": 18,
      "left_blank": 0,
      "gaps": []
    },
    "acknowledgement_form": {
      "fillable_fields": 3,
      "auto_filled": 1,
      "left_blank": 2,
      "reasons": ["Signature — must be signed manually", "Date — must be entered at signing"]
    }
  }
}
```

### 7.4 API endpoint for readiness check

| Method | Path | Description |
|---|---|---|
| GET | `/api/matches/{match_id}/apply-readiness` | Check if profile has enough data to fill all forms |
| POST | `/api/matches/{match_id}/generate-packet` | Generate all filled forms + tailored resume + merged packet |
| GET | `/api/matches/{match_id}/packet` | Get the generated packet with download links |

---

## Stage 8: Document Merge Service

### File to create: `services/api/app/services/document_merger.py`

### 8.1 Merge DOCX files into a single PDF

The merge service:

1. Takes an ordered list of documents (filled forms + tailored resume).
2. Converts each DOCX to PDF (using `python-docx` → PDF via `reportlab`, or via LibreOffice headless conversion).
3. Merges all PDFs into a single file in the specified order.
4. Names the output file per the employer's naming convention if specified.

**Dependencies to add to `services/api/requirements.txt`:**
```
PyPDF2>=3.0.0
```

**LibreOffice for DOCX→PDF conversion** (install in Docker/dev environment):
```bash
# In Docker or Linux:
apt-get install -y libreoffice-writer

# Conversion command:
libreoffice --headless --convert-to pdf input.docx --outdir /output/
```

**For Windows local dev** (PowerShell):
```powershell
# Use LibreOffice if installed, otherwise use python-docx2pdf
pip install docx2pdf --break-system-packages
```

### 8.2 Merge implementation

```python
import subprocess
from PyPDF2 import PdfMerger

def merge_documents_to_pdf(
    documents: list[dict],  # [{path, type, label}]
    output_path: str,
    output_filename: str
) -> str:
    """
    Convert all documents to PDF and merge in order.

    documents = [
        {"path": "/path/to/qualification_form_filled.docx", "type": "docx", "label": "Qualification Form"},
        {"path": "/path/to/tailored_resume.docx", "type": "docx", "label": "Resume"},
        {"path": "/path/to/reference_form_filled.docx", "type": "docx", "label": "Reference Form"},
        {"path": "/path/to/acknowledgement_filled.docx", "type": "docx", "label": "Acknowledgement"},
    ]
    """
    pdf_paths = []
    for doc in documents:
        if doc["type"] == "docx":
            pdf_path = convert_docx_to_pdf(doc["path"])
            pdf_paths.append(pdf_path)
        elif doc["type"] == "pdf":
            pdf_paths.append(doc["path"])

    merger = PdfMerger()
    for pdf_path in pdf_paths:
        merger.append(pdf_path)

    full_output = os.path.join(output_path, output_filename)
    merger.write(full_output)
    merger.close()

    return full_output
```

### 8.3 Naming convention

If the employer specifies a naming convention (e.g., `{solicitation_number}_{vendor_name}_{candidate_name}.pdf`), apply it:

```python
def apply_naming_convention(
    convention: str,
    solicitation_number: str,
    vendor_name: str,
    candidate_name: str
) -> str:
    return convention.format(
        solicitation_number=solicitation_number,
        vendor_name=vendor_name.replace(" ", ""),
        candidate_name=candidate_name.replace(" ", "")
    )
    # Example: "26R999999_PedigoStaffing_RonaldLevi.pdf"
```

---

## Stage 9: Frontend Integration

### 9.1 Job detail — Show associated forms

**File to modify:** `apps/web/app/matches/page.tsx` (or job detail page)

When viewing a job match, if the job has associated forms:
- Show a section: "Required Forms (3)" with a list of form types.
- Show readiness indicators per form: ✅ "Can be auto-filled" or ⚠️ "Missing data — review profile."
- Show "Generate Application Packet" button (only if status allows).

### 9.2 Form upload UI

**File to create:** `apps/web/app/jobs/[jobId]/forms/page.tsx`

- "Upload Form" button → file picker (accepts .docx, .pdf).
- Option: "Upload with new job" or "Link to existing job" (job search/picker).
- After upload: show parsed form structure preview (sections, detected fields, mapping).
- Allow user to correct field mappings if the parser got them wrong.

### 9.3 Application packet generation UI

**File to create:** `apps/web/app/matches/[matchId]/apply/page.tsx`

When user clicks "Generate Application Packet":

1. Show readiness check results (gaps, warnings, missing data).
2. Let user address gaps before generating (e.g., "Add missing references" link → references page).
3. Show "Generate Packet" button.
4. Show progress indicator while generating.
5. When complete, show:
   - Download links for each individual filled document.
   - Download link for the merged PDF packet.
   - List of fields left blank with reasons.
   - List of skill gaps detected.

### 9.4 Admin — Form templates page

**File to create:** `apps/web/app/admin/forms/page.tsx`

- List all uploaded forms across all jobs.
- Show parsing status (parsed / failed / pending).
- Allow re-parse.
- Show form type breakdown.

---

## File and Component Reference

| What | Where | Action |
|---|---|---|
| Form Parser Service | `services/api/app/services/form_parser.py` | CREATE |
| Form Filler Service | `services/api/app/services/form_filler.py` | CREATE |
| Document Merger Service | `services/api/app/services/document_merger.py` | CREATE |
| References Router | `services/api/app/routers/references.py` | CREATE |
| References Schema | `services/api/app/schemas/references.py` | CREATE |
| Job Forms Router | `services/api/app/routers/job_forms.py` | CREATE |
| Job Forms Schema | `services/api/app/schemas/job_forms.py` | CREATE |
| Job Forms Model | `services/api/app/models/job_form.py` | CREATE |
| Filled Forms Model | `services/api/app/models/filled_form.py` | CREATE |
| Merged Packets Model | `services/api/app/models/merged_packet.py` | CREATE |
| Candidate Profile Model | `services/api/app/models/candidate_profile.py` | MODIFY — add has_references |
| Profile Router | `services/api/app/routers/profile.py` | MODIFY — add skills/years endpoint |
| Matches Router | `services/api/app/routers/matches.py` | MODIFY — add apply-readiness, generate-packet |
| Resume Parser Service | `services/api/app/services/resume_parser.py` | MODIFY — add years-per-skill computation |
| Main App | `services/api/app/main.py` | MODIFY — register new routers |
| Alembic Migration | `services/api/alembic/versions/` | CREATE — new tables + profile column |
| Requirements | `services/api/requirements.txt` | MODIFY — add PyPDF2 |
| Frontend: References Page | `apps/web/app/profile/references/page.tsx` | CREATE |
| Frontend: Profile Skills | `apps/web/app/profile/page.tsx` | MODIFY — add years input per skill |
| Frontend: Job Forms Upload | `apps/web/app/jobs/[jobId]/forms/page.tsx` | CREATE |
| Frontend: Apply Packet | `apps/web/app/matches/[matchId]/apply/page.tsx` | CREATE |
| Frontend: Matches Page | `apps/web/app/matches/page.tsx` | MODIFY — show form indicators |
| Frontend: Admin Forms | `apps/web/app/admin/forms/page.tsx` | CREATE |

---

## Implementation Order

Follow these steps in exact order:

**Step 1:** Create the Alembic migration for new tables and columns.

**Step 2:** Create the SQLAlchemy models: `job_form.py`, `filled_form.py`, `merged_packet.py`. Update `candidate_profile.py` with the `has_references` column. Update `services/api/app/models/__init__.py` to import all new models.

**Step 3:** Create the references schema and router. Register the router in `services/api/app/main.py`.

**Step 4:** Modify the resume parser to compute years-per-skill from work history.

**Step 5:** Update the profile editor skills section to include years-per-skill input. Add the PATCH endpoint for skills years.

**Step 6:** Create the form parser service (`form_parser.py`).

**Step 7:** Create the form filler service (`form_filler.py`).

**Step 8:** Create the document merger service (`document_merger.py`). Add `PyPDF2` to `requirements.txt`.

**Step 9:** Create the job forms router and schema. Register in `main.py`.

**Step 10:** Add the apply-readiness and generate-packet endpoints to the matches router.

**Step 11:** Build the frontend references management page.

**Step 12:** Build the frontend form upload page.

**Step 13:** Build the frontend apply/packet generation page.

**Step 14:** Update the matches page to show form indicators and the "Generate Application Packet" button.

**Step 15:** Build the admin forms page.

**Step 16:** Test end-to-end: upload a solicitation document → parse forms → fill profile → apply → generate packet → verify output matches employer format exactly.

---

## Dependencies to Add

**File:** `services/api/requirements.txt`

Add these lines if not already present:
```
PyPDF2>=3.0.0
```

`python-docx` should already be present from PROMPT12. Verify it is there.

---

## Non-Goals (Do NOT implement in this prompt)

- Optical Character Recognition (OCR) for scanned PDF forms (future — use text-based PDFs and DOCX only for now).
- Electronic signature capture within Winnow (candidates sign outside the app).
- Auto-submission to employer portals (candidates download and submit manually).
- Form templates marketplace or sharing between users.
- PDF form field detection (Adobe AcroForm / XFA) — DOCX tables only for v1.

---

## Testing

- Add unit tests for:
  - Form parser: detect sections, extract fields, identify fillable vs. non-fillable.
  - Form filler: fill qualification table, reference table, acknowledgement form.
  - Document merger: merge 4 documents in order, verify page count.
  - Years-per-skill computation: overlapping dates, concurrent roles, "Present" end dates.
  - Reference CRUD: add, update, delete, list.
  - Field mapping: correct profile field matched to each form field.

**Test files:**
- `services/api/tests/test_form_parser.py`
- `services/api/tests/test_form_filler.py`
- `services/api/tests/test_document_merger.py`
- `services/api/tests/test_years_per_skill.py`
- `services/api/tests/test_references.py`

---

## Summary Checklist

- [ ] Alembic migration: `job_forms`, `filled_forms`, `merged_packets` tables + `has_references` column on `candidate_profiles`
- [ ] SQLAlchemy models: `JobForm`, `FilledForm`, `MergedPacket`
- [ ] Candidate profile: `references` array in `profile_json` with full CRUD API
- [ ] Candidate profile: `years_experience` + `years_experience_source` per skill
- [ ] Resume parser: auto-computes years-per-skill from work history date ranges
- [ ] Form parser: extracts structure from employer DOCX templates (tables, fields, checkboxes, sections)
- [ ] Form filler: populates fields from candidate profile preserving exact employer formatting
- [ ] Form filler: NEVER auto-fills signatures, dates-next-to-signatures, hourly rates, or vendor fields
- [ ] Skills matrix: matches skill descriptions to candidate skills, fills years, flags gaps
- [ ] Reference forms: fills from `profile_json.references`, handles repeated blocks
- [ ] Document merger: converts DOCX→PDF, merges in employer-specified order, applies naming convention
- [ ] Forms associated with jobs (upload together or link separately)
- [ ] Forms generated ONLY on apply action (never preemptively)
- [ ] Apply readiness check: shows gaps, warnings, missing data before generation
- [ ] Frontend: references management page with add/edit/delete
- [ ] Frontend: years-per-skill editing in profile skills section
- [ ] Frontend: form upload and job association UI
- [ ] Frontend: application packet generation with progress, downloads, gap report
- [ ] Frontend: matches page shows form indicators for jobs with required forms
- [ ] Admin: forms management page with parse status
- [ ] Unit tests for parser, filler, merger, years computation, references

Return code changes only.
