const pill = document.getElementById("pill");
const gate = document.getElementById("gate");
const decisionEl = document.getElementById("decision");
const results = document.getElementById("results");
const store = document.getElementById("store");
const catalog = document.getElementById("catalog");
const decisionCard = document.getElementById("decisionCard");
const stageBanner = document.getElementById("stageBanner");
const stageTitle = document.getElementById("stageTitle");
const stageSub = document.getElementById("stageSub");

let lastFingerprint = null;

async function refreshCatalog() {
  try {
    const status = await fetch("/lab/status").then((r) => r.json());
    catalog.innerHTML = (status.tools || [])
      .map((name) => `<span>${name}</span>`)
      .join("");
  } catch (error) {
    catalog.textContent = error.message;
  }
}

function fingerprint(data) {
  if (!data || !data.run_id) return null;
  const effect = data.outcome?.decisions?.[0]?.effect || "";
  return [data.run_id, data.status || "", effect].join("|");
}

function setStage(phase, title, sub) {
  stageBanner.className = `stage-banner is-${phase}`;
  stageTitle.textContent = title;
  stageSub.textContent = sub;
}

function renderLatest(data) {
  if (!data || !data.run_id) return;
  const fp = fingerprint(data);
  if (fp === lastFingerprint) return;
  lastFingerprint = fp;

  const status = data.status || "done";
  const call = (data.proposals || [])[0];

  if (status === "thinking" || status === "calling") {
    pill.className = "status-pill is-thinking pulse";
    pill.textContent = "STANDBY";
    decisionCard.classList.remove("is-allow", "is-deny", "pop");
    setStage(
      "thinking",
      "Waiting for tool call",
      call
        ? `Ready for ${call.name}`
        : "Tool window opens after the agent decides."
    );
    gate.textContent = "Gateway has not evaluated this call yet.";
    decisionEl.textContent = "Pending…";
    results.textContent = "·";
    store.textContent = "·";
    return;
  }

  if (status === "evaluating") {
    pill.className = "status-pill is-thinking pulse";
    pill.textContent = "CHECKING";
    decisionCard.classList.remove("is-allow", "is-deny", "pop");
    setStage(
      "calling",
      "Gateway evaluating tool call…",
      call ? `Checking policy for ${call.name}` : "Running policy checks"
    );
    gate.textContent = "toolgate is deciding ALLOW vs DENY…";
    decisionEl.textContent = "Evaluating…";
    results.textContent = "·";
    return;
  }

  if (status === "error") {
    pill.className = "status-pill is-deny";
    pill.textContent = "ERROR";
    setStage("deny", "Run failed", data.error || "No tool decision available.");
    gate.textContent = data.error || "Lab run failed before tools executed.";
    return;
  }

  const decision = data.outcome?.decisions?.[0];
  const allowed = decision?.effect === "ALLOW";
  pill.className = `status-pill ${allowed ? "is-ok" : "is-deny"}`;
  pill.textContent = allowed ? "SUCCESS" : "DENIED";
  decisionCard.classList.toggle("is-allow", !!allowed);
  decisionCard.classList.toggle("is-deny", !allowed);
  decisionCard.classList.remove("pop");
  void decisionCard.offsetWidth;
  decisionCard.classList.add("pop");

  if (allowed) {
    setStage(
      "allow",
      "Tool call succeeded",
      "Gateway ALLOW · SimulatedRuntime applied side effects."
    );
    gate.textContent = "Gateway ALLOW · tool executed against the project store.";
  } else {
    setStage(
      "deny",
      "Tool call denied",
      `Blocked by ${decision?.rule_id || "policy"} · no side effects.`
    );
    gate.textContent = "Gateway DENY · tool runtime skipped; store unchanged.";
  }

  decisionEl.textContent = JSON.stringify(decision || {}, null, 2);
  results.textContent = JSON.stringify(data.outcome?.results || [], null, 2);
  store.textContent = JSON.stringify(data.store_snapshot || {}, null, 2);
}

async function poll() {
  try {
    const data = await fetch("/lab/latest").then((r) => r.json());
    renderLatest(data);
  } catch {
    /* ignore */
  }
}

refreshCatalog();
poll();
setInterval(poll, 400);
