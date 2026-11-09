# Protecting the idea and the codebase

You asked what stops someone copying this once the repository is public. The honest answer: **nothing stops copying the code; what you protect is the business around it.** This page is the practical plan, not legal advice.

## What the challenge actually requires

The Clocked rules require a public repository with visible history so judges can see what was built and when. They also state that **you keep ownership of your project**. Public visibility is not the same as open source: you can publish the code with a proprietary licence.

You can make the repository private again after judging (18 November), but assume anything public has been cloned. Do not put anything in the repo that you would be unhappy to see copied permanently.

## What is already protected, automatically

| Asset | Protection | Notes |
| --- | --- | --- |
| Source code | Copyright, automatic | No registration needed. The `LICENSE` file makes the terms explicit. |
| Written reports, docs, screenshots | Copyright, automatic | Same. |
| Name "AuditTrail AI", logo | Trademark (unregistered) | Registration is cheap and worth doing before launch. |
| Customer data, contracts | Confidentiality terms | Never in the repo. |
| Rule packs, evaluation sets, prompts tuned on real deals | Trade secret | Keep them out of the public repo. |

Ideas and business models are **not** protectable by copyright. A competitor can read your pricing page and copy the tiers. What they cannot easily copy is distribution, trust, customer relationships, and the data you accumulate.

## What is in the public repo, and what should not be

Currently public in this repository:

- the five-step pipeline and gateway (`backend/clocked.py`)
- pseudonymisation and the deterministic rule engine (`backend/pseudonym.py`, `backend/rules.py`)
- policy scoring (`backend/policy.py`)
- the UI, schema, tests and these docs

That is a deliberate trade: judges need to see real engineering, and buyers need to trust the privacy claims. None of it is a moat on its own.

Keep **out** of the repository, now and later:

- `.env` or any key (already ignored; verified not in git history)
- jurisdiction rule packs tuned for paying customers
- evaluation corpora and accuracy benchmarks built from real leases
- customer names, documents, or audit data
- the fraud/abuse heuristics you add after launch

If you later want the rule engine private, split it into a published Python package installed at deploy time. The public repo then ships an interface, not the implementation.

## The licence you are publishing under

`LICENSE` is **proprietary, all rights reserved**, with two narrow permissions: viewing/cloning for evaluation, and quoting short excerpts with attribution. It is not MIT, Apache or GPL. That means:

- judges can read and run it, which is what the challenge needs;
- a competitor cannot legally reuse it in their product;
- you keep the option to dual-license or sell a commercial licence later.

GitHub will still let people fork a public repository through the platform. A fork is not a licence to commercialise; the `LICENSE` governs use, and GitHub's DMCA process handles clear copies.

## The five things actually worth doing

1. **Publish under the proprietary licence.** Done — `LICENSE`. Add your legal name before any commercial launch.
2. **Register the trademark.** "AuditTrail AI" in your jurisdiction, class 9 (software) and class 42 (SaaS). Cost is typically a few hundred dollars; it is the cheapest real protection you can buy.
3. **Sell access, not source.** Hosted SaaS is the default. Customers buy an account, not a copy. On-prem is an Enterprise contract with a licence key, not a repo handover.
4. **Keep the compounding assets private.** Rule packs per jurisdiction, evaluation data, and customer history are what make the product better every month. The public repo is the shell.
5. **Put terms around the product.** A short Terms of Service and Privacy Policy on the site, a confidentiality clause in enterprise contracts, and a contributor licence if you ever accept outside code.

## If someone does copy it

- **Direct copy of the repo**: DMCA takedown to GitHub with the repository URL and the `LICENSE`. GitHub responds to complete notices.
- **Clone of the UI or docs**: copyright claim; screenshots and copy are protected.
- **Confusingly similar name**: trademark claim once registered.
- **Former contractor or collaborator**: the contract matters more than the licence. Have one before sharing anything private.

## What not to do

- Do not strip the commit history to hide how it was built — the challenge requires visible history, and it is evidence you built it first.
- Do not put a restrictive licence on the Clocked SDK or other third-party code; keep their notices.
- Do not rely on a patent for a workflow this small. Software patents are slow, expensive, and rarely worth it at this stage.
- Do not publish customer documents "for the demo". Synthetic samples only — which is what `samples/` already contains.

## Timeline

| When | Action |
| --- | --- |
| Before submitting | Keep the repo public with `LICENSE` in place; confirm `.env` is ignored. |
| 10–17 November | Judging window: leave it public. |
| From 18 November | Optionally make the repo private. Assume forks persist. |
| Before first paying customer | Register the trademark, publish Terms and Privacy, add your legal name to `LICENSE`. |
| Before enterprise sales | Contract template, DPA, security questionnaire, E&O insurance. |

*This page is a practical summary, not legal advice. A one-hour consultation with an IP lawyer in your jurisdiction is worth it before you sign your first enterprise contract.*
