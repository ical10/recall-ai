// #47 Extension Auth Bridge — HITL (hand-written, manually audited)
//
// When #47 is implemented, this file should:
// 1. Call chrome.identity.launchWebAuthFlow → Google OAuth → get Google id_token
// 2. POST /api/auth/extension with the Google token → receive a backend bearer token
// 3. Store the backend token in chrome.storage.local
// 4. Attach as Authorization: Bearer <token> on all API calls
//
// Until then, the extension uses same-origin cookies (credentials: "include")
// which works during development (localhost:8000 served from localhost).
// In production, this must be replaced with the bearer token flow.
//
// The backend side needs:
// - POST /api/auth/extension handler that verifies a Google id_token,
//   finds/creates the user, issues a backend bearer token (JWT/signed)
// - Extend current_user dep to accept Authorization: Bearer OR session cookie
// - Extension needs its own Google OAuth client with a chrome-extension:// redirect URI
//
// See apps/api/plans/2026-06-30-phase-1-voice-extension.md #47 for full spec.
// This is intentionally not AI-written — auth code must be hand-written + reviewed.
