# Security policy

## Reporting a vulnerability

Email **hello@audittrail.ai** with a description and reproduction steps. Do not
open a public issue for a security report. You will get an acknowledgement within
two business days.

## Secrets

This repository deliberately contains **no credentials**. `.env` is git-ignored;
`.env.example` contains placeholders only.

If you deploy it, you need your own:

- `CLOCKED_API_KEY` — server-side only, never exposed to the browser.
- `SUPABASE_SECRET_KEY` — server-side only. The publishable key is the only
  Supabase key that may reach the client.
- `STRIPE_SECRET_KEY` — server-side only, optional.

If a key is ever committed or pasted into an issue, rotate it immediately:
Clocked → Settings → API Access; Supabase → Project Settings → API; Stripe →
Developers → API keys.

## Data handling

- Raw tenant identifiers are pseudonymised before extraction, verification and
  decision. Only masked text is stored.
- The re-identification key is returned once to the caller and is never written
  to the database, logs, or reports.
- Prompt-injection screening fails closed: a dangerous verdict stops the audit
  before any further model call.
- Pipeline errors are sanitised to a step name and a generic message; provider
  responses and keys are not returned to the client.

## Supported versions

The `main` branch is the only supported version. There are no maintained release
branches.

## Out of scope

- Findings that require the attacker to already hold the Clocked or Supabase
  secret key.
- Denial of service through the demo endpoint on a local, unexposed instance.
