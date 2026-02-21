# PROMPT18_Sieve_Backend_Completion.md

Read SPEC.md, ARCHITECTURE.md, CLAUDE.md, and SIEVE-IMPLEMENTATION.md before making changes.

## Purpose

Replace the Sieve chatbot's hardcoded demo keyword responses with a real backend API powered by Claude. Sieve becomes a context-aware AI concierge that knows the user's profile, matches, application tracking status, and can give genuinely useful guidance — not canned responses.

This is the transition from "pretty widget with fake answers" to "intelligent assistant that actually helps candidates."

---

## Triggers — When to Use This Prompt

- Wiring the Sieve chatbot widget to a real backend endpoint.
- Integrating Claude API as the LLM powering Sieve.
- Making Sieve context-aware (profile, matches, tracking data).
- Replacing `getDemoResponse()` in `SieveWidget.tsx` with real API calls.

---

## What Already Exists (DO NOT recreate — read the codebase first)

1. **Sieve widget (frontend):** `apps/web/app/components/sieve/SieveWidget.tsx` — fully styled floating chatbot with FAB, chat panel, message bubbles, typing indicator, input field. Currently uses a local `getDemoResponse()` function with keyword matching (help → capabilities, match/job → matches navigation, profile/resume → profile guidance, tailor/prepare → tailoring flow, default → generic fallback). The widget accepts an `apiBase` prop (currently unused).

2. **Sieve brand design:** Fully specified in `SIEVE-IMPLEMENTATION.md` — colors, typography, layout, animations, accessibility. DO NOT change any visual design.

3. **Auth system:** `services/api/app/services/auth.py` — `get_current_user` dependency reads the `rm_session` HttpOnly cookie. All Sieve API calls must be authenticated.

4. **Candidate profile:** `services/api/app/models/candidate_profile.py` — `profile_json` JSONB with experience, skills, preferences, etc.

5. **Matches:** `services/api/app/models/match.py` — `match_score`, `reasons` JSON, `application_status`, `referred`.

6. **Dashboard metrics:** `GET /api/dashboard/metrics` — returns profile completeness, qualified jobs count, applications, interviews, offers.

7. **Tailoring:** `POST /api/tailor/{job_id}` — already generates tailored resumes.

8. **Anthropic SDK:** Already in `requirements.txt` with `ANTHROPIC_API_KEY` in `.env` (from PROMPT11/PROMPT12).

9. **Queue/Worker:** `services/api/app/services/queue.py` + `services/api/app/worker.py` — RQ-based background jobs (NOT needed for Sieve — chat responses should be synchronous and fast).

10. **Root layout:** `apps/web/app/layout.tsx` — mounts `<SieveWidget />` (or `<AuthenticatedSieve />`) on all pages.

---

## Architecture Overview

```
  User types message in SieveWidget
          │
          ▼
  POST /api/sieve/chat  (with credentials: "include")
    Body: { "message": "...", "conversation_history": [...] }
          │
          ▼
  Backend: sieve router
    1. Load user context (profile, top matches, tracking stats, completeness)
    2. Build Claude system prompt with context
    3. Append conversation history (last 10 exchanges)
    4. Call Claude API (claude-sonnet-4-20250514, max_tokens=512)
    5. Return response + suggested quick-reply actions
          │
          ▼
  Frontend: display assistant message + quick-reply chips in chat panel
```

Key design decisions:
- **Synchronous, not queued.** Chat must feel instant. Claude Sonnet responds in 1–3 seconds which is acceptable for a chatbot.
- **No database for conversation history.** Store conversation history in frontend state (reset when widget closes). The backend receives the last N messages with each request for context. This keeps the implementation simple and avoids a new migration.
- **Context is injected per-request.** The backend loads the user's profile, top matches, and tracking stats fresh on each call. This keeps responses accurate and avoids stale data.

---

## What to Build

### Part 1: Sieve Backend Service

**File to create:** `services/api/app/services/sieve.py` (NEW)

This service handles context loading and Claude API calls.

#### 1.1 Context loader

Build a function that loads everything Sieve needs to know about the user:

```python
async def load_user_context(user_id: int, db) -> dict:
    """
    Load the user's current state for Sieve's system prompt.
    Returns a dict with profile summary, match highlights, tracking stats, etc.
    """
    context = {}

    # ── Profile ──────────────────────────────────
    # Load latest CandidateProfile for this user
    # Extract: name, skills count, experience count, preferences (target titles, remote pref, salary range)
    # Calculate or fetch profile completeness score
    context["profile"] = {
        "name": "...",                    # from profile_json.basics.name or contact_information.full_name
        "completeness_score": 72,         # from profile scoring service
        "skills_count": 15,
        "experience_count": 4,
        "target_titles": ["Backend Developer", "Python Engineer"],
        "remote_preference": "remote",
        "has_resume": True,               # whether resume_documents exists
    }

    # ── Matches ──────────────────────────────────
    # Load top 5 matches by match_score (active jobs only)
    # For each: job title, company, match_score, top 3 matched skills, top 2 missing skills
    context["matches"] = {
        "total_count": 47,
        "top_matches": [
            {"title": "Senior Python Developer", "company": "Acme Corp", "score": 89,
             "matched_skills": ["Python", "FastAPI", "PostgreSQL"], "missing_skills": ["Kubernetes"]},
            # ... up to 5
        ],
        "avg_match_score": 72,
    }

    # ── Tracking stats ───────────────────────────
    # Count matches by application_status
    context["tracking"] = {
        "saved": 5,
        "applied": 12,
        "interviewing": 2,
        "rejected": 3,
        "offer": 0,
    }

    # ── Tailored resumes ─────────────────────────
    # Count of generated tailored resumes
    context["tailored_resumes_count"] = 8

    return context
```

#### 1.2 System prompt builder

Build the system prompt that tells Claude who it is and gives it user context:

```python
def build_system_prompt(user_context: dict) -> str:
    """
    Build the Claude system prompt for Sieve.
    This defines Sieve's personality, capabilities, and the user's current state.
    """
    profile = user_context.get("profile", {})
    matches = user_context.get("matches", {})
    tracking = user_context.get("tracking", {})
    tailored_count = user_context.get("tailored_resumes_count", 0)

    return f"""You are Sieve, the personal AI concierge for Winnow — a job matching platform.

PERSONALITY:
- Warm, professional, and encouraging. Think: a supportive career coach who also has access to real data.
- Address the user by first name when you know it.
- Keep responses concise — 2–4 sentences for simple questions, up to a short paragraph for complex ones.
- Use a confident but not pushy tone. You are here to help, not sell.
- When you don't know something specific, say so honestly. Never fabricate data.

CAPABILITIES — What you CAN help with:
- Explaining match scores and why jobs matched (or didn't)
- Suggesting which matched jobs to apply to first (prioritization)
- Advising on profile improvements to increase match scores
- Guiding users through the tailored resume generation process
- Explaining the interview probability score and how to improve it
- Helping track application progress and next steps
- General job search tips, resume advice, interview preparation

LIMITATIONS — What you CANNOT do:
- You cannot apply to jobs on the user's behalf
- You cannot modify the user's profile directly (suggest they edit it)
- You cannot guarantee interview outcomes
- You cannot access external websites or job boards
- You do not have access to other users' data

CURRENT USER STATE:
- Name: {profile.get('name', 'there')}
- Profile completeness: {profile.get('completeness_score', 'unknown')}%
- Skills on profile: {profile.get('skills_count', 0)}
- Work experiences listed: {profile.get('experience_count', 0)}
- Target roles: {', '.join(profile.get('target_titles', ['not specified']))}
- Remote preference: {profile.get('remote_preference', 'not specified')}
- Has uploaded resume: {'Yes' if profile.get('has_resume') else 'No'}
- Total job matches: {matches.get('total_count', 0)}
- Average match score: {matches.get('avg_match_score', 0)}/100
- Tailored resumes generated: {tailored_count}

APPLICATION PIPELINE:
- Saved: {tracking.get('saved', 0)}
- Applied: {tracking.get('applied', 0)}
- Interviewing: {tracking.get('interviewing', 0)}
- Rejected: {tracking.get('rejected', 0)}
- Offers: {tracking.get('offer', 0)}

TOP MATCHES (for reference when user asks about matches):
{_format_top_matches(matches.get('top_matches', []))}

RESPONSE GUIDELINES:
- If profile completeness < 70%, gently suggest improvements when relevant.
- If user has 0 matches, suggest they check their preferences or add more skills.
- If user has matches but 0 applications, encourage them to start applying.
- If user asks about a specific job or match, reference the top matches data above.
- If user asks how to improve their score, give specific, actionable advice based on their profile gaps.
- If user mentions tailoring, explain that they can generate a job-specific ATS resume from any match.
- Always be honest about what the data shows. Do not inflate or minimize.
- Use markdown formatting sparingly (bold for emphasis, bullet lists only when listing 3+ items).
- End responses with a suggested next action when appropriate (e.g., "Want me to help you prioritize which jobs to apply to first?").
"""


def _format_top_matches(top_matches: list) -> str:
    """Format top matches for the system prompt."""
    if not top_matches:
        return "  No matches yet."
    lines = []
    for i, m in enumerate(top_matches, 1):
        matched = ', '.join(m.get('matched_skills', []))
        missing = ', '.join(m.get('missing_skills', []))
        lines.append(
            f"  {i}. {m['title']} at {m['company']} — Score: {m['score']}/100"
            f"\n     Matched: {matched}"
            f"\n     Missing: {missing}"
        )
    return '\n'.join(lines)
```

