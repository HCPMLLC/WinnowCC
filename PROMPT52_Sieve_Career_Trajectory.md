# PROMPT52: Sieve Career Trajectory Coaching — Proactive Nudges

Read CLAUDE.md, PROMPT24_Sieve_v2.md, and PROMPT51_5Stage_IPS_Coaching.md before making changes.

---

## Purpose

Make Sieve proactively suggest specific actions candidates can take to improve their Career Trajectory — the AI-predicted career paths from the Career Intelligence system (Pro only). This connects two existing systems that currently don't talk to each other:

1. **Sieve** (PROMPT24) — the AI concierge with a proactive trigger engine that nudges users about profile completeness, stale applications, etc.
2. **Career Intelligence** (candidate_insights router) — trajectory predictions, salary benchmarks, and market position scoring (Pro only).

After this prompt, Sieve will:
- Detect when a Pro user's career trajectory data reveals actionable gaps
- Proactively suggest skills to acquire, certifications to pursue, and roles to target
- Answer career trajectory questions in chat with grounded, data-driven suggestions
- Nudge candidates who haven't viewed their trajectory yet

---

## What Already Exists (DO NOT recreate)

1. **Sieve trigger engine:** `services/api/app/services/sieve_triggers.py` — `evaluate_triggers()` returns a list of `Trigger` objects based on user state. Currently has 7 trigger types (profile completeness, new matches, stale saved jobs, high-scoring unreviewed, no tailored resumes, usage limits, interview coaching).

2. **Sieve chat service:** `services/api/app/services/sieve_chat.py` — `generate_chat_response()` builds a system prompt with full user context (profile, matches, billing) and calls the Anthropic API. The system prompt is where Sieve gets its personality and knowledge.

3. **Sieve router:** `services/api/app/routers/sieve.py` — `POST /api/sieve/chat` and `POST /api/sieve/triggers`.

4. **Career Intelligence service:** `services/api/app/services/career_intelligence.py` — provides trajectory predictions, salary benchmarks, and market position scoring.

5. **Career Intelligence router:** `services/api/app/routers/candidate_insights.py` — `GET /api/candidate-insights/trajectory`, `GET /api/candidate-insights/salary`, `GET /api/candidate-insights/market-position`. All Pro-gated.

6. **Billing:** `get_user_plan()` returns "free", "starter", or "pro". Career Intelligence is Pro-only (`career_intelligence: true` only in pro limits).

---

## What to Build

Three changes, in order:

### Change 1: Add Career Trajectory Trigger to the Proactive Engine
### Change 2: Enrich Sieve's System Prompt with Career Trajectory Context
### Change 3: Add a Trajectory-Aware Chat Instruction Block

---

## Change 1: Add Career Trajectory Trigger

### Step 1: Edit the trigger engine

**Where:** Open `services/api/app/services/sieve_triggers.py`

**What to change:** Find the `evaluate_triggers()` function. Inside it, after the existing trigger checks (profile completeness, stale jobs, etc.), add a new trigger block for career trajectory.

**Find** the section at the end of evaluate_triggers where the triggers list is sorted and returned. **Before** that return, add:

```python
    # ── Trigger 8: Career Trajectory Coaching (Pro only) ──
    if "career_trajectory" not in dismissed_set:
        user_plan = get_user_plan(user.id, db)
        if user_plan == "pro":
            # Check if user has trajectory data and if there are actionable gaps
            trajectory_trigger = _evaluate_trajectory_trigger(user, db)
            if trajectory_trigger:
                triggers.append(trajectory_trigger)
```

**Note:** You'll need to import `get_user_plan` from billing at the top of the file:

```python
from app.services.billing import get_user_plan
```

### Step 2: Add the trajectory evaluation helper

**Where:** Same file, `services/api/app/services/sieve_triggers.py`

**Add** this helper function at the bottom of the file (before or after the other helper functions):

