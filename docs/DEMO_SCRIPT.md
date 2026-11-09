# Demo video script (3:00)

The entry form asks for a demo. Judges score usefulness, execution and Clocked integration; the video is where all three are visible. Record at 1440×900 (or 1920×1080), browser zoom 90%, notifications off, one tab.

## Pre-flight (five minutes before recording)

```powershell
# from the project root
.\.venv\Scripts\Activate.ps1
python run.py                 # http://127.0.0.1:8000
```

- Open `http://127.0.0.1:8000` and check the header says **engine live**.
- Click **Workspace → Load sample** once, then **reload the page** so the recording starts clean.
- Have the Supabase dashboard closed; do not show `.env` or any key on screen.
- If you will show the report, pre-run one audit so `/history` is not empty — but run the live audit again on camera.
- Do a full dry run and note the wall time (expect 5–7 seconds).

## Shot list

### 0:00–0:18 — The problem

**On screen:** landing hero, cursor still.

**Say:**
> "A commercial lease review takes three to six hours. Not because it is hard to read, but because someone has to check every operative clause against a zoning code — and then prove where the answer came from. You cannot paste a tenant's name and SSN into a chatbot to do it."

### 0:18–0:40 — What it is

**On screen:** scroll slowly to the pipeline section, then back to the top.

**Say:**
> "AuditTrail AI is a compliance first pass with receipts. Five Clocked endpoints: protect, guard, extract, verify, decide. Tenant identifiers are masked before anything else sees them. Every finding comes back with an evidence quote. And the arithmetic is computed in code, not guessed by a model."

Point at the specimen card: **HIGH RISK · score 100 · 2 rule failures**.

### 0:40–1:05 — The workspace

**On screen:** click **Run the sample lease** (or Workspace → Load sample). Show the lease on the left, the zoning source on the right.

**Say:**
> "Here is a synthetic lease and the Lusaka CBD zoning extract it has to satisfy. The lease contains a tenant contact — an email, a phone number, a person's name. Watch what reaches the model."

Scroll the lease to the contact line, highlight it with the cursor.

### 1:05–1:30 — The live pipeline

**On screen:** click **Run audit**. Let the five steps animate.

**Say:**
> "Protect finds six entities and replaces them with stable tokens. Guard screens the masked document for prompt injection and fails closed if it finds any. Extract reads twelve lease fields verbatim. Verify checks each operative claim against the zoning source. Decide returns calibrated risk with a review flag."

Do not talk over the whole run; let the last two steps land.

### 1:30–2:05 — The result

**On screen:** result panel. Point at the risk banner, then the rationale.

**Say:**
> "High risk, score 100. Not because the model felt uneasy — because two deterministic checks failed."

Point at the parking line:

> "The zoning code requires two parking bays per 100 square metres. The lease allocates four bays for 220 square metres. `ceil(220 ÷ 100 × 2) = 5`. One bay short, with the clause that requires it."

Point at the contradicted claim:

> "The lease says live entertainment after 22:00 needs only the landlord's consent. The code says it needs a supplementary entertainment permit. Verify marked it contradicted and quoted the sentence."

### 2:05–2:30 — Privacy and evidence

**On screen:** click the **Privacy** tab, then **Masked document**.

**Say:**
> "The document the pipeline saw contains `[ORG_1]`, `[ORG_2]`, `[EMAIL_1]` — no real identifiers. The tenant and the landlord remain distinguishable, which naive masking destroys. The re-identification key is generated once, handed to this browser, and never stored."

### 2:30–2:50 — The deliverable

**On screen:** click **Open printable report**. Scroll the report: banner, claims table, deterministic checks table.

**Say:**
> "The output is the thing a firm actually sends: a print-ready report with claim verdicts, evidence quotes and the arithmetic. HTML, Markdown or JSON. White-labelled on the Firm plan."

### 2:50–3:00 — Close

**On screen:** pricing page.

**Say:**
> "Three free audits, forty-nine dollars for a hundred, two dollars overage. A measured audit costs about one cent in Clocked credits. AuditTrail AI — lease compliance with receipts."

## Fallback if the API fails on camera

Do not fake it. Say:

> "The pipeline failed closed at step three — which is the behaviour we want. Here is the same audit from this morning."

Then open **History**, open the stored audit, and continue from 1:30. The stored record contains the full report, so the rest of the script is unchanged. Mention that raw documents are never written to logs and the failure returned only the step name.

## Editing notes

- Keep it under 3:00. The form does not reward length.
- Add captions for the two load-bearing lines: `ceil(220 ÷ 100 × 2) = 5` and "contradicted → supplementary entertainment permit required".
- No music, no intro animation. The first frame should be the product.
- Zoom the browser to 110% when showing the claim table; 90% for the landing page.
- Export 1080p, H.264, under 100 MB.

## Thumbnail

Use `docs/screenshots/result.png` cropped to the verdict banner and the parking rule. Do not use a stock photo.
