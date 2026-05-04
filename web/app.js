// ---------------------------------------------------------------------------
// Platform Ops Auditor — Static Developer Console
// ---------------------------------------------------------------------------

const API_BASE_URL = "https://1onxy44pd3.execute-api.us-east-1.amazonaws.com/dev";

// Catalog state (held in module scope for filter re-rendering without refetch)
let catalogServices = [];
const catalogFilters = { env: "all", status: "all", q: "" };

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function showResult(el, type, message) {
  el.textContent = message;
  el.className = `result-box ${type}`;
  el.hidden = false;
}

// Used only for controlled, hardcoded HTML — never with user-supplied data.
function showResultHTML(el, type, html) {
  el.innerHTML = html;
  el.className = `result-box ${type}`;
  el.hidden = false;
}

function hideResult(el) {
  el.hidden = true;
  el.textContent = "";
  el.className = "result-box";
}

function setLoading(btn, loading) {
  btn.disabled = loading;
  btn.textContent = loading ? "Loading…" : btn.dataset.label;
}

function scoreClass(score) {
  if (score >= 80) return "score-good";
  if (score >= 50) return "score-warn";
  return "score-bad";
}

function escapeHtml(s) {
  return String(s)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function relativeTime(epochSec) {
  if (!epochSec) return "\u2014";
  const diff = Math.max(0, Math.floor(Date.now() / 1000) - Number(epochSec));
  if (diff < 60)        return `${diff}s ago`;
  if (diff < 3600)      return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400)     return `${Math.floor(diff / 3600)}h ago`;
  if (diff < 86400 * 7) return `${Math.floor(diff / 86400)}d ago`;
  return new Date(Number(epochSec) * 1000).toLocaleDateString();
}

function repoLink(repo) {
  if (!repo) return '<span class="muted">&mdash;</span>';
  const safe = escapeHtml(repo);
  if (/^[\w.-]+\/[\w.-]+$/.test(repo)) {
    return `<a class="repo-link" href="https://github.com/${safe}" target="_blank" rel="noopener">${safe}</a>`;
  }
  return safe;
}

// Store original button labels on page load.
document.querySelectorAll("button").forEach((btn) => {
  btn.dataset.label = btn.textContent;
});

// ---------------------------------------------------------------------------
// Footer timestamp
// ---------------------------------------------------------------------------

function initFooterTimestamp() {
  const el = document.getElementById("footer-timestamp");
  if (el) el.textContent = `Loaded ${new Date().toLocaleString()}`;
}

initFooterTimestamp();

// ---------------------------------------------------------------------------
// API status pill
// ---------------------------------------------------------------------------

function setApiStatus(connected) {
  const pill = document.getElementById("api-status-pill");
  const text = document.getElementById("api-status-text");
  if (!pill || !text) return;
  pill.classList.remove("connected", "unreachable");
  pill.classList.add(connected ? "connected" : "unreachable");
  text.textContent = connected ? "API Connected" : "API Unreachable";
}

// ---------------------------------------------------------------------------
// Score bar
// ---------------------------------------------------------------------------

function showScoreBar(score) {
  const wrap = document.getElementById("score-bar-wrap");
  const fill = document.getElementById("score-bar-fill");
  const aria = document.getElementById("score-bar-aria");
  if (!wrap || !fill) return;
  wrap.hidden = false;
  // Remove classes for clean transition start
  fill.className = "score-bar-fill";
  fill.style.width = "0";
  // Double rAF to ensure transition fires after initial render
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      fill.classList.add(scoreClass(score));
      fill.style.width = `${score}%`;
      if (aria) aria.setAttribute("aria-valuenow", String(score));
    });
  });
}

function hideScoreBar() {
  const wrap = document.getElementById("score-bar-wrap");
  if (wrap) wrap.hidden = true;
}

// ---------------------------------------------------------------------------
// POST /audit
// ---------------------------------------------------------------------------

const auditForm   = document.getElementById("audit-form");
const auditResult = document.getElementById("audit-result");
const submitBtn   = document.getElementById("submit-btn");

auditForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  hideResult(auditResult);
  hideScoreBar();

  const body = {
    service_name: document.getElementById("service_name").value.trim(),
    environment:  document.getElementById("environment").value,
    status:       document.getElementById("status").value,
    repository:   document.getElementById("repository").value.trim() || undefined,
    owner:        document.getElementById("owner").value.trim() || undefined,
  };

  Object.keys(body).forEach((k) => body[k] === undefined && delete body[k]);

  if (!body.service_name) {
    showResult(auditResult, "error", "Service Name is required.");
    return;
  }

  setLoading(submitBtn, true);
  try {
    const res = await fetch(`${API_BASE_URL}/audit`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (res.ok) {
      const cls = scoreClass(data.score);
      const statusIcon = cls === "score-good" ? "✓" : cls === "score-warn" ? "⚠" : "✗";
      showResult(
        auditResult,
        "success",
        `${statusIcon}  Score: ${data.score}/100  ·  Audit ID: ${data.audit_id}`
      );
      showScoreBar(data.score);
      auditForm.reset();
      // Auto-refresh the catalog + summary so the new audit is immediately visible.
      // This is the connective tissue between submit form, summary, and catalog.
      await loadSummary();
    } else {
      showResult(auditResult, "error", `Error ${res.status}: ${data.message || data.error || JSON.stringify(data)}`);
    }
  } catch (err) {
    showResult(auditResult, "error", `Network error: ${err.message}`);
  } finally {
    setLoading(submitBtn, false);
  }
});

// ---------------------------------------------------------------------------
// GET /summary
// ---------------------------------------------------------------------------

const refreshBtn   = document.getElementById("refresh-btn");
const summaryResult = document.getElementById("summary-result");
const summaryContent = document.getElementById("summary-content");
let summaryLoaded = false;

async function loadSummary() {
  hideResult(summaryResult);
  setLoading(refreshBtn, true);
  try {
    const res = await fetch(`${API_BASE_URL}/summary`);
    const data = await res.json();

    setApiStatus(res.ok);

    if (!res.ok) {
      showResult(summaryResult, "error", `Error ${res.status}: ${data.message || data.error || JSON.stringify(data)}`);
      return;
    }

    // Stats
    const totalEl = document.getElementById("stat-total");
    const avgEl   = document.getElementById("stat-avg");
    const avgBlock = document.getElementById("stat-avg-block");

    totalEl.classList.remove("skeleton");
    avgEl.classList.remove("skeleton");
    totalEl.textContent = data.total_services_audited ?? "—";

    const avg = data.average_score;
    avgEl.textContent = avg != null ? String(avg) : "—";

    if (avgBlock && avg != null) {
      avgBlock.classList.remove("score-good", "score-warn", "score-bad");
      avgBlock.classList.add(scoreClass(avg));
    }

    // By environment
    renderEnvList("by-environment", data.by_environment);

    // By status
    renderStatusList("by-status", data.by_status);

    // Top findings
    const findingsEl = document.getElementById("top-findings");
    findingsEl.innerHTML = "";
    if (data.top_findings && data.top_findings.length > 0) {
      data.top_findings.forEach((f) => {
        const li = document.createElement("li");
        // Backwards-compat: accept either {finding,count} object or plain string
        const text = typeof f === "string" ? f : f.finding;
        const count = typeof f === "object" && f !== null ? f.count : null;
        const label = document.createElement("span");
        label.textContent = text;
        li.appendChild(label);
        if (count != null) {
          const badge = document.createElement("span");
          badge.className = "finding-count";
          badge.textContent = `\u00d7${count}`;
          li.appendChild(badge);
        }
        findingsEl.appendChild(li);
      });
    } else {
      const li = document.createElement("li");
      li.style.color = "var(--muted)";
      li.textContent = "No findings recorded.";
      findingsEl.appendChild(li);
    }

    // Recent events
    const eventsEl = document.getElementById("recent-events");
    eventsEl.innerHTML = "";
    if (data.recent_operational_events && data.recent_operational_events.length > 0) {
      data.recent_operational_events.forEach((ev) => {
        const li = document.createElement("li");
        if (typeof ev === "string") {
          li.textContent = ev;
        } else {
          const ts = document.createElement("span");
          ts.className = "event-ts";
          ts.textContent = relativeTime(ev.created_at);
          const type = document.createElement("span");
          type.className = `event-type event-type--${(ev.event_type || "").replace(/_/g, "-")}`;
          type.textContent = ev.event_type || "event";
          const route = document.createElement("span");
          route.className = "event-route";
          route.textContent = `${ev.method || ""} ${ev.route || ""}`.trim();
          const msg = document.createElement("span");
          msg.className = "event-msg";
          msg.textContent = ev.message || "";
          li.appendChild(ts);
          li.appendChild(type);
          li.appendChild(route);
          li.appendChild(msg);
        }
        eventsEl.appendChild(li);
      });
    } else {
      const li = document.createElement("li");
      li.style.color = "var(--muted)";
      li.textContent = "No recent events.";
      eventsEl.appendChild(li);
    }

    // Service catalog
    catalogServices = Array.isArray(data.services) ? data.services : [];
    renderCatalog();

    // Generated-at timestamp
    const genEl = document.getElementById("summary-generated-at");
    if (genEl && data.generated_at) {
      genEl.hidden = false;
      genEl.textContent = `Updated ${new Date(data.generated_at * 1000).toLocaleTimeString()}`;
    }

    // Fade-up on first load only
    if (!summaryLoaded && summaryContent) {
      summaryContent.classList.add("fade-in-up");
      summaryLoaded = true;
    }
  } catch (err) {
    setApiStatus(false);
    showResult(summaryResult, "error", `Network error: ${err.message}`);
  } finally {
    setLoading(refreshBtn, false);
  }
}

