/**
 * Winnow LinkedIn Content Script
 * Injected on linkedin.com/in/* -- extracts profile data from the DOM.
 *
 * Strategy: innerText line-by-line parsing, broad section finding
 * (h2/h3/h4/span headers, not just main>section>h2).
 */

const EXTRACTOR_VERSION = "1.1.0";

function extractProfile() {
  // ── Constants ──────────────────────────────────────────────────────────

  const SKIP = new Set([
    "...see more", "see more", "Show all", "see less", "Show less",
    "show more", "Show more results", "Show all skills", "Show credential",
    "more", "less", "Endorse", "Endorsed", "Follow", "Connect",
    "Message", "More actions", "Open to", "Collapse this section",
    "Report this profile", "Save to PDF",
  ]);

  const SECTION_KW = [
    "experience", "education", "skills", "licenses & certifications",
    "volunteer experience", "publications", "projects",
    "honors & awards", "about", "recommendations", "certifications",
    "volunteer", "interests", "courses", "languages",
  ];

  const PRONOUN_RE = /^(she|he|they|ze|xe|it)\/(her|him|them|hir|xem|his|its|hers|theirs)(\/\w+)?$/i;
  const DEGREE_RE = /^[·\u00b7]\s*(1st|2nd|3rd\+?|\d+th)$/i;
  const BULLET_RE = /^[•●○◆◇▪▸►\*✓✔☑→⬤∙⚬★☆\u2022\u2023\u2043\u25CF\u25CB\u25A0\u25AA]/;
  const MONTH_RE = /\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|january|february|march|april|june|july|august|september|october|november|december)\b/i;
  const YEAR_RE = /\b(19|20)\d{2}\b/;
  const DURATION_RE = /^\d+\s*(yr|yrs|year|years|mo|mos|month|months)/i;
  const EMP_TYPES = new Set([
    "full-time", "part-time", "self-employed", "freelance", "contract",
    "internship", "apprenticeship", "seasonal", "volunteer", "temporary",
  ]);

  // ── Line classifiers ──────────────────────────────────────────────────

  function isDate(t) { return MONTH_RE.test(t) || YEAR_RE.test(t) || /\bpresent\b/i.test(t); }
  function isDateRange(t) { return isDate(t) && (t.includes("-") || t.includes("–") || /present/i.test(t)); }
  function isDuration(t) { return DURATION_RE.test(t.replace(/^[·\u00b7]\s*/, "")); }
  function isLocation(t) {
    return (
      (/,\s*[A-Z]/.test(t) && t.length < 80) ||
      /metropolitan area/i.test(t) ||
      /^remote$/i.test(t.replace(/[·\u00b7]/g, "").trim()) ||
      /\b(united states|united kingdom|on-site|hybrid)\b/i.test(t)
    );
  }
  function isSkipLine(t) {
    if (!t || t.length <= 1) return true;
    if (SKIP.has(t)) return true;
    if (/^show all \d/i.test(t)) return true;
    if (/^show all \w/i.test(t) && t.length < 40) return true;
    if (/^\d+\s*(endorsement|connection|follower|mutual)/i.test(t)) return true;
    if (/^endorsed by/i.test(t)) return true;
    return false;
  }
  function isBullet(t) { return BULLET_RE.test(t); }
  function splitMiddleDot(line) {
    return line.split(/\s*[·\u00b7]\s*/).map((s) => s.trim()).filter(Boolean);
  }
  function isEmploymentType(t) {
    return EMP_TYPES.has(t.replace(/^[·\u00b7]\s*/, "").trim().toLowerCase());
  }

  // ── Debug accumulator ─────────────────────────────────────────────────

  const _debug = {
    sections_found: {},
    meta_title: document.title,
    page_height: Math.max(document.body.scrollHeight || 0, document.documentElement.scrollHeight || 0),
  };

  // ── Comprehensive DOM diagnostics ─────────────────────────────────────

  // All heading elements on the page
  const allHeadings = [];
  for (const tag of ["h1", "h2", "h3", "h4"]) {
    for (const el of document.querySelectorAll(tag)) {
      const t = (el.textContent || "").trim();
      if (t) allHeadings.push({ tag, text: t.substring(0, 60), inMain: !!el.closest("main") });
    }
  }
  _debug.all_headings = allHeadings.slice(0, 30);

  // All section elements (in main and outside)
  const allSections = [];
  for (const section of document.querySelectorAll("section")) {
    const heading = section.querySelector("h1, h2, h3, h4");
    const headingText = heading ? (heading.textContent || "").trim() : null;
    allSections.push({
      inMain: !!section.closest("main"),
      heading: headingText ? headingText.substring(0, 50) : null,
      headingTag: heading ? heading.tagName : null,
      textLen: (section.innerText || "").length,
      ariaLabel: section.getAttribute("aria-label")?.substring(0, 50) || null,
      childSections: section.querySelectorAll("section").length,
    });
  }
  _debug.all_sections = allSections;

  // Check for main element content
  const mainEl = document.querySelector("main");
  if (mainEl) {
    const mainText = mainEl.innerText || "";
    _debug.main_text_length = mainText.length;
    _debug.main_first_200 = mainText.substring(0, 200);
    _debug.main_children = [...mainEl.children].slice(0, 10).map((c) => ({
      tag: c.tagName,
      id: c.id?.substring(0, 30) || null,
      cls: (c.className || "").substring(0, 50),
      textLen: (c.innerText || "").length,
      sections: c.querySelectorAll("section").length,
    }));
  }

  // Search for section keywords in ANY element's text content
  const keywordMatches = {};
  for (const kw of ["Experience", "Education", "Skills"]) {
    const matches = [];
    // Check all elements that contain just the keyword as visible text
    for (const tag of ["h1", "h2", "h3", "h4", "span", "div"]) {
      for (const el of document.querySelectorAll(tag)) {
        const t = (el.textContent || "").trim();
        if (t.toLowerCase() === kw.toLowerCase() || t.toLowerCase() === kw.toLowerCase() + "s") {
          matches.push({
            tag, text: t,
            parentTag: el.parentElement?.tagName,
            closestSection: !!el.closest("section"),
            inMain: !!el.closest("main"),
            depth: getDepth(el),
          });
        }
      }
    }
    if (matches.length > 0) keywordMatches[kw] = matches.slice(0, 3);
  }
  _debug.keyword_matches = keywordMatches;

  function getDepth(el) {
    let d = 0;
    while (el && d < 30) { d++; el = el.parentElement; }
    return d;
  }

  // ── Section finder (broadened) ────────────────────────────────────────
  // Searches ALL sections (not just main), checks h2/h3/h4, aria-label

  function findSection(keyword) {
    const kw = keyword.toLowerCase();
    const allSecs = document.querySelectorAll("section");

    // Strategy 1: section with h2 matching keyword
    for (const section of allSecs) {
      const h2 = section.querySelector("h2");
      if (h2) {
        const ht = h2.textContent.trim().toLowerCase();
        if (ht === kw || ht === kw + "s" || ht.startsWith(kw + " ") || ht.startsWith(kw + "s") || ht === kw + "s & certifications") {
          _debug.sections_found[keyword] = `h2:"${h2.textContent.trim()}"`;
          return section;
        }
      }
    }

    // Strategy 2: section with h3 matching keyword
    for (const section of allSecs) {
      const h3 = section.querySelector("h3");
      if (h3) {
        const ht = h3.textContent.trim().toLowerCase();
        if (ht === kw || ht === kw + "s" || ht.startsWith(kw + " ") || ht.startsWith(kw + "s")) {
          _debug.sections_found[keyword] = `h3:"${h3.textContent.trim()}"`;
          return section;
        }
      }
    }

    // Strategy 3: section with aria-label matching keyword
    for (const section of allSecs) {
      const label = (section.getAttribute("aria-label") || "").toLowerCase();
      if (label.includes(kw)) {
        _debug.sections_found[keyword] = `aria-label:"${label}"`;
        return section;
      }
    }

    // Strategy 4: data-testid
    let el = document.querySelector(`[data-testid*="${keyword}" i]`);
    if (!el) el = document.querySelector(`[data-testid*="${keyword}"]`);
    if (el) {
      const section = el.closest("section");
      if (section) { _debug.sections_found[keyword] = "data-testid→section"; return section; }
      _debug.sections_found[keyword] = `data-testid(${el.tagName})`;
      return el;
    }

    // Strategy 5: find ANY element with exact keyword text and return its ancestor section/container
    for (const tag of ["h2", "h3", "h4", "span", "div"]) {
      for (const heading of document.querySelectorAll(tag)) {
        const ht = heading.textContent.trim().toLowerCase();
        if (ht === kw || ht === kw + "s") {
          // Walk up to find a meaningful container (section, or large parent div)
          let container = heading.closest("section");
          if (container) {
            _debug.sections_found[keyword] = `${tag}-walk→section`;
            return container;
          }
          // No section ancestor — use parent elements until we find one with substantial text
          container = heading.parentElement;
          for (let i = 0; i < 5 && container; i++) {
            if ((container.innerText || "").length > 200) {
              _debug.sections_found[keyword] = `${tag}-walk→parent(${container.tagName},d${i})`;
              return container;
            }
            container = container.parentElement;
          }
        }
      }
    }

    _debug.sections_found[keyword] = "NOT_FOUND";
    return null;
  }

  // ── Get visible text lines from a section ─────────────────────────────

  function getSectionLines(section) {
    if (!section) return [];
    const raw = section.innerText || "";
    return raw.split("\n").map((l) => l.trim()).filter((l) => l && !isSkipLine(l));
  }

  // ── Meta tag helpers ──────────────────────────────────────────────────

  function getMeta(name) {
    const el = document.querySelector(`meta[property="${name}"]`) || document.querySelector(`meta[name="${name}"]`);
    return el ? el.getAttribute("content") : null;
  }

  // ── Name ──────────────────────────────────────────────────────────────

  let name = null;
  const headingXL = document.querySelector("[class*='text-heading-xlarge']");
  if (headingXL) { name = headingXL.textContent.trim(); _debug.name_strategy = "text-heading-xlarge"; }

  if (!name) {
    const h1 = document.querySelector("main h1") || document.querySelector("h1");
    if (h1) { name = h1.textContent.trim(); _debug.name_strategy = "h1"; }
  }

  if (!name) {
    const m = document.title.match(/^(.+?)\s*[-–—|]\s*LinkedIn/);
    if (m) { name = m[1].split(/\s*[-–—]\s*/)[0].trim(); _debug.name_strategy = "document-title"; }
  }

  // ── Headline & Location ───────────────────────────────────────────────

  let headline = null, location = null;

  const nameEl = headingXL || document.querySelector("main h1") || document.querySelector("h1");
  if (nameEl) {
    // Find the top card: closest section or a few levels up
    const card = nameEl.closest("section") || (() => {
      let el = nameEl;
      for (let i = 0; i < 6; i++) { el = el.parentElement; if (!el) break; }
      return el;
    })();

    if (card) {
      const cardText = card.innerText || "";
      const cardLines = cardText.split("\n").map((l) => l.trim()).filter(Boolean);
      _debug.top_card_lines = cardLines.slice(0, 15);

      const candidates = [];
      let pastName = false;
      for (const line of cardLines) {
        if (!pastName) {
          if (line === name) pastName = true;
          continue;
        }
        if (line.length <= 2 || line.length >= 200) continue;
        if (DEGREE_RE.test(line)) continue;
        if (PRONOUN_RE.test(line)) continue;
        if (/^\d+\+?\s*(connections?|followers?|mutual)/i.test(line)) continue;
        if (/^(connect|follow|more|message|pending)$/i.test(line)) continue;
        if (SKIP.has(line)) continue;
        if (SECTION_KW.includes(line.toLowerCase())) break;
        candidates.push(line);
      }
      _debug.headline_candidates = candidates.slice(0, 8);

      if (candidates.length > 0) {
        headline = candidates[0];
        const geo = candidates.slice(1).find((t) => isLocation(t));
        location = geo || (candidates.length > 1 ? candidates[1] : null);
      }
    }
  }

  // Fallback: meta
  if (!headline) {
    const desc = getMeta("og:description") || getMeta("description") || "";
    let cleaned = desc;
    if (name && cleaned.startsWith(name)) cleaned = cleaned.substring(name.length).replace(/^\s*[·\u00b7|–—-]\s*/, "");
    const parts = cleaned.split(/\s*[·\u00b7]\s*/).filter(Boolean);
    if (parts.length > 0) headline = parts[0];
    if (!location && parts.length > 1 && isLocation(parts[1])) location = parts[1];
  }

  // ── Photo ─────────────────────────────────────────────────────────────

  const photoUrl = (() => {
    for (const sel of [
      "img.pv-top-card-profile-picture__image--show",
      "img.pv-top-card-profile-picture__image",
      "img[class*='profile-photo']",
      "main img[alt]",
      "img[alt]",
    ]) {
      const el = document.querySelector(sel);
      if (el) { const src = el.getAttribute("src"); if (src && src.startsWith("http")) return src; }
    }
    return null;
  })();

  // ── About ─────────────────────────────────────────────────────────────

  let about = null;
  const aboutSection = findSection("About");
  if (aboutSection) {
    const lines = getSectionLines(aboutSection).filter((l) => l.toLowerCase() !== "about");
    const meaningful = lines.filter((l) => l.length > 15);
    if (meaningful.length > 0) about = meaningful.join(" ");
    _debug.about_lines = lines.slice(0, 5);
  }

  // ── Experience ────────────────────────────────────────────────────────

  const experienceEntries = [];
  const expSection = findSection("Experience");
  if (expSection) {
    const lines = getSectionLines(expSection);
    _debug.exp_lines = lines.slice(0, 30).map((l) => l.substring(0, 120));

    let startIdx = 0;
    if (/^experience$/i.test(lines[0] || "")) startIdx = 1;

    let cur = null;

    function pushExp() {
      if (cur && cur.title) {
        experienceEntries.push({
          title: cur.title,
          company: cur.company || null,
          location: cur.location || null,
          date_range: cur.date_range || null,
          description: cur.descParts.length > 0 ? cur.descParts.join("\n") : null,
        });
      }
    }

    for (let i = startIdx; i < lines.length; i++) {
      const line = lines[i];
      const parts = splitMiddleDot(line);
      const hasDate = parts.some((p) => isDate(p));
      const hasEmpType = parts.some((p) => isEmploymentType(p));

      // Skip skill tag lines: "Strategy, Strategic Thinking and +22 skills"
      if (/and\s+\+\d+\s+skills?$/i.test(line)) continue;

      // Date range line
      if (hasDate || isDateRange(line)) {
        if (cur) {
          const datePart = parts.find((p) => isDate(p)) || line;
          if (!cur.date_range) cur.date_range = datePart;
        }
        continue;
      }

      // Pure duration
      if (isDuration(line) || (parts.length === 1 && parts.some((p) => isDuration(p)))) continue;

      // Location line
      if (isLocation(line) && !hasEmpType) {
        if (cur && !cur.location) cur.location = parts.find((p) => isLocation(p)) || line;
        continue;
      }

      // Company + employment type: "USAA · Full-time"
      if (hasEmpType && parts.length >= 2) {
        const companyPart = parts.find((p) => !isEmploymentType(p) && !isDuration(p));
        if (cur && !cur.company && companyPart) cur.company = companyPart;
        continue;
      }

      // Bullet or long text → description
      if (isBullet(line) || (cur && line.length > 100)) {
        if (cur) cur.descParts.push(line);
        continue;
      }

      // Short non-classified line → new entry title or company
      if (line.length <= 80 && !isBullet(line)) {
        if (!cur) {
          cur = { title: line, company: null, location: null, date_range: null, descParts: [] };
        } else if (!cur.company && cur.title) {
          // Lookahead: if next line has date/empType, this is company for current entry
          const nextLine = lines[i + 1] || "";
          const nextParts = splitMiddleDot(nextLine);
          if (nextParts.some((p) => isDate(p)) || nextParts.some((p) => isEmploymentType(p)) || isDuration(nextLine)) {
            cur.company = line;
          } else {
            pushExp();
            cur = { title: line, company: null, location: null, date_range: null, descParts: [] };
          }
        } else {
          pushExp();
          cur = { title: line, company: null, location: null, date_range: null, descParts: [] };
        }
        continue;
      }

      // Medium text → description
      if (cur) cur.descParts.push(line);
    }
    pushExp();
  }

  // ── Current company ───────────────────────────────────────────────────

  let currentCompany = experienceEntries.length > 0 ? experienceEntries[0].company : null;
  if (!currentCompany && headline && / at /i.test(headline)) {
    currentCompany = headline.split(/ at /i).pop().trim();
  }

  // ── Education ─────────────────────────────────────────────────────────

  const educationEntries = [];
  const eduSection = findSection("Education");
  if (eduSection) {
    const lines = getSectionLines(eduSection);
    _debug.edu_lines = lines.slice(0, 20).map((l) => l.substring(0, 100));

    let startIdx = 0;
    if (/^education$/i.test(lines[0] || "")) startIdx = 1;

    let cur = null;
    function pushEdu() {
      if (cur && cur.school) educationEntries.push({
        school: cur.school, degree: cur.degree || null,
        field: cur.field || null, date_range: cur.date_range || null,
        description: cur.descParts.length > 0 ? cur.descParts.join("\n") : null,
      });
    }

    for (let i = startIdx; i < lines.length; i++) {
      const line = lines[i];
      if (isDate(line) || isDateRange(line)) { if (cur && !cur.date_range) cur.date_range = line; continue; }
      if (isDuration(line)) continue;
      if (isBullet(line) || line.length > 120) { if (cur) cur.descParts.push(line); continue; }

      if (!cur) {
        cur = { school: line, degree: null, field: null, date_range: null, descParts: [] };
      } else if (!cur.degree) {
        cur.degree = line;
      } else if (!cur.field) {
        cur.field = line;
      } else {
        pushEdu();
        cur = { school: line, degree: null, field: null, date_range: null, descParts: [] };
      }
    }
    pushEdu();
  }

  // ── Skills ────────────────────────────────────────────────────────────

  const skills = [];
  const skillSection = findSection("Skill");
  if (skillSection) {
    const lines = getSectionLines(skillSection);
    _debug.skill_lines = lines.slice(0, 40);

    const seen = new Set();
    for (const line of lines) {
      if (/^skills?$/i.test(line)) continue;
      if (line.length > 60 || line.length <= 1) continue;
      if (/^\d+$/.test(line)) continue;
      if (isDate(line)) continue;
      if (/^endorse/i.test(line) || /endorsed by/i.test(line)) continue;
      if (BULLET_RE.test(line)) continue;
      if (/^show /i.test(line)) continue;
      if (/^\d+\s*(endorsement|connection|follower)/i.test(line)) continue;
      if (seen.has(line.toLowerCase())) continue;
      seen.add(line.toLowerCase());
      skills.push({ name: line, endorsements: null });
    }
  }

  // Also harvest skills from "Strategy, Strategic Thinking and +N skills" tags
  // embedded in experience entries (LinkedIn shows these under each role)
  if (expSection) {
    const expLines = getSectionLines(expSection);
    const skillTagRE = /^(.+?)\s+and\s+\+\d+\s+skills?$/i;
    for (const line of expLines) {
      const m = line.match(skillTagRE);
      if (m) {
        // "Strategy, Strategic Thinking and +22 skills" → ["Strategy", "Strategic Thinking"]
        const tagSkills = m[1].split(/,\s*/).map((s) => s.trim()).filter(Boolean);
        for (const s of tagSkills) {
          if (s.length > 60 || s.length <= 1) continue;
          const key = s.toLowerCase();
          if (!skills.some((sk) => sk.name.toLowerCase() === key)) {
            skills.push({ name: s, endorsements: null });
          }
        }
      }
    }
  }

  // ── Certifications ────────────────────────────────────────────────────

  const certifications = [];
  const certSection = findSection("Certification") || findSection("License");
  if (certSection) {
    const lines = getSectionLines(certSection);
    _debug.cert_lines = lines.slice(0, 20);
    let startIdx = 0;
    if (/^(licenses|certifications|licenses & certifications)/i.test(lines[0] || "")) startIdx = 1;

    let cur = null;
    for (let i = startIdx; i < lines.length; i++) {
      const line = lines[i];
      if (isDate(line)) { if (cur && !cur.date) cur.date = line; continue; }
      if (isDuration(line)) continue;
      if (isBullet(line) || line.length > 100) continue;
      if (/^(issued|expires|credential id|see credential)/i.test(line)) continue;
      // Skip pure numeric strings (credential IDs like "11352")
      if (/^\d{3,}$/.test(line.trim())) continue;

      if (!cur) { cur = { name: line, issuing_org: null, date: null }; }
      else if (!cur.issuing_org) { cur.issuing_org = line; }
      else { certifications.push(cur); cur = { name: line, issuing_org: null, date: null }; }
    }
    if (cur && cur.name) certifications.push(cur);
  }

  // ── Volunteer ─────────────────────────────────────────────────────────

  const volunteer = [];
  const volunteerSection = findSection("Volunteer");
  if (volunteerSection) {
    const lines = getSectionLines(volunteerSection);
    let startIdx = 0;
    if (/^volunteer/i.test(lines[0] || "")) startIdx = 1;
    let cur = null;

    for (let i = startIdx; i < lines.length; i++) {
      const line = lines[i];
      if (isDate(line) || isDateRange(line)) { if (cur && !cur.date_range) cur.date_range = line; continue; }
      if (isDuration(line)) continue;
      if (isBullet(line) || line.length > 100) continue;
      if (!cur) { cur = { role: line, organization: null, date_range: null }; }
      else if (!cur.organization) { cur.organization = line; }
      else { volunteer.push(cur); cur = { role: line, organization: null, date_range: null }; }
    }
    if (cur && cur.role) volunteer.push(cur);
  }

  // ── Publications ──────────────────────────────────────────────────────

  const publications = [];
  const pubSection = findSection("Publication");
  if (pubSection) {
    const lines = getSectionLines(pubSection);
    let startIdx = 0;
    if (/^publication/i.test(lines[0] || "")) startIdx = 1;
    let cur = null;

    for (let i = startIdx; i < lines.length; i++) {
      const line = lines[i];
      if (isDate(line)) { if (cur && !cur.date) cur.date = line; continue; }
      if (isBullet(line) || line.length > 100) continue;
      if (!cur) { cur = { title: line, publisher: null, date: null }; }
      else if (!cur.publisher) { cur.publisher = line; }
      else { publications.push(cur); cur = { title: line, publisher: null, date: null }; }
    }
    if (cur && cur.title) publications.push(cur);
  }

  // ── Projects ──────────────────────────────────────────────────────────

  const projects = [];
  const projectSection = findSection("Project");
  if (projectSection) {
    const lines = getSectionLines(projectSection);
    let startIdx = 0;
    if (/^project/i.test(lines[0] || "")) startIdx = 1;
    let cur = null;

    for (let i = startIdx; i < lines.length; i++) {
      const line = lines[i];
      if (isDate(line) || isDateRange(line)) { if (cur && !cur.date_range) cur.date_range = line; continue; }
      if (isDuration(line)) continue;
      if (!cur) { cur = { name: line, description: null, date_range: null }; }
      else if (!cur.description && (isBullet(line) || line.length > 60)) { cur.description = line; }
      else if (line.length <= 80 && !isBullet(line)) { projects.push(cur); cur = { name: line, description: null, date_range: null }; }
    }
    if (cur && cur.name) projects.push(cur);
  }

  // ── Contact info ──────────────────────────────────────────────────────

  let contactInfo = null;
  {
    let email = null, phone = null, website = null;
    for (const a of document.querySelectorAll("a[href]")) {
      const href = a.getAttribute("href") || "";
      if (!email && href.startsWith("mailto:")) email = href.replace("mailto:", "").split("?")[0];
      else if (!phone && href.startsWith("tel:")) phone = href.replace("tel:", "");
      else if (!website && /^https?:\/\//.test(href) && !href.includes("linkedin.com") && !href.includes("google.com") && a.textContent.trim().length > 3) {
        website = href;
      }
    }
    if (email || phone || website) contactInfo = { email, phone, website };
  }

  // ── Open to Work ──────────────────────────────────────────────────────

  let openToWork = false;
  if (/open to work/i.test(document.body.innerText?.substring(0, 3000) || "")) openToWork = true;

  // ── Recommendations count ─────────────────────────────────────────────

  let recommendationsCount = null;
  const recSection = findSection("Recommendation");
  if (recSection) {
    const lines = getSectionLines(recSection).filter((l) => !/^recommendation/i.test(l));
    if (lines.length > 0) recommendationsCount = Math.max(1, Math.floor(lines.length / 3));
  }

  // ── Extraction quality score ─────────────────────────────────────────

  const _extraction_quality = (
    (name ? 0.20 : 0) +
    (headline ? 0.10 : 0) +
    (location ? 0.05 : 0) +
    (experienceEntries.length > 0 ? 0.25 : 0) +
    (educationEntries.length > 0 ? 0.15 : 0) +
    (skills.length > 0 ? 0.15 : 0) +
    (about ? 0.05 : 0) +
    (window.location.href.includes("linkedin.com/in/") ? 0.05 : 0)
  );

  // ── Return ────────────────────────────────────────────────────────────

  return {
    name, headline, location,
    linkedin_url: window.location.href.split("?")[0],
    photo_url: photoUrl,
    current_company: currentCompany,
    experience: experienceEntries,
    education: educationEntries,
    skills, about, certifications, volunteer, publications, projects,
    contact_info: contactInfo,
    open_to_work: openToWork,
    recommendations_count: recommendationsCount,
    _version: EXTRACTOR_VERSION,
    _extraction_quality: Math.round(_extraction_quality * 100) / 100,
    _debug,
  };
}

