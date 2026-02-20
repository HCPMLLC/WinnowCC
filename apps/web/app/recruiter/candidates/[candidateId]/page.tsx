"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import IntroductionRequestModal from "../../../components/IntroductionRequestModal";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

interface ExperienceEntry {
  title?: string;
  company?: string;
  start_date?: string;
  end_date?: string;
  date_range?: string; // Chrome extension format
  description?: string;
  location?: string;
  job_location?: string;
  duties?: string[];
  quantified_accomplishments?: string[];
  skills_used?: string[];
  technologies_used?: string[];
}

interface EducationEntry {
  school?: string;
  degree?: string;
  field?: string;
  start_date?: string;
  end_date?: string;
  date_range?: string;
}

interface CertEntry {
  name?: string;
  issuing_org?: string;
  date?: string;
}

interface VolunteerEntry {
  role?: string;
  organization?: string;
  start_date?: string;
  end_date?: string;
  date_range?: string;
}

interface PublicationEntry {
  title?: string;
  publisher?: string;
  date?: string;
}

interface ProjectEntry {
  name?: string;
  description?: string;
  start_date?: string;
  end_date?: string;
  date_range?: string;
}

interface ContactInfo {
  email?: string;
  phone?: string;
  website?: string;
}

interface ProfileJson {
  name?: string;
  headline?: string;
  location?: string;
  current_company?: string;
  about?: string;
  linkedin_url?: string;
  source?: string;
  open_to_work?: boolean;
  recommendations_count?: number;
  experience?: ExperienceEntry[];
  education?: EducationEntry[];
  skills?: (string | { name?: string; endorsements?: number })[];
  certifications?: CertEntry[];
  volunteer?: VolunteerEntry[];
  publications?: PublicationEntry[];
  projects?: ProjectEntry[];
  contact_info?: ContactInfo;
  notes?: string;
  // Resume-parsed profile fields
  professional_summary?: string;
  sourced_by_user_id?: number;
  // basics fallback (from parsed profiles)
  basics?: Record<string, unknown>;
}

interface CandidateDetail {
  candidate_profile_id: number;
  profile_json: ProfileJson;
  created_at: string | null;
  updated_at: string | null;
}

const inputCls =
  "w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500";

function skillName(s: string | { name?: string; endorsements?: number }): string {
  return typeof s === "string" ? s : s.name || "";
}

function skillEndorsements(s: string | { name?: string; endorsements?: number }): number | null {
  return typeof s === "object" && s.endorsements ? s.endorsements : null;
}

function dateDisplay(entry: { start_date?: string; end_date?: string; date_range?: string }): string | null {
  if (entry.date_range) return entry.date_range;
  if (entry.start_date || entry.end_date) return `${entry.start_date || "?"} – ${entry.end_date || "Present"}`;
  return null;
}

const EMPTY_EXPERIENCE: ExperienceEntry = { title: "", company: "", start_date: "", end_date: "", description: "", location: "" };
const EMPTY_EDUCATION: EducationEntry = { school: "", degree: "", field: "", start_date: "", end_date: "" };
const EMPTY_CERT: CertEntry = { name: "", issuing_org: "", date: "" };
const EMPTY_VOLUNTEER: VolunteerEntry = { role: "", organization: "", start_date: "", end_date: "" };
const EMPTY_PUBLICATION: PublicationEntry = { title: "", publisher: "", date: "" };
const EMPTY_PROJECT: ProjectEntry = { name: "", description: "", start_date: "", end_date: "" };

