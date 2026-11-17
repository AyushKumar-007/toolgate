const verdict = document.getElementById("verdict");
const decisionOut = document.getElementById("decisionOut");
const resultOut = document.getElementById("resultOut");
const agentOut = document.getElementById("agentOut");
const auditList = document.getElementById("auditList");
const flowStatus = document.getElementById("flowStatus");
const packet = document.getElementById("packet");
const packetLabel = document.getElementById("packetLabel");
const flowRoot = document.getElementById("flowRoot");

const nodeUser = document.getElementById("nodeUser");
const nodeAgent = document.getElementById("nodeAgent");
const agentTitle = document.getElementById("agentTitle");
const nodeEnforce = document.getElementById("nodeEnforce");
const nodeDecision = document.getElementById("nodeDecision");
const nodeAudit = document.getElementById("nodeAudit");
const nodeTools = document.getElementById("nodeTools");
const nodeBlocked = document.getElementById("nodeBlocked");

const briefing = document.getElementById("briefing");
const briefKicker = document.getElementById("briefKicker");
const briefTitle = document.getElementById("briefTitle");
const briefSummary = document.getElementById("briefSummary");
const briefTool = document.getElementById("briefTool");
const briefExpect = document.getElementById("briefExpect");
const briefSteps = document.getElementById("briefSteps");
const briefProtect = document.getElementById("briefProtect");
const briefProtectLabel = document.getElementById("briefProtectLabel");
const briefProtectBody = document.getElementById("briefProtectBody");
const misuseCard = document.getElementById("misuseCard");
const misuseKicker = document.getElementById("misuseKicker");
const misuseBody = document.getElementById("misuseBody");

const labPreset = document.getElementById("labPreset");
const labPrincipal = document.getElementById("labPrincipal");
const labTask = document.getElementById("labTask");
const labHint = document.getElementById("labHint");
const labRunBtn = document.getElementById("labRunBtn");
const labResetBtn = document.getElementById("labResetBtn");
const labModelHint = document.getElementById("labModelHint");
const labPill = document.getElementById("labPill");
const labDot = document.getElementById("labDot");
const labPillText = document.getElementById("labPillText");

const RULE_ORDER = [
  "context",
  "schema",
  "tenant",
  "ownership",
  "actions",
  "arguments",
  "approval",
];

let labStatus = null;
let labMode = "gateway";
let animating = false;

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function setMode(next) {
  labMode = next;
  document.querySelectorAll(".lab-mode").forEach((btn) => {
    btn.classList.toggle("is-active", btn.dataset.mode === labMode);
  });
  nodeEnforce.textContent = `Mode = ${labMode}`;
}

function followFocus(el, { block = "center", inline = "nearest" } = {}) {
  if (!el || typeof el.scrollIntoView !== "function") return;
  const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches;
  el.scrollIntoView({
    behavior: reduce ? "auto" : "smooth",
    block,
    inline,
  });
}

function setStatus(text) {
  flowStatus.textContent = text;
}

async function desktopClose() {
  try {
    await fetch("/lab/desktop/close", { method: "POST" });
  } catch {
    /* ignore */
  }
}

async function desktopOpen(kind) {
  try {
    const response = await fetch(`/lab/desktop/${kind}`, { method: "POST" });
    if (!response.ok) {
      window.open(`/lab/${kind}`, `toolgate-${kind}`);
    }
  } catch {
    window.open(`/lab/${kind}`, `toolgate-${kind}`);
  }
}

function clearFlow() {
  document.querySelectorAll(".node").forEach((node) => {
    node.classList.remove(
      "is-active",
      "is-done",
      "is-allow",
      "is-deny",
      "is-skip",
      "is-thinking"
    );
  });
  document.querySelectorAll(".edge").forEach((edge) => edge.classList.remove("is-hot"));
  document.querySelectorAll(".rules span").forEach((rule) => {
    rule.classList.remove("is-checking", "is-pass", "is-fail");
  });
  packet.classList.remove("is-visible", "is-allow", "is-deny");
  packet.style.left = "18px";
  packet.style.top = "18px";
  setStatus("Idle · pick a preset and run the live agent.");
}

function activateNode(name, state = "is-active") {
  document.querySelectorAll(".node").forEach((node) => {
    node.classList.remove("is-active", "is-thinking");
  });
  const node = document.querySelector(`[data-node="${name}"]`);
  if (!node) return;
  node.classList.add(state);
  if (state === "is-active" || state === "is-thinking") node.classList.add("is-done");
}

