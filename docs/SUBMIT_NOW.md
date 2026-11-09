# Submit now — the 10-minute checklist

Everything is built. These are the only steps left, in order. The deadline is **10 November 2026, 11:59 p.m. ET** — that is **11 November, 10:29 a.m. IST**.

## What you are actually submitting

| Item | Where it is |
| --- | --- |
| Public repository | push this project to GitHub (step 2) |
| Demo video | record from the running app (step 3) |
| Entry text | [`SUBMISSION.md`](SUBMISSION.md) — paste-ready |
| Attachment (if the form allows one) | [`AuditTrail-AI-submission.pdf`](AuditTrail-AI-submission.pdf) |
| The SQL you need for Supabase | [`../supabase/schema.sql`](../supabase/schema.sql) |

There is no single "submission file". The entry form takes a repository URL, a demo URL/video, and the written sections.

## Step 1 — Supabase (2 minutes)

1. Open `https://supabase.com/dashboard/project/ttdogpagtsabxldkhsbh/sql/new`.
2. Open `supabase/schema.sql`, select all, paste into the editor, click **Run**.
3. Run the verification query at the bottom of the file. You should see four `at_*` tables and seven policies.
4. Reload `http://127.0.0.1:8077` (or `http://127.0.0.1:8000` if you started it with `run.py`). The server probes Supabase every 15 seconds and switches automatically — no restart needed.

Confirm with:

```bash
curl http://127.0.0.1:8077/api/v1/health
```

Expected: `"storage": {"backend": "supabase", ...}`. If it still says `sqlite`, the `supabase_reason` field tells you why (usually a missing grant or a policy typo).

## Step 2 — Push the public repo (3 minutes)

You are currently authenticated to GitHub as **`pranpat01-cpu`**, which cannot write to `pranpatel08-web/AuditTrail-AI`. Either create a new repository under `pranpat01-cpu`, or add that account as a collaborator on the old one.

Create an **empty public** repo (no README), then:

```powershell
cd "C:\DEV\AuditTrail AI"
git remote set-url origin https://github.com/pranpat01-cpu/AuditTrail-AI.git
git push -u origin main
```

Before pushing, confirm the secret file is not included:

```powershell
git status --short          # .env must not appear
git log --all --oneline     # five commits, no key material
```

The repo already contains `LICENSE` (proprietary, all rights reserved) and `SECURITY.md`. Read [`IP_PROTECTION.md`](IP_PROTECTION.md) before you make it public.

## Step 3 — Demo video (10 minutes, optional but scored)

Follow [`DEMO_SCRIPT.md`](DEMO_SCRIPT.md). Minimum viable version: a single 60–90 second screen recording showing Load sample → Run audit → the HIGH result → the rule arithmetic → the privacy tab. Upload to YouTube as **unlisted** and paste the link.

A silent recording with the cursor is better than no video. Judges score execution, and a working demo is the fastest way to show it.

## Step 4 — Fill the entry form (3 minutes)

1. `https://clocked.rezolve.ai/challenge` → **SIGN IN** (the account that holds your credits).
2. Account page → redeem `CLOCKEDHACKATHON` if you have not already (+16,000 credits).
3. **SUBMIT YOUR PROJECT** → select **all four** judged awards.
4. Paste the fields from [`SUBMISSION.md`](SUBMISSION.md): name, tagline, description, built with, how you used Clocked, URLs, team.
5. Submit. You can edit the entry until 11:59 p.m. ET.

## Step 5 — After submitting

- Screenshot the confirmation page and keep the email.
- For **People's Choice** (separate $200): one public LinkedIn post showing the demo, tag the Clocked page, include `#ClockedChallenge`, and add the post URL to the entry before the deadline. Engagement only counts from 11 November.
- Keep the repo public through judging (11–17 November). You can make it private after 18 November, but assume any fork persists.

## If something fails

| Problem | Do this |
| --- | --- |
| Supabase still reports SQLite | The app still works on SQLite. Submit, then fix the SQL after. Do not miss the deadline for this. |
| No demo URL | The entry accepts a video link instead. Record locally and upload unlisted. |
| GitHub push denied | Create the repo from the account you are signed into (`pranpat01-cpu`), not the old org. |
| Clocked credits exhausted | Top up or use a second account's free allowance; the pipeline needs ~30 credits per audit. |
