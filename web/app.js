// ---------------------------------------------------------------------------
// Platform Ops Auditor — Static Developer Console
// ---------------------------------------------------------------------------

const API_BASE_URL = "https://1onxy44pd3.execute-api.us-east-1.amazonaws.com/dev";

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
      // Refresh summary after a short delay so new record is visible
      setTimeout(loadSummary, 600);
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
        li.textContent = f;
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
        li.textContent = typeof ev === "string" ? ev : JSON.stringify(ev);
        eventsEl.appendChild(li);
      });
    } else {
      const li = document.createElement("li");
      li.style.color = "var(--muted)";
      li.textContent = "No recent events.";
      eventsEl.appendChild(li);
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
