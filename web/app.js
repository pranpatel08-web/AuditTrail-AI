/* AuditTrail AI — product application
   Vanilla ES modules: no build step, no CDN, works offline. */

const API = "/api/v1";
const SESSION_KEY = "audittrail.session";

const state = {
  config: null,
  health: null,
  session: null,
  audit: null,
  key: null,
  usage: null,
  samples: null,
  timer: null,
  step: 0,
  tab: "findings",
};

/* ------------------------------------------------------------------ utils */
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const esc = (value) =>
  String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmtDate = (iso) => {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { day: "2-digit", month: "short", year: "numeric" });
};
const fmtTime = (iso) => {
  if (!iso) return "";
  return new Date(iso).toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
};
const bytes = (n) => (n > 1024 ? `${(n / 1024).toFixed(1)} KB` : `${n} B`);

function toast(message, kind = "") {
  const el = $("#toast");
  el.textContent = message;
  el.className = `toast show ${kind}`;
  clearTimeout(el._t);
  el._t = setTimeout(() => (el.className = "toast"), 3600);
}

class ApiError extends Error {
  constructor(payload, status) {
    const detail = payload?.detail ?? payload;
    super(typeof detail === "string" ? detail : detail?.message || `Request failed (${status})`);
    this.status = status;
    this.detail = detail;
  }
}