function renderEnvList(elId, obj) {
  const el = document.getElementById(elId);
  el.innerHTML = "";
  if (!obj || Object.keys(obj).length === 0) {
    const li = document.createElement("li");
    li.style.color = "var(--muted)";
    li.textContent = "No data.";
    el.appendChild(li);
    return;
  }
  Object.entries(obj).forEach(([key, val]) => {
    const li = document.createElement("li");
    const dot = document.createElement("span");
    dot.className = `env-dot env-dot--${key}`;
    const name = document.createElement("span");
    name.appendChild(dot);
    name.appendChild(document.createTextNode(key));
    const count = document.createElement("span");
    count.className = "kv-count";
    count.textContent = String(val);
    li.appendChild(name);
    li.appendChild(count);
    el.appendChild(li);
  });
}

function renderStatusList(elId, obj) {
  const el = document.getElementById(elId);
  el.innerHTML = "";
  if (!obj || Object.keys(obj).length === 0) {
    const li = document.createElement("li");
    li.style.color = "var(--muted)";
    li.textContent = "No data.";
    el.appendChild(li);
    return;
  }
  const colorMap = { healthy: "kv-status-healthy", degraded: "kv-status-degraded", unhealthy: "kv-status-unhealthy" };
  Object.entries(obj).forEach(([key, val]) => {
    const li = document.createElement("li");
    const name = document.createElement("span");
    name.textContent = key;
    const count = document.createElement("span");
    count.className = `kv-count ${colorMap[key] || ""}`.trim();
    count.textContent = String(val);
    li.appendChild(name);
    li.appendChild(count);
    el.appendChild(li);
  });
}

refreshBtn.addEventListener("click", loadSummary);
loadSummary();

// ---------------------------------------------------------------------------
// Service catalog (filters + render)
// ---------------------------------------------------------------------------

function renderCatalog() {
  const tbody = document.getElementById("catalog-body");
  const countEl = document.getElementById("catalog-count");
  if (!tbody) return;

  const q = catalogFilters.q.trim().toLowerCase();
  const filtered = catalogServices.filter((s) => {
    if (catalogFilters.env !== "all" && s.environment !== catalogFilters.env) return false;
    if (catalogFilters.status !== "all" && s.status !== catalogFilters.status) return false;
    if (q) {
      const hay = `${s.service_name} ${s.owner || ""} ${s.repository || ""}`.toLowerCase();
      if (!hay.includes(q)) return false;
    }
    return true;
  });

  if (countEl) {
    const total = catalogServices.length;
    countEl.textContent = filtered.length === total
      ? `${total} service${total === 1 ? "" : "s"}`
      : `${filtered.length} of ${total} services`;
  }

  if (filtered.length === 0) {
    const msg = catalogServices.length === 0
      ? "No services audited yet. Submit one above to populate the catalog."
      : "No services match the current filters.";
    tbody.innerHTML = `<tr><td colspan="7" class="empty-cell">${escapeHtml(msg)}</td></tr>`;
    return;
  }

  tbody.innerHTML = filtered.map((s) => {
    const sCls = scoreClass(s.score);
    const env = escapeHtml(s.environment || "");
    const st  = escapeHtml(s.status || "");
    const name = escapeHtml(s.service_name);
    return `
      <tr class="catalog-row" data-service-name="${name}" tabindex="0" role="button" aria-label="View detail for ${name}">
        <td class="svc-name">${name}</td>
        <td><span class="env-dot env-dot--${env}"></span>${env}</td>
        <td><span class="status-chip status-chip--${st}">${st}</span></td>
        <td class="score-cell ${sCls}">${Number(s.score)}</td>
        <td>${s.owner ? escapeHtml(s.owner) : '<span class="muted">&mdash;</span>'}</td>
        <td>${repoLink(s.repository)}</td>
        <td class="muted">${escapeHtml(relativeTime(s.created_at))}</td>
      </tr>`;
  }).join("");

  // Wire row clicks (event delegation kept simple here since rows are re-rendered)
  tbody.querySelectorAll(".catalog-row").forEach((row) => {
    const name = row.getAttribute("data-service-name");
    row.addEventListener("click", () => openServiceDetail(name));
    row.addEventListener("keydown", (e) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        openServiceDetail(name);
      }
    });
  });
}