export default function CandidateDetailPage() {
  const params = useParams();
  const router = useRouter();
  const candidateId = params.candidateId as string;

  const [candidate, setCandidate] = useState<CandidateDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [saving, setSaving] = useState(false);
  const [showIntroModal, setShowIntroModal] = useState(false);
  const [introSent, setIntroSent] = useState(false);

  // Form state
  const [form, setForm] = useState({
    name: "",
    headline: "",
    location: "",
    current_company: "",
    about: "",
    open_to_work: false,
    recommendations_count: 0,
    notes: "",
  });
  const [contactInfo, setContactInfo] = useState<ContactInfo>({ email: "", phone: "", website: "" });
  const [experience, setExperience] = useState<ExperienceEntry[]>([]);
  const [education, setEducation] = useState<EducationEntry[]>([]);
  const [skills, setSkills] = useState("");
  const [certifications, setCertifications] = useState<CertEntry[]>([]);
  const [volunteer, setVolunteer] = useState<VolunteerEntry[]>([]);
  const [publications, setPublications] = useState<PublicationEntry[]>([]);
  const [projects, setProjects] = useState<ProjectEntry[]>([]);

  function populateForm(pj: ProfileJson) {
    const basics = pj.basics || {};
    setForm({
      name: pj.name || (basics.name as string) || "",
      headline: pj.headline || "",
      location: pj.location || (basics.location as string) || "",
      current_company: pj.current_company || "",
      about: pj.about || pj.professional_summary || "",
      open_to_work: pj.open_to_work || false,
      recommendations_count: pj.recommendations_count || 0,
      notes: pj.notes || "",
    });
    setContactInfo(pj.contact_info || { email: "", phone: "", website: "" });
    // Normalize date_range to start_date for the edit form
    setExperience(
      (pj.experience || []).map((e) => ({
        ...e,
        start_date: e.start_date || e.date_range || "",
        end_date: e.end_date || "",
      }))
    );
    setEducation(
      (pj.education || []).map((e) => ({
        ...e,
        start_date: e.start_date || e.date_range || "",
        end_date: e.end_date || "",
      }))
    );
    setSkills(
      (pj.skills || []).map((s) => skillName(s)).filter(Boolean).join(", ")
    );
    setCertifications(pj.certifications?.length ? pj.certifications : []);
    setVolunteer(pj.volunteer?.length ? pj.volunteer : []);
    setPublications(pj.publications?.length ? pj.publications : []);
    setProjects(pj.projects?.length ? pj.projects : []);
  }

  useEffect(() => {
    if (!candidateId) return;
    fetch(`${API_BASE}/api/recruiter/candidates/${candidateId}`, { credentials: "include" })
      .then((r) => (r.ok ? r.json() : null))
      .then((data: CandidateDetail | null) => {
        setCandidate(data);
        if (data) populateForm(data.profile_json);
      })
      .finally(() => setLoading(false));
  }, [candidateId]);

  function startEditing() {
    if (candidate) populateForm(candidate.profile_json);
    setEditing(true);
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);

    const body: Record<string, unknown> = {};
    if (form.name) body.name = form.name;
    if (form.headline) body.headline = form.headline;
    body.location = form.location;
    body.current_company = form.current_company;
    body.about = form.about;
    body.open_to_work = form.open_to_work;
    body.recommendations_count = form.recommendations_count;
    body.notes = form.notes;

    const ci: ContactInfo = {};
    if (contactInfo.email) ci.email = contactInfo.email;
    if (contactInfo.phone) ci.phone = contactInfo.phone;
    if (contactInfo.website) ci.website = contactInfo.website;
    if (Object.keys(ci).length) body.contact_info = ci;

    if (experience.length > 0) {
      body.experience = experience.filter((x) => x.title || x.company);
    }
    if (education.length > 0) {
      body.education = education.filter((x) => x.school || x.degree);
    }
    if (skills.trim()) {
      body.skills = skills.split(",").map((s) => s.trim()).filter(Boolean);
    }
    if (certifications.length > 0) {
      body.certifications = certifications.filter((x) => x.name);
    }
    if (volunteer.length > 0) {
      body.volunteer = volunteer.filter((x) => x.role || x.organization);
    }
    if (publications.length > 0) {
      body.publications = publications.filter((x) => x.title);
    }
    if (projects.length > 0) {
      body.projects = projects.filter((x) => x.name);
    }

    try {
      const res = await fetch(`${API_BASE}/api/recruiter/candidates/${candidateId}`, {
        method: "PUT",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (res.ok) {
        const updated = await res.json();
        setCandidate({
          candidate_profile_id: updated.candidate_profile_id,
          profile_json: updated.profile_json,
          created_at: candidate?.created_at || null,
          updated_at: new Date().toISOString(),
        });
        populateForm(updated.profile_json);
        setEditing(false);
      }
    } catch {
      /* ignore */
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-sm text-slate-500">Loading candidate...</div>
      </div>
    );
  }

  if (!candidate) {
    return (
      <div className="py-20 text-center">
        <h2 className="text-xl font-semibold text-slate-900">Candidate not found</h2>
        <button onClick={() => router.back()} className="mt-4 inline-block text-sm text-slate-600 hover:text-slate-900">
          &larr; Go Back
        </button>
      </div>
    );
  }

  const pj = candidate.profile_json;
  const basics = pj.basics || {};
  const displayName = pj.name || (basics.name as string) || "Unknown";
  const displayLocation = pj.location || (basics.location as string) || "";
  const displayAbout = pj.about || pj.professional_summary || "";
  const displaySkills = pj.skills || [];
  const displayExperience = pj.experience || [];
  const displayEducation = pj.education || [];
  const displayCerts = pj.certifications || [];
  const displayVolunteer = pj.volunteer || [];
  const displayPubs = pj.publications || [];
  const displayProjects = pj.projects || [];
  const displayContact = pj.contact_info || {};
  const displayNotes = pj.notes || "";
  const isPlatformCandidate = !pj.source && !pj.sourced_by_user_id;

  // Derive headline and current company from experience if not set at top level
  const firstExp = displayExperience.length > 0 ? displayExperience[0] : null;
  const displayHeadline = pj.headline || (
    firstExp ? [firstExp.title, firstExp.company].filter(Boolean).join(" at ") : ""
  );
  const displayCompany = pj.current_company || (firstExp?.company ?? "");
  const displaySource = isPlatformCandidate ? "Winnowcc.ai" : (pj.source || "Unknown");

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <button onClick={() => router.back()} className="mb-2 inline-block text-sm text-slate-500 hover:text-slate-700">
            &larr; Back
          </button>
          <h1 className="text-3xl font-bold text-slate-900">{displayName}</h1>
          <div className="mt-1 flex flex-wrap items-center gap-3 text-sm text-slate-500">
            {displayHeadline && <span>{displayHeadline}</span>}
            {displayLocation && <span>{displayLocation}</span>}
            {pj.open_to_work && (
              <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-800">
                Open to Work
              </span>
            )}
            {pj.source === "linkedin_extension" && (
              <span className="rounded-full bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-700">
                LinkedIn
              </span>
            )}
            {isPlatformCandidate && (
              <span className="rounded-full bg-indigo-50 px-2 py-0.5 text-xs font-medium text-indigo-700">
                Winnowcc.ai
              </span>
            )}
          </div>
          {pj.linkedin_url && (
            <a
              href={pj.linkedin_url}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-1 inline-block text-sm text-blue-600 hover:underline"
            >
              View LinkedIn Profile
            </a>
          )}
        </div>
        <div className="flex items-center gap-2">
          {!editing && !introSent && isPlatformCandidate && (
            <button
              onClick={() => setShowIntroModal(true)}
              className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800"
            >
              Request Introduction
            </button>
          )}
          {introSent && (
            <span className="rounded-md bg-emerald-50 px-4 py-2 text-sm font-medium text-emerald-700">
              Introduction Sent
            </span>
          )}
          <button
            onClick={() => (editing ? setEditing(false) : startEditing())}
            className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            {editing ? "Cancel" : "Edit"}
          </button>
        </div>
      </div>

      {showIntroModal && candidate && (
        <IntroductionRequestModal
          candidateProfileId={candidate.candidate_profile_id}
          candidateName={pj.name || (basics.name as string) || `Candidate ${candidateId}`}
          onClose={() => setShowIntroModal(false)}
          onSuccess={() => {
            setShowIntroModal(false);
            setIntroSent(true);
          }}
        />
      )}

      {editing ? (
        /* ======================== EDIT MODE ======================== */
        <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="mb-4 text-lg font-semibold text-slate-900">Edit Candidate</h2>
          <form onSubmit={handleSave} className="space-y-5">
            {/* Basic fields */}
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">Name</label>
                <input type="text" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} className={inputCls} />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">Headline</label>
                <input type="text" value={form.headline} onChange={(e) => setForm({ ...form, headline: e.target.value })} className={inputCls} />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">Location</label>
                <input type="text" value={form.location} onChange={(e) => setForm({ ...form, location: e.target.value })} className={inputCls} />
              </div>
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">Current Company</label>
                <input type="text" value={form.current_company} onChange={(e) => setForm({ ...form, current_company: e.target.value })} className={inputCls} />
              </div>
            </div>

            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">About</label>
              <textarea value={form.about} onChange={(e) => setForm({ ...form, about: e.target.value })} rows={4} className={inputCls} />
            </div>

            <div className="grid gap-4 sm:grid-cols-3">
              <label className="flex items-center gap-2 text-sm text-slate-700">
                <input
                  type="checkbox"
                  checked={form.open_to_work}
                  onChange={(e) => setForm({ ...form, open_to_work: e.target.checked })}
                  className="rounded border-slate-300"
                />
                Open to Work
              </label>
              <div>
                <label className="mb-1 block text-sm font-medium text-slate-700">Recommendations</label>
                <input
                  type="number"
                  min={0}
                  value={form.recommendations_count}
                  onChange={(e) => setForm({ ...form, recommendations_count: parseInt(e.target.value) || 0 })}
                  className={inputCls}
                />
              </div>
            </div>

            {/* Contact Info */}
            <div>
              <label className="mb-2 block text-sm font-medium text-slate-700">Contact Info</label>
              <div className="grid gap-4 sm:grid-cols-3">
                <input type="email" placeholder="Email" value={contactInfo.email || ""} onChange={(e) => setContactInfo({ ...contactInfo, email: e.target.value })} className={inputCls} />
                <input type="tel" placeholder="Phone" value={contactInfo.phone || ""} onChange={(e) => setContactInfo({ ...contactInfo, phone: e.target.value })} className={inputCls} />
                <input type="url" placeholder="Website" value={contactInfo.website || ""} onChange={(e) => setContactInfo({ ...contactInfo, website: e.target.value })} className={inputCls} />
              </div>
            </div>

            {/* Skills */}
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">Skills (comma-separated)</label>
              <input type="text" value={skills} onChange={(e) => setSkills(e.target.value)} className={inputCls} placeholder="Python, React, SQL..." />
            </div>

            {/* Experience */}
            <div>
              <div className="mb-2 flex items-center justify-between">
                <label className="text-sm font-medium text-slate-700">Experience</label>
                <button type="button" onClick={() => setExperience([...experience, { ...EMPTY_EXPERIENCE }])} className="flex items-center gap-1 rounded-md border border-slate-300 px-2 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50">
                  <span className="text-base leading-none">+</span> Add
                </button>
              </div>
              <div className="space-y-3">
                {experience.map((exp, idx) => (
                  <div key={idx} className="rounded-md border border-slate-200 p-3 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-medium text-slate-500">Experience {idx + 1}</span>
                      <button type="button" onClick={() => setExperience(experience.filter((_, i) => i !== idx))} className="text-slate-400 hover:text-red-500">
                        <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
                      </button>
                    </div>
                    <div className="grid gap-2 sm:grid-cols-2">
                      <input type="text" placeholder="Title" value={exp.title || ""} onChange={(e) => { const u = [...experience]; u[idx] = { ...u[idx], title: e.target.value }; setExperience(u); }} className={inputCls} />
                      <input type="text" placeholder="Company" value={exp.company || ""} onChange={(e) => { const u = [...experience]; u[idx] = { ...u[idx], company: e.target.value }; setExperience(u); }} className={inputCls} />
                      <input type="text" placeholder="Start date" value={exp.start_date || ""} onChange={(e) => { const u = [...experience]; u[idx] = { ...u[idx], start_date: e.target.value }; setExperience(u); }} className={inputCls} />
                      <input type="text" placeholder="End date" value={exp.end_date || ""} onChange={(e) => { const u = [...experience]; u[idx] = { ...u[idx], end_date: e.target.value }; setExperience(u); }} className={inputCls} />
                    </div>
                    <textarea placeholder="Description" value={exp.description || ""} onChange={(e) => { const u = [...experience]; u[idx] = { ...u[idx], description: e.target.value }; setExperience(u); }} rows={2} className={inputCls} />
                  </div>
                ))}
              </div>
            </div>

            {/* Education */}
            <div>
              <div className="mb-2 flex items-center justify-between">
                <label className="text-sm font-medium text-slate-700">Education</label>
                <button type="button" onClick={() => setEducation([...education, { ...EMPTY_EDUCATION }])} className="flex items-center gap-1 rounded-md border border-slate-300 px-2 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50">
                  <span className="text-base leading-none">+</span> Add
                </button>
              </div>
              <div className="space-y-3">
                {education.map((edu, idx) => (
                  <div key={idx} className="rounded-md border border-slate-200 p-3 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-medium text-slate-500">Education {idx + 1}</span>
                      <button type="button" onClick={() => setEducation(education.filter((_, i) => i !== idx))} className="text-slate-400 hover:text-red-500">
                        <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
                      </button>
                    </div>
                    <div className="grid gap-2 sm:grid-cols-2">
                      <input type="text" placeholder="School" value={edu.school || ""} onChange={(e) => { const u = [...education]; u[idx] = { ...u[idx], school: e.target.value }; setEducation(u); }} className={inputCls} />
                      <input type="text" placeholder="Degree" value={edu.degree || ""} onChange={(e) => { const u = [...education]; u[idx] = { ...u[idx], degree: e.target.value }; setEducation(u); }} className={inputCls} />
                      <input type="text" placeholder="Start date" value={edu.start_date || ""} onChange={(e) => { const u = [...education]; u[idx] = { ...u[idx], start_date: e.target.value }; setEducation(u); }} className={inputCls} />
                      <input type="text" placeholder="End date" value={edu.end_date || ""} onChange={(e) => { const u = [...education]; u[idx] = { ...u[idx], end_date: e.target.value }; setEducation(u); }} className={inputCls} />
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Certifications */}
            <div>
              <div className="mb-2 flex items-center justify-between">
                <label className="text-sm font-medium text-slate-700">Certifications</label>
                <button type="button" onClick={() => setCertifications([...certifications, { ...EMPTY_CERT }])} className="flex items-center gap-1 rounded-md border border-slate-300 px-2 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50">
                  <span className="text-base leading-none">+</span> Add
                </button>
              </div>
              <div className="space-y-2">
                {certifications.map((cert, idx) => (
                  <div key={idx} className="flex items-center gap-2">
                    <input type="text" placeholder="Certification Name" value={cert.name || ""} onChange={(e) => { const u = [...certifications]; u[idx] = { ...u[idx], name: e.target.value }; setCertifications(u); }} className={`${inputCls} flex-1 min-w-[10rem]`} />
                    <input type="text" placeholder="Issuing Organization" value={cert.issuing_org || ""} onChange={(e) => { const u = [...certifications]; u[idx] = { ...u[idx], issuing_org: e.target.value }; setCertifications(u); }} className={`${inputCls} flex-1 min-w-[11rem]`} />
                    <input type="text" placeholder="Expiry Date" value={cert.date || ""} onChange={(e) => { const u = [...certifications]; u[idx] = { ...u[idx], date: e.target.value }; setCertifications(u); }} className={`${inputCls} w-36`} />
                    <button type="button" onClick={() => setCertifications(certifications.filter((_, i) => i !== idx))} className="flex-shrink-0 text-slate-400 hover:text-red-500">
                      <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
                    </button>
                  </div>
                ))}
              </div>
            </div>

            {/* Volunteer */}
            <div>
              <div className="mb-2 flex items-center justify-between">
                <label className="text-sm font-medium text-slate-700">Volunteer</label>
                <button type="button" onClick={() => setVolunteer([...volunteer, { ...EMPTY_VOLUNTEER }])} className="flex items-center gap-1 rounded-md border border-slate-300 px-2 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50">
                  <span className="text-base leading-none">+</span> Add
                </button>
              </div>
              <div className="space-y-2">
                {volunteer.map((vol, idx) => (
                  <div key={idx} className="flex items-center gap-2">
                    <input type="text" placeholder="Role" value={vol.role || ""} onChange={(e) => { const u = [...volunteer]; u[idx] = { ...u[idx], role: e.target.value }; setVolunteer(u); }} className={`${inputCls} flex-1`} />
                    <input type="text" placeholder="Organization" value={vol.organization || ""} onChange={(e) => { const u = [...volunteer]; u[idx] = { ...u[idx], organization: e.target.value }; setVolunteer(u); }} className={`${inputCls} flex-1`} />
                    <input type="text" placeholder="Start" value={vol.start_date || ""} onChange={(e) => { const u = [...volunteer]; u[idx] = { ...u[idx], start_date: e.target.value }; setVolunteer(u); }} className={`${inputCls} w-28`} />
                    <input type="text" placeholder="End" value={vol.end_date || ""} onChange={(e) => { const u = [...volunteer]; u[idx] = { ...u[idx], end_date: e.target.value }; setVolunteer(u); }} className={`${inputCls} w-28`} />
                    <button type="button" onClick={() => setVolunteer(volunteer.filter((_, i) => i !== idx))} className="flex-shrink-0 text-slate-400 hover:text-red-500">
                      <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
                    </button>
                  </div>
                ))}
              </div>
            </div>

            {/* Publications */}
            <div>
              <div className="mb-2 flex items-center justify-between">
                <label className="text-sm font-medium text-slate-700">Publications</label>
                <button type="button" onClick={() => setPublications([...publications, { ...EMPTY_PUBLICATION }])} className="flex items-center gap-1 rounded-md border border-slate-300 px-2 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50">
                  <span className="text-base leading-none">+</span> Add
                </button>
              </div>
              <div className="space-y-2">
                {publications.map((pub, idx) => (
                  <div key={idx} className="flex items-center gap-2">
                    <input type="text" placeholder="Title" value={pub.title || ""} onChange={(e) => { const u = [...publications]; u[idx] = { ...u[idx], title: e.target.value }; setPublications(u); }} className={`${inputCls} flex-1`} />
                    <input type="text" placeholder="Publisher" value={pub.publisher || ""} onChange={(e) => { const u = [...publications]; u[idx] = { ...u[idx], publisher: e.target.value }; setPublications(u); }} className={`${inputCls} flex-1`} />
                    <input type="text" placeholder="Date" value={pub.date || ""} onChange={(e) => { const u = [...publications]; u[idx] = { ...u[idx], date: e.target.value }; setPublications(u); }} className={`${inputCls} w-32`} />
                    <button type="button" onClick={() => setPublications(publications.filter((_, i) => i !== idx))} className="flex-shrink-0 text-slate-400 hover:text-red-500">
                      <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
                    </button>
                  </div>
                ))}
              </div>
            </div>

            {/* Projects */}
            <div>
              <div className="mb-2 flex items-center justify-between">
                <label className="text-sm font-medium text-slate-700">Projects</label>
                <button type="button" onClick={() => setProjects([...projects, { ...EMPTY_PROJECT }])} className="flex items-center gap-1 rounded-md border border-slate-300 px-2 py-1 text-xs font-medium text-slate-600 hover:bg-slate-50">
                  <span className="text-base leading-none">+</span> Add
                </button>
              </div>
              <div className="space-y-3">
                {projects.map((proj, idx) => (
                  <div key={idx} className="rounded-md border border-slate-200 p-3 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-medium text-slate-500">Project {idx + 1}</span>
                      <button type="button" onClick={() => setProjects(projects.filter((_, i) => i !== idx))} className="text-slate-400 hover:text-red-500">
                        <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
                      </button>
                    </div>
                    <div className="grid gap-2 sm:grid-cols-2">
                      <input type="text" placeholder="Name" value={proj.name || ""} onChange={(e) => { const u = [...projects]; u[idx] = { ...u[idx], name: e.target.value }; setProjects(u); }} className={inputCls} />
                      <div className="flex gap-2">
                        <input type="text" placeholder="Start" value={proj.start_date || ""} onChange={(e) => { const u = [...projects]; u[idx] = { ...u[idx], start_date: e.target.value }; setProjects(u); }} className={inputCls} />
                        <input type="text" placeholder="End" value={proj.end_date || ""} onChange={(e) => { const u = [...projects]; u[idx] = { ...u[idx], end_date: e.target.value }; setProjects(u); }} className={inputCls} />
                      </div>
                    </div>
                    <textarea placeholder="Description" value={proj.description || ""} onChange={(e) => { const u = [...projects]; u[idx] = { ...u[idx], description: e.target.value }; setProjects(u); }} rows={2} className={inputCls} />
                  </div>
                ))}
              </div>
            </div>

            {/* Notes */}
            <div>
              <label className="mb-1 block text-sm font-medium text-slate-700">Recruiter Notes</label>
              <textarea value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} rows={3} className={inputCls} placeholder="Add private notes about this candidate..." />
            </div>

            <div className="flex justify-end gap-3">
              <button type="button" onClick={() => setEditing(false)} className="rounded-md border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50">
                Cancel
              </button>
              <button type="submit" disabled={saving} className="rounded-md bg-slate-900 px-4 py-2 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50">
                {saving ? "Saving..." : "Save Changes"}
              </button>
            </div>
          </form>
        </div>
      ) : (
        /* ======================== READ-ONLY VIEW ======================== */
        <div className="space-y-4">
          {/* Summary Card */}
          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
            <h2 className="mb-3 text-lg font-semibold text-slate-900">Summary</h2>
            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <h3 className="text-sm font-medium text-slate-500">Headline</h3>
                <p className="mt-0.5 text-sm text-slate-700">{displayHeadline || <span className="italic text-slate-400">Not provided</span>}</p>
              </div>
              <div>
                <h3 className="text-sm font-medium text-slate-500">Location</h3>
                <p className="mt-0.5 text-sm text-slate-700">{displayLocation || <span className="italic text-slate-400">Not provided</span>}</p>
              </div>
              <div>
                <h3 className="text-sm font-medium text-slate-500">Current Company</h3>
                <p className="mt-0.5 text-sm text-slate-700">{displayCompany || <span className="italic text-slate-400">Not provided</span>}</p>
              </div>
              <div>
                <h3 className="text-sm font-medium text-slate-500">Source</h3>
                <p className="mt-0.5 text-sm text-slate-700">{displaySource}</p>
              </div>
            </div>
          </div>

          {/* About */}
          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
            <h2 className="mb-2 text-lg font-semibold text-slate-900">About</h2>
            {displayAbout ? (
              <p className="whitespace-pre-wrap text-sm text-slate-700">{displayAbout}</p>
            ) : (
              <p className="text-sm italic text-slate-400">Not provided</p>
            )}
          </div>

          {/* Experience */}
          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
            <h2 className="mb-3 text-lg font-semibold text-slate-900">Experience</h2>
            {displayExperience.length > 0 ? (
              <div className="space-y-4">
                {displayExperience.map((exp, idx) => {
                  const dates = dateDisplay(exp);
                  const loc = exp.job_location || exp.location;
                  const bullets = exp.duties || [];
                  const accomplishments = exp.quantified_accomplishments || [];
                  return (
                    <div key={idx} className="border-l-2 border-slate-200 pl-4">
                      <p className="text-sm font-medium text-slate-900">{exp.title}</p>
                      {exp.company && <p className="text-sm text-slate-600">{exp.company}</p>}
                      <div className="flex flex-wrap items-center gap-x-3 text-xs text-slate-500">
                        {dates && <span>{dates}</span>}
                        {loc && <span>{loc}</span>}
                      </div>
                      {exp.description && <p className="mt-1 whitespace-pre-wrap text-sm text-slate-600">{exp.description}</p>}
                      {bullets.length > 0 && (
                        <ul className="mt-1.5 list-disc space-y-0.5 pl-4 text-sm text-slate-600">
                          {bullets.map((b, bi) => <li key={bi}>{b}</li>)}
                        </ul>
                      )}
                      {accomplishments.length > 0 && (
                        <ul className="mt-1 list-disc space-y-0.5 pl-4 text-sm text-slate-600">
                          {accomplishments.map((a, ai) => <li key={ai}>{a}</li>)}
                        </ul>
                      )}
                      {exp.skills_used && exp.skills_used.length > 0 && (
                        <div className="mt-1.5 flex flex-wrap gap-1">
                          {exp.skills_used.map((s) => (
                            <span key={s} className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-500">{s}</span>
                          ))}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            ) : (
              <p className="text-sm italic text-slate-400">Not provided</p>
            )}
          </div>

          {/* Education */}
          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
            <h2 className="mb-3 text-lg font-semibold text-slate-900">Education</h2>
            {displayEducation.length > 0 ? (
              <div className="space-y-3">
                {displayEducation.map((edu, idx) => {
                  const dates = dateDisplay(edu);
                  return (
                    <div key={idx} className="border-l-2 border-slate-200 pl-4">
                      <p className="text-sm font-medium text-slate-900">{edu.school}</p>
                      {(edu.degree || edu.field) && (
                        <p className="text-sm text-slate-600">{[edu.degree, edu.field].filter(Boolean).join(", ")}</p>
                      )}
                      {dates && <p className="text-xs text-slate-500">{dates}</p>}
                    </div>
                  );
                })}
              </div>
            ) : (
              <p className="text-sm italic text-slate-400">Not provided</p>
            )}
          </div>

          {/* Skills */}
          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
            <h2 className="mb-3 text-lg font-semibold text-slate-900">Skills</h2>
            {displaySkills.length > 0 ? (
              <div className="flex flex-wrap gap-2">
                {displaySkills.map((s, idx) => {
                  const name = skillName(s);
                  const endorsements = skillEndorsements(s);
                  return (
                    <span key={idx} className="rounded-full bg-slate-100 px-3 py-1 text-sm text-slate-700">
                      {name}
                      {endorsements != null && endorsements > 0 && (
                        <span className="ml-1 text-xs text-slate-400">({endorsements})</span>
                      )}
                    </span>
                  );
                })}
              </div>
            ) : (
              <p className="text-sm italic text-slate-400">Not provided</p>
            )}
          </div>

          {/* Certifications */}
          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
            <h2 className="mb-3 text-lg font-semibold text-slate-900">Certifications</h2>
            {displayCerts.length > 0 ? (
              <div className="space-y-2">
                {displayCerts.map((cert, idx) => (
                  <div key={idx} className="text-sm">
                    <span className="font-medium text-slate-900">{cert.name}</span>
                    {cert.issuing_org && <span className="text-slate-500"> &middot; {cert.issuing_org}</span>}
                    {cert.date && <span className="text-slate-400"> &middot; {cert.date}</span>}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm italic text-slate-400">Not provided</p>
            )}
          </div>

          {/* Volunteer */}
          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
            <h2 className="mb-3 text-lg font-semibold text-slate-900">Volunteer</h2>
            {displayVolunteer.length > 0 ? (
              <div className="space-y-2">
                {displayVolunteer.map((vol, idx) => {
                  const dates = dateDisplay(vol);
                  return (
                    <div key={idx} className="border-l-2 border-slate-200 pl-4">
                      <p className="text-sm font-medium text-slate-900">{vol.role}</p>
                      {vol.organization && <p className="text-sm text-slate-600">{vol.organization}</p>}
                      {dates && <p className="text-xs text-slate-500">{dates}</p>}
                    </div>
                  );
                })}
              </div>
            ) : (
              <p className="text-sm italic text-slate-400">Not provided</p>
            )}
          </div>

          {/* Publications */}
          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
            <h2 className="mb-3 text-lg font-semibold text-slate-900">Publications</h2>
            {displayPubs.length > 0 ? (
              <div className="space-y-2">
                {displayPubs.map((pub, idx) => (
                  <div key={idx} className="text-sm">
                    <span className="font-medium text-slate-900">{pub.title}</span>
                    {pub.publisher && <span className="text-slate-500"> &middot; {pub.publisher}</span>}
                    {pub.date && <span className="text-slate-400"> &middot; {pub.date}</span>}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm italic text-slate-400">Not provided</p>
            )}
          </div>

          {/* Projects */}
          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
            <h2 className="mb-3 text-lg font-semibold text-slate-900">Projects</h2>
            {displayProjects.length > 0 ? (
              <div className="space-y-3">
                {displayProjects.map((proj, idx) => {
                  const dates = dateDisplay(proj);
                  return (
                    <div key={idx} className="border-l-2 border-slate-200 pl-4">
                      <p className="text-sm font-medium text-slate-900">{proj.name}</p>
                      {dates && <p className="text-xs text-slate-500">{dates}</p>}
                      {proj.description && <p className="mt-1 whitespace-pre-wrap text-sm text-slate-600">{proj.description}</p>}
                    </div>
                  );
                })}
              </div>
            ) : (
              <p className="text-sm italic text-slate-400">Not provided</p>
            )}
          </div>

          {/* Contact Info */}
          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
            <h2 className="mb-3 text-lg font-semibold text-slate-900">Contact Info</h2>
            {(displayContact.email || displayContact.phone || displayContact.website) ? (
              <div className="grid gap-4 sm:grid-cols-3">
                <div>
                  <h3 className="text-sm font-medium text-slate-500">Email</h3>
                  <p className="mt-0.5 text-sm text-slate-700">{displayContact.email || <span className="italic text-slate-400">Not provided</span>}</p>
                </div>
                <div>
                  <h3 className="text-sm font-medium text-slate-500">Phone</h3>
                  <p className="mt-0.5 text-sm text-slate-700">{displayContact.phone || <span className="italic text-slate-400">Not provided</span>}</p>
                </div>
                <div>
                  <h3 className="text-sm font-medium text-slate-500">Website</h3>
                  {displayContact.website ? (
                    <a href={displayContact.website} target="_blank" rel="noopener noreferrer" className="mt-0.5 text-sm text-blue-600 hover:underline">{displayContact.website}</a>
                  ) : (
                    <p className="mt-0.5 text-sm italic text-slate-400">Not provided</p>
                  )}
                </div>
              </div>
            ) : (
              <p className="text-sm italic text-slate-400">Not provided</p>
            )}
          </div>

          {/* Recommendations */}
          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
            <h2 className="mb-2 text-lg font-semibold text-slate-900">Recommendations</h2>
            {pj.recommendations_count != null && pj.recommendations_count > 0 ? (
              <p className="text-sm text-slate-700">{pj.recommendations_count} recommendation{pj.recommendations_count !== 1 ? "s" : ""}</p>
            ) : (
              <p className="text-sm italic text-slate-400">None</p>
            )}
          </div>

          {/* Notes */}
          <div className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
            <h2 className="mb-2 text-lg font-semibold text-slate-900">Recruiter Notes</h2>
            {displayNotes ? (
              <p className="whitespace-pre-wrap text-sm text-slate-700">{displayNotes}</p>
            ) : (
              <p className="text-sm italic text-slate-400">No notes added yet</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