```python
def _evaluate_trajectory_trigger(user, db: Session) -> Trigger | None:
    """
    Check if the Pro user has career trajectory data with actionable insights.
    
    Returns a trigger if:
    1. User has never viewed their trajectory (encourage exploration), OR
    2. User's trajectory reveals skill gaps they could close, OR
    3. User hasn't checked trajectory in >14 days (re-engagement)
    
    Returns None if no trajectory trigger is appropriate.
    """
    from app.services.career_intelligence import (
        get_career_trajectory,
        get_market_position,
    )

    try:
        # Get trajectory data
        trajectory = get_career_trajectory(user.id, db)
        if not trajectory:
            # No trajectory data yet — nudge them to explore it
            return Trigger(
                trigger_id="career_trajectory",
                priority=4,
                message="You haven't explored your Career Trajectory yet. See AI-predicted career paths based on your experience and discover which skills could open new doors.",
                action_label="View My Trajectory",
                action_type="navigate",
                action_target="/insights",
            )

        # Check if trajectory has skill gaps the user could act on
        paths = trajectory.get("paths", [])
        all_gap_skills = []
        for path in paths:
            gap_skills = path.get("skills_to_acquire", [])
            all_gap_skills.extend(gap_skills)

        if all_gap_skills:
            # Pick the top 2-3 most mentioned skills across paths
            from collections import Counter
            skill_counts = Counter(all_gap_skills)
            top_skills = [s for s, _ in skill_counts.most_common(3)]
            skills_text = ", ".join(top_skills)

            return Trigger(
                trigger_id="career_trajectory",
                priority=3,
                message=f"Your Career Trajectory shows that learning {skills_text} could unlock your next career move. Want to explore how?",
                action_label="Ask Sieve for a plan",
                action_type="chat",
                action_target=f"What's the best way to learn {top_skills[0]} to advance my career?",
            )

        # Trajectory exists but no clear gaps — check for market position insights
        market = get_market_position(user.id, db)
        if market and market.get("percentile", 100) < 60:
            return Trigger(
                trigger_id="career_trajectory",
                priority=5,
                message=f"Your market position is in the {market.get('percentile', 0)}th percentile. Sieve can suggest specific actions to move up.",
                action_label="Get improvement tips",
                action_type="chat",
                action_target="How can I improve my market position for my target roles?",
            )

    except Exception as e:
        logger.warning(f"Career trajectory trigger evaluation failed: {e}")
        return None

    return None
```

**Important:** The `get_career_trajectory` and `get_market_position` function signatures depend on what's actually in your `career_intelligence.py` service. Read that file first and adjust the import names and parameter signatures to match. The logic above is the pattern — adapt the function calls to your actual implementation.

---

## Change 2: Enrich Sieve's System Prompt with Career Context

### Step 3: Edit the Sieve chat service

**Where:** Open `services/api/app/services/sieve_chat.py`

**What to change:** Find the function that builds the system prompt for the LLM (the one that assembles user context — profile, matches, billing, etc. — into a system message). It's likely called something like `_build_system_prompt()` or is inline in `generate_chat_response()`.

**Find** the section where user context is assembled. After the existing context blocks (profile, matches, billing), **add** a new block for career intelligence data. Add this **only for Pro users**:

```python
    # ── Career Intelligence Context (Pro only) ──
    career_context = ""
    if user_plan == "pro":
        try:
            from app.services.career_intelligence import (
                get_career_trajectory,
                get_market_position,
                get_salary_benchmarks,
            )

            trajectory = get_career_trajectory(user.id, db)
            market_pos = get_market_position(user.id, db)
            
            if trajectory:
                paths_summary = []
                for i, path in enumerate(trajectory.get("paths", [])[:3], 1):
                    title = path.get("target_title", "Unknown")
                    timeline = path.get("timeline_months", "?")
                    skills_needed = path.get("skills_to_acquire", [])
                    salary_range = path.get("expected_salary", "")
                    paths_summary.append(
                        f"  Path {i}: {title} (est. {timeline} months). "
                        f"Skills to acquire: {', '.join(skills_needed[:5]) if skills_needed else 'None identified'}. "
                        f"Expected salary: {salary_range}"
                    )
                career_context += f"""
## CAREER TRAJECTORY (Pro Feature)
The candidate has {len(trajectory.get('paths', []))} predicted career paths:
{chr(10).join(paths_summary)}
"""

            if market_pos:
                career_context += f"""
## MARKET POSITION
Percentile: {market_pos.get('percentile', 'N/A')}th
Strengths: {', '.join(market_pos.get('strengths', ['Not assessed'])[:5])}
Weaknesses: {', '.join(market_pos.get('weaknesses', ['Not assessed'])[:5])}
"""

        except Exception as e:
            logger.warning(f"Failed to load career context for Sieve: {e}")
```

**Then append `career_context` to the system prompt string.** Find where the system prompt is finalized (concatenated) and add `career_context` to it.

---

## Change 3: Add Trajectory-Aware Instructions to System Prompt

### Step 4: Add coaching instructions to the system prompt

**Where:** Same file, `services/api/app/services/sieve_chat.py`

**What to change:** Find the system prompt instructions — the block that tells the LLM how to behave as Sieve (personality, rules, what data it has access to). **Add** these instructions to the prompt:

**Find** the existing instruction text (something like "You are Sieve, an AI career concierge..."). **After** the existing instructions, add this paragraph:

