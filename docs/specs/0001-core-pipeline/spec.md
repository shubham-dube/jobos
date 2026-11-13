# Spec 0001: Core pipeline (founder MVP)

Status: In progress (implemented on `feat/core-pipeline`; founder acceptance pending)
Workstreams: A, B, C, D, E, F, G, H, I · Phase: P1 · PRD: FR-PROF-1..4, FR-ANS-1..3, FR-SRCH-1, FR-POL-1..2,
FR-DISC-1..3,5, FR-VER-1, FR-MATCH-1..2, FR-APP-1,3,5,6,7, FR-HITL-1..5, FR-MAIL-1..3, FR-DASH-1
ADRs: 0004, 0005, 0008, 0010–0015

## Problem
The founder needs the autopilot working end to end on their own machine: find → verify → match → apply via a real
browser → ask when unsure → remember → track replies.

## Acceptance criteria
- [x] AC1 Profile import from resume/profile text produces a structured, versioned master profile (raw values only).
- [x] AC2 Discovery crawls Greenhouse/Lever/Ashby boards (111 seeded, grows from pasted URLs), dedups, filters
      (keywords, seniority, countries, recency), assesses visa/eligibility for an Indian citizen, scores legitimacy,
      and LLM-scores fit with reasons/gaps.
- [x] AC3 Applying works on unknown sites via the generic extractor; verified live (dry run) on Greenhouse and Lever.
- [x] AC4 Every filled value has a source; unknown required answers become interventions; answers are remembered.
      Required uploads other than the resume (transcript, cover letter) are filled from Documents by kind; if none
      is stored, the intervention asks for a file, which is saved to Documents and reused (never put in the answer
      bank). Required-ness is read from the visible label too (Greenhouse hides the input's own label).
- [x] AC5b A submit the site's own validation rejects (form still on screen with field errors) is recorded as
      `failed` (nothing was sent, retryable), never `uncertain`.
- [x] AC5 Submit only via the gate; default review; founder-defined approval rules can auto-submit.
- [x] AC6 Durable: waiting days for an answer or review survives restarts; tab loss after review triggers replay.
- [x] AC7 Evidence: per-page fill plan, read-back results, screenshots, timeline.
- [x] AC8 Inbox: IMAP (Gmail/Zoho app passwords) sync, classification, linking, state updates.
- [x] AC9 Notifications: WhatsApp (buttons/list/text replies) and Resend email.
- [x] AC10 Dashboard: overview, jobs, applications (evidence), inbox, profile/answers/resumes, settings.
- [ ] AC11 Founder runs it for 2 weeks on Windows with ≥ 50 real applications and 0 wrong submissions.

## Security & privacy
Personal data stays local (`.private/`, `data/` git-ignored; fake profiles in tests). Runner tokens hashed;
mailbox passwords encrypted; LLM sees page text only inside untrusted blocks; runner refuses submit without gate
token; navigator restricted to allowed hosts and cannot submit.

## Open questions
- Platform-native apply (LinkedIn Easy Apply / Naukri): build next or after two weeks of ATS-only use?
- Workday: coded adapter (account creation + vault) is the next big unlock for US/UK employers.
