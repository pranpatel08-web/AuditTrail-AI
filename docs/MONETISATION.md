# Monetisation model

The brief asked for a product that can be sold, not a hackathon demo. This is the pricing, the measured unit economics, and the path from the first paying user.

## Who pays

**Primary: the associate or broker who does the first pass.** Commercial brokerage teams, tenant-rep firms, and boutique real-estate counsel (2–20 fee earners). They review leases weekly, bill by the hour, and cannot send tenant data to a consumer chatbot.

**Secondary: the firm.** Once two or three associates use it, the firm buys seats for consistency: shared history, white-labelled reports, a reviewer queue.

**Tertiary: the platform.** Property-management and diligence platforms that want a compliance check inside their workflow, via the API.

## Pricing

| Plan | Price | Included | Overage | Positioning |
| --- | ---: | --- | ---: | --- |
| Review | $0 | 3 audits/month | — | Try it on a live deal |
| Solo | $49/mo | 100 audits, export, API keys | $2.00/audit | One reviewer closing deals weekly |
| Firm | $199/mo | 500 audits, 5 seats, white-label | $2.00/audit | Boutique diligence team |
| Enterprise | Custom (from $15k/yr) | Unlimited, on-prem/VPC, SSO, rule packs | — | Institutions with residency constraints |

Annual billing at 10 months' price is the planned default; it is not implemented in the sandbox.

## Measured cost to serve

Clocked bills **1 credit per 25 ms of successful model time**, rounded up per request. The measured sample audit used **588–759 ms of model time across five calls → 24–31 credits**; the tables below use the conservative 31.

| Clocked plan | Effective $/1,000 credits | Cost per audit (31 credits) |
| --- | ---: | ---: |
| Build — $29 / 120,000 credits | $0.242 | **$0.0075** |
| Build overage | $0.300 | **$0.0093** |
| Production — $249 / 1,250,000 | $0.199 | $0.0062 |
| Scale — $999 / 6,500,000 | $0.154 | $0.0048 |

Prices from [clocked.rezolve.ai/pricing](https://clocked.rezolve.ai/pricing). A longer lease or a bigger regulatory source increases model time; assume a 3× worst case of ~$0.03 per audit and the margin still holds.

### Gross margin

| Plan | Revenue per audit | Cost per audit | Gross margin |
| --- | ---: | ---: | ---: |
| Solo ($49 / 100) | $0.49 | $0.0093 | **98.1%** |
| Firm ($199 / 500) | $0.398 | $0.0093 | **97.7%** |
| Overage | $2.00 | $0.0093 | **99.5%** |
| Enterprise (blended) | ~$1.25 | $0.0062 | 99.5% |

Infrastructure adds a few dollars per customer per month: one container ($7–25), Supabase Pro ($25 at scale), Stripe at 2.9% + $0.30 per transaction. At Solo, Stripe alone is ~$1.72, still leaving >94% contribution margin.

## Break-even and scenarios

Fixed cost assumption: **$60/month** (hosting, Supabase, domain).

| Paying customers | Mix | MRR | Clocked + infra | Contribution |
| ---: | --- | ---: | ---: | ---: |
| 2 | Solo | $98 | $62 | $36 |
| 25 | 20 Solo, 5 Firm | $1,975 | $170 | $1,805 |
| 100 | 80 Solo, 20 Firm | $7,900 | $650 | $7,250 |
| 500 | 400 Solo, 100 Firm | $39,500 | $3,200 | $36,300 |

Break-even is roughly **two Solo customers**. The constraint is distribution, not cost of goods.

## Why this pricing shape

- **Per reviewer, not per document.** Buyers compare to an hour of associate time ($150–$450), not to a $0.01 API call. A per-document price anchors them to the wrong number and punishes the heavy user who needs it most.
- **Generous allowance, expensive overage.** Deals arrive unevenly. 100 audits covers a normal Solo month; $2 overage never blocks a closing and is still 99% margin.
- **White-label is the Firm upsell.** The report goes to the firm's client. Removing the AuditTrail header is worth more than five seats, and it is cheap to deliver.
- **Free tier is a demo with a deadline.** Three audits is enough to run a real lease and see the evidence table; it is not enough to run a diligence week.

## Go to market

1. **Proof-first outbound.** Post a redacted sample audit (the bundled Lusaka lease) in brokerage and legal-ops communities. The artifact is the pitch: a claim table with quotes and arithmetic is more persuasive than a landing page.
2. **Associations and continuing education.** Commercial brokerage associations run lunch-and-learns on lease compliance. Offer a free firm audit in exchange for a 30-minute session.
3. **Land and expand.** Solo seats start with one associate. Firm plans follow when a second person asks for shared history — the product already stores it per account.
4. **API partnerships.** Property-management and diligence platforms embed the pipeline; priced per audit with a floor. The API key, quota and usage meter already exist.
5. **Waitlist for Enterprise.** On-prem/VPC is the answer to the only objection large firms raise: "the document cannot leave our network."

## Retention and expansion

- **Habit:** audit history becomes the firm's diligence record; switching costs rise with every stored audit.
- **Coverage:** jurisdiction rule packs are sold as add-ons (e.g. "UK commercial service charge pack").
- **Seats:** Firm plans expand with headcount; usage expands with deal volume.
- **Annual prepay:** 10% discount improves cash and reduces churn.

## Risks

| Risk | Mitigation |
| --- | --- |
| Clocked price or limit changes | Cost is <2% of revenue; a 10× increase still leaves >80% margin. Provider abstraction is one module (`backend/clocked.py`). |
| Accuracy liability | Decision support, not legal advice; human review flag; evidence quotes let the reviewer verify; E&O insurance before enterprise sales. |
| Data residency | On-prem/VPC tier; only masked text is stored; the re-identification key never leaves the customer. |
| Incumbent legal-AI vendors | They sell to AmLaw 100 at $100k+; AuditTrail sells to the 2–20 person firm that cannot buy a platform. |
| Low willingness to pay for "another AI tool" | Price against hours saved, ship the report the firm already produces, and let the free audit prove it. |

## What is already implemented

Plans, server-side quotas, usage metering, overage pricing display, plan switching (sandbox), Stripe Checkout adapter, hashed API keys gated to paid plans, white-label report branding, and audit history. The billing sandbox is labelled in the UI; adding `STRIPE_SECRET_KEY` and two price IDs switches checkout to live without code changes.