async function api(path, { method = "GET", body } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (state.session?.access_token) headers.Authorization = `Bearer ${state.session.access_token}`;
  const res = await fetch(API + path, { method, headers, body: body ? JSON.stringify(body) : undefined });
  if (res.status === 401 && state.session?.refresh_token) {
    if (await refreshSession()) return api(path, { method, body });
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new ApiError(data, res.status);
  return data;
}

/* -------------------------------------------------------------- supabase auth */
async function supabaseAuth(path, body, token) {
  const url = state.config?.supabase_url;
  const key = state.config?.supabase_key;
  if (!url || !key) throw new Error("Supabase is not configured on this deployment. Use the demo session.");
  const res = await fetch(`${url}/auth/v1/${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", apikey: key, Authorization: `Bearer ${token || key}` },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error_description || data.msg || data.message || "Authentication failed");
  return data;
}

function saveSession(payload) {
  state.session = {
    access_token: payload.access_token,
    refresh_token: payload.refresh_token,
    user: payload.user,
  };
  localStorage.setItem(SESSION_KEY, JSON.stringify(state.session));
}

async function refreshSession() {
  try {
    const data = await supabaseAuth("token?grant_type=refresh_token", { refresh_token: state.session.refresh_token });
    saveSession(data);
    return true;
  } catch {
    signOut(false);
    return false;
  }
}

function signOut(route = true) {
  state.session = null;
  localStorage.removeItem(SESSION_KEY);
  updateAccount();
  if (route) location.hash = "#/";
}

/* ------------------------------------------------------------------- icons */
const ICON = {
  shield: '<path d="M12 2.6 4.2 6v6.2c0 4.3 3.1 7.7 7.8 9.2 4.7-1.5 7.8-4.9 7.8-9.2V6L12 2.6Z" stroke="currentColor" stroke-width="1.5"/><path d="M8.4 12.1l2.5 2.5 4.7-5" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/>',
  check: '<path d="M4 12.5l5 5L20 6.5" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
  arrow: '<path d="M5 12h14M13 6l6 6-6 6" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/>',
  alert: '<path d="M12 3 2.6 20h18.8L12 3Z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/><path d="M12 9v5M12 17.2v.2" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>',
  lock: '<rect x="4.5" y="10" width="15" height="10.5" rx="2" stroke="currentColor" stroke-width="1.5"/><path d="M8 10V7.5a4 4 0 0 1 8 0V10" stroke="currentColor" stroke-width="1.5"/>',
  download: '<path d="M12 3v12M7 11l5 5 5-5M4 21h16" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/>',
  play: '<path d="M7 4.5 19 12 7 19.5V4.5Z" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/>',
  doc: '<path d="M6 3h8l4 4v14H6V3Z" stroke="currentColor" stroke-width="1.5"/><path d="M14 3v4h4" stroke="currentColor" stroke-width="1.5"/>',
};
const icon = (name, size = 16) =>
  `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" aria-hidden="true">${ICON[name] || ""}</svg>`;

/* ------------------------------------------------------------------- chrome */
function updateAccount() {
  const el = $("#account");
  if (state.session?.user) {
    const email = state.session.user.email || "signed in";
    el.innerHTML = `<button class="btn btn-ghost btn-sm" id="signout-btn" title="${esc(email)}">${esc(email.split("@")[0])} · Sign out</button>`;
    $("#signout-btn").addEventListener("click", () => signOut());
  } else {
    el.innerHTML = `<a class="btn btn-ghost btn-sm" href="#/login">Sign in</a>`;
  }
}

function updateStatus() {
  const chip = $("#status-chip");
  const text = $("#status-text");
  const storage = state.health?.storage?.backend || "local";
  const live = state.health?.clocked_live;
  chip.className = `status-chip ${live ? "ok" : "bad"}`;
  text.textContent = `${live ? "engine live" : "engine offline"} · ${storage}`;
  chip.title = live
    ? `Clocked connected. Storage: ${state.health.storage.detail}`
    : "CLOCKED_API_KEY is not configured";
}

/* ------------------------------------------------------------------- router */
const ROUTES = ["/", "/workspace", "/history", "/pricing", "/method", "/login", "/billing"];

async function router() {
  const hash = location.hash.replace(/^#/, "") || "/";
  const [path, param] = hash.replace(/^\//, "").split("/");
  const route = `/${path}`;
  $$("#nav a").forEach((a) => a.classList.toggle("active", a.getAttribute("href") === `#${route}`));
  $("#nav").classList.remove("open");

  const main = $("#main");
  main.innerHTML = `<div class="wrap section"><p class="muted">Loading…</p></div>`;
  try {
    if (route === "/" ) main.innerHTML = viewHome();
    else if (route === "/workspace") { main.innerHTML = viewWorkspace(); bindWorkspace(); if (state.samples) applySamples(); if (sessionStorage.getItem("at.loadSample")) { sessionStorage.removeItem("at.loadSample"); loadSample(); } }
    else if (route === "/history") { main.innerHTML = await viewHistory(); }
    else if (route === "/pricing") { main.innerHTML = viewPricing(); bindPricing(); }
    else if (route === "/method") main.innerHTML = viewMethod();
    else if (route === "/login") { main.innerHTML = viewLogin(); bindLogin(); }
    else if (route === "/billing") { main.innerHTML = await viewBilling(); bindBilling(); }
    else if (route === "/audit" && param) { main.innerHTML = await viewAuditDetail(param); bindTabs(); }
    else main.innerHTML = viewNotFound();
  } catch (err) {
    main.innerHTML = `<div class="wrap section"><div class="notice notice-error">${icon("alert")}<div><strong>Could not load this view.</strong><br>${esc(err.message)}</div></div></div>`;
  }
  window.scrollTo({ top: 0, behavior: "instant" });
  $$(".fade-up").forEach((el) => el.classList.add("fade-up"));
}

/* ------------------------------------------------------------------- home */
function viewHome() {
  const plans = state.config?.plans || [];
  const pro = plans.find((p) => p.id === "pro");
  return `
  <section class="hero">
    <div class="wrap hero-grid">
      <div class="fade-up">
        <div class="eyebrow">Clocked Build Challenge · 2026</div>
        <h1>Every lease clause, checked against the code. <em>With the receipt.</em></h1>
        <p class="lede">AuditTrail reads a commercial lease, masks every tenant identifier before analysis, and tests each operative clause against the zoning source you supply. Five Clocked endpoints. Deterministic arithmetic. A citation for every finding.</p>
        <div class="cta-row">
          <a class="btn btn-primary" href="#/workspace" data-sample="1">Run the sample lease ${icon("arrow")}</a>
          <a class="btn btn-ghost" href="#/method">Read the method</a>
        </div>
        <div class="trust-row">
          <span>${icon("check", 14)} PII masked before extraction</span>
          <span>${icon("check", 14)} Fail-closed on injection</span>
          <span>${icon("check", 14)} Evidence offsets, not prose</span>
        </div>
      </div>
      <div class="fade-up">
        <div class="specimen" aria-label="Example audit result">
          <div class="specimen-head">
            <span class="specimen-title">Audit · 412 Harbor Street</span>
            <span class="score">5.1s · 5 endpoints</span>
          </div>
          <div class="specimen-body">
            <div class="risk-strip">
              <span class="risk-badge risk-high">HIGH RISK</span>
              <span class="score">score 100 / 100</span>
              <span class="score" style="margin-left:auto">2 rule failures</span>
            </div>
            <div class="claim">
              <div>
                <p>Minimum parking allocation</p>
                <div class="quote">ceil(220 ÷ 100 × 2) = 5 required vs 4 allocated</div>
              </div>
              <span class="pill pill-fail">Fail</span>
            </div>
            <div class="claim">
              <div>
                <p>Live entertainment after 22:00</p>
                <div class="quote">“Live entertainment after 22:00 requires a supplementary entertainment permit…”</div>
              </div>
              <span class="pill pill-contradicted">Contradicted</span>
            </div>
            <div class="claim">
              <div>
                <p>Assignment consent at sole discretion</p>
                <div class="quote">“a ‘sole discretion’ landlord consent clause is lawful…”</div>
              </div>
              <span class="pill pill-pass">Pass</span>
            </div>
          </div>
        </div>
        <p class="caption">Actual output from the bundled sample lease.</p>
      </div>
    </div>
  </section>

  <section class="section-tight">
    <div class="wrap">
      <div class="grid-3">
        <div class="card card-pad">
          <h3>Generic LLMs invent clauses</h3>
          <p class="muted">A plausible sentence is not a citation. Every finding here is tied to a verdict and an evidence quote from the regulatory source, with character offsets.</p>
        </div>
        <div class="card card-pad">
          <h3>Diligence is billed by the hour</h3>
          <p class="muted">A first-pass lease review takes 3–6 hours. AuditTrail returns a structured, reviewable first pass in about five seconds, so counsel spends time on judgement, not Ctrl-F.</p>
        </div>
        <div class="card card-pad">
          <h3>Tenant data leaves the building</h3>
          <p class="muted">Names, emails, phone numbers and addresses are replaced with stable tokens before any analysis. The re-identification key is handed to you once and never stored.</p>
        </div>
      </div>
    </div>
  </section>

  <hr class="rule">
  <section class="section">
    <div class="wrap">
      <div class="eyebrow">The pipeline</div>
      <h2 style="font-size:clamp(28px,3.4vw,42px);max-width:20em">Five specialised endpoints, each one changing what the next one sees.</h2>
      <div class="grid-2" style="margin-top:32px;align-items:start">
        <div class="steps">
          ${[
            ["1", "Protect", "/clocked/pii", "Tenant names, emails, phones and addresses are replaced with stable tokens. Only the masked copy moves forward."],
            ["2", "Guard", "/clocked/injection", "The masked document is screened for prompt injection. A dangerous verdict stops the audit before any further model call."],
            ["3", "Extract", "/clocked/extract", "Twelve lease fields are read verbatim with character spans. Missing fields stay null; they are never guessed."],
            ["4", "Verify", "/clocked/grounding", "Each operative claim is tested against your zoning source: supported, contradicted, or not stated, with a quote."],
            ["5", "Decide", "/clocked/decide", "Typed decisions with probabilities set the risk banner, the remediation checklist and the human-review flag."],
          ].map(([n, title, code, body]) => `
            <div class="step done">
              <div class="step-num">${n}</div>
              <div><h4>${title} <span class="step-code">${code}</span></h4><p>${body}</p></div>
            </div>`).join("")}
        </div>
        <div class="card card-pad">
          <div class="eyebrow" style="margin-bottom:12px">Why the arithmetic is separate</div>
          <h3 style="margin-bottom:10px">Models read. Code counts.</h3>
          <p class="muted">Asked whether four parking bays satisfy a two-per-100 sqm rule on 220 sqm, a language model says “not stated”. The rule engine computes <code>ceil(220 ÷ 100 × 2) = 5</code> and reports a one-bay shortfall with the clause that requires it.</p>
          <p class="muted">Every numeric check is computed in application code and shown with its formula. Clocked handles reading and legal judgement; the product owns the maths and the policy.</p>
          <div class="notice notice-info" style="margin-top:16px">${icon("shield")}<div>Two layers, one report: model verdicts for language, deterministic checks for numbers.</div></div>
        </div>
      </div>
    </div>
  </section>

  <hr class="rule">
  <section class="section">
    <div class="wrap">
      <div class="eyebrow">Pricing</div>
      <div style="display:flex;justify-content:space-between;align-items:end;gap:20px;flex-wrap:wrap">
        <h2 style="font-size:clamp(28px,3.4vw,40px)">Priced per reviewer, not per seat you forgot to cancel.</h2>
        <a href="#/pricing" class="btn btn-ghost">Compare plans ${icon("arrow")}</a>
      </div>
      <div class="price-grid" style="margin-top:28px">
        ${plans.filter((p) => ["free", "pro", "firm"].includes(p.id)).map((p) => priceCard(p, p.id === "pro")).join("")}
        <div class="price">
          <h3>Enterprise</h3>
          <div class="amount">Custom</div>
          <p class="tagline">On-premise or private VPC for institutions that cannot use a shared cloud.</p>
          <ul><li>Unlimited audits &amp; seats</li><li>SSO / SAML, audit-log export</li><li>Custom jurisdiction rule packs</li></ul>
          <a class="btn btn-ghost" href="mailto:sales@audittrail.ai?subject=AuditTrail%20Enterprise">Talk to us</a>
        </div>
      </div>
      <p class="price-note">${pro ? `$${pro.price_monthly}/month includes ${pro.audits_per_month} audits. Extra audits are $2.00 each.` : ""} Prices in USD.</p>
    </div>
  </section>

  <section class="section-tight">
    <div class="wrap">
      <div class="card card-pad" style="display:flex;justify-content:space-between;align-items:center;gap:24px;flex-wrap:wrap;background:var(--navy);border-color:var(--navy)">
        <div>
          <h2 style="color:#fff;font-size:28px">Bring a lease. Leave with a defensible first pass.</h2>
          <p style="color:#a9bbb2;margin:6px 0 0">No sign-up for the sample. Three free audits on a real document.</p>
        </div>
        <a class="btn btn-primary" href="#/workspace" data-sample="1">Open the workspace ${icon("arrow")}</a>
      </div>
    </div>
  </section>`;
}

function priceCard(plan, featured) {
  const amount = plan.price_monthly === null ? "Custom" : plan.price_monthly === 0 ? "$0" : `$${plan.price_monthly}`;
  return `<div class="price ${featured ? "featured" : ""}">
    ${featured ? '<span class="price-tag">Most popular</span>' : ""}
    <h3>${esc(plan.name)}</h3>
    <div class="amount">${amount}${plan.price_monthly ? "<small>/mo</small>" : ""}</div>
    <p class="tagline">${esc(plan.tagline)}</p>
    <ul>${plan.features.map((f) => `<li>${esc(f)}</li>`).join("")}</ul>
    <a class="btn ${featured ? "btn-primary" : "btn-ghost"}" href="#/pricing">Choose ${esc(plan.name)}</a>
  </div>`;
}

/* -------------------------------------------------------------- workspace */
function viewWorkspace() {
  return `
  <div class="wrap">
    <div class="ws-head">
      <div>
        <div class="eyebrow" style="margin-bottom:10px">Workspace</div>
        <h1>New compliance audit</h1>
        <p>Paste a lease and the regulatory source it must satisfy. Nothing is stored until the audit completes.</p>
      </div>
      <div id="usage-chip"></div>
    </div>
    <div class="ws-grid">
      <div class="panel">
        <div class="panel-head"><h2>Sources</h2><button class="btn btn-quiet btn-sm" id="sample-btn">Load sample</button></div>
        <div class="panel-body">
          <label class="field"><span class="label">Lease or deed <span class="tiny muted" id="lease-count">0 chars</span></span>
            <textarea class="textarea mono" id="lease" placeholder="Paste the commercial lease text…" style="min-height:210px"></textarea>
          </label>
          <label class="field"><span class="label">Regulatory source <span class="tiny muted" id="rules-count">0 chars</span></span>
            <textarea class="textarea mono" id="rules" placeholder="Paste the zoning code, municipal bylaw or regulatory extract…" style="min-height:160px"></textarea>
          </label>
          <label class="field"><span class="label">Audit title <span class="tiny muted">optional</span></span>
            <input class="input" id="title" maxlength="140" placeholder="e.g. 412 Harbor Street — Verde Coffee Roasters">
          </label>
          <div class="notice notice-warn" id="ws-notice" hidden></div>
        </div>
        <div class="panel-foot">
          <button class="btn btn-primary btn-wide" id="run-btn">${icon("play", 15)} Run audit</button>
          <p class="hint center" style="margin:10px 0 0">Uses one audit credit · about 5 seconds</p>
        </div>
      </div>

      <div class="panel" id="run-panel">
        <div class="run-empty" id="run-empty">
          <div style="width:52px;height:52px;border-radius:50%;background:var(--green-soft);display:grid;place-items:center;margin:0 auto 14px;color:var(--green)">${icon("shield", 24)}</div>
          <h3>No audit yet</h3>
          <p>Load the sample to see a lease with a parking shortfall, an entertainment-licensing conflict and two documentation gaps.</p>
          <button class="btn btn-ghost" id="empty-sample">Load the sample lease</button>
        </div>
      </div>
    </div>
  </div>`;
}

function bindWorkspace() {
  const lease = $("#lease");
  const rules = $("#rules");
  const count = () => {
    $("#lease-count").textContent = `${lease.value.length.toLocaleString()} chars`;
    $("#rules-count").textContent = `${rules.value.length.toLocaleString()} chars`;
  };
  lease.addEventListener("input", count);
  rules.addEventListener("input", count);
  $("#sample-btn").addEventListener("click", loadSample);
  $("#empty-sample")?.addEventListener("click", loadSample);
  $("#run-btn").addEventListener("click", runAudit);
  count();
  loadUsage();
}

async function loadUsage() {
  try {
    const usage = await api("/billing/usage");
    state.usage = usage;
    const chip = $("#usage-chip");
    if (chip) {
      const label = usage.limit === null ? "Unlimited" : `${usage.remaining} of ${usage.limit} left`;
      chip.innerHTML = `<span class="status-chip ok" style="padding:8px 13px"><span class="dot"></span>${esc(usage.plan_name)} · ${esc(label)}</span>`;
    }
  } catch { /* usage is informative only */ }
}

async function loadSample() {
  try {
    if (!state.samples) state.samples = await api("/samples");
    applySamples();
    toast("Sample lease and zoning source loaded");
  } catch (err) {
    toast(err.message, "error");
  }
}

function applySamples() {
  if (!state.samples || !$("#lease")) return;
  $("#lease").value = state.samples.lease;
  $("#rules").value = state.samples.zoning;
  $("#title").value = "412 Harbor Street — Verde Coffee Roasters";
  $("#lease-count").textContent = `${state.samples.lease.length.toLocaleString()} chars`;
  $("#rules-count").textContent = `${state.samples.zoning.length.toLocaleString()} chars`;
}

async function runAudit() {
  const lease = $("#lease").value.trim();
  const rules = $("#rules").value.trim();
  const title = $("#title").value.trim();
  const notice = $("#ws-notice");
  notice.hidden = true;
  if (lease.length < 20 || rules.length < 20) {
    notice.hidden = false;
    notice.className = "notice notice-warn";
    notice.innerHTML = `${icon("alert")}<div>Both the lease and the regulatory source are required.</div>`;
    return;
  }

  const button = $("#run-btn");
  button.disabled = true;
  button.innerHTML = `<span class="spinner"></span> Running five-step audit…`;
  const panel = $("#run-panel");
  panel.innerHTML = renderRunning();
  animateSteps();

  try {
    const data = await api("/audit/process", {
      method: "POST",
      body: { document_text: lease, compliance_rules: rules, title },
    });
    stopSteps();
    state.audit = data.audit;
    state.key = data.reidentification_key || null;
    state.usage = data.usage;
    panel.innerHTML = renderAudit(data.audit, { live: true });
    bindTabs();
    bindResultActions();
    loadUsage();
    toast(`Audit complete · ${data.audit.risk?.risk_level || "done"}`);
  } catch (err) {
    stopSteps();
    panel.innerHTML = renderRunError(err);
    if (err.status === 402 && err.detail?.usage) {
      state.usage = err.detail.usage;
    }
  } finally {
    button.disabled = false;
    button.innerHTML = `${icon("play", 15)} Run audit`;
  }
}

function renderRunning() {
  const steps = [
    ["Protect", "Masking tenant identifiers"],
    ["Guard", "Screening for prompt injection"],
    ["Extract", "Reading lease fields verbatim"],
    ["Verify", "Testing claims against the source"],
    ["Decide", "Calibrating risk and actions"],
  ];
  return `<div class="panel-head"><h2>Live pipeline</h2><span class="score" id="run-clock">0.0s</span></div>
    <div class="panel-body">
      <div class="steps" id="run-steps">
        ${steps.map(([name, body], i) => `
          <div class="step ${i === 0 ? "active" : "pending"}" data-step="${i}">
            <div class="step-num">${i + 1}</div>
            <div><h4>${name}</h4><p>${body}</p></div>
          </div>`).join("")}
      </div>
      <p class="hint" style="margin-top:14px">This runs a real Clocked pipeline. Typical duration: 4–7 seconds.</p>
    </div>`;
}

function animateSteps() {
  state.step = 0;
  const started = performance.now();
  clearInterval(state.timer);
  state.timer = setInterval(() => {
    const clock = $("#run-clock");
    if (clock) clock.textContent = `${((performance.now() - started) / 1000).toFixed(1)}s`;
    const nodes = $$("#run-steps .step");
    if (!nodes.length) return;
    const advance = state.step < 4 && (performance.now() - started) > (state.step + 1) * 950;
    if (advance) {
      nodes[state.step].className = "step done";
      state.step += 1;
      nodes[state.step].className = "step active";
    }
  }, 120);
}
function stopSteps() {
  clearInterval(state.timer);
  state.timer = null;
}

function renderRunError(err) {
  const detail = err.detail || {};
  const quota = err.status === 402;
  const step = detail.step ? `<p class="small muted" style="margin:8px 0 0">Failed at step: <code>${esc(detail.step)}</code></p>` : "";
  return `<div class="panel-head"><h2>Audit</h2><span class="pill pill-fail">Stopped</span></div>
    <div class="panel-body">
      <div class="notice ${quota ? "notice-warn" : "notice-error"}">
        ${icon("alert")}
        <div>
          <strong>${quota ? "Monthly allowance reached" : "The pipeline stopped"}</strong>
          <p style="margin:6px 0 0">${esc(err.message)}</p>
          ${step}
          ${quota ? `<p style="margin:10px 0 0"><a href="#/billing">Upgrade the plan</a> or wait for the next billing period.</p>` : `<p style="margin:10px 0 0" class="small">Nothing was stored. Retry with the same documents, or check <a href="/api/v1/health" target="_blank" rel="noopener">engine health</a>.</p>`}
        </div>
      </div>
    </div>`;
}

/* --------------------------------------------------------------- result view */
function renderAudit(record, { live = false } = {}) {
  const risk = record.risk || {};
  const level = (risk.risk_level || "LOW").toLowerCase();
  const stats = risk.claim_stats || {};
  const rules = risk.rule_stats || {};
  const actions = risk.required_actions || [];
  const labels = risk.action_labels || {};
  const blocked = record.status === "blocked";
  const score = risk.score ?? 0;

  const head = blocked
    ? `<div class="panel-head"><h2>Audit blocked</h2><span class="pill pill-fail">Fail-closed</span></div>`
    : `<div class="panel-head"><h2>Audit result</h2><span class="score">${esc(record.id.slice(0, 8))} · ${record.timings?.total_ms ?? 0} ms</span></div>`;

  const verdict = blocked
    ? `<div class="verdict high">
        <div class="verdict-top">
          <div><div class="verdict-level">BLOCKED</div><div class="verdict-sub">Prompt injection detected</div></div>
          <div><h2>The document was not analysed.</h2><p class="small muted" style="margin:6px 0 0">${esc(record.message || "")}</p></div>
        </div>
        <div class="verdict-stats">
          <div class="stat"><b>${esc(record.guard?.verdict || "—")}</b><span>Guard verdict</span></div>
          <div class="stat"><b>${Number(record.guard?.probability || 0).toFixed(3)}</b><span>Injection probability</span></div>
          <div class="stat"><b>2 / 5</b><span>Steps completed</span></div>
        </div>
      </div>`
    : `<div class="verdict ${level}">
        <div class="verdict-top">
          <div>
            <div class="verdict-level">${esc(risk.risk_level || "—")}</div>
            <div class="verdict-sub">Risk score ${score}/100${risk.escalated ? " · escalated by rules" : ""}</div>
          </div>
          <div class="meter" aria-hidden="true"><div class="meter-bar"><div class="meter-fill" style="width:${score}%"></div></div></div>
          <div style="flex:1;min-width:220px">
            <h2>${esc(risk.headline || "")}</h2>
            <p class="small muted" style="margin:4px 0 0">Model assessment: ${esc(risk.model_level || "—")}${risk.escalated ? " → raised to HIGH by deterministic checks" : ""}</p>
          </div>
        </div>
        <div class="verdict-stats">
          <div class="stat"><b>${stats.contradicted ?? 0}</b><span>Claims contradicted</span></div>
          <div class="stat"><b>${stats.supported ?? 0}</b><span>Claims supported</span></div>
          <div class="stat"><b>${rules.fail ?? 0}</b><span>Rule failures</span></div>
          <div class="stat"><b>${rules.review ?? 0}</b><span>Needs review</span></div>
          <div class="stat"><b>${record.pii?.entity_count ?? 0}</b><span>Entities masked</span></div>
          <div class="stat"><b>${record.usage?.credits ?? "—"}</b><span>Clocked credits</span></div>
          <div class="stat"><b>${record.timings?.total_ms ?? 0} ms</b><span>Pipeline time</span></div>
        </div>
      </div>`;

  return `${head}
    <div class="panel-body">
      ${verdict}

      ${!blocked ? `
      <div class="grid-2" style="margin-top:20px">
        <div>
          <h3 style="font-family:var(--sans);font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);margin-bottom:8px">Why this outcome</h3>
          <ul class="rationale">${(risk.rationale || ["No material findings."]).map((r) => `<li>${esc(r)}</li>`).join("")}</ul>
        </div>
        <div>
          <h3 style="font-family:var(--sans);font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);margin-bottom:8px">Required actions</h3>
          <ul class="actions">${actions.map((a) => `<li><input type="checkbox" id="act-${esc(a)}"><label for="act-${esc(a)}">${esc(labels[a] || a)}</label></li>`).join("") || "<li>None.</li>"}</ul>
        </div>
      </div>

      <div class="tabs" role="tablist">
        <button class="tab active" data-tab="findings" role="tab">Findings</button>
        <button class="tab" data-tab="rules" role="tab">Rule engine</button>
        <button class="tab" data-tab="terms" role="tab">Lease terms</button>
        <button class="tab" data-tab="privacy" role="tab">Privacy</button>
        <button class="tab" data-tab="document" role="tab">Masked document</button>
        <button class="tab" data-tab="json" role="tab">JSON</button>
      </div>
      <div id="tab-body"></div>

      <div class="panel-foot" style="margin:22px -18px -18px;display:flex;gap:8px;flex-wrap:wrap;align-items:center">
        ${live ? `<button class="btn btn-ghost btn-sm" id="key-btn">${icon("lock", 14)} Re-identification key</button>` : ""}
        <button class="btn btn-ghost btn-sm" data-download="html">${icon("download", 14)} Report (HTML)</button>
        <button class="btn btn-ghost btn-sm" data-download="md">${icon("download", 14)} Markdown</button>
        <button class="btn btn-ghost btn-sm" data-download="json">${icon("download", 14)} JSON</button>
        <a class="btn btn-quiet btn-sm" href="/api/v1/audits/${record.id}/report.html" target="_blank" rel="noopener">Open printable report ${icon("arrow", 13)}</a>
      </div>` : `
      <div class="panel-foot" style="margin:22px -18px -18px">
        <p class="small muted" style="margin:0">No lease fields were extracted and no claims were verified. The audit stopped by design.</p>
      </div>`}
    </div>`;
}

function bindTabs() {
  const body = $("#tab-body");
  if (!body || !state.audit) return;
  const render = (name) => {
    $$(".tab").forEach((t) => t.classList.toggle("active", t.dataset.tab === name));
    body.innerHTML = tabContent(name, state.audit);
  };
  $$(".tab").forEach((tab) => tab.addEventListener("click", () => render(tab.dataset.tab)));
  render(state.tab || "findings");
}

function tabContent(name, record) {
  if (name === "findings") {
    const claims = record.claims || [];
    if (!claims.length) return `<p class="muted small">No claims were verified.</p>`;
    return `<div class="table-wrap"><table class="data">
      <thead><tr><th>#</th><th>Claim tested</th><th>Verdict</th><th>Evidence from the source</th></tr></thead>
      <tbody>${claims.map((c, i) => `<tr>
        <td class="num">${i + 1}</td>
        <td>${esc(c.claim)}</td>
        <td><span class="pill pill-${esc(c.verdict)}">${esc((c.verdict || "").replace("_", " "))}</span></td>
        <td class="quote">${c.evidence_quote ? `“${esc(c.evidence_quote)}”` : '<span class="muted">No statement in the source</span>'}</td>
      </tr>`).join("")}</tbody></table></div>
      ${(record.claims_skipped || []).length ? `<p class="hint">${record.claims_skipped.length} claim(s) skipped: the regulatory source does not address that topic, so it cannot adjudicate it.</p>` : ""}`;
  }
  if (name === "rules") {
    const rules = record.rules || [];
    if (!rules.length) return `<p class="muted small">No deterministic rule matched these documents.</p>`;
    return `<div class="table-wrap"><table class="data">
      <thead><tr><th>Check</th><th>Result</th><th>Computation</th><th>Source clause</th></tr></thead>
      <tbody>${rules.map((r) => `<tr>
        <td><strong>${esc(r.title)}</strong><div class="hint">${esc(r.detail)}</div></td>
        <td><span class="pill pill-${esc(r.status)}">${esc(r.status)}</span></td>
        <td class="mono" style="font-size:11.5px">${esc(r.computation || "—")}</td>
        <td class="quote">${r.evidence_quote ? `“${esc(r.evidence_quote)}”` : "—"}</td>
      </tr>`).join("")}</tbody></table></div>
      <p class="hint">Computed in application code, not by a language model. Each formula is reproducible.</p>`;
  }
  if (name === "terms") {
    return `<div class="table-wrap"><table class="data">
      <thead><tr><th>Field</th><th>Value read verbatim (pseudonymised)</th><th>Confidence</th></tr></thead>
      <tbody>${Object.entries(record.extracted || {}).map(([key, f]) => `<tr>
        <td class="mono" style="font-size:11.5px">${esc(key)}</td>
        <td>${esc(f.value || "—")}</td>
        <td class="mono" style="font-size:11.5px">${f.confidence ? (f.confidence * 100).toFixed(0) + "%" : "—"}</td>
      </tr>`).join("")}</tbody></table></div>`;
  }
  if (name === "privacy") {
    const pii = record.pii || {};
    return `<div class="grid-2">
      <div>
        <h3 style="font-family:var(--sans);font-size:13px;margin-bottom:8px">Masked before analysis</h3>
        <table class="kv">${Object.entries(pii.counts || {}).map(([k, v]) => `<tr><th>${esc(k)}</th><td>${v}</td></tr>`).join("")}</table>
        <p class="hint">${pii.entity_count || 0} entities across ${pii.mentions || 0} mentions. Only the masked text reached Extract, Verify and Decide.</p>
      </div>
      <div>
        <h3 style="font-family:var(--sans);font-size:13px;margin-bottom:8px">Tokens in the masked document</h3>
        <table class="kv">${(pii.entities || []).map((e) => `<tr><th>${esc(e.token)}</th><td>${esc(e.type)} · ${e.mentions} mention(s)</td></tr>`).join("")}</table>
        <div class="notice notice-info" style="margin-top:12px">${icon("lock")}<div>The mapping back to real values is never stored. ${state.key ? "It is available once from this run." : "It was handed to the browser that ran the audit."}</div></div>
      </div>
    </div>`;
  }
  if (name === "document") {
    return `<div class="doc-highlight">${esc(record.document?.masked_document || "")}</div>
      <p class="hint">This is exactly what the later pipeline steps saw. ${record.document?.truncated ? "Input was truncated to the configured limit." : ""}</p>`;
  }
  return `<pre class="code">${esc(JSON.stringify(record, null, 2))}</pre>`;
}

function bindResultActions() {
  $$("[data-download]").forEach((btn) =>
    btn.addEventListener("click", () => downloadReport(btn.dataset.download))
  );
  $("#key-btn")?.addEventListener("click", downloadKey);
  $("#run-panel").scrollIntoView({ behavior: "smooth", block: "start" });
}

async function downloadReport(kind) {
  const id = state.audit?.id;
  if (!id) return;
  const ext = kind === "md" ? "md" : kind;
  const filename = `audittrail-${id.slice(0, 8)}.${ext}`;
  try {
    const headers = state.session?.access_token ? { Authorization: `Bearer ${state.session.access_token}` } : {};
    const res = await fetch(`${API}/audits/${id}/report.${ext}`, { headers });
    if (!res.ok) throw new Error("Export failed");
    const blob = await res.blob();
    triggerDownload(blob, filename);
    toast(`Downloaded ${filename}`);
  } catch (err) {
    toast(err.message, "error");
  }
}

function downloadKey() {
  if (!state.key) return;
  const payload = {
    audit_id: state.audit?.id,
    created_at: new Date().toISOString(),
    notice: "Store this file securely. AuditTrail does not keep a copy.",
    mapping: state.key,
  };
  triggerDownload(new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" }), `reidentification-key-${state.audit.id.slice(0, 8)}.json`);
  toast("Key downloaded — store it securely");
}

function triggerDownload(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

/* ---------------------------------------------------------------- history */
async function viewHistory() {
  let audits = [];
  try {
    audits = (await api("/audits?limit=50")).audits || [];
  } catch (err) {
    return `<div class="wrap section"><div class="notice notice-error">${icon("alert")}<div>${esc(err.message)}</div></div></div>`;
  }
  return `<div class="wrap">
    <div class="ws-head">
      <div><div class="eyebrow" style="margin-bottom:10px">Audit history</div><h1>Every run, retained.</h1>
      <p>${audits.length} audit(s) visible to this ${state.session ? "account" : "demo session"}. Row-level security isolates accounts in Supabase deployments.</p></div>
      <a class="btn btn-primary btn-sm" href="#/workspace">New audit ${icon("arrow", 14)}</a>
    </div>
    <div class="panel">
      ${audits.length ? audits.map((a) => `
        <a class="list-row" href="#/audit/${a.id}" style="text-decoration:none;color:inherit">
          <div><div class="list-title">${esc(a.title)}</div>
            <div class="list-meta">${fmtDate(a.created_at)} · ${fmtTime(a.created_at)} · ${a.total_ms ?? 0} ms · ${a.contradicted} contradicted · ${a.rule_failures} rule failures</div></div>
          <span class="pill pill-${(a.risk_level || "low").toLowerCase() === "high" ? "fail" : (a.risk_level || "").toLowerCase() === "medium" ? "review" : "pass"}">${esc(a.risk_level || "—")}</span>
          <span class="mono small">${a.score ?? "—"}/100</span>
          <span class="list-arrow">${icon("arrow", 16)}</span>
        </a>`).join("") : `<div class="run-empty"><h3>No audits yet</h3><p>Run the sample lease to create your first report.</p><a class="btn btn-ghost" href="#/workspace">Open workspace</a></div>`}
    </div>
  </div>`;
}

async function viewAuditDetail(id) {
  const { audit } = await api(`/audits/${id}`);
  state.audit = audit;
  state.key = null;
  return `<div class="wrap">
    <div class="ws-head">
      <div><div class="eyebrow" style="margin-bottom:10px"><a href="#/history">History</a> / ${esc(id.slice(0, 8))}</div>
      <h1>${esc(audit.title)}</h1><p>${fmtDate(audit.created_at)} · ${fmtTime(audit.created_at)} · ${audit.timings?.total_ms ?? 0} ms</p></div>
      <a class="btn btn-ghost btn-sm" href="#/workspace">New audit</a>
    </div>
    <div class="panel">${renderAudit(audit, { live: false })}</div>
  </div>`;
}

/* ----------------------------------------------------------------- pricing */
function viewPricing() {
  const plans = state.config?.plans || [];
  return `<div class="wrap section">
    <div class="center" style="max-width:640px;margin:0 auto 36px">
      <div class="eyebrow" style="justify-content:center">Pricing</div>
      <h1 style="font-size:clamp(32px,4vw,48px)">Start with three audits. Pay when it saves you a morning.</h1>
      <p class="muted" style="margin-top:14px">Every plan runs the same five-endpoint pipeline. Higher tiers add volume, export, white-labelling and deployment options.</p>
    </div>
    <div class="price-grid">
      ${plans.map((p) => `
        <div class="price ${p.id === "pro" ? "featured" : ""}">
          ${p.id === "pro" ? '<span class="price-tag">Most popular</span>' : ""}
          <h3>${esc(p.name)}</h3>
          <div class="amount">${p.price_monthly === null ? "Custom" : p.price_monthly === 0 ? "$0" : `$${p.price_monthly}`}${p.price_monthly ? "<small>/mo</small>" : ""}</div>
          <p class="tagline">${esc(p.tagline)}</p>
          <ul>${p.features.map((f) => `<li>${esc(f)}</li>`).join("")}</ul>
          <button class="btn ${p.id === "pro" ? "btn-primary" : "btn-ghost"}" data-plan="${p.id}">
            ${p.id === "free" ? "Start free" : p.id === "enterprise" ? "Talk to us" : `Choose ${esc(p.name)}`}
          </button>
        </div>`).join("")}
    </div>
    <div class="grid-2" style="margin-top:44px">
      <div class="card card-pad">
        <h3>Why usage-based overage beats a hard cap</h3>
        <p class="muted">Deals do not arrive evenly. Overage is $2.00 per audit, billed monthly, so a busy week never blocks a closing. Unused credits do not roll over.</p>
      </div>
      <div class="card card-pad">
        <h3>What “white-label” means</h3>
        <p class="muted">Firm plans replace the AuditTrail header on exported reports with your firm's name, so the deliverable goes to your client under your brand.</p>
      </div>
    </div>
    <div class="center" style="margin-top:32px"><p class="hint">Prices in USD. ${state.config?.billing_live ? "Live billing via Stripe." : "Billing is in sandbox mode on this deployment — plan changes are instant and free."}</p></div>
  </div>`;
}

function bindPricing() {
  $$("[data-plan]").forEach((btn) =>
    btn.addEventListener("click", async () => {
      const plan = btn.dataset.plan;
      if (plan === "free") return (location.hash = "#/workspace");
      if (plan === "enterprise") return (location.href = "mailto:sales@audittrail.ai?subject=AuditTrail%20Enterprise");
      try {
        const data = await api("/billing/checkout", { method: "POST", body: { plan, return_url: location.origin } });
        if (data.url) location.href = data.url;
        else toast(data.message || "Checkout unavailable");
      } catch (err) {
        toast(err.message, "error");
      }
    })
  );
}

/* ------------------------------------------------------------------ billing */
async function viewBilling() {
  const usage = await api("/billing/usage");
  state.usage = usage;
  const plans = state.config?.plans || [];
  const keys = await api("/api-keys").catch(() => ({ api_access: false, keys: [] }));
  const pct = usage.percent ?? 0;
  return `<div class="wrap section">
    <div class="ws-head">
      <div><div class="eyebrow" style="margin-bottom:10px">Billing</div><h1>Plan and usage</h1>
      <p>${state.config?.billing_live ? "Live Stripe billing." : "Sandbox mode: plan changes are applied immediately and no card is charged."}</p></div>
      <a class="btn btn-ghost btn-sm" href="#/pricing">Compare plans</a>
    </div>
    <div class="grid-2">
      <div class="card card-pad">
        <div class="eyebrow" style="margin-bottom:10px">Current plan</div>
        <h2 style="font-size:28px">${esc(usage.plan_name)}</h2>
        <p class="muted small">${usage.limit === null ? "Unlimited audits." : `${usage.used} of ${usage.limit} audits used this month.`}</p>
        <div class="meter-bar" style="height:9px;margin:16px 0 8px"><div class="meter-fill" style="width:${pct}%;background:${pct > 85 ? "var(--signal)" : "var(--green)"}"></div></div>
        <p class="hint">${usage.remaining === null ? "No monthly cap." : `${usage.remaining} remaining · resets ${fmtDate(usage.period_end)}`}</p>
        ${usage.used ? `<p class="hint">Overage beyond the allowance: $${usage.overage_price.toFixed(2)} per audit.</p>` : ""}
      </div>
      <div class="card card-pad">
        <div class="eyebrow" style="margin-bottom:10px">Change plan</div>
        <div style="display:grid;gap:8px">
          ${plans.filter((p) => p.id !== "enterprise").map((p) => `
            <div style="display:flex;justify-content:space-between;align-items:center;gap:12px;padding:10px 0;border-bottom:1px solid #efebe1">
              <div><strong>${esc(p.name)}</strong><div class="hint">${p.audits_per_month === null ? "Unlimited" : p.audits_per_month + " audits/mo"} · ${p.price_monthly ? "$" + p.price_monthly + "/mo" : "Free"}</div></div>
              ${p.id === usage.plan ? '<span class="pill pill-pass">Current</span>' : `<button class="btn btn-ghost btn-sm" data-switch="${p.id}">Switch</button>`}
            </div>`).join("")}
        </div>
      </div>
    </div>
    <div class="card card-pad" style="margin-top:18px">
      <div class="eyebrow" style="margin-bottom:10px">API access</div>
      ${keys.api_access ? `
        <p class="muted small">Send <code>X-API-Key</code> with the same <code>/api/v1</code> routes. Keys are stored as a SHA-256 digest.</p>
        <div style="display:flex;gap:8px;align-items:center;margin:14px 0;flex-wrap:wrap">
          <input class="input" id="key-label" placeholder="Key label (e.g. diligence-bot)" style="max-width:280px">
          <button class="btn btn-primary btn-sm" id="key-create">Generate key</button>
        </div>
        <div id="key-new"></div>
        ${keys.keys.length ? `<table class="kv">${keys.keys.map((k) => `<tr><th class="mono" style="text-transform:none;letter-spacing:0">${esc(k.prefix || "at_…")}…</th><td>${esc(k.label || "untitled")} · created ${fmtDate(k.created_at)} · last used ${k.last_used ? fmtDate(k.last_used) : "never"}</td></tr>`).join("")}</table>` : '<p class="hint">No keys yet.</p>'}
      ` : `<div class="notice notice-warn">${icon("lock")}<div><strong>API access is a Solo feature.</strong><br>Upgrade to generate a key and call the pipeline from your own systems.</div></div>`}
    </div>
  </div>`;
}

function bindBilling() {
  $$("[data-switch]").forEach((btn) =>
    btn.addEventListener("click", async () => {
      try {
        await api("/billing/plan", { method: "POST", body: { plan: btn.dataset.switch } });
        toast("Plan updated");
        router();
      } catch (err) {
        toast(err.message, "error");
      }
    })
  );

  $("#key-create")?.addEventListener("click", async () => {
    const label = $("#key-label")?.value.trim();
    try {
      const data = await api("/api-keys", { method: "POST", body: { label } });
      const box = $("#key-new");
      box.innerHTML = `<div class="notice notice-info" style="margin-bottom:14px">${icon("lock")}<div style="flex:1;min-width:0"><strong>Your new key</strong><div class="mono small" style="word-break:break-all;margin-top:4px" id="key-value">${esc(data.key)}</div><div class="hint">${esc(data.notice)}</div></div><button class="btn btn-ghost btn-sm" id="key-copy">Copy</button></div>`;
      $("#key-copy").addEventListener("click", async () => {
        try {
          await navigator.clipboard.writeText(data.key);
          toast("Key copied");
        } catch {
          toast("Select and copy the key manually", "error");
        }
      });
    } catch (err) {
      toast(err.message, "error");
    }
  });
}

/* -------------------------------------------------------------------- login */
function viewLogin() {
  const configured = Boolean(state.config?.supabase_url && state.config?.supabase_key);
  return `<div class="auth-shell">
    <aside class="auth-side">
      <div class="eyebrow" style="color:#8fd3bf">Account</div>
      <h2>Your audits are isolated by row-level security.</h2>
      <p>Each account only ever sees its own documents. Audits are keyed to the verified Supabase user id, never to a value the browser supplies.</p>
      <div class="steps" style="margin-top:18px">
        <div class="step done"><div class="step-num">1</div><div><h4>Sign in or create an account</h4><p>Email and password, handled by Supabase Auth.</p></div></div>
        <div class="step done"><div class="step-num">2</div><div><h4>Run an audit</h4><p>The backend verifies your token before reading or writing.</p></div></div>
        <div class="step done"><div class="step-num">3</div><div><h4>Export the report</h4><p>HTML, Markdown or JSON, with your firm's name on Firm plans.</p></div></div>
      </div>
    </aside>
    <section class="auth-main">
      <h1 id="auth-title">Sign in</h1>
      <p class="muted small">Use your firm email. ${configured ? "" : "Supabase is not configured on this deployment, so only the demo session works."}</p>
      <div class="seg" role="tablist">
        <button class="active" data-mode="signin">Sign in</button>
        <button data-mode="signup">Create account</button>
      </div>
      <form id="auth-form">
        <label class="field"><span class="label">Email</span><input class="input" type="email" id="auth-email" autocomplete="email" required></label>
        <label class="field"><span class="label">Password</span><input class="input" type="password" id="auth-password" autocomplete="current-password" minlength="6" required></label>
        <div id="auth-error" class="notice notice-error" hidden></div>
        <button class="btn btn-primary btn-wide" type="submit" id="auth-submit">Sign in</button>
      </form>
      <div style="display:flex;align-items:center;gap:12px;margin:20px 0"><hr class="rule" style="flex:1"><span class="tiny muted">OR</span><hr class="rule" style="flex:1"></div>
      <button class="btn btn-ghost btn-wide" id="demo-btn">Continue with the demo session</button>
      <p class="hint" style="margin-top:12px">The demo session uses a shared local identity. Sign in to prove tenant isolation.</p>
    </section>
  </div>`;
}

function bindLogin() {
  let mode = "signin";
  $$(".seg button").forEach((btn) =>
    btn.addEventListener("click", () => {
      mode = btn.dataset.mode;
      $$(".seg button").forEach((b) => b.classList.toggle("active", b === btn));
      $("#auth-title").textContent = mode === "signin" ? "Sign in" : "Create account";
      $("#auth-submit").textContent = mode === "signin" ? "Sign in" : "Create account";
      $("#auth-password").autocomplete = mode === "signin" ? "current-password" : "new-password";
    })
  );

  $("#demo-btn").addEventListener("click", () => {
    signOut(false);
    location.hash = "#/workspace";
  });

  $("#auth-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    const email = $("#auth-email").value.trim();
    const password = $("#auth-password").value;
    const errorBox = $("#auth-error");
    const submit = $("#auth-submit");
    errorBox.hidden = true;
    submit.disabled = true;
    submit.innerHTML = `<span class="spinner"></span> ${mode === "signin" ? "Signing in…" : "Creating…"}`;
    try {
      const data =
        mode === "signin"
          ? await supabaseAuth("token?grant_type=password", { email, password })
          : await supabaseAuth("signup", { email, password });
      if (!data.access_token) {
        errorBox.hidden = false;
        errorBox.innerHTML = `${icon("alert")}<div>Account created. Check your email to confirm the address, then sign in.</div>`;
        return;
      }
      saveSession(data);
      updateAccount();
      toast("Signed in");
      location.hash = "#/workspace";
    } catch (err) {
      errorBox.hidden = false;
      errorBox.innerHTML = `${icon("alert")}<div>${esc(err.message)}</div>`;
    } finally {
      submit.disabled = false;
      submit.textContent = mode === "signin" ? "Sign in" : "Create account";
    }
  });
}

/* ------------------------------------------------------------------- method */
function viewMethod() {
  return `<div class="wrap section"><div class="prose">
    <div class="eyebrow">Method</div>
    <h1 style="font-size:clamp(32px,4vw,48px)">What this product does, and what it refuses to do.</h1>
    <p class="lede" style="font-size:17px;color:var(--ink-soft);margin-top:16px">AuditTrail is a compliance first pass, not an oracle. It reads a lease, checks it against a source you supply, and shows its work. Where the source is silent, it says so.</p>

    <h2>The five steps</h2>
    <table class="data" style="margin:12px 0 20px">
      <thead><tr><th>Step</th><th>Clocked endpoint</th><th>What it decides</th></tr></thead>
      <tbody>
        <tr><td>Protect</td><td class="mono">POST /clocked/pii</td><td>Which spans are identifiers, and what the masked copy looks like.</td></tr>
        <tr><td>Guard</td><td class="mono">POST /clocked/injection</td><td>Whether the document is trying to instruct the model. A dangerous verdict stops the run.</td></tr>
        <tr><td>Extract</td><td class="mono">POST /clocked/extract</td><td>Twelve lease fields, verbatim, with character spans. Missing stays missing.</td></tr>
        <tr><td>Verify</td><td class="mono">POST /clocked/grounding</td><td>Supported / contradicted / not stated, with an evidence quote for each claim.</td></tr>
        <tr><td>Decide</td><td class="mono">POST /clocked/decide</td><td>Calibrated risk level, remediation actions, human-review flag.</td></tr>
      </tbody>
    </table>

    <h2>Where the model stops</h2>
    <p>Numeric rules are computed in application code and shown with their formula. If a zoning source says “two parking bays per 100 square metres” and the lease allocates four bays for 220 sqm, the rule engine reports <code>ceil(220 ÷ 100 × 2) = 5</code> required and a shortfall of one — regardless of what the model thinks. Model verdicts cover language; the rule engine covers arithmetic; the policy layer combines them and can escalate but never silently downgrade a deterministic failure.</p>

    <h2>Privacy posture</h2>
    <ul>
      <li>Identifiers are replaced with stable tokens before extraction, verification or decision.</li>
      <li>Tokens preserve referential integrity: the tenant and the landlord remain distinguishable.</li>
      <li>Only masked text is persisted. The re-identification key is returned once to the signed-in user and never stored.</li>
      <li>Fail-closed: a prompt-injection verdict stops the audit before further model calls.</li>
      <li>Raw documents are not written to logs.</li>
    </ul>

    <h2>Limitations</h2>
    <blockquote>The supplied regulatory source is the only authority used for verification. A term absent from that source is reported as “not stated”, which is not a finding of compliance. This report is decision support, not legal advice, and should be reviewed by qualified counsel before execution.</blockquote>

    <h2>Storage modes</h2>
    <p>Supabase (Postgres with row-level security) is the production store. When it is not configured or its schema has not been applied, the server falls back to a local SQLite store so the product remains demonstrable offline. The active backend is always reported in the header and at <a href="/api/v1/health">/api/v1/health</a>.</p>

    <h2>API</h2>
    <p>The same pipeline is available over HTTP. Interactive docs: <a href="/docs">/docs</a>. Key routes: <code>POST /api/v1/audit/process</code>, <code>GET /api/v1/audits</code>, <code>GET /api/v1/audits/{id}/report.html</code>.</p>
  </div></div>`;
}

function viewNotFound() {
  return `<div class="wrap section center"><div class="eyebrow" style="justify-content:center">404</div><h1>That page does not exist.</h1><p class="muted">Check the address, or start a new audit.</p><a class="btn btn-primary" href="#/workspace">Open workspace</a></div>`;
}

/* -------------------------------------------------------------------- boot */
async function boot() {
  $("#menu-btn").addEventListener("click", () => {
    const nav = $("#nav");
    nav.classList.toggle("open");
    $("#menu-btn").setAttribute("aria-expanded", String(nav.classList.contains("open")));
  });

  const saved = localStorage.getItem(SESSION_KEY);
  if (saved) {
    try {
      state.session = JSON.parse(saved);
    } catch { localStorage.removeItem(SESSION_KEY); }
  }
  updateAccount();

  try {
    const [config, health] = await Promise.all([api("/config"), api("/health")]);
    state.config = config;
    state.health = health;
    updateStatus();
  } catch (err) {
    $("#status-text").textContent = "server unreachable";
    $("#status-chip").className = "status-chip bad";
  }

  window.addEventListener("hashchange", router);
  document.addEventListener("click", (event) => {
    const trigger = event.target.closest("[data-sample]");
    if (trigger) sessionStorage.setItem("at.loadSample", "1");
  });
  await router();
}

boot();