#### 1.3 Chat handler

```python
import os
import anthropic
import logging

logger = logging.getLogger(__name__)

_client = None

def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    return _client


async def handle_chat(
    user_id: int,
    message: str,
    conversation_history: list[dict],
    db,
) -> str:
    """
    Process a user message and return Sieve's response.

    Args:
        user_id: Authenticated user's ID
        message: The user's latest message
        conversation_history: List of prior messages [{"role": "user"|"assistant", "content": "..."}]
        db: Database session

    Returns:
        Sieve's response text
    """
    # 0. Check API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return _get_fallback_response(message)

    # 1. Rate limit
    if not _check_rate_limit(user_id):
        return "You're sending messages quite fast! Give me a moment to catch up. Try again in a few seconds."

    # 2. Load user context
    user_context = await load_user_context(user_id, db)

    # 3. Build system prompt
    system_prompt = build_system_prompt(user_context)

    # 4. Build messages array (keep last 20 messages = ~10 exchanges)
    messages = []
    for msg in conversation_history[-20:]:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": message})

    # 5. Call Claude
    try:
        client = _get_client()
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=512,
            system=system_prompt,
            messages=messages,
        )
        return response.content[0].text
    except anthropic.APIError as e:
        logger.error(f"Sieve Claude API error: {e}")
        return "I'm having trouble connecting right now. Please try again in a moment."
    except Exception as e:
        logger.error(f"Sieve unexpected error: {e}")
        return "Something went wrong on my end. Try asking again?"
```

#### 1.4 Rate limiter

```python
import time
from collections import defaultdict

_rate_limits: dict[int, list[float]] = defaultdict(list)
MAX_MESSAGES_PER_MINUTE = 10

def _check_rate_limit(user_id: int) -> bool:
    """Returns True if the user is within rate limits."""
    now = time.time()
    _rate_limits[user_id] = [t for t in _rate_limits[user_id] if now - t < 60]
    if len(_rate_limits[user_id]) >= MAX_MESSAGES_PER_MINUTE:
        return False
    _rate_limits[user_id].append(now)
    return True
```

#### 1.5 Fallback responses (when API key is not configured)

```python
def _get_fallback_response(message: str) -> str:
    """Keyword-based fallback mirroring original demo mode."""
    lower = message.lower()
    if any(w in lower for w in ["help", "what can you"]):
        return "I can help you navigate your profile, understand your job matches, and guide you through generating tailored resumes. What would you like to know?"
    if any(w in lower for w in ["match", "job"]):
        return "Check out your Matches page to see jobs ranked by how well they fit your profile. You can generate a tailored resume for any match!"
    if any(w in lower for w in ["profile", "resume", "skill"]):
        return "A complete profile leads to better matches. Head to your Profile page to review and update your skills, experience, and preferences."
    if any(w in lower for w in ["tailor", "ats", "prepare", "apply"]):
        return "On any match card, click 'Generate ATS Resume' to create a job-specific resume. It highlights your most relevant experience for that role."
    return "I'm here to help with your job search. Try asking about your matches, profile, or how to generate a tailored resume."
```

#### 1.6 Suggested actions generator

