# SIEVE-IMPLEMENTATION.md — Chatbot Widget Integration Spec

## Overview

**Sieve** is Winnow's in-app AI concierge — a floating chatbot widget that helps candidates navigate their profile, matches, tailoring, and application tracking. It appears as a persistent floating button in the bottom-right corner of every authenticated page.

---

## Design System

### Brand Identity
- **Name:** Sieve (she/her)
- **Tagline:** "Your Personal Concierge"
- **Greeting:** "Greetings. I'm Sieve, your personal concierge. Ask me anything and I'll start sifting."
- **Logo:** Gold mining sieve with sage green holes and cascading gold particles

### Name Origin & Identity
A sieve is a utensil used for sifting, straining, or filtering solids from liquids or coarser from finer particles. Her name's pronunciation is a homonym for Siv, a Scandinavian feminine given name derived from *sif*, meaning "bride," "wife," or "connection by marriage," often associated with the Norse goddess Sif — the wife of Thor. Sif's golden hair represented fields of golden wheat, which when cut became a catalyst for the creation of the treasures of the Gods, including Thor's hammer Mjolnir. In this way, Siv is the perfect name for a companion of Winnow — the platform that separates the wheat from the chaff.

Sieve is female. She uses she/her pronouns. She is aware of her dual identity: a filtering tool that sifts the best opportunities from the noise, and a figure rooted in Norse mythology whose golden wheat connects her to the very act of winnowing. When asked about her name, she can share this story naturally and with warmth.

### Color Palette
| Token | Hex | Usage |
|-------|-----|-------|
| Hunter Green Dark | `#1B3025` | Header gradient start, user bubbles |
| Hunter Green Mid | `#243D2E` | Header gradient mid |
| Hunter Green Light | `#2A5038` | Header gradient end, FAB |
| Sieve Gold | `#E8C84A` | Logo, title text, active accents |
| Warm Parchment | `#FAF6EE` | Chat background top |
| Warm Linen | `#F5F0E4` | Chat background bottom |
| Body Text | `#3E3525` | Assistant message text |
| User Text | `#F0E8D0` | User message text |
| Sage Accent | `#CEE3D8` | Subtitle text, status text |
| Status Green | `#5CB87A` | Online indicator |

### Typography
- **Header title:** Georgia/serif, 18px, 700 weight, gold
- **Header subtitle:** System sans-serif, 11px, sage at 75% opacity
- **Messages:** System sans-serif, 14px
- **Input:** System sans-serif, 14px

### Layout
- **FAB:** 64×64px rounded circle, hunter green gradient, pulsing ring animation
- **Panel:** 380×540px, rounded-2xl (16px), drop shadow
- **Header:** 3-column CSS Grid (`1fr auto 1fr`)
  - Left: Title + subtitle
  - Center: 80px logo
  - Right: Close button + online status

---

## File Structure

```
apps/web/
├── public/
│   └── golden-sieve.svg          # Optional: standalone SVG (logo is also inline in component)
├── app/
│   ├── components/
│   │   └── sieve/
│   │       └── SieveWidget.tsx    # Main widget component
│   └── layout.tsx                 # Mount point (add <SieveWidget /> here)
```

---

## Integration Steps

### Step 1: Copy the Component

Place `SieveWidget.tsx` at:
```
apps/web/app/components/sieve/SieveWidget.tsx
```

### Step 2: Add to Root Layout

Edit `apps/web/app/layout.tsx`:

```tsx
import SieveWidget from "./components/sieve/SieveWidget";

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        {children}
        {/* Sieve chatbot — renders on all pages */}
        <SieveWidget />
      </body>
    </html>
  );
}
```

**Conditional rendering** (only for authenticated users):

```tsx
// Option A: Client-side auth check wrapper
"use client";
import { useEffect, useState } from "react";
import SieveWidget from "./components/sieve/SieveWidget";

function AuthenticatedSieve() {
  const [isAuth, setIsAuth] = useState(false);

  useEffect(() => {
    fetch(`${process.env.NEXT_PUBLIC_API_BASE_URL}/api/auth/me`, {
      credentials: "include",
    })
      .then((r) => r.ok && setIsAuth(true))
      .catch(() => {});
  }, []);

  return isAuth ? <SieveWidget /> : null;
}

// Then in layout: <AuthenticatedSieve />
```

### Step 3: Optional — Use External SVG

The component includes an inline SVG logo for zero-dependency usage. If you prefer to reference the external file:

1. Copy `golden-sieve.svg` to `apps/web/public/golden-sieve.svg`
2. Replace the `<SieveLogo>` component with:
   ```tsx
   <img src="/golden-sieve.svg" alt="Sieve" width={80} />
   ```

---

## Props

| Prop | Type | Default | Description |
|------|------|---------|-------------|
| `apiBase` | `string` | `undefined` | Backend API URL (for future real chat endpoint) |
| `position` | `"bottom-right" \| "bottom-left"` | `"bottom-right"` | Screen position |
| `greeting` | `string` | *(see above)* | Override the initial greeting message |

---

## Current Status: Demo Mode

The widget currently uses **hardcoded demo responses** keyed on simple keyword matching. This is intentional for v1 — it lets you validate the UX before wiring up the backend.

### Demo Response Keywords
| Input contains | Response topic |
|---------------|---------------|
| "help" | General capabilities |
| "match", "job" | Matches navigation |
| "profile", "resume" | Profile guidance |
| "tailor", "prepare" | Tailoring flow |
| *(anything else)* | Generic fallback |

---

## Backend Implementation (Future)

### Recommended: `POST /api/sieve/chat`

```python
# services/api/app/routers/sieve.py

@router.post("/api/sieve/chat")
async def sieve_chat(
    payload: SieveChatRequest,
    user: User = Depends(get_current_user),
):
    """
    Process a user message and return a contextual response.
    
    Future: integrate with LLM (Claude API) with system prompt
    that has access to user's profile, matches, and app state.
    """
    return {"response": generate_response(payload.message, user)}
```

### Request/Response Schema
```json
// Request
{ "message": "What jobs match my profile?" }

// Response  
{ "response": "You have 12 matches. Your top match is..." }
```

### Proactive Triggers (v2)
- Profile completeness < 70% → "Your profile is 65% complete. Want help finishing it?"
- New matches available → "3 new jobs matched since yesterday!"
- Stale application → "You saved a job 5 days ago but haven't applied. Need help?"

### Escalation Flow (v2)
- 3+ unanswered questions → "I'm not sure about that. Would you like to contact support?"
- Complex request → "That's a detailed question — let me research and get back to you."

---

## Accessibility

- FAB has `aria-label="Open Sieve assistant"`
- Close button has `aria-label="Close Sieve"`
- Input has `aria-label="Chat message"`
- Send button has `aria-label="Send message"`
- Focus is trapped in panel when open (input auto-focuses)
- Keyboard: Enter to send, standard tab navigation

---

## Animation Reference

| Animation | Duration | Purpose |
|-----------|----------|---------|
| `sieve-pulse` | 3s infinite | FAB attention ring |
| `sieve-fade-in` | 0.3s ease-out | Panel open |
| `sieve-dot-bounce` | 1.2s infinite | Typing indicator |

---

## Summary

Sieve is designed to be **drop-in ready**: one component file, one line in layout.tsx, zero external dependencies beyond React. The inline SVG logo means no additional asset files are strictly required. Future backend integration replaces a single `getDemoResponse()` function with a real API call.
