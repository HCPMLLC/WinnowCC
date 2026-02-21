# PROMPT 38: Two-Sided Marketplace - Frontend Employer UI

## Objective
Build all employer-facing pages: dashboard, job posting/management, candidate search, saved candidates, and analytics. Create a complete employer experience that matches the backend API from PROMPT36.

---

## Context
With the backend API complete (PROMPT36) and authentication updated (PROMPT37), we can now build the employer user interface. This includes creating jobs, searching for candidates, managing saved talent, and viewing analytics.

---

## Prerequisites
- ✅ PROMPT36 completed (backend API working)
- ✅ PROMPT37 completed (auth with role support)
- ✅ Can access `/employer` routes as employer user

---

## Page Structure Overview

```
web/app/employer/
├── layout.tsx              # Employer layout with nav
├── onboarding/
│   └── page.tsx           # Initial employer profile setup
├── dashboard/
│   └── page.tsx           # Overview with analytics
├── jobs/
│   ├── page.tsx           # Job list
│   ├── new/
│   │   └── page.tsx       # Create new job
│   └── [id]/
│       ├── page.tsx       # View/edit job
│       └── edit/
│           └── page.tsx   # Edit job form
├── candidates/
│   ├── page.tsx           # Candidate search
│   ├── saved/
│   │   └── page.tsx       # Saved candidates
│   └── [id]/
│       └── page.tsx       # Candidate profile view
└── settings/
    └── page.tsx           # Company profile, billing
```

---

## Implementation Steps

### Step 1: Create Employer Layout

**Location:** Create `web/app/employer/layout.tsx`

**Instructions:** Create layout with employer-specific navigation.

**Code:**

```typescript
import { Navigation } from '@/components/Navigation';

export default function EmployerLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen bg-gray-50">
      <Navigation />
      
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {children}
      </main>
    </div>
  );
}
```

---

### Step 2: Employer Onboarding Page

**Location:** Create `web/app/employer/onboarding/page.tsx`

**Instructions:** Initial employer profile setup after signup.

**Code:**