```python
def get_suggested_actions(user_context: dict) -> list[str]:
    """Generate 2–3 context-aware quick-reply suggestions."""
    profile = user_context.get("profile", {})
    matches = user_context.get("matches", {})
    tracking = user_context.get("tracking", {})

    suggestions = []

    if profile.get("completeness_score", 0) < 70:
        suggestions.append("How can I improve my profile?")
    if matches.get("total_count", 0) > 0 and tracking.get("applied", 0) == 0:
        suggestions.append("Which jobs should I apply to first?")
    if tracking.get("applied", 0) > 0 and tracking.get("interviewing", 0) == 0:
        suggestions.append("Any tips for getting interviews?")
    if matches.get("total_count", 0) > 0:
        suggestions.append("Tell me about my top match")
    if tracking.get("interviewing", 0) > 0:
        suggestions.append("Help me prepare for interviews")

    if not suggestions:
        suggestions = ["What can you help me with?", "Show me my matches", "How's my profile?"]

    return suggestions[:3]
```

---

### Part 2: Sieve API Router

**File to create:** `services/api/app/routers/sieve.py` (NEW)

```python
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.services.auth import get_current_user
from app.db.session import get_db

router = APIRouter(prefix="/api/sieve", tags=["sieve"])


class SieveChatRequest(BaseModel):
    message: str
    conversation_history: list[dict] = []


class SieveChatResponse(BaseModel):
    response: str
    suggested_actions: list[str] = []


@router.post("/chat", response_model=SieveChatResponse)
async def sieve_chat(
    payload: SieveChatRequest,
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    """Send a message to Sieve and get a contextual response. Requires authentication."""
    from app.services.sieve import handle_chat, load_user_context, get_suggested_actions

    # Validate input
    if len(payload.message.strip()) == 0:
        return SieveChatResponse(response="I didn't catch that. Could you try again?")
    if len(payload.message) > 2000:
        return SieveChatResponse(response="That's a very long message! Could you break it into shorter questions?")

    # Truncate history to prevent abuse
    history = payload.conversation_history[-20:] if payload.conversation_history else []

    # Get response
    response_text = await handle_chat(
        user_id=user.id,
        message=payload.message,
        conversation_history=history,
        db=db,
    )

    # Get suggested actions
    user_context = await load_user_context(user.id, db)
    suggestions = get_suggested_actions(user_context)

    return SieveChatResponse(response=response_text, suggested_actions=suggestions)
```

**File to modify:** `services/api/app/main.py`

Add the Sieve router alongside the existing routers:

```python
from app.routers import sieve as sieve_router

# In the router registration section:
app.include_router(sieve_router.router)
```

---

### Part 3: Update the Frontend Widget

**File to modify:** `apps/web/app/components/sieve/SieveWidget.tsx`

Replace the demo response logic with real API calls. **Do NOT change any visual design, colors, typography, layout, or animations.**

#### 3.1 Changes required

1. **Remove** the `getDemoResponse()` function entirely.

2. **Add** conversation history and suggested actions state:
   ```typescript
   const [conversationHistory, setConversationHistory] = useState<
     { role: "user" | "assistant"; content: string }[]
   >([]);
   const [suggestedActions, setSuggestedActions] = useState<string[]>([]);
   ```

3. **Replace** the message send handler. Currently it calls `getDemoResponse()`. Replace with:

   ```typescript
   const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || "";

   // Show typing indicator
   setIsTyping(true);

   try {
     const res = await fetch(`${apiBase}/api/sieve/chat`, {
       method: "POST",
       headers: { "Content-Type": "application/json" },
       credentials: "include",
       body: JSON.stringify({
         message: userMessage,
         conversation_history: conversationHistory,
       }),
     });

     if (!res.ok) throw new Error(`Sieve API error: ${res.status}`);

     const data = await res.json();

     // Update conversation history
     setConversationHistory(prev => [
       ...prev,
       { role: "user", content: userMessage },
       { role: "assistant", content: data.response },
     ]);

     // Update suggested actions
     setSuggestedActions(data.suggested_actions || []);

     // Display the response
     setMessages(prev => [...prev, { role: "assistant", content: data.response }]);
   } catch (error) {
     console.error("Sieve chat error:", error);
     setMessages(prev => [
       ...prev,
       { role: "assistant", content: "I'm having trouble connecting. Please try again." },
     ]);
   } finally {
     setIsTyping(false);
   }
   ```

4. **Keep the typing indicator** showing during the API call (the widget already has the animation — just keep `isTyping` true until the response arrives).