// ── Scroll + wait for content to load ─────────────────────────────────

async function scrollToLoadAll() {
  // Wait for initial page to settle
  await new Promise((r) => setTimeout(r, 2000));

  // LinkedIn may use document.documentElement or body for scroll height
  function getScrollHeight() {
    return Math.max(
      document.body.scrollHeight || 0,
      document.documentElement.scrollHeight || 0,
    );
  }

  const step = Math.max(400, Math.floor(window.innerHeight * 0.6));

  // First pass — slow scroll to trigger lazy loading
  let prevHeight = 0;
  for (let pass = 0; pass < 3; pass++) {
    const height = getScrollHeight();
    if (pass > 0 && height <= prevHeight) break; // no new content loaded
    prevHeight = height;

    for (let pos = 0; pos <= height + step; pos += step) {
      window.scrollTo({ top: pos, behavior: "instant" });
      await new Promise((r) => setTimeout(r, pass === 0 ? 800 : 400));
    }
    window.scrollTo({ top: height, behavior: "instant" });
    await new Promise((r) => setTimeout(r, 1200));
  }

  // Click "see more" / "show all" buttons to expand ALL sections
  async function clickExpandButtons() {
    const btns = document.querySelectorAll(
      'button, [role="button"], a.optional-action-target-wrapper'
    );
    let clicked = 0;
    for (const btn of btns) {
      const txt = (btn.textContent || "").trim().toLowerCase();
      if (
        txt === "see more" ||
        txt === "...see more" ||
        txt === "\u2026see more" ||
        /^show all \d/i.test(txt) ||
        /^show all \w/i.test(txt) ||
        txt.startsWith("show all ") ||
        txt === "show more" ||
        txt === "show credentials"
      ) {
        try {
          btn.scrollIntoView({ block: "center" });
          await new Promise((r) => setTimeout(r, 100));
          btn.click();
          clicked++;
          await new Promise((r) => setTimeout(r, 400));
        } catch {}
      }
    }
    return clicked;
  }

  // Click expand buttons in multiple rounds (clicking one may reveal more)
  for (let round = 0; round < 3; round++) {
    const clicked = await clickExpandButtons();
    if (clicked === 0) break;
    await new Promise((r) => setTimeout(r, 800));
    // Re-scroll after expanding to catch newly revealed content
    const h = getScrollHeight();
    for (let pos = 0; pos <= h + step; pos += step) {
      window.scrollTo({ top: pos, behavior: "instant" });
      await new Promise((r) => setTimeout(r, 200));
    }
  }

  // Wait for sections to appear (up to 5 seconds)
  for (let attempt = 0; attempt < 5; attempt++) {
    const sections = document.querySelectorAll("section");
    let found = false;
    for (const s of sections) {
      const h = s.querySelector("h2, h3, h4");
      if (h && /experience|education|skill/i.test(h.textContent || "")) { found = true; break; }
    }
    // Also check for keyword text anywhere
    if (!found) {
      const bodyText = document.body.innerText || "";
      if (/\nExperience\n/i.test(bodyText) && bodyText.length > 2000) found = true;
    }
    if (found) break;
    await new Promise((r) => setTimeout(r, 1000));
  }

  // Back to top
  window.scrollTo({ top: 0, behavior: "instant" });
  await new Promise((r) => setTimeout(r, 300));
}

// ── Message listener ──────────────────────────────────────────────────

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message.action === "extractProfile") {
    scrollToLoadAll()
      .then(() => {
        const data = extractProfile();
        sendResponse({ success: true, data });
      })
      .catch((err) => {
        sendResponse({ success: false, error: err.message });
      });
  }
  return true;
});