```typescript
'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';

export default function EmployerOnboarding() {
  const router = useRouter();
  const [formData, setFormData] = useState({
    company_name: '',
    company_size: '',
    industry: '',
    company_website: '',
    company_description: '',
  });
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  const companySizes = ['1-10', '11-50', '51-200', '201-500', '501-1000', '1000+'];

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      const token = localStorage.getItem('accessToken');
      
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/employer/profile`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(formData),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Failed to create profile');
      }

      // Profile created - go to dashboard
      router.push('/employer/dashboard');
    } catch (err: any) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="max-w-2xl mx-auto">
      <div className="bg-white rounded-lg shadow p-8">
        <h1 className="text-3xl font-bold mb-2">Welcome to Winnow!</h1>
        <p className="text-gray-600 mb-8">
          Let's set up your employer profile to get started.
        </p>

        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Company Name */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Company Name *
            </label>
            <input
              type="text"
              required
              value={formData.company_name}
              onChange={(e) => setFormData({ ...formData, company_name: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Acme Corp"
            />
          </div>

          {/* Company Size */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Company Size *
            </label>
            <select
              required
              value={formData.company_size}
              onChange={(e) => setFormData({ ...formData, company_size: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">Select size...</option>
              {companySizes.map(size => (
                <option key={size} value={size}>{size} employees</option>
              ))}
            </select>
          </div>

          {/* Industry */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Industry
            </label>
            <input
              type="text"
              value={formData.industry}
              onChange={(e) => setFormData({ ...formData, industry: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Technology"
            />
          </div>

          {/* Website */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Company Website
            </label>
            <input
              type="url"
              value={formData.company_website}
              onChange={(e) => setFormData({ ...formData, company_website: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="https://acme.com"
            />
          </div>

          {/* Description */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Company Description
            </label>
            <textarea
              value={formData.company_description}
              onChange={(e) => setFormData({ ...formData, company_description: e.target.value })}
              rows={4}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Tell candidates about your company..."
            />
          </div>

          {error && (
            <div className="text-red-600 text-sm">{error}</div>
          )}

          <button
            type="submit"
            disabled={isLoading}
            className="w-full bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 disabled:opacity-50"
          >
            {isLoading ? 'Creating profile...' : 'Complete Setup'}
          </button>
        </form>
      </div>
    </div>
  );
}
```

---

### Step 3: Employer Dashboard

**Location:** Create `web/app/employer/dashboard/page.tsx`

**Instructions:** Overview page with analytics and quick actions.

**Code:**

```typescript
'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';

interface Analytics {
  active_jobs: number;
  total_job_views: number;
  total_applications: number;
  candidate_views_this_month: number;
  candidate_views_limit: number | null;
  saved_candidates: number;
  subscription_tier: string;
  subscription_status: string;
}

export default function EmployerDashboard() {
  const [analytics, setAnalytics] = useState<Analytics | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    fetchAnalytics();
  }, []);

  async function fetchAnalytics() {
    try {
      const token = localStorage.getItem('accessToken');
      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/employer/analytics/summary`,
        {
          headers: { Authorization: `Bearer ${token}` },
        }
      );

      if (res.ok) {
        const data = await res.json();
        setAnalytics(data);
      }
    } catch (error) {
      console.error('Failed to fetch analytics:', error);
    } finally {
      setIsLoading(false);
    }
  }

  if (isLoading) {
    return <div>Loading...</div>;
  }

  return (
    <div>
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">Dashboard</h1>
        <p className="text-gray-600 mt-1">Overview of your hiring activity</p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-8">
        <StatCard
          title="Active Jobs"
          value={analytics?.active_jobs || 0}
          icon="📋"
          link="/employer/jobs"
        />
        <StatCard
          title="Total Views"
          value={analytics?.total_job_views || 0}
          icon="👁️"
        />
        <StatCard
          title="Applications"
          value={analytics?.total_applications || 0}
          icon="📨"
        />
        <StatCard
          title="Saved Candidates"
          value={analytics?.saved_candidates || 0}
          icon="⭐"
          link="/employer/candidates/saved"
        />
      </div>

      {/* Candidate Views Limit */}
      {analytics?.candidate_views_limit && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-8">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="font-medium text-blue-900">Candidate Views This Month</h3>
              <p className="text-sm text-blue-700">
                {analytics.candidate_views_this_month} / {analytics.candidate_views_limit} views used
              </p>
            </div>
            <div className="text-2xl">
              {analytics.candidate_views_this_month >= analytics.candidate_views_limit ? '⚠️' : '✅'}
            </div>
          </div>
          <div className="mt-2 bg-blue-200 rounded-full h-2">
            <div
              className="bg-blue-600 h-2 rounded-full transition-all"
              style={{
                width: `${Math.min(
                  (analytics.candidate_views_this_month / analytics.candidate_views_limit) * 100,
                  100
                )}%`,
              }}
            />
          </div>
          {analytics.candidate_views_this_month >= analytics.candidate_views_limit && (
            <p className="text-sm text-blue-700 mt-2">
              You've reached your monthly limit. <Link href="/employer/settings" className="underline">Upgrade</Link> to view more candidates.
            </p>
          )}
        </div>
      )}

      {/* Quick Actions */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <QuickActionCard
          title="Post a New Job"
          description="Create a job posting to attract candidates"
          icon="➕"
          href="/employer/jobs/new"
          buttonText="Create Job"
        />
        <QuickActionCard
          title="Search Candidates"
          description="Find talent that matches your requirements"
          icon="🔍"
          href="/employer/candidates"
          buttonText="Search Now"
        />
      </div>

      {/* Subscription Info */}
      <div className="mt-8 bg-gray-100 rounded-lg p-6">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="font-medium text-gray-900">Current Plan</h3>
            <p className="text-sm text-gray-600 capitalize">
              {analytics?.subscription_tier} tier
              {analytics?.subscription_status !== 'active' && (
                <span className="ml-2 text-red-600">({analytics?.subscription_status})</span>
              )}
            </p>
          </div>
          <Link
            href="/employer/settings"
            className="text-blue-600 hover:text-blue-700 text-sm font-medium"
          >
            Manage Subscription →
          </Link>
        </div>
      </div>
    </div>
  );
}

function StatCard({
  title,
  value,
  icon,
  link,
}: {
  title: string;
  value: number;
  icon: string;
  link?: string;
}) {
  const content = (
    <div className="bg-white rounded-lg shadow p-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-600">{title}</p>
          <p className="text-3xl font-bold text-gray-900 mt-1">{value}</p>
        </div>
        <div className="text-4xl">{icon}</div>
      </div>
    </div>
  );

  if (link) {
    return <Link href={link}>{content}</Link>;
  }

  return content;
}

function QuickActionCard({
  title,
  description,
  icon,
  href,
  buttonText,
}: {
  title: string;
  description: string;
  icon: string;
  href: string;
  buttonText: string;
}) {
  return (
    <div className="bg-white rounded-lg shadow p-6">
      <div className="text-4xl mb-4">{icon}</div>
      <h3 className="text-lg font-semibold text-gray-900 mb-2">{title}</h3>
      <p className="text-sm text-gray-600 mb-4">{description}</p>
      <Link
        href={href}
        className="inline-block bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 text-sm font-medium"
      >
        {buttonText}
      </Link>
    </div>
  );
}
```

---

### Step 4: Job List Page

**Location:** Create `web/app/employer/jobs/page.tsx`

**Instructions:** List all jobs with filters and create button.

**Code:**

```typescript
'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';

interface Job {
  id: string;
  title: string;
  status: string;
  location: string | null;
  remote_policy: string | null;
  employment_type: string | null;
  view_count: number;
  application_count: number;
  created_at: string;
  posted_at: string | null;
}

export default function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    fetchJobs();
  }, [statusFilter]);

  async function fetchJobs() {
    try {
      const token = localStorage.getItem('accessToken');
      const url = new URL(`${process.env.NEXT_PUBLIC_API_URL}/api/employer/jobs`);
      if (statusFilter) {
        url.searchParams.set('status_filter', statusFilter);
      }

      const res = await fetch(url.toString(), {
        headers: { Authorization: `Bearer ${token}` },
      });

      if (res.ok) {
        const data = await res.json();
        setJobs(data);
      }
    } catch (error) {
      console.error('Failed to fetch jobs:', error);
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Job Postings</h1>
          <p className="text-gray-600 mt-1">Manage your job listings</p>
        </div>
        <Link
          href="/employer/jobs/new"
          className="bg-blue-600 text-white px-4 py-2 rounded-md hover:bg-blue-700 font-medium"
        >
          + Create Job
        </Link>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-lg shadow p-4 mb-6">
        <div className="flex gap-4 items-center">
          <label className="text-sm font-medium text-gray-700">Filter by status:</label>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-3 py-1.5 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <option value="">All</option>
            <option value="draft">Draft</option>
            <option value="active">Active</option>
            <option value="paused">Paused</option>
            <option value="closed">Closed</option>
          </select>
        </div>
      </div>

      {/* Jobs List */}
      {isLoading ? (
        <div className="text-center py-12">Loading jobs...</div>
      ) : jobs.length === 0 ? (
        <div className="bg-white rounded-lg shadow p-12 text-center">
          <div className="text-6xl mb-4">📋</div>
          <h3 className="text-xl font-semibold text-gray-900 mb-2">No jobs yet</h3>
          <p className="text-gray-600 mb-6">Create your first job posting to start attracting candidates.</p>
          <Link
            href="/employer/jobs/new"
            className="inline-block bg-blue-600 text-white px-6 py-2 rounded-md hover:bg-blue-700 font-medium"
          >
            Create Your First Job
          </Link>
        </div>
      ) : (
        <div className="space-y-4">
          {jobs.map((job) => (
            <JobCard key={job.id} job={job} />
          ))}
        </div>
      )}
    </div>
  );
}

function JobCard({ job }: { job: Job }) {
  const statusColors = {
    draft: 'bg-gray-100 text-gray-800',
    active: 'bg-green-100 text-green-800',
    paused: 'bg-yellow-100 text-yellow-800',
    closed: 'bg-red-100 text-red-800',
  };

  return (
    <Link href={`/employer/jobs/${job.id}`}>
      <div className="bg-white rounded-lg shadow p-6 hover:shadow-md transition-shadow">
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <div className="flex items-center gap-3 mb-2">
              <h3 className="text-lg font-semibold text-gray-900">{job.title}</h3>
              <span
                className={`px-2 py-1 rounded-full text-xs font-medium ${
                  statusColors[job.status as keyof typeof statusColors]
                }`}
              >
                {job.status}
              </span>
            </div>

            <div className="flex flex-wrap gap-4 text-sm text-gray-600">
              {job.location && (
                <span className="flex items-center gap-1">
                  📍 {job.location}
                </span>
              )}
              {job.remote_policy && (
                <span className="capitalize">{job.remote_policy}</span>
              )}
              {job.employment_type && (
                <span className="capitalize">{job.employment_type}</span>
              )}
            </div>

            <div className="flex gap-6 mt-4 text-sm text-gray-600">
              <span>👁️ {job.view_count} views</span>
              <span>📨 {job.application_count} applications</span>
              <span>
                Created {new Date(job.created_at).toLocaleDateString()}
              </span>
            </div>
          </div>

          <div className="text-gray-400">→</div>
        </div>
      </div>
    </Link>
  );
}
```

---

### Step 5: Create Job Page

**Location:** Create `web/app/employer/jobs/new/page.tsx`

**Instructions:** Form to create a new job posting.

**Code:**

```typescript
'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';

export default function CreateJobPage() {
  const router = useRouter();
  const [formData, setFormData] = useState({
    title: '',
    description: '',
    requirements: '',
    nice_to_haves: '',
    location: '',
    remote_policy: '',
    employment_type: '',
    salary_min: '',
    salary_max: '',
    salary_currency: 'USD',
    equity_offered: false,
    application_email: '',
  });
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      const token = localStorage.getItem('accessToken');

      // Convert empty strings to null and numbers
      const payload = {
        ...formData,
        salary_min: formData.salary_min ? parseInt(formData.salary_min) : null,
        salary_max: formData.salary_max ? parseInt(formData.salary_max) : null,
        location: formData.location || null,
        remote_policy: formData.remote_policy || null,
        employment_type: formData.employment_type || null,
        application_email: formData.application_email || null,
      };

      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/employer/jobs`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Failed to create job');
      }

      const job = await res.json();
      router.push(`/employer/jobs/${job.id}`);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div className="max-w-3xl mx-auto">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900">Create Job Posting</h1>
        <p className="text-gray-600 mt-1">Fill in the details for your new position</p>
      </div>

      <form onSubmit={handleSubmit} className="bg-white rounded-lg shadow p-8 space-y-6">
        {/* Job Title */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Job Title *
          </label>
          <input
            type="text"
            required
            value={formData.title}
            onChange={(e) => setFormData({ ...formData, title: e.target.value })}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="Senior Software Engineer"
          />
        </div>

        {/* Description */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Job Description *
          </label>
          <textarea
            required
            value={formData.description}
            onChange={(e) => setFormData({ ...formData, description: e.target.value })}
            rows={6}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="Describe the role, responsibilities, and what makes it exciting..."
          />
        </div>

        {/* Requirements */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Requirements
          </label>
          <textarea
            value={formData.requirements}
            onChange={(e) => setFormData({ ...formData, requirements: e.target.value })}
            rows={4}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="Required qualifications, skills, and experience..."
          />
        </div>

        {/* Nice to Haves */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Nice to Haves
          </label>
          <textarea
            value={formData.nice_to_haves}
            onChange={(e) => setFormData({ ...formData, nice_to_haves: e.target.value })}
            rows={3}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="Preferred but not required qualifications..."
          />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Location */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Location
            </label>
            <input
              type="text"
              value={formData.location}
              onChange={(e) => setFormData({ ...formData, location: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="San Francisco, CA"
            />
          </div>

          {/* Remote Policy */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Remote Policy
            </label>
            <select
              value={formData.remote_policy}
              onChange={(e) => setFormData({ ...formData, remote_policy: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">Select...</option>
              <option value="on-site">On-site</option>
              <option value="hybrid">Hybrid</option>
              <option value="remote">Remote</option>
            </select>
          </div>

          {/* Employment Type */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Employment Type
            </label>
            <select
              value={formData.employment_type}
              onChange={(e) => setFormData({ ...formData, employment_type: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="">Select...</option>
              <option value="full-time">Full-time</option>
              <option value="part-time">Part-time</option>
              <option value="contract">Contract</option>
              <option value="internship">Internship</option>
            </select>
          </div>
        </div>

        {/* Salary Range */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Salary Range
          </label>
          <div className="grid grid-cols-2 gap-4">
            <input
              type="number"
              value={formData.salary_min}
              onChange={(e) => setFormData({ ...formData, salary_min: e.target.value })}
              className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Min (e.g., 100000)"
            />
            <input
              type="number"
              value={formData.salary_max}
              onChange={(e) => setFormData({ ...formData, salary_max: e.target.value })}
              className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Max (e.g., 150000)"
            />
          </div>
        </div>

        {/* Equity */}
        <div className="flex items-center gap-2">
          <input
            type="checkbox"
            id="equity"
            checked={formData.equity_offered}
            onChange={(e) => setFormData({ ...formData, equity_offered: e.target.checked })}
            className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
          />
          <label htmlFor="equity" className="text-sm font-medium text-gray-700">
            Equity offered
          </label>
        </div>

        {/* Application Email */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Application Email
          </label>
          <input
            type="email"
            value={formData.application_email}
            onChange={(e) => setFormData({ ...formData, application_email: e.target.value })}
            className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            placeholder="jobs@company.com"
          />
        </div>

        {error && (
          <div className="text-red-600 text-sm">{error}</div>
        )}

        <div className="flex gap-4">
          <button
            type="button"
            onClick={() => router.back()}
            className="px-6 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={isLoading}
            className="flex-1 bg-blue-600 text-white py-2 px-4 rounded-md hover:bg-blue-700 disabled:opacity-50"
          >
            {isLoading ? 'Creating...' : 'Create Job (Draft)'}
          </button>
        </div>
      </form>
    </div>
  );
}
```

---

Due to length constraints, I'll create a summary for the remaining pages. Would you like me to:

1. **Continue with the remaining employer pages in this prompt** (candidate search, saved candidates, job detail/edit)
2. **Create a separate PROMPT39** for the remaining pages
3. **Provide component code snippets** you can adapt

Let me finish this prompt with a summary and next steps:

---

## Remaining Pages to Implement

### Step 6: Job Detail/Edit Page
**Location:** `web/app/employer/jobs/[id]/page.tsx`
- View job details
- Edit button to `/employer/jobs/[id]/edit`
- Publish/pause/close actions
- View analytics (views, applications)

### Step 7: Candidate Search Page
**Location:** `web/app/employer/candidates/page.tsx`
- Search filters (skills, experience, location)
- Results grid with candidate cards
- "Save" button on each result
- Click to view full profile at `/employer/candidates/[id]`

### Step 8: Candidate Profile View
**Location:** `web/app/employer/candidates/[id]/page.tsx`
- Full candidate profile (or anonymized)
- Save candidate button
- Add notes
- Respect anonymization rules

### Step 9: Saved Candidates Page
**Location:** `web/app/employer/candidates/saved/page.tsx`
- List of all saved candidates
- Notes display/edit
- Unsave button

### Step 10: Settings Page
**Location:** `web/app/employer/settings/page.tsx`
- Company profile edit
- Subscription/billing info
- Upgrade options

---

## Testing Checklist

After implementation:

✅ Can access `/employer/onboarding` after signup  
✅ Can create employer profile  
✅ Dashboard shows correct analytics  
✅ Can create new job posting  
✅ Jobs list shows all jobs with filters  
✅ Can edit job status (draft → active)  
✅ Can search candidates with filters  
✅ Can view candidate profile (counts as view)  
✅ Can save candidates with notes  
✅ Saved candidates page shows favorites  
✅ Subscription limits enforced in UI  

---

## Success Criteria

✅ All employer pages created  
✅ Complete job CRUD workflow  
✅ Candidate search with filters  
✅ Save/unsave candidates  
✅ Analytics dashboard functional  
✅ Proper error handling  
✅ Loading states for all API calls  
✅ Responsive design  

---

**Status:** Partial implementation (dashboard, jobs list/create completed)  
**Estimated Time:** 3-4 hours for all pages  
**Dependencies:** PROMPT37 (auth working)  
**Next Prompt:** PROMPT39 (Subscription & Billing - Optional)