5. **Keep the static greeting** as the first message. It does NOT come from the API.

6. **Reset conversation history** when the widget is closed:
   ```typescript
   const handleClose = () => {
     setIsOpen(false);
     // Optional: reset on close
     // setConversationHistory([]);
     // setMessages([initialGreeting]);
     // setSuggestedActions([]);
   };
   ```

#### 3.2 Quick-reply chips

After the last assistant message, render clickable suggestion chips:

```typescript
{suggestedActions.length > 0 && (
  <div style={{ display: "flex", flexWrap: "wrap", gap: "6px", padding: "4px 16px 8px" }}>
    {suggestedActions.map((action, i) => (
      <button
        key={i}
        onClick={() => handleSendMessage(action)}
        style={{
          background: "transparent",
          border: "1px solid #E8C84A",
          borderRadius: "16px",
          padding: "6px 14px",
          fontSize: "12px",
          color: "#3E3525",
          cursor: "pointer",
          transition: "all 0.2s",
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.background = "#E8C84A";
          e.currentTarget.style.color = "#1B3025";
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.background = "transparent";
          e.currentTarget.style.color = "#3E3525";
        }}
      >
        {action}
      </button>
    ))}
  </div>
)}
```

Clicking a chip should trigger the same send flow as typing a message and pressing Enter.

#### 3.3 Markdown rendering (optional enhancement)

For rendering light markdown (bold, bullets) in assistant messages, either:

**Option A: Simple regex (no dependencies)**
```typescript
function renderMarkdown(text: string): string {
  let html = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  const lines = html.split('\n');
  let inList = false;
  const rendered = lines.map(line => {
    if (line.trim().startsWith('- ')) {
      if (!inList) { inList = true; return '<ul style="margin:4px 0;padding-left:18px"><li>' + line.trim().slice(2) + '</li>'; }
      return '<li>' + line.trim().slice(2) + '</li>';
    } else {
      if (inList) { inList = false; return '</ul>' + line; }
      return line;
    }
  }).join('<br/>');
  return rendered + (inList ? '</ul>' : '');
}
// Use: <div dangerouslySetInnerHTML={{ __html: renderMarkdown(msg.content) }} />
```

**Option B: Install react-markdown**
```powershell
cd apps/web
npm install react-markdown
```
```typescript
import ReactMarkdown from 'react-markdown';
// Use: <ReactMarkdown>{msg.content}</ReactMarkdown>
```

---

## File and Component Reference

| What | Where | Action |
|------|-------|--------|
| Sieve service (core logic) | `services/api/app/services/sieve.py` | CREATE — context loader, system prompt, Claude API call, rate limiter, fallback, suggested actions |
| Sieve router | `services/api/app/routers/sieve.py` | CREATE — POST /api/sieve/chat endpoint |
| Register router | `services/api/app/main.py` | MODIFY — import and include sieve router |
| Sieve widget | `apps/web/app/components/sieve/SieveWidget.tsx` | MODIFY — replace getDemoResponse with real API call, add conversation history, add quick-reply chips |

---

## Implementation Order (for a beginner following in Cursor)

### Phase 1: Backend Service (Steps 1–4)

1. **Step 1:** Create `services/api/app/services/sieve.py`.
   - Start with the `load_user_context` function. Read the existing models to understand the schema.
   - Implement using SQLAlchemy queries to load profile, matches, tracking stats.

2. **Step 2:** In the same file, add `build_system_prompt` and `_format_top_matches`.

3. **Step 3:** In the same file, add `handle_chat` with Claude API call, `_check_rate_limit`, and `_get_fallback_response`.

4. **Step 4:** In the same file, add `get_suggested_actions`.

### Phase 2: API Router (Steps 5–6)

5. **Step 5:** Create `services/api/app/routers/sieve.py` with the `POST /api/sieve/chat` endpoint.

6. **Step 6:** Register the router in `services/api/app/main.py`:
   ```python
   from app.routers import sieve as sieve_router
   app.include_router(sieve_router.router)
   ```

### Phase 3: Test the Backend (Step 7)

