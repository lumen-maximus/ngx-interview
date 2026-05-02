// ---------------------------------------------------------------------------
// Platform Ops Auditor — Static Developer Console
// ---------------------------------------------------------------------------

// Replace this value with the Terraform output `api_base_url` after deployment.
// Example: "https://1onxy44pd3.execute-api.us-east-1.amazonaws.com/dev"
const API_BASE_URL = "https://1onxy44pd3.execute-api.us-east-1.amazonaws.com/dev";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function showResult(el, type, message) {
  el.textContent = message;
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

// Store original button labels on page load.
document.querySelectorAll("button").forEach((btn) => {
  btn.dataset.label = btn.textContent;
});

// ---------------------------------------------------------------------------
// POST /audit
// ---------------------------------------------------------------------------

const auditForm = document.getElementById("audit-form");
const auditResult = document.getElementById("audit-result");
const submitBtn = document.getElementById("submit-btn");

auditForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  hideResult(auditResult);

  const body = {
    service_name: document.getElementById("service_name").value.trim(),
    environment:  document.getElementById("environment").value,
    status:       document.getElementById("status").value,
    repository:   document.getElementById("repository").value.trim() || undefined,
    owner:        document.getElementById("owner").value.trim() || undefined,
  };

  // Remove undefined keys so the JSON body stays clean.
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
      showResult(
        auditResult,
        "success",
        `Audit recorded — Score: ${data.score}/100  |  ID: ${data.audit_id}`
      );
      auditForm.reset();
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

const refreshBtn = document.getElementById("refresh-btn");
const summaryResult = document.getElementById("summary-result");

async function loadSummary() {
  hideResult(summaryResult);
  setLoading(refreshBtn, true);
  try {
    const res = await fetch(`${API_BASE_URL}/summary`);
    const data = await res.json();
    if (!res.ok) {
      showResult(summaryResult, "error", `Error ${res.status}: ${data.message || data.error || JSON.stringify(data)}`);
      return;
    }

    // Stats
    document.getElementById("stat-total").textContent = data.total_services_audited ?? "—";
    document.getElementById("stat-avg").textContent =
      data.average_score != null ? `${data.average_score}` : "—";

    // By environment
    renderKvList("by-environment", data.by_environment);

    // By status
    renderKvList("by-status", data.by_status);

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
      findingsEl.innerHTML = "<li style='color:var(--muted)'>No findings recorded.</li>";
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
      eventsEl.innerHTML = "<li style='color:var(--muted)'>No recent events.</li>";
    }
  } catch (err) {
    showResult(summaryResult, "error", `Network error: ${err.message}`);
  } finally {
    setLoading(refreshBtn, false);
  }
}

function renderKvList(elId, obj) {
  const el = document.getElementById(elId);
  el.innerHTML = "";
  if (!obj || Object.keys(obj).length === 0) {
    el.innerHTML = "<li style='color:var(--muted)'>No data.</li>";
    return;
  }
  Object.entries(obj).forEach(([key, val]) => {
    const li = document.createElement("li");
    li.innerHTML = `<span>${key}</span><span class="kv-count">${val}</span>`;
    el.appendChild(li);
  });
}

refreshBtn.addEventListener("click", loadSummary);

// Auto-load summary on page open.
loadSummary();

// ---------------------------------------------------------------------------
// POST /summarize  (optional Bedrock AI summary)
// ---------------------------------------------------------------------------

const aiBtn = document.getElementById("ai-btn");
const aiResult = document.getElementById("ai-result");
const aiContent = document.getElementById("ai-content");

aiBtn.addEventListener("click", async () => {
  hideResult(aiResult);
  aiContent.hidden = true;
  setLoading(aiBtn, true);
  try {
    const res = await fetch(`${API_BASE_URL}/summarize`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
    const data = await res.json();

    if (res.status === 501) {
      // Bedrock is disabled in Terraform — show a clean informational message.
      showResult(
        aiResult,
        "info",
        "AI summary is disabled. Set enable_bedrock_summary = true in terraform.tfvars and redeploy to enable it."
      );
      return;
    }

    if (!res.ok) {
      showResult(aiResult, "error", `Error ${res.status}: ${data.message || data.error || JSON.stringify(data)}`);
      return;
    }

    document.getElementById("ai-text").textContent = data.summary;
    const ts = data.generated_at ? new Date(data.generated_at * 1000).toLocaleString() : "";
    document.getElementById("ai-meta").textContent =
      `Model: ${data.model_id}${ts ? "  |  Generated: " + ts : ""}${data.summary_id ? "  |  ID: " + data.summary_id : ""}`;
    aiContent.hidden = false;
  } catch (err) {
    showResult(aiResult, "error", `Network error: ${err.message}`);
  } finally {
    setLoading(aiBtn, false);
  }
});
