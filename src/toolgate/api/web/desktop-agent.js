const pill = document.getElementById("pill");
const runtime = document.getElementById("runtime");
const task = document.getElementById("task");
const principal = document.getElementById("principal");
const proposal = document.getElementById("proposal");
const proposalCard = document.getElementById("proposalCard");
const raw = document.getElementById("raw");
const stageBanner = document.getElementById("stageBanner");
const stageTitle = document.getElementById("stageTitle");
const stageSub = document.getElementById("stageSub");

let lastFingerprint = null;
let animToken = 0;
let callingPlayedFor = null;
let settledFor = null;
let stageLock = null;

async function refreshStatus() {
  try {
    const status = await fetch("/lab/status").then((r) => r.json());
    runtime.textContent = status.ollama_ok
      ? `Ollama online · ${status.preferred_model}`
      : `Ollama offline · ${status.error || "start ollama"}`;
  } catch (error) {
    runtime.textContent = error.message;
  }
}

function fingerprint(data) {
  if (!data || !data.run_id) return null;
  const effect = data.outcome?.decisions?.[0]?.effect || "";
  return [data.run_id, data.status || "", effect, data.agent_backend || ""].join("|");
}

function setStage(phase, title, sub) {
  stageBanner.className = `stage-banner is-${phase}`;
  stageTitle.textContent = title;
  stageSub.textContent = sub;
}

function popProposal() {
  proposalCard.classList.remove("pop");
  void proposalCard.offsetWidth;
  proposalCard.classList.add("pop");
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function fillCommon(data) {
  task.textContent = data.task || "·";
  principal.textContent = JSON.stringify(data.principal || {}, null, 2);
  raw.textContent =
    data.agent_raw && Object.keys(data.agent_raw).length
      ? JSON.stringify(data.agent_raw, null, 2)
      : "·";
}

async function playCallingAnimation(data) {
  const token = ++animToken;
  const call = (data.proposals || [])[0];
  callingPlayedFor = data.run_id;
  proposalCard.classList.remove("is-allow", "is-deny");
  pill.className = "status-pill is-ok";
  pill.textContent =
    data.agent_backend === "ollama"
      ? `proposed · ${data.model}`
      : `fallback · ${data.model}`;

  const fallback = data.agent_backend === "fallback";
  setStage(
    "decided",
    fallback ? "Preset call submitted" : "Agent decided to call a tool",
    fallback
      ? "Ollama did not return a tool call. The preset's scripted call was sent to the gateway."
      : call
        ? `Selected ${call.name}`
        : "Selected a tool call"
  );
  proposal.textContent = call
    ? JSON.stringify(
        {
          decision: "use_tool",
          tool: call.name,
          arguments: call.arguments,
        },
        null,
        2
      )
    : "[]";
  popProposal();
  await sleep(900);
  if (token !== animToken) return;

  // Evaluating or a final decision arrived while the calling beat was playing.
  if (settledFor === data.run_id || stageLock === data.run_id) return;

  setStage(
    "calling",
    "Calling tool…",
    call
      ? `Invoking ${call.name} through toolgate`
      : "Handing the call to toolgate"
  );
  proposal.textContent = call
    ? JSON.stringify(
        {
          action: "calling_tool",
          tool: call.name,
          arguments: call.arguments,
          call_id: call.call_id,
        },
        null,
        2
      )
    : "[]";
  popProposal();
}

function renderOutcome(data) {
  const call = (data.proposals || [])[0];
  const decision = data.outcome?.decisions?.[0];
  const allowed = decision?.effect === "ALLOW";
  settledFor = data.run_id;
  stageLock = data.run_id;
  animToken += 1;

  proposalCard.classList.toggle("is-allow", !!allowed);
  proposalCard.classList.toggle("is-deny", !allowed);
  pill.className = `status-pill ${allowed ? "is-ok" : "is-deny"}`;
  pill.textContent = allowed
    ? `allowed · ${data.model || "gateway"}`
    : `denied · ${decision?.rule_id || "policy"}`;

  const fallback = data.agent_backend === "fallback";
  const source = fallback
    ? "Preset scripted call"
    : "Model proposal";
  if (allowed) {
    setStage(
      "allow",
      "Tool call allowed",
      call
        ? `${source} · gateway ALLOW · ${call.name} may execute`
        : `${source} · gateway ALLOW · tool may execute`
    );
  } else {
    setStage(
      "deny",
      "Tool call denied",
      decision
        ? `${source} · gateway DENY · ${decision.rule_id} · ${decision.reason}`
        : `${source} · gateway DENY · tool runtime skipped`
    );
  }

  proposal.textContent = JSON.stringify(
    {
      action: allowed ? "tool_allowed" : "tool_denied",
      tool: call?.name || null,
      arguments: call?.arguments || null,
      call_id: call?.call_id || null,
      gateway: decision
        ? {
            effect: decision.effect,
            rule_id: decision.rule_id,
            reason: decision.reason,
          }
        : null,
    },
    null,
    2
  );
  popProposal();
}

function renderEvaluating(data) {
  const call = (data.proposals || [])[0];
  stageLock = data.run_id;
  pill.className = "status-pill is-thinking pulse";
  pill.textContent = "awaiting gateway";
  proposalCard.classList.remove("is-allow", "is-deny");
  setStage(
    "calling",
    "Waiting on toolgate…",
    call
      ? `Gateway is checking policy for ${call.name}`
      : "Gateway is checking policy"
  );
  if (call) {
    proposal.textContent = JSON.stringify(
      {
        action: "submitted_to_gateway",
        tool: call.name,
        arguments: call.arguments,
        call_id: call.call_id,
      },
      null,
      2
    );
  }
}

function renderLatest(data) {
  if (!data || !data.run_id) return;
  const fp = fingerprint(data);
  if (fp === lastFingerprint) return;
  lastFingerprint = fp;

  const status = data.status || "done";
  fillCommon(data);

  if (status === "thinking") {
    animToken += 1;
    callingPlayedFor = null;
    settledFor = null;
    stageLock = null;
    proposalCard.classList.remove("is-allow", "is-deny");
    pill.className = "status-pill is-thinking pulse";
    pill.textContent = `thinking · ${data.model || "ollama"}`;
    setStage(
      "thinking",
      "LLM is thinking…",
      "Ollama is choosing which tool to call for this task."
    );
    proposal.textContent = "Awaiting tool decision…";
    return;
  }

  if (status === "error") {
    animToken += 1;
    settledFor = data.run_id;
    pill.className = "status-pill is-deny";
    pill.textContent = "error";
    setStage("deny", "Agent error", data.error || "The live agent failed.");
    proposal.textContent = data.error || "Agent error";
    return;
  }

  // Final gateway decision · always win over "Calling tool…".
  if (status === "done" && data.outcome?.decisions?.[0]) {
    renderOutcome(data);
    return;
  }

  // Gateway is already deciding. Do not start (or restart) the calling beat.
  if (status === "evaluating") {
    renderEvaluating(data);
    return;
  }

  if (status === "calling" && (data.proposals || []).length && callingPlayedFor !== data.run_id) {
    playCallingAnimation(data);
  }
}

async function poll() {
  try {
    const data = await fetch("/lab/latest").then((r) => r.json());
    renderLatest(data);
  } catch {
    /* ignore */
  }
}

refreshStatus();
poll();
setInterval(refreshStatus, 5000);
setInterval(poll, 400);