function hotEdge(id) {
  const edge = document.querySelector(`[data-edge="${id}"]`);
  if (edge) edge.classList.add("is-hot");
}

function movePacketTo(selector, { follow = true } = {}) {
  const target = document.querySelector(selector);
  if (!target || !flowRoot) return;
  const rootBox = flowRoot.getBoundingClientRect();
  const box = target.getBoundingClientRect();
  const packetW = packet.offsetWidth || 120;
  const packetH = packet.offsetHeight || 36;
  let left = box.left - rootBox.left + flowRoot.scrollLeft + 10;
  let top = box.top - rootBox.top + flowRoot.scrollTop - packetH - 10;
  const maxLeft = Math.max(8, rootBox.width - packetW - 8);
  left = Math.min(Math.max(8, left), maxLeft);
  top = Math.max(4, top);
  packet.classList.add("is-visible");
  packet.style.left = `${left}px`;
  packet.style.top = `${top}px`;
  if (follow) followFocus(target);
}

async function animateRules(decision, activeMode) {
  const failing =
    decision?.rule_id && RULE_ORDER.includes(decision.rule_id) ? decision.rule_id : null;
  const isAllow = decision?.effect === "ALLOW";
  movePacketTo('[data-node="policy"]');

  for (const rule of RULE_ORDER) {
    const el = document.querySelector(`[data-rule="${rule}"]`);
    if (!el) continue;
    el.classList.add("is-checking");
    followFocus(el, { block: "nearest" });
    setStatus(`Policy check → ${rule}`);
    await sleep(300);
    el.classList.remove("is-checking");

    if (!isAllow && failing === rule) {
      el.classList.add("is-fail");
      setStatus(`Policy DENY at rule → ${rule}`);
      await sleep(450);
      return;
    }
    if (activeMode === "gateway") el.classList.add("is-pass");
    await sleep(120);
    if (activeMode !== "gateway") break;
  }
  if (isAllow) {
    document.querySelectorAll(".rules span").forEach((el) => el.classList.add("is-pass"));
  }
}

async function animatePipeline(current, outcome, options = {}) {
  clearFlow();
  const decision = outcome.decisions?.[0];
  const allowed = decision?.effect === "ALLOW";
  const proposal = current.proposals?.[0];
  const activeMode = outcome.mode;
  const agentName = options.agentTitle || "Catalog Agent";

  agentTitle.textContent = agentName;
  packetLabel.textContent = (proposal?.name || "TOOL CALL").toUpperCase();
  nodeEnforce.textContent = `Mode = ${activeMode}`;
  nodeDecision.textContent = "Evaluating…";
  nodeUser.textContent = `${current.principal.user_id} · ${current.principal.tenant_id} · ${current.principal.role}`;
  nodeAgent.textContent = proposal
    ? `${proposal.name}(${Object.keys(proposal.arguments || {}).join(", ")})`
    : "Proposing…";

  followFocus(flowRoot, { block: "start" });
  await sleep(250);

  activateNode("user");
  movePacketTo('[data-node="user"]');
  setStatus("Packet enters with authenticated principal");
  await sleep(500);

  hotEdge("e1");
  if (options.showThinking) {
    activateNode("agent", "is-thinking");
    movePacketTo('[data-node="agent"]');
    setStatus(`${agentName} is thinking…`);
    await sleep(options.thinkMs || 700);
  }

  activateNode("agent");
  movePacketTo('[data-node="agent"]');
  setStatus(
    proposal
      ? `Agent decided to call ${proposal.name}`
      : "Agent proposed a structured tool call"
  );
  await sleep(550);

  hotEdge("e2");
  activateNode("enforce");
  movePacketTo('[data-node="enforce"]');
  setStatus(`Enforcement mode selected: ${activeMode}`);
  await sleep(450);

  hotEdge("e3");
  activateNode("policy");
  movePacketTo('[data-node="policy"]');

  if (activeMode === "gateway") {
    await animateRules(decision, activeMode);
  } else if (activeMode === "direct") {
    setStatus("direct mode bypasses policy · always ALLOW path");
    document.querySelectorAll(".rules span").forEach((el) => el.classList.add("is-pass"));
    await sleep(400);
  } else {
    setStatus("prompt_only uses soft flag, not independent policy rules");
    await sleep(400);
  }

  hotEdge("e4");
  activateNode("decision", allowed ? "is-allow" : "is-deny");
  movePacketTo('[data-node="decision"]');
  nodeDecision.textContent = `${decision.effect} · ${decision.rule_id}`;
  packet.classList.toggle("is-allow", allowed);
  packet.classList.toggle("is-deny", !allowed);
  setStatus(`Decision = ${decision.effect} (${decision.reason})`);
  await sleep(650);

  activateNode("audit", "is-done");
  movePacketTo('[data-node="audit"]');
  nodeAudit.textContent = `${decision.effect} recorded for ${proposal?.call_id || "call"}`;
  setStatus("Audit log appends the decision");
  await sleep(550);

  if (options.stopAfterAudit) {
    await sleep(200);
    return;
  }

  await animateToolBranch(outcome, allowed);
}

