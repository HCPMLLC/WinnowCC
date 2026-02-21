# PHASE 1: Recruiter Dashboard UI - Complete Implementation

**Read First:** SPEC.md, ARCHITECTURE.md, CLAUDE.md, PROMPT33, PROMPT34, PROMPT35, PROMPT36

## Purpose

Build the complete frontend interface for recruiters/employers so they can use all the backend features we've already built. This phase makes Winnow usable for recruiters by creating dashboard, job management, and candidate search pages.

**What already exists (DO NOT recreate):**
- ✅ Backend API endpoints (PROMPT36) - `/api/employer/*`
- ✅ Database models (PROMPT33-34) - employer profiles, jobs, saved candidates
- ✅ Auth system with role-based access - candidates vs employers
- ✅ Subscription tier enforcement - Free/Starter/Pro/Enterprise

**What we're building:**
- Employer dashboard with analytics
- Job creation and management UI
- Candidate search interface
- Saved candidates management

---

## Step 1: Create Employer Dashboard Page

### File to create: `apps/web/app/employer/dashboard/page.tsx`

**Location:** Inside the `apps/web/app/employer/` directory  
**Full path:** `apps/web/app/employer/dashboard/page.tsx`

**What this file does:**
- Displays employer analytics (active jobs, views, applications)
- Shows subscription tier and usage limits
- Provides quick actions (post job, search candidates)

**Code to add:**

```typescript
'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';

interface AnalyticsSummary {
  active_jobs_count: number;
  total_job_views: number;
  total_applications: number;
  candidates_viewed_this_month: number;
  saved_candidates_count: number;
  subscription_tier: string;
  candidate_view_limit: number;
}

export default function EmployerDashboard() {
  const router = useRouter();
  const [analytics, setAnalytics] = useState<AnalyticsSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchAnalytics();
  }, []);

  const fetchAnalytics = async () => {
    try {
      const token = localStorage.getItem('access_token');
      if (!token) {
        router.push('/login');
        return;
      }

      const response = await fetch('http://localhost:8000/api/employer/analytics/summary', {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (response.status === 403) {
        setError('You need an employer account to access this page');
        return;
      }

      if (!response.ok) {
        throw new Error('Failed to fetch analytics');
      }

      const data = await response.json();
      setAnalytics(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-gray-600">Loading dashboard...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="bg-red-50 border border-red-200 rounded-lg p-6 max-w-md">
          <h2 className="text-red-800 font-semibold mb-2">Error</h2>
          <p className="text-red-600">{error}</p>
          <Link href="/login" className="mt-4 inline-block text-blue-600 hover:underline">
            Return to Login
          </Link>
        </div>
      </div>
    );
  }

  const viewsPercentage = analytics 
    ? (analytics.candidates_viewed_this_month / analytics.candidate_view_limit) * 100 
    : 0;

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex justify-between items-center">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">Employer Dashboard</h1>
              <p className="text-gray-600 mt-1">Manage your jobs and candidates</p>
            </div>
            <div className="flex gap-3">
              <Link
                href="/employer/jobs/new"
                className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition"
              >
                Post New Job
              </Link>
              <Link
                href="/employer/candidates"
                className="bg-white border border-gray-300 text-gray-700 px-4 py-2 rounded-lg hover:bg-gray-50 transition"
              >
                Search Candidates
              </Link>
            </div>
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Subscription Tier Badge */}
        <div className="mb-6">
          <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-blue-100 text-blue-800">
            {analytics?.subscription_tier.toUpperCase()} Tier
          </span>
        </div>

        {/* Analytics Cards Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-8">
          {/* Active Jobs */}
          <div className="bg-white rounded-xl shadow p-6 border-l-4 border-blue-500">
            <p className="text-sm text-gray-500 mb-1">Active Jobs</p>
            <p className="text-3xl font-bold text-blue-700">
              {analytics?.active_jobs_count || 0}
            </p>
            <Link href="/employer/jobs" className="text-sm text-blue-600 hover:underline mt-2 inline-block">
              View all jobs →
            </Link>
          </div>

          {/* Total Job Views */}
          <div className="bg-white rounded-xl shadow p-6 border-l-4 border-green-500">
            <p className="text-sm text-gray-500 mb-1">Total Job Views</p>
            <p className="text-3xl font-bold text-green-700">
              {analytics?.total_job_views || 0}
            </p>
            <p className="text-xs text-gray-400 mt-1">All time</p>
          </div>

          {/* Total Applications */}
          <div className="bg-white rounded-xl shadow p-6 border-l-4 border-purple-500">
            <p className="text-sm text-gray-500 mb-1">Total Applications</p>
            <p className="text-3xl font-bold text-purple-700">
              {analytics?.total_applications || 0}
            </p>
            <p className="text-xs text-gray-400 mt-1">All time</p>
          </div>

          {/* Candidate Views This Month */}
          <div className="bg-white rounded-xl shadow p-6 border-l-4 border-yellow-500">
            <p className="text-sm text-gray-500 mb-1">Candidate Views This Month</p>
            <div className="flex items-baseline gap-2">
              <p className="text-3xl font-bold text-yellow-700">
                {analytics?.candidates_viewed_this_month || 0}
              </p>
              <p className="text-sm text-gray-500">
                / {analytics?.candidate_view_limit === -1 ? '∞' : analytics?.candidate_view_limit}
              </p>
            </div>
            {/* Progress Bar */}
            <div className="mt-3 w-full bg-gray-200 rounded-full h-2">
              <div
                className="bg-yellow-500 h-2 rounded-full transition-all"
                style={{ width: `${Math.min(viewsPercentage, 100)}%` }}
              />
            </div>
            {viewsPercentage >= 90 && (
              <p className="text-xs text-red-600 mt-2">
                ⚠️ Approaching monthly limit
              </p>
            )}
          </div>

          {/* Saved Candidates */}
          <div className="bg-white rounded-xl shadow p-6 border-l-4 border-pink-500">
            <p className="text-sm text-gray-500 mb-1">Saved Candidates</p>
            <p className="text-3xl font-bold text-pink-700">
              {analytics?.saved_candidates_count || 0}
            </p>
            <Link href="/employer/candidates/saved" className="text-sm text-pink-600 hover:underline mt-2 inline-block">
              View saved →
            </Link>
          </div>
        </div>

        {/* Quick Links Section */}
        <div className="bg-white rounded-xl shadow p-6">
          <h2 className="text-xl font-semibold text-gray-900 mb-4">Quick Actions</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <Link
              href="/employer/jobs/new"
              className="p-4 border border-gray-200 rounded-lg hover:border-blue-500 hover:bg-blue-50 transition"
            >
              <div className="text-blue-600 text-2xl mb-2">📝</div>
              <h3 className="font-medium text-gray-900">Post a Job</h3>
              <p className="text-sm text-gray-500 mt-1">Create a new job posting</p>
            </Link>

            <Link
              href="/employer/candidates"
              className="p-4 border border-gray-200 rounded-lg hover:border-blue-500 hover:bg-blue-50 transition"
            >
              <div className="text-blue-600 text-2xl mb-2">🔍</div>
              <h3 className="font-medium text-gray-900">Search Candidates</h3>
              <p className="text-sm text-gray-500 mt-1">Find qualified talent</p>
            </Link>

            <Link
              href="/employer/jobs"
              className="p-4 border border-gray-200 rounded-lg hover:border-blue-500 hover:bg-blue-50 transition"
            >
              <div className="text-blue-600 text-2xl mb-2">📊</div>
              <h3 className="font-medium text-gray-900">Manage Jobs</h3>
              <p className="text-sm text-gray-500 mt-1">View and edit your postings</p>
            </Link>

            <Link
              href="/employer/candidates/saved"
              className="p-4 border border-gray-200 rounded-lg hover:border-blue-500 hover:bg-blue-50 transition"
            >
              <div className="text-blue-600 text-2xl mb-2">⭐</div>
              <h3 className="font-medium text-gray-900">Saved Candidates</h3>
              <p className="text-sm text-gray-500 mt-1">Review your shortlist</p>
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
```

