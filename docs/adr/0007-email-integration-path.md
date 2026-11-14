# ADR-0007: Email integration path

- Status: Accepted with amendment (2026-11-13): founder uses Gmail + Zoho Mail. Implementation order: IMAP with app passwords (both providers) → runner-driven webmail fallback → Gmail API (founder testing mode)
- Date: 2026-11-12
- Related: FR-MAIL-*, FR-ACC-3, risk R6

## Context
Inbox access powers tracking, job-alert discovery, and verification links/OTPs. Gmail API read scopes are "restricted": a public app needs Google verification plus an annual CASA security assessment (cost estimates vary widely). An unverified app can still serve up to 100 test users.

## Options
1. **Gmail API** — best UX (push notifications, labels). Restricted-scope verification for public launch.
2. **Forwarding** — user creates a Gmail filter forwarding job-related mail to `u-<id>@in.<ourdomain>`; we parse inbound mail. No Google verification. Can't read OTP mail unless it's forwarded too.
3. **IMAP with app password** — works with Gmail (2FA + app password), Outlook, others; full read; user setup friction; we store a powerful credential.
4. **Local runner reads mail** via the logged-in Gmail web session — no credentials stored server-side, but brittle.

## Decision (proposed)
- P1 (founder only): Gmail API with the founder's own Google Cloud project in testing mode.
- P2–P3 public beta: **forwarding** as the default (zero-trust, simple), IMAP as an advanced option.
- Gmail API publicly + CASA once paid users justify the cost.

## Consequences
+ No blocking compliance work before revenue.
− Forwarding setup friction; must provide a guided filter-creation flow.