async function animateToolBranch(outcome, allowed) {
  if (allowed) {
    document.querySelector('[data-node="blocked"]')?.classList.add("is-skip");
    document.querySelector('[data-node="tools"]')?.classList.remove("is-skip");
    activateNode("tools", "is-allow");
    movePacketTo('[data-node="tools"]');
    nodeTools.textContent = outcome.results?.length
      ? "Tool executed · side effects applied"
      : "ALLOW with empty tool payload";
    setStatus("Packet reaches tool runtime · side effects allowed");
  } else {
    document.querySelector('[data-node="tools"]')?.classList.add("is-skip");
    document.querySelector('[data-node="blocked"]')?.classList.remove("is-skip");
    activateNode("blocked", "is-deny");
    movePacketTo('[data-node="blocked"]');
    nodeBlocked.textContent = "Tool runtime skipped";
    setStatus("Packet blocked · no tool side effects");
  }
  await sleep(450);
}

function renderLabBriefing() {
  const preset = selectedLabPreset();
  const principal = selectedPrincipal();
  const principalMatches =
    !!preset &&
    principal.user_id === preset.principal.user_id &&
    principal.tenant_id === preset.principal.tenant_id &&
    principal.role === preset.principal.role;
  const expectDeny = preset?.kind === "attack" && principalMatches;

  briefing.classList.toggle("is-attack", !!expectDeny);
  briefKicker.textContent = preset
    ? preset.kind === "attack"
      ? "Live Lab · attack preset"
      : "Live Lab · safe preset"
    : "Live Lab";
  briefTitle.textContent = preset?.title || "Custom live task";
  briefSummary.textContent =
    !principalMatches && preset
      ? `Principal overridden to ${principal.user_id} (${principal.role}). Policy will evaluate this identity, not the preset's default.`
      : preset?.hint ||
        "Ollama proposes a real tool call; toolgate enforces policy before any side effect.";
  briefTool.textContent = "ollama → toolgate";
  briefExpect.textContent = expectDeny
    ? "Expect DENY"
    : preset?.kind === "safe"
      ? "Expect ALLOW"
      : "Expect ALLOW / decide";
  briefSteps.innerHTML = [
    "Natural-language task is sent to the project Ollama agent with native tool schemas.",
    "If the model returns no call, the preset's scripted call is sent and labeled as a fallback.",
    "toolgate runs context→schema→tenant→ownership→actions→arguments→approval.",
    "ALLOW executes SimulatedRuntime tools against the seeded store; DENY skips side effects.",
  ]
    .map((step) => `<li>${step}</li>`)
    .join("");
  if (expectDeny) {
    briefProtect.hidden = false;
    briefProtect.classList.remove("is-safe");
    briefProtectLabel.textContent = "What this live attack tries";
    briefProtectBody.textContent =
      preset.hint || "Gateway should stop the misuse before tools run.";
  } else {
    briefProtect.hidden = false;
    briefProtect.classList.add("is-safe");
    briefProtectLabel.textContent = "Live lab goal";
    briefProtectBody.textContent =
      preset?.id === "lab_safe_delete"
        ? "Admin Cara deletes rec_a2 with a matching approval token · gateway should ALLOW."
        : "Show a real open-source agent proposing tools, then prove the gateway still mediates execution.";
  }
}