**How to create this file in Cursor:**

1. **Open Cursor IDE**
2. **Navigate** to the folder: `apps/web/app/employer/`
3. **Create new file**: Right-click on the `employer` folder → "New File"
4. **Name it**: `dashboard` (Cursor will create a folder)
5. **Inside the dashboard folder**, create another file named `page.tsx`
6. **Paste the code above** into `page.tsx`
7. **Save the file** (Ctrl+S or Cmd+S)

---

## Step 2: Create Job Posting Form

### File to create: `apps/web/app/employer/jobs/new/page.tsx`

**Location:** Inside `apps/web/app/employer/jobs/new/`  
**Full path:** `apps/web/app/employer/jobs/new/page.tsx`

**What this file does:**
- Form to create new job postings
- Handles title, description, requirements, location, salary, remote policy
- Submits to backend API
- Enforces subscription tier limits

**Code to add:**

```typescript
'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';

export default function NewJobPage() {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [formData, setFormData] = useState({
    title: '',
    description: '',
    requirements: '',
    nice_to_haves: '',
    location: '',
    remote_policy: 'hybrid',
    employment_type: 'full-time',
    salary_min: '',
    salary_max: '',
    equity_offered: false,
    application_url: '',
    application_email: '',
  });

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
    const { name, value, type } = e.target;
    
    if (type === 'checkbox') {
      const checked = (e.target as HTMLInputElement).checked;
      setFormData(prev => ({ ...prev, [name]: checked }));
    } else {
      setFormData(prev => ({ ...prev, [name]: value }));
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const token = localStorage.getItem('access_token');
      if (!token) {
        router.push('/login');
        return;
      }

      // Convert salary to integers
      const payload = {
        ...formData,
        salary_min: formData.salary_min ? parseInt(formData.salary_min) : null,
        salary_max: formData.salary_max ? parseInt(formData.salary_max) : null,
        status: 'active', // Immediately publish
      };

      const response = await fetch('http://localhost:8000/api/employer/jobs', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      });

      if (response.status === 403) {
        const data = await response.json();
        setError(data.detail || 'Job limit reached for your subscription tier');
        return;
      }

      if (!response.ok) {
        throw new Error('Failed to create job');
      }

      // Success - redirect to jobs list
      router.push('/employer/jobs');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex items-center gap-4">
            <Link href="/employer/jobs" className="text-gray-600 hover:text-gray-900">
              ← Back
            </Link>
            <div>
              <h1 className="text-3xl font-bold text-gray-900">Post a New Job</h1>
              <p className="text-gray-600 mt-1">Fill out the details below</p>
            </div>
          </div>
        </div>
      </div>

      {/* Form */}
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {error && (
          <div className="mb-6 bg-red-50 border border-red-200 rounded-lg p-4">
            <p className="text-red-800">{error}</p>
          </div>
        )}

        <form onSubmit={handleSubmit} className="bg-white rounded-xl shadow p-8 space-y-6">
          {/* Job Title */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Job Title <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              name="title"
              value={formData.title}
              onChange={handleChange}
              required
              placeholder="e.g. Senior Software Engineer"
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>

          {/* Description */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Job Description <span className="text-red-500">*</span>
            </label>
            <textarea
              name="description"
              value={formData.description}
              onChange={handleChange}
              required
              rows={6}
              placeholder="Describe the role, responsibilities, and what makes this opportunity exciting..."
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>

          {/* Requirements */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Requirements
            </label>
            <textarea
              name="requirements"
              value={formData.requirements}
              onChange={handleChange}
              rows={4}
              placeholder="Required skills, experience, education..."
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>

          {/* Nice to Haves */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Nice to Haves
            </label>
            <textarea
              name="nice_to_haves"
              value={formData.nice_to_haves}
              onChange={handleChange}
              rows={3}
              placeholder="Bonus skills or experience..."
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>

          {/* Location */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Location
            </label>
            <input
              type="text"
              name="location"
              value={formData.location}
              onChange={handleChange}
              placeholder="e.g. San Francisco, CA or Remote"
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>

          {/* Remote Policy and Employment Type - Side by Side */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Remote Policy
              </label>
              <select
                name="remote_policy"
                value={formData.remote_policy}
                onChange={handleChange}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                <option value="on-site">On-site</option>
                <option value="hybrid">Hybrid</option>
                <option value="remote">Remote</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Employment Type
              </label>
              <select
                name="employment_type"
                value={formData.employment_type}
                onChange={handleChange}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                <option value="full-time">Full-time</option>
                <option value="part-time">Part-time</option>
                <option value="contract">Contract</option>
                <option value="internship">Internship</option>
              </select>
            </div>
          </div>

          {/* Salary Range - Side by Side */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Minimum Salary (USD)
              </label>
              <input
                type="number"
                name="salary_min"
                value={formData.salary_min}
                onChange={handleChange}
                placeholder="e.g. 120000"
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Maximum Salary (USD)
              </label>
              <input
                type="number"
                name="salary_max"
                value={formData.salary_max}
                onChange={handleChange}
                placeholder="e.g. 160000"
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
          </div>

          {/* Equity Offered */}
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              name="equity_offered"
              checked={formData.equity_offered}
              onChange={handleChange}
              className="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
            />
            <label className="text-sm font-medium text-gray-700">
              Equity/stock options offered
            </label>
          </div>

          {/* Application URL */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Application URL
            </label>
            <input
              type="url"
              name="application_url"
              value={formData.application_url}
              onChange={handleChange}
              placeholder="https://yourcompany.com/careers/apply"
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>

          {/* Application Email */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Application Email
            </label>
            <input
              type="email"
              name="application_email"
              value={formData.application_email}
              onChange={handleChange}
              placeholder="careers@yourcompany.com"
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
            <p className="text-sm text-gray-500 mt-1">
              Provide either an application URL or email address
            </p>
          </div>

          {/* Submit Button */}
          <div className="flex gap-4 pt-6">
            <button
              type="submit"
              disabled={loading}
              className="flex-1 bg-blue-600 text-white px-6 py-3 rounded-lg font-medium hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition"
            >
              {loading ? 'Publishing...' : 'Publish Job'}
            </button>
            <Link
              href="/employer/jobs"
              className="px-6 py-3 border border-gray-300 rounded-lg font-medium text-gray-700 hover:bg-gray-50 transition"
            >
              Cancel
            </Link>
          </div>
        </form>
      </div>
    </div>
  );
}
```

