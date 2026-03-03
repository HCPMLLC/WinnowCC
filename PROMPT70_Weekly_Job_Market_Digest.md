# PROMPT70: Weekly Job Market Digest

## Purpose

Deliver a personalized weekly email digest to candidates summarizing new matches, market trends, salary data, and a "hidden gem" job they may have overlooked. This is a low-cost retention driver (~$0.005–0.01/user/week using Claude Haiku) available to **all tiers** (free/starter/pro).

## Triggers

- **Automated**: RQ Scheduler cron fires every Sunday at 7:00 AM UTC
- **Manual**: Admin endpoint `POST /api/admin/scheduler/trigger-digest`

## What Already Exists

| Component | Location | Reuse |
|-----------|----------|-------|
| Candidate model | `app/models/candidate.py` | `consent_marketing`, `alert_frequency` fields for opt-in/out |
| Match model | `app/models/match.py` | `match_score`, `application_status`, `job_id` for top matches + hidden gem |
| Job model | `app/models/job.py` | `title`, `company`, `salary_min/max`, `remote_flag`, `location` |
| User model | `app/models/user.py` | `email` for delivery |
| Email service | `app/services/email.py` | `_send()` helper, `RESEND_API_KEY` guard, deliverability headers |
| Scheduled jobs | `app/services/scheduled_jobs.py` | Session pattern, return dict, try/except/finally |
| Scheduler | `app/scheduler.py` | Cron registration with dedup via `meta["scheduled_job_type"]` |
| Queue | `app/services/queue.py` | `get_queue("low")` for low-priority batch work |
| Admin router | `app/routers/scheduler.py` | `ScheduledTask`, admin trigger pattern |

## Architecture Overview

```
Sunday 7am UTC
      │
      ▼
  RQ Scheduler (cron)
      │
      ▼
  scheduled_send_weekly_digests()    ← scheduled_jobs.py wrapper
      │
      ▼
  send_weekly_digests()              ← weekly_digest.py orchestrator
      │
      ├── _get_eligible_candidates() → candidates with consent + not already sent
      │
      ├── for each candidate:
      │   ├── _aggregate_user_data() → new matches, market stats, hidden gem
      │   ├── _generate_summary()    → Claude Haiku 3-paragraph summary
      │   ├── send_weekly_digest_email() → email.py
      │   └── log to weekly_digest_logs
      │
      └── return {sent, skipped, errors}
```

## Implementation Steps

### 1. Database: `weekly_digest_logs` table

| Column | Type | Notes |
|--------|------|-------|
| id | Integer PK | Auto-increment |
| candidate_id | Integer FK → candidate.id CASCADE | Who received it |
| digest_json | JSONB | Full aggregated data snapshot |
| summary_text | Text | LLM-generated summary |
| hidden_gem_job_id | Integer FK → jobs.id SET NULL | Featured hidden gem |
| email_id | String(100) | Resend message ID |
| sent_at | DateTime TZ | When email was sent |
| week_start | Date | Monday of the digest week |
| week_end | Date | Sunday of the digest week |

- **Unique index**: `(candidate_id, week_start)` — prevents duplicate sends on retries

### 2. Email Template

- Subject: "Your Weekly Job Market Digest — {new_match_count} new matches"
- Top 3 matches table (title, company, score)
- AI summary (3 paragraphs)
- Hidden gem CTA button → `/matches?highlight={job_id}`
- Market stats (total jobs, new this week, avg salary, remote %)
- Unsubscribe footer → `/settings`

### 3. Core Service Logic

- **Eligibility**: `consent_marketing = True` AND (`alert_frequency` IS NULL OR `= "weekly"`) AND NOT already sent this week
- **Skip empty**: No email if zero new matches AND no hidden gem
- **Hidden gem**: Match with score >= 60, `application_status` IS NULL, created > 3 days ago
- **LLM**: Claude Haiku for cost efficiency; if LLM fails, skip user (don't send without summary)
- **Per-user try/except**: One failure doesn't block the batch

### 4. Scheduled Job

- Wrapper in `scheduled_jobs.py` following existing pattern
- Cron: `0 7 * * 0` (Sunday 7am UTC) on `"low"` queue
- Admin trigger: `POST /api/admin/scheduler/trigger-digest`

## Key Design Decisions

- **All tiers**: Available to free/starter/pro — retention driver, not upsell
- **Low queue**: Never blocks matching/parsing on default/critical queues
- **Dedup**: UNIQUE index prevents duplicate emails on retry
- **`alert_frequency` NULL = weekly**: Most candidates have NULL; default opt-in is right for retention. Explicit `"none"`/`"never"` opts out
- **Cost**: ~$0.005–0.01/user/week with Claude Haiku (~500 input / ~300 output tokens)
