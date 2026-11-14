# ADR-0013: Staged authentication

- Status: Accepted (decision delegated to Claude by founder)
- Date: 2026-11-13
- Related: FR-PLAT-1, security-and-privacy.md

## Decision
- **Now (single owner):** the API requires `Authorization: Bearer <JOBOS_API_TOKEN>` for dashboard calls (the Next.js server holds the token; browsers never see it) and per-runner device tokens (hashed in DB, revocable) for runners. The web app is protected by an owner password (`JOBOS_WEB_PASSWORD`) → signed HTTP-only session cookie.
- The data model is already multi-tenant (`org_id`, `candidate_id`), so nothing changes in the schema later.
- **Phase 3 (public):** Clerk (Google sign-in, MFA, organizations for agency mode); the API verifies Clerk JWTs via JWKS; an `AuthContext` dependency is the single place that changes.

## Consequences
+ Secure enough for a self-hosted single user; no vendor dependency yet.
− Must not expose the API publicly without the token; webhooks use their own signature verification.