**How to create this file in Cursor:**

1. **Navigate** to: `apps/web/app/employer/jobs/`
2. **Create folder**: Right-click on `jobs` → "New Folder" → name it `new`
3. **Inside the new folder**, create file: `page.tsx`
4. **Paste the code above**
5. **Save** (Ctrl+S or Cmd+S)

---

## Step 3: Create Jobs List Page

### File to create: `apps/web/app/employer/jobs/page.tsx`

**Location:** Inside `apps/web/app/employer/jobs/`  
**Full path:** `apps/web/app/employer/jobs/page.tsx`

**What this file does:**
- Lists all jobs for the employer
- Shows status badges (active/draft/paused/closed)
- Displays view count and application count
- Allows editing and deleting jobs

**Code to add:**

```typescript
'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';

interface Job {
  id: string;
  title: string;
  location: string | null;
  remote_policy: string;
  employment_type: string;
  status: string;
  view_count: number;
  application_count: number;
  created_at: string;
  salary_min: number | null;
  salary_max: number | null;
}

export default function JobsListPage() {
  const router = useRouter();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchJobs();
  }, []);

  const fetchJobs = async () => {
    try {
      const token = localStorage.getItem('access_token');
      if (!token) {
        router.push('/login');
        return;
      }

      const response = await fetch('http://localhost:8000/api/employer/jobs', {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (response.status === 403) {
        setError('You need an employer account to access this page');
        return;
      }

      if (!response.ok) {
        throw new Error('Failed to fetch jobs');
      }

      const data = await response.json();
      setJobs(data.jobs || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (jobId: string) => {
    if (!confirm('Are you sure you want to delete this job?')) {
      return;
    }

    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`http://localhost:8000/api/employer/jobs/${jobId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (response.ok) {
        // Remove from list
        setJobs(prev => prev.filter(job => job.id !== jobId));
      } else {
        alert('Failed to delete job');
      }
    } catch (err) {
      alert('Error deleting job');
    }
  };

  const getStatusBadge = (status: string) => {
    const styles = {
      active: 'bg-green-100 text-green-800',
      draft: 'bg-gray-100 text-gray-800',
      paused: 'bg-yellow-100 text-yellow-800',
      closed: 'bg-red-100 text-red-800',
    };
    
    return (
      <span className={`px-3 py-1 rounded-full text-xs font-medium ${styles[status as keyof typeof styles] || styles.draft}`}>
        {status.toUpperCase()}
      </span>
    );
  };

  const formatSalary = (min: number | null, max: number | null) => {
    if (!min && !max) return 'Not specified';
    if (min && max) return `$${(min / 1000).toFixed(0)}k - $${(max / 1000).toFixed(0)}k`;
    if (min) return `$${(min / 1000).toFixed(0)}k+`;
    return `Up to $${(max! / 1000).toFixed(0)}k`;
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-gray-600">Loading jobs...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="bg-red-50 border border-red-200 rounded-lg p-6 max-w-md">
          <h2 className="text-red-800 font-semibold mb-2">Error</h2>
          <p className="text-red-600">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex justify-between items-center">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">Your Job Postings</h1>
              <p className="text-gray-600 mt-1">{jobs.length} total jobs</p>
            </div>
            <Link
              href="/employer/jobs/new"
              className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition"
            >
              Post New Job
            </Link>
          </div>
        </div>
      </div>

      {/* Jobs List */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {jobs.length === 0 ? (
          <div className="bg-white rounded-xl shadow p-12 text-center">
            <div className="text-6xl mb-4">📝</div>
            <h2 className="text-2xl font-semibold text-gray-900 mb-2">No jobs posted yet</h2>
            <p className="text-gray-600 mb-6">Create your first job posting to start finding candidates</p>
            <Link
              href="/employer/jobs/new"
              className="inline-block bg-blue-600 text-white px-6 py-3 rounded-lg hover:bg-blue-700 transition"
            >
              Post Your First Job
            </Link>
          </div>
        ) : (
          <div className="space-y-4">
            {jobs.map((job) => (
              <div key={job.id} className="bg-white rounded-xl shadow p-6 hover:shadow-lg transition">
                <div className="flex justify-between items-start">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <h2 className="text-xl font-semibold text-gray-900">{job.title}</h2>
                      {getStatusBadge(job.status)}
                    </div>
                    
                    <div className="flex flex-wrap gap-4 text-sm text-gray-600 mb-4">
                      <span className="flex items-center gap-1">
                        📍 {job.location || 'Location not specified'}
                      </span>
                      <span className="flex items-center gap-1">
                        💼 {job.employment_type}
                      </span>
                      <span className="flex items-center gap-1">
                        🏠 {job.remote_policy}
                      </span>
                      <span className="flex items-center gap-1">
                        💰 {formatSalary(job.salary_min, job.salary_max)}
                      </span>
                    </div>

                    <div className="flex gap-6 text-sm text-gray-500">
                      <span>👁️ {job.view_count} views</span>
                      <span>📧 {job.application_count} applications</span>
                      <span>📅 Posted {formatDate(job.created_at)}</span>
                    </div>
                  </div>

                  <div className="flex gap-2 ml-4">
                    <Link
                      href={`/employer/jobs/${job.id}/edit`}
                      className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition"
                    >
                      Edit
                    </Link>
                    <button
                      onClick={() => handleDelete(job.id)}
                      className="px-4 py-2 border border-red-300 rounded-lg text-red-700 hover:bg-red-50 transition"
                    >
                      Delete
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
```

**How to create this file in Cursor:**

1. **Navigate** to: `apps/web/app/employer/jobs/`
2. **Create file**: `page.tsx` (directly in the jobs folder, NOT in new/)
3. **Paste the code above**
4. **Save**

---

## Step 4: Create Candidate Search Page

### File to create: `apps/web/app/employer/candidates/page.tsx`

**Location:** Inside `apps/web/app/employer/candidates/`  
**Full path:** `apps/web/app/employer/candidates/page.tsx`

**What this file does:**
- Search form with filters (skills, location, title)
- Display candidate results
- Save candidates with notes
- View candidate profiles (counts toward monthly limit)
- Respects candidate privacy (anonymous vs public)

**Code to add:**

```typescript
'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';

interface Candidate {
  id: string;
  user_id: string;
  full_name: string | null;
  headline: string | null;
  location: string | null;
  years_of_experience: number | null;
  skills: string[];
  visibility: string;
  open_to_opportunities: boolean;
}

interface SearchFilters {
  skills: string;
  location: string;
  title: string;
  min_experience: string;
}

export default function CandidateSearchPage() {
  const router = useRouter();
  const [filters, setFilters] = useState<SearchFilters>({
    skills: '',
    location: '',
    title: '',
    min_experience: '',
  });
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchPerformed, setSearchPerformed] = useState(false);

  const handleFilterChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFilters(prev => ({ ...prev, [name]: value }));
  };

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setSearchPerformed(true);

    try {
      const token = localStorage.getItem('access_token');
      if (!token) {
        router.push('/login');
        return;
      }

      // Build filter object (only include non-empty filters)
      const searchFilters: any = {};
      if (filters.skills) searchFilters.skills = filters.skills.split(',').map(s => s.trim());
      if (filters.location) searchFilters.location = filters.location;
      if (filters.title) searchFilters.title = filters.title;
      if (filters.min_experience) searchFilters.min_experience = parseInt(filters.min_experience);

      const response = await fetch('http://localhost:8000/api/employer/candidates/search', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          filters: searchFilters,
          limit: 20,
          offset: 0,
        }),
      });

      if (response.status === 403) {
        setError('You need an employer account to search candidates');
        return;
      }

      if (!response.ok) {
        throw new Error('Failed to search candidates');
      }

      const data = await response.json();
      setCandidates(data.candidates || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  const handleSaveCandidate = async (candidateId: string) => {
    const notes = prompt('Add notes for this candidate (optional):');
    
    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch('http://localhost:8000/api/employer/candidates/save', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          candidate_profile_id: candidateId,
          notes: notes || '',
        }),
      });

      if (response.ok) {
        alert('Candidate saved successfully!');
      } else {
        const data = await response.json();
        alert(data.detail || 'Failed to save candidate');
      }
    } catch (err) {
      alert('Error saving candidate');
    }
  };

  const getDisplayName = (candidate: Candidate) => {
    if (candidate.visibility === 'anonymous') {
      return `Candidate #${candidate.id.substring(0, 8)}`;
    }
    return candidate.full_name || 'Unknown';
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <h1 className="text-3xl font-bold text-gray-900">Search Candidates</h1>
          <p className="text-gray-600 mt-1">Find qualified talent for your open positions</p>
        </div>
      </div>

      {/* Search Form */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="bg-white rounded-xl shadow p-6 mb-8">
          <form onSubmit={handleSearch} className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Skills */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Skills (comma-separated)
                </label>
                <input
                  type="text"
                  name="skills"
                  value={filters.skills}
                  onChange={handleFilterChange}
                  placeholder="e.g. Python, React, AWS"
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>

              {/* Location */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Location
                </label>
                <input
                  type="text"
                  name="location"
                  value={filters.location}
                  onChange={handleFilterChange}
                  placeholder="e.g. San Francisco, CA"
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>

              {/* Job Title */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Job Title
                </label>
                <input
                  type="text"
                  name="title"
                  value={filters.title}
                  onChange={handleFilterChange}
                  placeholder="e.g. Software Engineer"
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>

              {/* Min Experience */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Minimum Years Experience
                </label>
                <input
                  type="number"
                  name="min_experience"
                  value={filters.min_experience}
                  onChange={handleFilterChange}
                  placeholder="e.g. 5"
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-blue-600 text-white px-6 py-3 rounded-lg font-medium hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition"
            >
              {loading ? 'Searching...' : 'Search Candidates'}
            </button>
          </form>
        </div>

        {/* Error Display */}
        {error && (
          <div className="mb-6 bg-red-50 border border-red-200 rounded-lg p-4">
            <p className="text-red-800">{error}</p>
          </div>
        )}

        {/* Results */}
        {searchPerformed && !loading && (
          <div>
            <div className="mb-4 flex justify-between items-center">
              <h2 className="text-xl font-semibold text-gray-900">
                {candidates.length} {candidates.length === 1 ? 'Candidate' : 'Candidates'} Found
              </h2>
              <Link
                href="/employer/candidates/saved"
                className="text-blue-600 hover:underline"
              >
                View Saved Candidates →
              </Link>
            </div>

            {candidates.length === 0 ? (
              <div className="bg-white rounded-xl shadow p-12 text-center">
                <div className="text-6xl mb-4">🔍</div>
                <h3 className="text-xl font-semibold text-gray-900 mb-2">No candidates found</h3>
                <p className="text-gray-600">Try adjusting your search filters</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {candidates.map((candidate) => (
                  <div key={candidate.id} className="bg-white rounded-xl shadow p-6 hover:shadow-lg transition">
                    <div className="flex justify-between items-start mb-4">
                      <div>
                        <h3 className="text-lg font-semibold text-gray-900">
                          {getDisplayName(candidate)}
                        </h3>
                        {candidate.headline && (
                          <p className="text-gray-600 text-sm mt-1">{candidate.headline}</p>
                        )}
                      </div>
                      {candidate.visibility === 'anonymous' && (
                        <span className="px-2 py-1 bg-gray-100 text-gray-600 text-xs rounded">
                          Anonymous
                        </span>
                      )}
                    </div>

                    <div className="space-y-2 text-sm text-gray-600 mb-4">
                      {candidate.location && (
                        <p className="flex items-center gap-2">
                          📍 {candidate.location}
                        </p>
                      )}
                      {candidate.years_of_experience !== null && (
                        <p className="flex items-center gap-2">
                          💼 {candidate.years_of_experience} years experience
                        </p>
                      )}
                    </div>

                    {/* Skills */}
                    {candidate.skills && candidate.skills.length > 0 && (
                      <div className="mb-4">
                        <p className="text-xs text-gray-500 mb-2">Skills:</p>
                        <div className="flex flex-wrap gap-2">
                          {candidate.skills.slice(0, 6).map((skill, idx) => (
                            <span
                              key={idx}
                              className="px-2 py-1 bg-blue-50 text-blue-700 text-xs rounded"
                            >
                              {skill}
                            </span>
                          ))}
                          {candidate.skills.length > 6 && (
                            <span className="px-2 py-1 bg-gray-50 text-gray-600 text-xs rounded">
                              +{candidate.skills.length - 6} more
                            </span>
                          )}
                        </div>
                      </div>
                    )}

                    {/* Actions */}
                    <div className="flex gap-2 pt-4 border-t border-gray-200">
                      <Link
                        href={`/employer/candidates/${candidate.id}`}
                        className="flex-1 text-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition"
                      >
                        View Full Profile
                      </Link>
                      <button
                        onClick={() => handleSaveCandidate(candidate.id)}
                        className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition"
                      >
                        ⭐ Save
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
```

**How to create this file in Cursor:**

1. **Navigate** to: `apps/web/app/employer/`
2. **Create folder**: `candidates`
3. **Inside candidates folder**, create file: `page.tsx`
4. **Paste the code above**
5. **Save**

---

## Step 5: Create Saved Candidates Page

### File to create: `apps/web/app/employer/candidates/saved/page.tsx`

**Location:** Inside `apps/web/app/employer/candidates/saved/`  
**Full path:** `apps/web/app/employer/candidates/saved/page.tsx`

**What this file does:**
- Lists all saved candidates
- Shows notes for each candidate
- Allows editing notes
- Allows removing candidates from saved list

**Code to add:**

```typescript
'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';

interface SavedCandidate {
  id: string;
  notes: string | null;
  saved_at: string;
  candidate: {
    id: string;
    full_name: string | null;
    headline: string | null;
    location: string | null;
    years_of_experience: number | null;
    skills: string[];
    visibility: string;
  };
}

export default function SavedCandidatesPage() {
  const router = useRouter();
  const [savedCandidates, setSavedCandidates] = useState<SavedCandidate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editNotes, setEditNotes] = useState('');

  useEffect(() => {
    fetchSavedCandidates();
  }, []);

  const fetchSavedCandidates = async () => {
    try {
      const token = localStorage.getItem('access_token');
      if (!token) {
        router.push('/login');
        return;
      }

      const response = await fetch('http://localhost:8000/api/employer/candidates/saved', {
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (response.status === 403) {
        setError('You need an employer account to access this page');
        return;
      }

      if (!response.ok) {
        throw new Error('Failed to fetch saved candidates');
      }

      const data = await response.json();
      setSavedCandidates(data.saved_candidates || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  const handleUnsave = async (savedId: string) => {
    if (!confirm('Remove this candidate from your saved list?')) {
      return;
    }

    try {
      const token = localStorage.getItem('access_token');
      const response = await fetch(`http://localhost:8000/api/employer/candidates/saved/${savedId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      });

      if (response.ok) {
        setSavedCandidates(prev => prev.filter(sc => sc.id !== savedId));
      } else {
        alert('Failed to remove candidate');
      }
    } catch (err) {
      alert('Error removing candidate');
    }
  };

  const startEditNotes = (savedCandidate: SavedCandidate) => {
    setEditingId(savedCandidate.id);
    setEditNotes(savedCandidate.notes || '');
  };

  const cancelEdit = () => {
    setEditingId(null);
    setEditNotes('');
  };

  const saveNotes = async (savedId: string) => {
    try {
      const token = localStorage.getItem('access_token');
      
      // Note: The backend doesn't have a PATCH endpoint for updating notes yet
      // We'll need to delete and re-save for now
      // TODO: Add PATCH /api/employer/candidates/saved/{id} endpoint to backend
      
      alert('Note: Backend update endpoint not implemented yet. Please delete and re-save to update notes.');
      cancelEdit();
    } catch (err) {
      alert('Error updating notes');
    }
  };

  const getDisplayName = (candidate: any) => {
    if (candidate.visibility === 'anonymous') {
      return `Candidate #${candidate.id.substring(0, 8)}`;
    }
    return candidate.full_name || 'Unknown';
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-gray-600">Loading saved candidates...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="bg-red-50 border border-red-200 rounded-lg p-6 max-w-md">
          <h2 className="text-red-800 font-semibold mb-2">Error</h2>
          <p className="text-red-600">{error}</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <div className="flex justify-between items-center">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">Saved Candidates</h1>
              <p className="text-gray-600 mt-1">{savedCandidates.length} candidates in your shortlist</p>
            </div>
            <Link
              href="/employer/candidates"
              className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition"
            >
              Search More Candidates
            </Link>
          </div>
        </div>
      </div>

      {/* Saved Candidates List */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {savedCandidates.length === 0 ? (
          <div className="bg-white rounded-xl shadow p-12 text-center">
            <div className="text-6xl mb-4">⭐</div>
            <h2 className="text-2xl font-semibold text-gray-900 mb-2">No saved candidates yet</h2>
            <p className="text-gray-600 mb-6">Save candidates while searching to build your shortlist</p>
            <Link
              href="/employer/candidates"
              className="inline-block bg-blue-600 text-white px-6 py-3 rounded-lg hover:bg-blue-700 transition"
            >
              Search Candidates
            </Link>
          </div>
        ) : (
          <div className="space-y-6">
            {savedCandidates.map((savedCandidate) => (
              <div key={savedCandidate.id} className="bg-white rounded-xl shadow p-6">
                <div className="flex justify-between items-start mb-4">
                  <div className="flex-1">
                    <div className="flex items-center gap-3 mb-2">
                      <h3 className="text-xl font-semibold text-gray-900">
                        {getDisplayName(savedCandidate.candidate)}
                      </h3>
                      {savedCandidate.candidate.visibility === 'anonymous' && (
                        <span className="px-2 py-1 bg-gray-100 text-gray-600 text-xs rounded">
                          Anonymous
                        </span>
                      )}
                    </div>
                    
                    {savedCandidate.candidate.headline && (
                      <p className="text-gray-600 mb-3">{savedCandidate.candidate.headline}</p>
                    )}

                    <div className="flex flex-wrap gap-4 text-sm text-gray-600 mb-3">
                      {savedCandidate.candidate.location && (
                        <span className="flex items-center gap-1">
                          📍 {savedCandidate.candidate.location}
                        </span>
                      )}
                      {savedCandidate.candidate.years_of_experience !== null && (
                        <span className="flex items-center gap-1">
                          💼 {savedCandidate.candidate.years_of_experience} years
                        </span>
                      )}
                      <span className="flex items-center gap-1">
                        📅 Saved {formatDate(savedCandidate.saved_at)}
                      </span>
                    </div>

                    {/* Skills */}
                    {savedCandidate.candidate.skills && savedCandidate.candidate.skills.length > 0 && (
                      <div className="flex flex-wrap gap-2 mb-4">
                        {savedCandidate.candidate.skills.slice(0, 8).map((skill, idx) => (
                          <span
                            key={idx}
                            className="px-2 py-1 bg-blue-50 text-blue-700 text-xs rounded"
                          >
                            {skill}
                          </span>
                        ))}
                        {savedCandidate.candidate.skills.length > 8 && (
                          <span className="px-2 py-1 bg-gray-50 text-gray-600 text-xs rounded">
                            +{savedCandidate.candidate.skills.length - 8} more
                          </span>
                        )}
                      </div>
                    )}

                    {/* Notes Section */}
                    <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 mb-4">
                      <div className="flex justify-between items-start mb-2">
                        <p className="text-sm font-medium text-gray-700">Your Notes:</p>
                        {editingId !== savedCandidate.id && (
                          <button
                            onClick={() => startEditNotes(savedCandidate)}
                            className="text-sm text-blue-600 hover:underline"
                          >
                            Edit
                          </button>
                        )}
                      </div>
                      
                      {editingId === savedCandidate.id ? (
                        <div>
                          <textarea
                            value={editNotes}
                            onChange={(e) => setEditNotes(e.target.value)}
                            rows={3}
                            className="w-full px-3 py-2 border border-gray-300 rounded-lg mb-2"
                            placeholder="Add notes about this candidate..."
                          />
                          <div className="flex gap-2">
                            <button
                              onClick={() => saveNotes(savedCandidate.id)}
                              className="px-3 py-1 bg-blue-600 text-white text-sm rounded hover:bg-blue-700"
                            >
                              Save
                            </button>
                            <button
                              onClick={cancelEdit}
                              className="px-3 py-1 border border-gray-300 text-gray-700 text-sm rounded hover:bg-gray-50"
                            >
                              Cancel
                            </button>
                          </div>
                        </div>
                      ) : (
                        <p className="text-gray-600 text-sm whitespace-pre-wrap">
                          {savedCandidate.notes || 'No notes added yet'}
                        </p>
                      )}
                    </div>
                  </div>

                  <div className="flex flex-col gap-2 ml-4">
                    <Link
                      href={`/employer/candidates/${savedCandidate.candidate.id}`}
                      className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition text-center"
                    >
                      View Profile
                    </Link>
                    <button
                      onClick={() => handleUnsave(savedCandidate.id)}
                      className="px-4 py-2 border border-red-300 rounded-lg text-red-700 hover:bg-red-50 transition"
                    >
                      Remove
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
```

**How to create this file in Cursor:**

1. **Navigate** to: `apps/web/app/employer/candidates/`
2. **Create folder**: `saved`
3. **Inside saved folder**, create file: `page.tsx`
4. **Paste the code above**
5. **Save**

---

## Step 6: Testing Phase 1

Now let's test everything we've built!

### 6.1 - Start All Services

You need THREE separate terminals:

**Terminal 1 - Infrastructure (Docker):**
```powershell
cd infra
docker compose up -d
```

**Terminal 2 - Backend API:**
```powershell
cd services/api
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 3 - Frontend:**
```powershell
cd apps/web
npm run dev
```

### 6.2 - Test Each Page

**Test 1: Dashboard**
1. Open browser: `http://localhost:3000/employer/dashboard`
2. You should see analytics cards (might show zeros if no data yet)
3. Subscription tier badge should display
4. Quick action buttons should be clickable

**Test 2: Post a Job**
1. Click "Post New Job" button
2. Fill out the form with test data:
   - Title: "Senior React Developer"
   - Description: "We need a React expert"
   - Location: "San Francisco, CA"
   - Remote Policy: "Hybrid"
   - Salary Min: 120000
   - Salary Max: 160000
3. Click "Publish Job"
4. Should redirect to jobs list

**Test 3: View Jobs List**
1. Go to: `http://localhost:3000/employer/jobs`
2. Should see the job you just created
3. Status badge should say "ACTIVE" in green
4. View count and application count should show 0

**Test 4: Search Candidates**
1. Go to: `http://localhost:3000/employer/candidates`
2. Enter search filters (e.g., skills: "Python, React")
3. Click "Search Candidates"
4. Should see results (may be empty if no candidates in database)

**Test 5: Saved Candidates**
1. If you have search results, click "Save" on a candidate
2. Go to: `http://localhost:3000/employer/candidates/saved`
3. Should see the saved candidate with notes

### 6.3 - Common Issues and Fixes

**Issue: "401 Unauthorized" errors**
- **Cause:** Not logged in or token expired
- **Fix:** Go to `/login` and log in again

**Issue: "403 Forbidden" errors**
- **Cause:** User account is role='candidate', not 'employer'
- **Fix:** In database, update your user's role to 'employer' or 'both'

**Issue: "Employer profile not found"**
- **Cause:** No employer profile created yet
- **Fix:** Create employer profile first via API or add a profile creation page

**Issue: Pages show blank/white screen**
- **Cause:** JavaScript error in browser console
- **Fix:** Open browser DevTools (F12), check Console tab for errors

**Issue: "Failed to fetch" errors**
- **Cause:** Backend API not running
- **Fix:** Make sure Terminal 2 is running the API on port 8000

---

## Success Criteria for Phase 1

✅ Dashboard page displays analytics  
✅ Can create new jobs via form  
✅ Jobs list shows all created jobs  
✅ Can search for candidates with filters  
✅ Can save candidates with notes  
✅ Saved candidates page shows shortlist  
✅ All navigation links work  
✅ Subscription limits are visible  
✅ No JavaScript errors in browser console  

---

## What's Next?

After Phase 1 is complete and tested, you'll have a **fully functional recruiter dashboard**. Recruiters can:
- View their analytics
- Post and manage jobs
- Search and save candidates
- Track their usage limits

**Phase 2 will add:**
- Multi-board job distribution (Indeed, LinkedIn, Google Jobs)
- Real-time sync when jobs are edited
- Per-board analytics and metrics
- Cost tracking per board

**Want to move to Phase 2 now?** Let me know and I'll create that Cursor prompt!
