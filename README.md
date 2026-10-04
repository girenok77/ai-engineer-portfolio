# AI Engineer Portfolio and Career Workspace

Public portfolio and job-search journal for Yevhenii Hyrenko, with an owner-only workspace for NAV vacancies, application documents, Gmail preparation and Codex activity.

## Pages

- `/`: English professional profile and original supplied CV downloads (PDF/DOCX).
- `/applications`: public journal of actually submitted applications; no private CVs, notes, email addresses or message contents.
- `/workspace`: sign-in and owner allowlist; vacancy filters, saved applications, reviewable Gmail drafts, private uploaded CV versions and responses.
- `/sessions`: owner-only Codex activity by day, execution duration and token counters.

## Implementation

React/TypeScript on the Vinext Sites starter. Server routes use Cloudflare D1 (SQLite migrations) and R2 for private documents. The Python standard-library updater imports the official NAV feed and local Codex JSONL metadata. Production secrets are Sites environment variables; local automation reads ignored `.env`. Main CV downloads are deliberately public. Adapted documents and mailbox contents never go into Git.

## Local development

Node 22+ and Python 3.10+ are required. `npm ci`, `npm run build`, and `npm run dev`. After building, apply each migration once in filename order:

```sh
node --import ./scripts/sites-env.mjs ./node_modules/wrangler/bin/wrangler.js d1 execute DB --local --config dist/server/wrangler.json --persist-to .wrangler/state --file drizzle/0000_sparkling_bug.sql
node --import ./scripts/sites-env.mjs ./node_modules/wrangler/bin/wrangler.js d1 execute DB --local --config dist/server/wrangler.json --persist-to .wrangler/state --file drizzle/0001_volatile_agent_brand.sql
```

Local development supports mock ChatGPT sign-in; it is enabled only in development. Production checks the exact `OWNER_EMAIL` after trusted ChatGPT authentication. Configure `UPDATE_TOKEN` as a strong secret in Sites and an ignored local `.env`. `.dev.vars` can provide the same secret to local Wrangler. Never commit these files.

```sh
SITE_URL=https://your-site.example
UPDATE_TOKEN=replace-with-a-strong-secret
# Optional registered NAV consumer token; otherwise uses experimental public token.
NAV_TOKEN=optional
```

Run `python3 scripts/daily_sync.py`. `--only nav` / `--only sessions` select imports; `--inspect` reports only aggregate local session metadata. NAV refresh scans feed changes from the last 14 days, deduplicates latest ad state, masks inactive records and reapplies preferences. It is not a full all-active archive. Existing older records remain until expiry or an inactive update. The public experimental token is fetched on every run; long-term use should obtain a registered token following [NAV documentation](https://navikt.github.io/pam-stilling-feed/).

## Codex daily workflow

The local heartbeat uses Python imports plus connected Gmail tools. It requires this computer and Codex to be available. It prepares at most three compatible unsent application drafts per run. It may reorder or emphasise supported CV facts, never add skills, credentials or employment. A suitable existing CV may be reused.

- Save a vacancy with `kind: action`, `action: save`, `jobId`.
- Upload reviewed document using `daily_sync.py --upload-cv path --application-id UUID`.
- Create an unsent Gmail draft with actual CV attachment, record it with `kind: prepare`, application `id`, `cvId`, `emailTo`, `subject`, `body`, `draftId`.
- The owner reviews the visible recipient, text and downloadable attachment, then explicitly approves it. Approval fails when the selected CV differs from the prepared attachment.
- The agent atomically claims only approved drafts via `kind: claim`. It sends the saved draft through Gmail, then records the confirmed provider message/thread IDs via `kind: complete` and the returned lock. Uncertain sends stay locked and require checking Gmail; they are never automatically retried.
- Read only tracked employer threads for responses, then import via `kind: reply`. Duplicate message IDs are ignored.

`python3 scripts/agent_rpc.py` reads private state. `--payload ignored-file.json` writes an agent action. `--download-cv UUID --output private-file.docx` downloads a private CV. Keep payloads/documents under ignored `.private/`.

ATS application portals are not automatically submitted. A contact address is not assumed to be an application address. Mark a manually completed ATS submission with its actual date and the CV version used.

## Metrics

A session groups turns of one top-level Codex chat with gaps up to 30 minutes. Dates use Europe/Oslo and each turn is assigned to its start day. Execution duration is the sum of observed turn intervals, not human attention or manual coding time. Input includes cached input; total is input plus output, so cached tokens are not added again. Unknown usage stays null. Imports cover available local session files from 60 days; discussions can also be included. No prompt text, conversation titles, authentication files, provider credentials or full filesystem paths are uploaded. Counts reflect logged token traffic, not billing or subscription cost.

## Validation and deployment

Run `npx tsc --noEmit` and the Site build. Verify anonymous public API, forbidden private API/CV access, rejection of forged user headers, application save idempotency, valid CV upload, and rejection of approval without a prepared Gmail draft. Build/package and publish through Sites using the existing `.openai/hosting.json` project. Runtime data stays in D1/R2 between versions. The GitHub repository contains source and only the intentionally public main CV.