document.querySelectorAll(".filter-pill").forEach((btn) => {
  btn.addEventListener("click", () => {
    const group = btn.dataset.filter;
    const value = btn.dataset.value;
    catalogFilters[group] = value;
    document.querySelectorAll(`.filter-pill[data-filter="${group}"]`).forEach((b) => {
      b.classList.toggle("is-active", b.dataset.value === value);
    });
    renderCatalog();
  });
});

const catalogSearch = document.getElementById("catalog-search");
if (catalogSearch) {
  catalogSearch.addEventListener("input", (e) => {
    catalogFilters.q = e.target.value;
    renderCatalog();
  });
}

// ---------------------------------------------------------------------------
// API reference (curl examples)
// ---------------------------------------------------------------------------

function renderApiReference() {
  const baseEl = document.getElementById("api-base-url");
  if (baseEl) baseEl.textContent = API_BASE_URL;

  const audit = document.getElementById("curl-audit");
  const summary = document.getElementById("curl-summary");
  const summarize = document.getElementById("curl-summarize");

  if (audit) audit.textContent =
    `curl -sX POST ${API_BASE_URL}/audit \\\n  -H 'Content-Type: application/json' \\\n  -d '{
    "service_name": "ngx-payments-gateway",
    "environment": "prod",
    "status": "healthy",
    "repository": "ngx/payments-gateway",
    "owner": "ngx-platform-team"
  }'`;

  if (summary) summary.textContent = `curl -s ${API_BASE_URL}/summary | jq .`;

  const auditByService = document.getElementById("curl-audit-by-service");
  if (auditByService) auditByService.textContent =
    `curl -s ${API_BASE_URL}/audit/ngx-payments-gateway | jq .`;

  if (summarize) summarize.textContent =
    `curl -sX POST ${API_BASE_URL}/summarize \\\n  -H 'Content-Type: application/json' -d '{}' | jq .`;
}

renderApiReference();

// ---------------------------------------------------------------------------
// POST /summarize
// ---------------------------------------------------------------------------

const aiBtn     = document.getElementById("ai-btn");
const aiResult  = document.getElementById("ai-result");
const aiContent = document.getElementById("ai-content");

aiBtn.addEventListener("click", async () => {
  aiContent.hidden = true;
  hideResult(aiResult);
  setLoading(aiBtn, true);
  try {
    const res = await fetch(`${API_BASE_URL}/summarize`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    const data = await res.json();
    if (res.status === 501) {
      // Hardcoded HTML — no user data involved, safe from XSS
      showResultHTML(
        aiResult,
        "warn",
        `AI summaries are currently disabled (<code>bedrock_stub = true</code>).<br>` +
        `To enable live Bedrock responses, set in <code>terraform/terraform.tfvars</code>:` +
        `<code class="ai-hint-code">enable_bedrock_summary = true\nbedrock_stub           = false</code>` +
        `Then run <code>terraform apply</code> and redeploy.`
      );
      return;
    }
    if (!res.ok) {
      showResult(aiResult, "error", `Error ${res.status}: ${data.error || JSON.stringify(data)}`);
      return;
    }
    document.getElementById("ai-text").textContent = data.summary;
    document.getElementById("ai-meta").textContent =
      `Model: ${data.model_id} · Generated ${new Date().toLocaleTimeString()}`;
    aiContent.hidden = false;
  } catch (err) {
    showResult(aiResult, "error", `Network error: ${err.message}`);
  } finally {
    setLoading(aiBtn, false);
  }
});

// ---------------------------------------------------------------------------
// GET /audit/{service_name} — service drill-down
// ---------------------------------------------------------------------------

const detailOverlay = document.getElementById("service-detail-overlay");
const detailTitle   = document.getElementById("detail-title");
const detailBody    = document.getElementById("detail-body");
const detailClose   = document.getElementById("detail-close");

function closeServiceDetail() {
  if (!detailOverlay) return;
  detailOverlay.hidden = true;
  document.body.classList.remove("modal-open");
}

if (detailClose) detailClose.addEventListener("click", closeServiceDetail);
if (detailOverlay) detailOverlay.addEventListener("click", (e) => {
  if (e.target === detailOverlay) closeServiceDetail();
});
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && detailOverlay && !detailOverlay.hidden) closeServiceDetail();
});