function renderVerdict(outcome, extras = {}) {
  const decision = outcome.decisions?.[0];
  if (!decision) {
    verdict.className = "verdict is-idle";
    verdict.innerHTML =
      '<p class="verdict-label">Waiting</p><p class="verdict-detail">No decision returned.</p>';
    misuseCard.hidden = true;
    return;
  }
  const allowed = decision.effect === "ALLOW";
  verdict.className = `verdict ${allowed ? "is-allow" : "is-deny"}`;
  verdict.innerHTML = `
    <p class="verdict-label">${decision.effect}</p>
    <p class="verdict-detail">
      mode <strong>${outcome.mode}</strong> · rule <strong>${decision.rule_id}</strong> · ${decision.reason}
    </p>
  `;

  misuseCard.hidden = false;
  if (!allowed) {
    misuseCard.className = "misuse-card is-deny";
    misuseKicker.textContent = "Misuse blocked · what the system was saved from";
    misuseBody.textContent =
      extras.misuseNote ||
      `Denied by rule ${decision.rule_id}: ${decision.reason}. Tool side effects were skipped.`;
  } else {
    misuseCard.className = "misuse-card is-allow";
    misuseKicker.textContent = "Allowed · live tool execution completed";
    misuseBody.textContent =
      extras.whySafe ||
      "Policy checks passed; SimulatedRuntime applied side effects to the project store.";
  }

  agentOut.textContent = extras.agentPayload
    ? JSON.stringify(extras.agentPayload, null, 2)
    : JSON.stringify(
        {
          principal: extras.principal || null,
          proposal: extras.proposal || null,
        },
        null,
        2
      );

  decisionOut.textContent = JSON.stringify(
    {
      decisions: outcome.decisions,
      executed_call_ids: outcome.executed_call_ids,
      decision_latency_ms: outcome.decision_latency_ms,
      tool_latency_ms: outcome.tool_latency_ms,
    },
    null,
    2
  );

  resultOut.textContent = JSON.stringify(
    {
      results: outcome.results,
      store_snapshot: extras.storeSnapshot || null,
    },
    null,
    2
  );
}

function renderAudit(rows) {
  if (!rows.length) {
    auditList.innerHTML = '<p class="hint">Audit log is empty.</p>';
    return;
  }
  auditList.innerHTML = rows
    .slice()
    .reverse()
    .map(
      (row) => `
      <div class="audit-item">
        <span class="pill ${row.effect === "ALLOW" ? "allow" : "deny"}">${row.effect}</span>
        <div>
          <div>${row.tool_name} · ${row.reason}</div>
          <div class="muted">${row.call_id} · rule ${row.rule_id}</div>
        </div>
        <span class="muted">${row.user_id}</span>
      </div>
    `
    )
    .join("");
}

function selectedLabPreset() {
  const id = labPreset.value;
  return (labStatus?.presets || []).find((p) => p.id === id) || null;
}

function applyLabPreset() {
  const preset = selectedLabPreset();
  if (!preset) return;
  labTask.value = preset.task;
  labHint.textContent = preset.hint || "";
  const match = (labStatus?.principals || []).find(
    (item) => item.user_id === preset.principal.user_id
  );
  if (match) labPrincipal.value = match.user_id;
  renderLabBriefing();
}

function selectedPrincipal() {
  const userId = labPrincipal.value;
  return (labStatus?.principals || []).find((item) => item.user_id === userId) || {
    user_id: userId,
    tenant_id: "",
    role: "",
  };
}

async function loadLabStatus(options = {}) {
  const preserve = options.preserve === true;
  const presetId = labPreset.value;
  const principalValue = labPrincipal.value;
  const taskText = labTask.value;

  const response = await fetch("/lab/status");
  if (!response.ok) throw new Error("Failed to load lab status");
  labStatus = await response.json();
  labPill.classList.toggle("is-ok", !!labStatus.ollama_ok);
  labPill.classList.toggle("is-bad", !labStatus.ollama_ok);
  labPillText.textContent = labStatus.ollama_ok
    ? `Ollama ready · ${labStatus.preferred_model}`
    : `Ollama offline · ${labStatus.error || "start ollama serve"}`;
  labModelHint.textContent = labStatus.ollama_ok
    ? `Model: ${labStatus.preferred_model} · tools: ${(labStatus.tools || []).length}`
    : "Model unavailable · presets fall back to a scripted tool call so the gateway can still decide.";

  labPreset.innerHTML = (labStatus.presets || [])
    .map(
      (p) =>
        `<option value="${p.id}">${p.title} (${p.kind})</option>`
    )
    .join("");
  labPrincipal.innerHTML = (labStatus.principals || [])
    .map(
      (p) =>
        `<option value="${p.user_id}">${p.user_id} · ${p.role} · ${p.tenant_id}</option>`
    )
    .join("");
  if (preserve && [...labPreset.options].some((opt) => opt.value === presetId)) {
    labPreset.value = presetId;
  }
  applyLabPreset();
  if (!preserve) return;
  if ([...labPrincipal.options].some((opt) => opt.value === principalValue)) {
    labPrincipal.value = principalValue;
  }
  labTask.value = taskText;
  renderLabBriefing();
}

