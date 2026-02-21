Prompt: Update the Winnow login/landing page
Update the app’s login/landing experience so that it:
Branding
Use the Winnow logo for brand recognition (text or image).
Layout
Two-column layout: left = login, right = sign-up/visual.
Left: distraction-free login form.
Right: sign-up CTA and supporting content.
Clean, modern, professional look.
Login section (left)
Email + password fields.
Forgot password link (e.g. to /forgot-password or Auth0 reset).
Social login via Auth0 with buttons for: LinkedIn, Google, GitHub, Microsoft, Apple.
Short headline or welcome line that explains the page.
Sign-up prompt for new users (e.g. “Don’t have an account? Sign up”).
Right column
Background: video from public/winnow-bg.mp4 (user copies “Winnow Vid AI Gend.mp4” to that path).
Sign-up CTA and value copy (no heavy images; use copy to add value).
Optional: highlight for returning users and a clear CTA (e.g. “Learn more” about new/plugin features).
Technical
Keep existing email/password API login; add Auth0 for social logins (Auth0 SDK + env vars).
Ensure / and /login are public and that unauthenticated users see this page; after login, redirect per existing redirect/onboarding logic.
Copy and UX
Headline and short welcome text that clarify the page’s purpose.
Clear value for both new users (sign up) and returning users (login + feature highlights).
One bold primary CTA (e.g. “Log in” or “Sign in”) and a secondary CTA for sign-up/learn more.
Implement this in the Next.js app under apps/web (e.g. by redesigning the home page and/or login page and wiring Auth0 and the video path).