async function openServiceDetail(serviceName) {
  if (!detailOverlay) return;
  detailOverlay.hidden = false;
  document.body.classList.add("modal-open");
  detailTitle.textContent = serviceName;
  detailBody.innerHTML = '<p class="muted">Loading audit history&hellip;</p>';

  try {
    const res = await fetch(`${API_BASE_URL}/audit/${encodeURIComponent(serviceName)}`);
    const data = await res.json();
    if (!res.ok) {
      detailBody.innerHTML = `<p class="result-box error" style="margin:0">Error ${res.status}: ${escapeHtml(data.message || data.error || "Failed to load")}</p>`;
      return;
    }
    renderServiceDetail(data);
  } catch (err) {
    detailBody.innerHTML = `<p class="result-box error" style="margin:0">Network error: ${escapeHtml(err.message)}</p>`;
  }
}

function renderServiceDetail(data) {
  const latest = data.latest || {};
  const history = Array.isArray(data.history) ? data.history : [];
  const cls = scoreClass(latest.score || 0);

  const findingsHtml = (latest.findings || []).length
    ? `<ul class="detail-findings">${latest.findings.map((f) => `<li>${escapeHtml(f)}</li>`).join("")}</ul>`
    : '<p class="muted" style="margin:0">No findings recorded.</p>';

  const historyRows = history.map((h) => `
    <tr>
      <td class="muted">${escapeHtml(relativeTime(h.created_at))}</td>
      <td><span class="env-dot env-dot--${escapeHtml(h.environment || "")}"></span>${escapeHtml(h.environment || "")}</td>
      <td><span class="status-chip status-chip--${escapeHtml(h.status || "")}">${escapeHtml(h.status || "")}</span></td>
      <td class="score-cell ${scoreClass(h.score || 0)}">${Number(h.score || 0)}</td>
      <td class="muted detail-audit-id">${escapeHtml(h.audit_id || "")}</td>
    </tr>`).join("");

  detailBody.innerHTML = `
    <div class="detail-latest">
      <div class="detail-latest-stats">
        <div class="detail-stat">
          <span class="stat-label">Latest Score</span>
          <span class="stat-value ${cls}">${Number(latest.score || 0)}</span>
        </div>
        <div class="detail-stat">
          <span class="stat-label">Status</span>
          <span class="status-chip status-chip--${escapeHtml(latest.status || "")}">${escapeHtml(latest.status || "")}</span>
        </div>
        <div class="detail-stat">
          <span class="stat-label">Environment</span>
          <span><span class="env-dot env-dot--${escapeHtml(latest.environment || "")}"></span>${escapeHtml(latest.environment || "")}</span>
        </div>
        <div class="detail-stat">
          <span class="stat-label">Audits</span>
          <span class="stat-value">${Number(data.audit_count || 0)}</span>
        </div>
      </div>
      <div class="detail-meta-row">
        <div><span class="stat-label">Owner</span><span>${latest.owner ? escapeHtml(latest.owner) : '<span class="muted">&mdash;</span>'}</span></div>
        <div><span class="stat-label">Repository</span><span>${repoLink(latest.repository || "")}</span></div>
      </div>
      <div>
        <h4 class="detail-section-title">Latest Findings</h4>
        ${findingsHtml}
      </div>
    </div>
    <div>
      <h4 class="detail-section-title">Audit History (${history.length})</h4>
      <div class="table-wrap detail-history-wrap">
        <table class="detail-history">
          <thead>
            <tr>
              <th scope="col">When</th>
              <th scope="col">Env</th>
              <th scope="col">Status</th>
              <th scope="col">Score</th>
              <th scope="col">Audit ID</th>
            </tr>
          </thead>
          <tbody>${historyRows}</tbody>
        </table>
      </div>
    </div>
  `;
}
