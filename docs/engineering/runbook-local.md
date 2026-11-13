# Runbook: run JobOS on your own machine (Windows first)

Status: Approved — matches the code on `feat/core-pipeline`.

You run three things: **Postgres**, the **JobOS server** (API + agents/workflows), and the **runner** (drives a dedicated
Chrome profile). The **dashboard** is a Next.js app. Everything stays on your computer.

## 1. One-time install (Windows 11, PowerShell)

```powershell
winget install --id=astral-sh.uv -e          # Python toolchain
winget install --id=OpenJS.NodeJS.LTS -e      # Node 22 for the dashboard
winget install --id=Docker.DockerDesktop -e   # or install PostgreSQL 16 natively
npm install -g pnpm
git clone https://github.com/shubham-dube/jobos.git
cd jobos
uv sync --all-packages
cd apps/web; pnpm install; cd ../..
copy .env.example .env    # then edit .env (see §2)
docker compose up -d postgres
uv run jobos migrate
```

## 2. Configure `.env`
Minimum: `JOBOS_API_TOKEN` (any long random string), `JOBOS_SECRET_KEY` (32+ random chars),
`JOBOS_OPENROUTER_API_KEY`. Optional: Resend + WhatsApp (see §6). Model routing per task via `JOBOS_LLM_ROUTES`.
The dashboard reads `JOBOS_API_URL`, `JOBOS_API_TOKEN` and `JOBOS_WEB_PASSWORD` from the same file when you start it
from the repo root, or set them in `apps/web/.env.local`.

## 3. Start
```powershell
uv run jobos serve --role all          # API + agents on http://localhost:8000
cd apps/web; pnpm build; pnpm start    # dashboard on http://localhost:3000
```

## 4. Load your data (Profile & answers page)
1. **Import profile**: paste your master profile document (or upload a resume PDF) → "Build profile with AI".
   Review the JSON: the agent copies raw values; fix anything it got wrong and save.
2. **Upload resumes** with labels (e.g. `Backend`, `AI Engineer`, `Agentic Systems`, `Flutter`) and mark one default.
   The matcher picks the best label per job.
3. **Answer bank**: add things forms ask often (notice period, expected CTC in INR and in USD/GBP/CHF, relocation,
   earliest start date, "how did you hear").

## 5. Connect your browser (runner)
```powershell
# Settings → Runners → "Create runner token", then:
uv run jobos-runner setup --api http://localhost:8000 --token jr_xxx --max-sessions 2
uv run jobos-runner login      # opens the dedicated JobOS Chrome profile: sign in to Google, LinkedIn, Naukri…
uv run jobos-runner run        # leave running; it applies in that Chrome window at a human pace
```
The runner uses your installed Google Chrome with its own profile folder (`%LOCALAPPDATA%\JobOS\chrome-profile`), so
logins persist across restarts and never leave your PC.

## 6. Notifications (optional but recommended)
- **Email (Resend)**: set `JOBOS_RESEND_API_KEY`, `JOBOS_EMAIL_FROM` (on your verified domain), `JOBOS_NOTIFY_EMAIL_TO`.
- **WhatsApp Cloud API**: create a Meta app with WhatsApp, get a permanent token + phone number ID, set
  `JOBOS_WHATSAPP_*`. Expose the API publicly for replies, e.g. `cloudflared tunnel --url http://localhost:8000`,
  then set the webhook URL to `https://<tunnel>/webhooks/whatsapp` with your `JOBOS_WHATSAPP_VERIFY_TOKEN`.
  Register a template (e.g. `jobos_action_needed` with one body variable) for messages outside the 24h window.

## 7. Mail tracking (Gmail + Zoho)
Settings → Mailboxes. Use **app passwords** (Gmail: Google Account → Security → 2-Step Verification → App passwords;
Zoho: My Account → Security → App Passwords; India accounts use `imap.zoho.in`). Synced every 5 minutes; emails are
classified and linked to applications (received / rejected / interview / assessment / offer / OTP).

## 8. Daily use
- Settings → Searches: create a search (filters JSON). Keep **auto-queue** off at first; use Jobs → Apply.
- Everything goes to **review** until you add approval rules (Settings → `approval_rules`, ADR-0015).
- Inbox shows questions/reviews/logins; WhatsApp/email point to the same items.

## Troubleshooting
| Symptom | Fix |
|---|---|
| "runner offline" notifications | start `jobos-runner run`; check Settings → Runners shows *online* |
| Application stuck in `needs_input` | answer it in Inbox; the workflow resumes exactly where it stopped |
| `uncertain` state | submit clicked but no confirmation page; check the screenshot and your email |
| LLM budget reached | raise `JOBOS_LLM_DAILY_BUDGET_USD` or route bulk tasks to cheaper models |