7. **Step 7:** Test the endpoint manually:
   ```powershell
   cd infra
   docker compose up -d

   cd services/api
   .\.venv\Scripts\Activate.ps1
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

   Open `http://127.0.0.1:8000/docs`, authenticate, then test:
   ```json
   POST /api/sieve/chat
   {
     "message": "What are my best job matches?",
     "conversation_history": []
   }
   ```

   Verify:
   - [ ] Response comes back in < 5 seconds
   - [ ] Response references the user's actual profile data
   - [ ] Response mentions specific matches (if any exist)
   - [ ] `suggested_actions` array is returned
   - [ ] Rate limiting works (send 11 messages quickly)
   - [ ] Empty message handled gracefully
   - [ ] Long message (>2000 chars) handled gracefully

### Phase 4: Frontend Integration (Steps 8–10)

8. **Step 8:** Open `apps/web/app/components/sieve/SieveWidget.tsx` in Cursor.
   - Add `conversationHistory` and `suggestedActions` state.
   - Remove the `getDemoResponse` function.
   - Replace the message send handler with the real API call.
   - Keep typing indicator showing during the API call.
   - Keep the static greeting as first message.

9. **Step 9:** Add quick-reply chip rendering below the last assistant message. Style with Sieve brand colors (gold border, pill shape).

10. **Step 10:** (Optional) Add markdown rendering for assistant messages using the simple regex renderer or `react-markdown`.

### Phase 5: End-to-End Test (Step 11)

11. **Step 11:** Full end-to-end verification. Open `http://localhost:3000/dashboard`. Click the Sieve FAB. Test:

    - [ ] "What can you help me with?" → Returns capabilities
    - [ ] "Tell me about my top matches" → References actual match data
    - [ ] "How can I improve my profile?" → Specific advice based on completeness score
    - [ ] "How do I generate a tailored resume?" → Explains the tailoring flow
    - [ ] "What should I apply to first?" → Prioritizes based on match scores
    - [ ] Multi-turn: ask a follow-up → Claude remembers context
    - [ ] Quick-reply chips appear after responses
    - [ ] Clicking a chip sends it as a message
    - [ ] Typing indicator shows while waiting
    - [ ] Error state: stop the API → widget shows fallback error message
    - [ ] Close and reopen widget → conversation resets

### Phase 6: Lint (Step 12)

12. **Step 12:** Lint and format:
    ```powershell
    cd services/api
    python -m ruff check .
    python -m ruff format .

    cd apps/web
    npm run lint
    ```

---

## Cost Estimate

- Claude Sonnet: ~$3/M input tokens, ~$15/M output tokens
- Sieve system prompt: ~800 tokens per call
- Average conversation (5 exchanges): ~5,000 input + ~2,500 output tokens ≈ $0.05
- Per user per day (3 conversations): ~$0.005
- 1,000 active users: ~$5/day ≈ $150/month

The rate limiter (10 messages/minute) prevents abuse.

---

## Non-Goals (Do NOT implement in this prompt)

- Conversation persistence in the database (keep in frontend state only)
- Streaming responses (future enhancement — start with synchronous)
- Proactive triggers / push messages (that's SIEVE v2)
- Tool use / function calling (Claude directly querying the DB — too complex for v1)
- Multi-modal input (image upload in chat)
- Admin dashboard for Sieve analytics
- A/B testing of system prompts

---

## Summary Checklist

- [ ] Backend service: `sieve.py` created with context loader, system prompt builder, Claude API call
- [ ] Backend service: fallback responses when ANTHROPIC_API_KEY not set
- [ ] Backend service: rate limiter (10 messages/minute per user)
- [ ] Backend service: suggested actions generator (context-aware quick replies)
- [ ] Router: `POST /api/sieve/chat` endpoint with auth, validation, response schema
- [ ] Router: registered in `main.py`
- [ ] Frontend: `getDemoResponse` removed from SieveWidget.tsx
- [ ] Frontend: real API call with `credentials: "include"` replaces demo logic
- [ ] Frontend: conversation history tracked in state and sent with each request
- [ ] Frontend: typing indicator shown during API call
- [ ] Frontend: quick-reply chips rendered below assistant messages (Sieve Gold border, pill shape)
- [ ] Frontend: error handling for API failures (shows fallback message)
- [ ] Frontend: static greeting message preserved as first message
- [ ] Frontend: (optional) markdown rendering for assistant messages
- [ ] End-to-end: Sieve references real user data (profile, matches, tracking)
- [ ] End-to-end: multi-turn conversation works (Claude remembers context)
- [ ] End-to-end: response time < 5 seconds
- [ ] Linted and formatted

Return code changes only.