```python
    # Add this to the system prompt instructions string:
    career_coaching_instructions = ""
    if user_plan == "pro" and career_context:
        career_coaching_instructions = """

## CAREER TRAJECTORY COACHING RULES

When the candidate asks about career growth, trajectory, next steps, skill development, 
certifications, promotions, or their market position, you MUST:

1. Reference their ACTUAL career trajectory data shown above. Do not guess — use the 
   predicted paths, skills to acquire, and timeline estimates from the data.

2. Give SPECIFIC, actionable suggestions. Not "consider learning new skills" but rather 
   "Your trajectory shows that learning Kubernetes and Terraform could qualify you for 
   Cloud Infrastructure Manager roles within 12-18 months."

3. Prioritize suggestions by impact:
   a. Skills that appear in multiple career paths (highest leverage)
   b. Skills that close gaps for their top-scoring job matches
   c. Certifications that are commonly required for their target roles
   d. Experience types they're missing (leadership, cross-functional, etc.)

4. When suggesting skill development, be concrete about HOW:
   - Free resources (official docs, YouTube channels, open courseware)
   - Certifications with estimated time and cost
   - Side projects they could build to demonstrate the skill
   - Ways to gain the experience at their current job

5. Connect trajectory advice to their CURRENT matches when relevant. For example:
   "Your top match at Stripe requires Kubernetes — learning it would boost your 
   Resume Fit score for that role AND move you toward the Cloud Infrastructure path."

6. If the candidate's market position percentile is below 60, proactively mention 
   specific actions that would improve their ranking. Be encouraging but honest.

7. Never fabricate career data. If trajectory data is limited, say so and suggest 
   completing their profile to improve predictions.

8. For Starter or Free users who ask about career trajectory, explain that this is 
   a Pro feature and briefly describe what they'd get — but don't gate the general 
   career advice. Give them useful direction, just without the personalized trajectory data.
"""
```

**Append `career_coaching_instructions` to the system prompt** in the same place you added `career_context`.

---

## Testing

### Step 5: Test the trigger

**Where:** Terminal in `services/api/`

1. Start all services: `.\start-dev.ps1`

2. **As a Pro user who has NOT viewed their trajectory:**
   - Call `POST /api/sieve/triggers`
   - Verify response includes a trigger with `trigger_id: "career_trajectory"` and message about exploring trajectory
   - Verify `action_type: "navigate"` with `action_target: "/insights"`

3. **As a Pro user WITH trajectory data showing skill gaps:**
   - Ensure trajectory data exists (call `GET /api/candidate-insights/trajectory` first to generate it)
   - Call `POST /api/sieve/triggers`
   - Verify trigger message mentions specific skills (e.g., "learning Kubernetes, Terraform could unlock...")
   - Verify `action_type: "chat"` with a pre-filled question as `action_target`

4. **As a Free or Starter user:**
   - Call `POST /api/sieve/triggers`
   - Verify NO career_trajectory trigger appears (it's Pro-only)

### Step 6: Test the chat integration

1. **As a Pro user, open the Sieve chat widget**

2. **Ask:** "What should I do to advance my career?"
   - Verify Sieve references the actual career trajectory paths from the data
   - Verify suggestions are specific (skill names, certifications, timelines)
   - Verify Sieve connects advice to current job matches when relevant

3. **Ask:** "How do I learn [skill from trajectory gaps]?"
   - Verify Sieve provides concrete learning resources and approaches
   - Verify suggestions include free resources, certifications, and side projects

4. **Ask:** "What's my market position and how can I improve it?"
   - Verify Sieve references actual percentile and strengths/weaknesses
   - Verify improvement suggestions are specific and actionable

5. **As a Starter user, ask:** "What career paths are available to me?"
   - Verify Sieve provides useful general advice
   - Verify Sieve mentions that Career Trajectory is a Pro feature with personalized predictions
   - Verify Sieve does NOT fabricate trajectory data it doesn't have

### Step 7: Test trigger dismissal

1. Click the career trajectory trigger in the Sieve widget
2. Dismiss it
3. Refresh and verify it doesn't reappear

### Step 8: Lint and format

```powershell
cd services/api
.\.venv\Scripts\Activate.ps1
python -m ruff check .
python -m ruff format .
```

---

## Summary — Files Changed

| # | Action | File | What |
|---|--------|------|------|
| 1 | **EDIT** | `services/api/app/services/sieve_triggers.py` | Add trigger type 8: career_trajectory (Pro only) + `_evaluate_trajectory_trigger()` helper |
| 2 | **EDIT** | `services/api/app/services/sieve_chat.py` | Add career intelligence context block to system prompt (trajectory paths, market position) |
| 3 | **EDIT** | `services/api/app/services/sieve_chat.py` | Add CAREER TRAJECTORY COACHING RULES instruction block to system prompt |

**Total: 2 files edited. No new files. No migration. No new endpoints.**

---

## How It Works End-to-End

1. **Pro user logs in.** Sieve widget opens.
2. **Trigger engine runs.** Checks career trajectory data. Finds the user hasn't viewed it yet, OR finds skill gaps.
3. **Nudge appears** in the Sieve widget: "Your Career Trajectory shows that learning Kubernetes and Terraform could unlock your next career move. Want to explore how?"
4. **User clicks "Ask Sieve for a plan."** Chat opens with pre-filled message: "What's the best way to learn Kubernetes to advance my career?"
5. **Sieve responds** with the user's actual trajectory data as context. Gives specific learning resources, certification recommendations, side project ideas, and connects it to their current job matches.
6. **User asks follow-up:** "Which of my current matches would benefit most from Kubernetes?"
7. **Sieve cross-references** trajectory skills with match gap data and identifies the specific matches where Kubernetes would boost their Resume Fit score.

This creates a feedback loop: trajectory → skill gaps → learning plan → better matches → better IPS → more interviews. That's the stickiness that keeps Pro users subscribed.