async function loadAudit() {
  const response = await fetch("/audit");
  if (!response.ok) throw new Error("Failed to load audit");
  renderAudit(await response.json());
}

async function runLiveLab() {
  if (animating) return;
  animating = true;
  labRunBtn.disabled = true;
  try {
    const preset = selectedLabPreset();
    const runId = `lab_${Math.random().toString(16).slice(2, 12)}`;

    followFocus(flowRoot, { block: "start" });
    clearFlow();

    setStatus("Reseeding store for a clean live run…");
    await fetch("/reset", { method: "POST" });
    await sleep(200);
    const sessionRes = await fetch("/lab/session", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: selectedPrincipal().user_id }),
    });
    if (!sessionRes.ok) throw new Error("Could not open a session for this principal");
    const session = await sessionRes.json();
    const body = {
      run_id: runId,
      task: labTask.value.trim(),
      access_token: session.session_id,
      mode: labMode,
      model: labStatus?.preferred_model || null,
      preset_id: preset?.id || null,
      allow_fallback: true,
    };
    const authHeaders = {
      "Content-Type": "application/json",
      Authorization: `Bearer ${session.session_id}`,
    };

    // 1) Always relaunch: close both, then open Agent for thinking.
    setStatus("Relaunching desktops · closing previous Agent/Tools…");
    await desktopClose();
    await sleep(800);

    setStatus("LLM thinking · launching Agent window…");
    activateNode("agent", "is-thinking");
    nodeAgent.textContent = "Ollama thinking…";
    agentTitle.textContent = "Ollama Agent";
    movePacketTo('[data-node="agent"]');
    await desktopOpen("agent");
    await sleep(350);

    const thinkRes = await fetch("/lab/thinking", {
      method: "POST",
      headers: authHeaders,
      body: JSON.stringify(body),
    });
    if (!thinkRes.ok) throw new Error((await thinkRes.text()) || "Failed to start thinking");
    await sleep(700);

    // 2) Ask Ollama · Agent window stays on thinking until propose returns.
    setStatus("Agent is deciding which tool to call…");
    const proposeRes = await fetch("/lab/propose", {
      method: "POST",
      headers: authHeaders,
      body: JSON.stringify(body),
    });
    if (!proposeRes.ok) throw new Error((await proposeRes.text()) || "Propose failed");
    const proposed = await proposeRes.json();
    const proposal = proposed.proposals?.[0];
    const rejected = proposed.rejected || [];
    const shown = proposal || rejected[0];

    nodeAgent.textContent = shown
      ? `${shown.name}(${Object.keys(shown.arguments || {}).join(", ")})`
      : "No tool proposal";
    setStatus(
      proposal
        ? proposed.agent_backend === "fallback"
          ? `Preset scripted call ${proposal.name} · the model did not return a call`
          : `Model proposed ${proposal.name}`
        : rejected.length
          ? `Model returned ${rejected[0].name || "a call"} · the gateway will judge the raw payload`
          : "Agent finished proposing"
    );
    // Let Agent desktop play decided → calling animation.
    await sleep(1600);

    // 3) Enforce now, but keep Tools desktop closed and status=evaluating
    //    until the gateway workflow animation finishes.
    setStatus("Gateway evaluating tool call on the workflow…");
    const enforceRes = await fetch("/lab/enforce", {
      method: "POST",
      headers: authHeaders,
      body: JSON.stringify({
        run_id: proposed.run_id,
        task: proposed.task,
        access_token: session.session_id,
        principal: proposed.principal,
        mode: labMode,
        proposals: proposed.proposals,
        rejected,
        agent_backend: proposed.agent_backend,
        model: proposed.model,
        preset_id: preset?.id || null,
        agent_raw: proposed.agent_raw,
        events: proposed.events,
        reveal: false,
      }),
    });
    if (!enforceRes.ok) throw new Error((await enforceRes.text()) || "Enforce failed");
    const lab = await enforceRes.json();

    const synthetic = {
      case_id: lab.run_id,
      label: preset?.kind === "attack" ? "attack" : "legitimate",
      threat_id: preset?.kind === "attack" ? "lab_live" : null,
      task: lab.task,
      principal: lab.principal,
      proposals: lab.proposals?.length ? lab.proposals : rejected,
      prompt_only_would_execute: true,
    };

    // 4) Play gateway packet animation first (through audit).
    await animatePipeline(synthetic, lab.outcome, {
      agentTitle:
        lab.agent_backend === "ollama"
          ? `Ollama · ${lab.model}`
          : `Fallback · ${lab.model}`,
      showThinking: false,
      stopAfterAudit: true,
    });

    // 5) Reveal decision to Agent; open Tools only on ALLOW.
    const allowed = lab.outcome?.decisions?.[0]?.effect === "ALLOW";
    if (allowed) {
      setStatus("Opening Tools window · gateway ALLOW…");
      await desktopOpen("tools");
      await sleep(700);
    } else {
      setStatus("Gateway DENY · Tools window stays closed (no side effects).");
    }
    await fetch("/lab/reveal", { method: "POST" });
    await sleep(allowed ? 900 : 500);

    await animateToolBranch(lab.outcome, allowed);

    renderVerdict(lab.outcome, {
      principal: lab.principal,
      proposal: lab.proposals?.[0] || rejected[0],
      agentPayload: {
        backend: lab.agent_backend,
        model: lab.model,
        task: lab.task,
        raw: lab.agent_raw,
        proposals: lab.proposals,
      },
      storeSnapshot: lab.store_snapshot,
      misuseNote: lab.misuse_note,
      whySafe:
        lab.agent_backend === "ollama"
          ? "Live Ollama proposal passed gateway checks; tools ran against the seeded store."
          : "Preset fallback proposal was gated by toolgate (Ollama did not return a usable call).",
    });
    await loadAudit();
    await sleep(200);
    followFocus(misuseCard.hidden ? verdict : misuseCard, { block: "center" });
  } catch (error) {
    clearFlow();
    verdict.className = "verdict is-deny";
    verdict.innerHTML = `<p class="verdict-label">Lab error</p><p class="verdict-detail">${error.message}</p>`;
    setStatus(error.message);
  } finally {
    animating = false;
    labRunBtn.disabled = false;
  }
}

