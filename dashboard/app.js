const apiBaseInput = document.getElementById("api-base");
const queueBody = document.getElementById("queue-body");
const queueEmpty = document.getElementById("queue-empty");
const refreshBtn = document.getElementById("refresh-btn");

const detailPlaceholder = document.getElementById("detail-placeholder");
const detailContent = document.getElementById("detail-content");
const detailCustomer = document.getElementById("detail-customer");
const detailTypology = document.getElementById("detail-typology");
const detailScore = document.getElementById("detail-score");
const explanationBars = document.getElementById("explanation-bars");
const rawFeaturesTable = document.querySelector("#raw-features-table tbody");

const dispositionForm = document.getElementById("disposition-form");
const decisionSelect = document.getElementById("decision-select");
const rationaleInput = document.getElementById("rationale-input");
const analystInput = document.getElementById("analyst-input");
const dispositionStatus = document.getElementById("disposition-status");

let selectedAlertId = null;

function apiBase() {
  return apiBaseInput.value.replace(/\/$/, "");
}

async function loadQueue() {
  const resp = await fetch(`${apiBase()}/alerts?status=OPEN`);
  const alerts = await resp.json();

  queueBody.innerHTML = "";
  queueEmpty.hidden = alerts.length > 0;

  for (const alert of alerts) {
    const row = document.createElement("tr");
    row.className = "queue-row";
    row.dataset.alertId = alert.id;
    if (alert.id === selectedAlertId) row.classList.add("selected");
    row.innerHTML = `
      <td>#${alert.id}</td>
      <td>${alert.customer_id}</td>
      <td>${alert.typology_hint}</td>
      <td>${(alert.score * 100).toFixed(1)}%</td>
      <td>${new Date(alert.created_at).toLocaleString()}</td>
    `;
    row.addEventListener("click", () => selectAlert(alert.id));
    queueBody.appendChild(row);
  }
}

async function selectAlert(alertId) {
  selectedAlertId = alertId;
  const resp = await fetch(`${apiBase()}/alerts/${alertId}`);
  if (!resp.ok) return;
  const alert = await resp.json();

  detailPlaceholder.hidden = true;
  detailContent.hidden = false;
  dispositionStatus.textContent = "";
  decisionSelect.value = "";
  rationaleInput.value = "";
  analystInput.value = "";
  decisionSelect.disabled = false;
  rationaleInput.disabled = false;
  analystInput.disabled = false;
  dispositionForm.querySelector("button[type=submit]").disabled = false;

  detailCustomer.textContent = alert.customer_id;
  detailTypology.textContent = alert.typology_hint;
  detailScore.textContent = `${(alert.score * 100).toFixed(1)}%`;

  const maxAbs = Math.max(...alert.explanation.map((e) => Math.abs(e.contribution)), 0.001);
  explanationBars.innerHTML = "";
  for (const item of alert.explanation) {
    const pct = (Math.abs(item.contribution) / maxAbs) * 50; // half-width max, bars grow from center
    const isPositive = item.contribution >= 0;
    const row = document.createElement("div");
    row.className = "bar-row";
    row.innerHTML = `
      <span>${item.feature}</span>
      <span class="bar-track">
        <span class="bar-fill ${isPositive ? "positive" : "negative"}" style="width:${pct}%"></span>
      </span>
      <span>${item.contribution.toFixed(3)}</span>
    `;
    explanationBars.appendChild(row);
  }

  rawFeaturesTable.innerHTML = "";
  for (const [key, value] of Object.entries(alert.raw_features)) {
    const row = document.createElement("tr");
    row.innerHTML = `<td>${key}</td><td>${value}</td>`;
    rawFeaturesTable.appendChild(row);
  }

  await loadQueue(); // re-render to reflect selection highlight
}

dispositionForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!selectedAlertId) return;

  dispositionStatus.textContent = "Submitting…";
  dispositionStatus.className = "status-msg";

  const resp = await fetch(`${apiBase()}/alerts/${selectedAlertId}/disposition`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      decision: decisionSelect.value,
      rationale: rationaleInput.value,
      analyst: analystInput.value,
    }),
  });

  if (resp.ok) {
    dispositionStatus.textContent = "Disposition recorded.";
    dispositionStatus.className = "status-msg ok";
    // Leave the detail panel showing the confirmation rather than
    // snapping back to the placeholder in the same tick -- an
    // earlier version did that and the message was never actually
    // visible to anyone, caught by a Playwright check that waited
    // for the message and found the whole panel already hidden.
    decisionSelect.disabled = true;
    rationaleInput.disabled = true;
    analystInput.disabled = true;
    dispositionForm.querySelector("button[type=submit]").disabled = true;
    selectedAlertId = null;
    await loadQueue();
  } else if (resp.status === 409) {
    dispositionStatus.textContent = "This alert was already decided by someone else — refreshing the queue.";
    dispositionStatus.className = "status-msg err";
    await loadQueue();
  } else {
    const body = await resp.json().catch(() => ({}));
    dispositionStatus.textContent = `Failed: ${body.detail || resp.status}`;
    dispositionStatus.className = "status-msg err";
  }
});

refreshBtn.addEventListener("click", loadQueue);

loadQueue();
