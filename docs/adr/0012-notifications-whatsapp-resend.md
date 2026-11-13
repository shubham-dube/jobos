# ADR-0012: Notifications — WhatsApp (Cloud API) + email (Resend)

- Status: Accepted
- Date: 2026-11-13
- Related: FR-HITL-3, NFR-9

## Decision
- `Notifier` interface with channels: `whatsapp` (Meta WhatsApp Cloud API), `email` (Resend), `console` (dev). Channels enabled by config; every intervention fans out to all enabled channels.
- WhatsApp messages use **interactive reply buttons** for yes/no and short choices (≤3 options), list messages for up to 10 options, and free-text replies otherwise. Each outbound message id is stored; inbound replies (webhook `/webhooks/whatsapp`) are matched by the replied-to message id (or the single open intervention) and signal the waiting workflow.
- WhatsApp business-initiated messages outside the 24h session window require an approved template; we register one generic template (`jobos_action_needed`) and switch to free-form inside an open session.
- Email via Resend from the founder's verified domain; links open the dashboard intervention page.
- Telegram channel remains a possible later addition (not built now).

## Consequences
+ The founder answers from WhatsApp in one tap.
− Needs a public HTTPS URL for the webhook when running locally (Cloudflare Tunnel recommended) and a Meta app with a WhatsApp Business phone number.