async function resetStore() {
  if (animating) return;
  await fetch("/reset", { method: "POST" });
  await desktopClose();
  clearFlow();
  verdict.className = "verdict is-idle";
  verdict.innerHTML =
    '<p class="verdict-label">Waiting</p><p class="verdict-detail">The packet has not entered the pipeline yet.</p>';
  misuseCard.hidden = true;
  decisionOut.textContent = "·";
  resultOut.textContent = "·";
  agentOut.textContent = "·";
  nodeDecision.textContent = "ALLOW / DENY";
  nodeAudit.textContent = "Record every decision";
  nodeTools.textContent = "Execute only on ALLOW";
  nodeBlocked.textContent = "No side effects";
  renderLabBriefing();
  await loadAudit();
  await loadLabStatus({ preserve: true });
}

document.querySelectorAll(".lab-mode").forEach((btn) => {
  btn.addEventListener("click", () => setMode(btn.dataset.mode));
});
labPreset.addEventListener("change", applyLabPreset);
labPrincipal.addEventListener("change", renderLabBriefing);
labRunBtn.addEventListener("click", runLiveLab);
labResetBtn.addEventListener("click", resetStore);
window.addEventListener("resize", () => {
  if (packet.classList.contains("is-visible")) {
    const active = document.querySelector(
      ".node.is-active, .node.is-allow, .node.is-deny, .node.is-thinking"
    );
    if (active) movePacketTo(`[data-node="${active.dataset.node}"]`, { follow: false });
  }
});

Promise.all([loadLabStatus(), loadAudit()])
  .then(() => {
    agentTitle.textContent = "Ollama Agent";
    renderLabBriefing();
    setMode(labMode);
  })
  .catch((error) => {
    labPill.classList.add("is-bad");
    labPillText.textContent = error.message;
  });
