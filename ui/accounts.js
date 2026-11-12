/* Token Center status only. No cmSessions subscription and no invented balance.
   The sessions page already posts verbs to /api/run as { action }. */
(function () {
  var BRIDGE = "csm_core.tokenctr_bridge";
  var SECRET = /sk-ant-|sk-[A-Za-z0-9_\-]{20,}|xai-[A-Za-z0-9_\-]{8,}|gh[pousr]_|xox[baprs]-|AIza[0-9A-Za-z_\-]{10,}|AKIA[0-9A-Z]{16}|\bbearer\s+\S+|api[_-]?key|password|passwd|client[_-]?secret/i;
  var generation = 0;

  function $(id) { return document.getElementById(id); }

  function safeText(value) {
    if (value == null || typeof value === "object") return "";
    var text = String(value).replace(/\s+/g, " ").trim();
    if (!text || text.length > 240) return "";
    if (SECRET.test(text)) return "";
    return text;
  }

  window.cmAccountStatus = function () {
    return {
      available: false,
      status: "unavailable",
      kind: "UNAVAILABLE",
      verb: "account_status",
      source: "token-center",
      bridge: BRIDGE,
      reason: BRIDGE + " is missing",
      detail: "Token Center status is unavailable. There is no cmSessions subscription. No balance is shown.",
      subscription: null,
      balance: null,
      burn_today: null
    };
  };

  function gateOf(rec) {
    if (!rec || typeof rec !== "object" || !rec.gate || typeof rec.gate !== "object") return {};
    return rec.gate;
  }

  function bridgeMissing(rec) {
    var gate = gateOf(rec);
    var kind = String(rec.kind || gate.kind || "").toUpperCase();
    if (rec.available === false || gate.available === false) return true;
    if (rec.status === "unavailable" || gate.status === "unavailable") return true;
    if (kind === "UNAVAILABLE" || kind === "MISSING" || kind === "UNMEASURED" || kind === "BAD_ACTION") return true;
    var parts = [rec.bridge, rec.module, rec.detail, rec.reason, rec.error, gate.bridge, gate.module, gate.detail, gate.reason];
    var i;
    for (i = 0; i < parts.length; i += 1) {
      var text = String(parts[i] || "");
      if (/tokenctr_bridge/i.test(text) && /missing|unavailable|absent|not found|not available/i.test(text)) return true;
    }
    return false;
  }

  function readAmount(sources, keys) {
    var s, k, value;
    for (s = 0; s < sources.length; s += 1) {
      if (!sources[s] || typeof sources[s] !== "object") continue;
      for (k = 0; k < keys.length; k += 1) {
        value = sources[s][keys[k]];
        if (typeof value === "number" && isFinite(value)) return value;
        if (typeof value === "string" && /^-?\d+(\.\d+)?$/.test(value.trim())) return value.trim();
      }
    }
    return null;
  }

  function readIdentity(sources) {
    var keys = ["display_name", "identity", "account_name", "name", "handle", "user"];
    var s, k, text;
    for (s = 0; s < sources.length; s += 1) {
      if (!sources[s] || typeof sources[s] !== "object") continue;
      for (k = 0; k < keys.length; k += 1) {
        text = safeText(sources[s][keys[k]]);
        if (text) return text;
      }
    }
    return "";
  }

  function formatAmount(value) {
    if (value == null) return "Not reported";
    if (typeof value === "number") return value.toLocaleString();
    return String(value);
  }

  function ensureStatePanels() {
    var root = $("account-root");
    var anchor = $("panel-status");
    if (!root) return;
    if (!$("panel-empty")) {
      var empty = document.createElement("section");
      empty.id = "panel-empty";
      empty.className = "panel empty";
      empty.hidden = true;
      empty.setAttribute("role", "status");
      empty.setAttribute("aria-live", "polite");
      empty.innerHTML = "<h2>No account yet</h2><p id=\"empty-detail\"></p>";
      if (anchor) root.insertBefore(empty, anchor);
      else root.appendChild(empty);
    }
    if (!$("panel-error")) {
      var failed = document.createElement("section");
      failed.id = "panel-error";
      failed.className = "panel error";
      failed.hidden = true;
      failed.setAttribute("role", "alert");
      failed.innerHTML = "<h2>Account status failed</h2><p id=\"error-detail\"></p>";
      if (anchor) root.insertBefore(failed, anchor);
      else root.appendChild(failed);
    }
  }

  function setMode(mode) {
    ensureStatePanels();
    var root = $("account-root");
    var panels = {
      loading: $("panel-loading"),
      unavailable: $("panel-unavailable"),
      empty: $("panel-empty"),
      error: $("panel-error"),
      ready: $("panel-status")
    };
    var key;
    for (key in panels) {
      if (panels[key]) panels[key].hidden = key !== mode;
    }
    if (root) root.setAttribute("aria-busy", mode === "loading" ? "true" : "false");
    var button = $("account-refresh");
    if (button) button.disabled = mode === "loading";
  }

  function actionableError(rec) {
    if (rec && rec.error === "network") {
      return "Token Center did not answer. Check that it is running, then refresh.";
    }
    if (rec && rec.error === "bad-body") {
      return "The account reply could not be read. Refresh to try again.";
    }
    return "Token Center could not load the account. Refresh to try again.";
  }

  function accountIsEmpty(rec) {
    var gate = gateOf(rec);
    var sources = [gate, rec];
    var status = String(rec.status || gate.status || "").toLowerCase();
    var kind = String(rec.kind || gate.kind || "").toUpperCase();
    if (readIdentity(sources)) return status === "empty" || kind === "EMPTY";
    if (readAmount(sources, ["balance", "token_balance", "tokens_remaining", "remaining"]) != null) return false;
    if (readAmount(sources, ["burn_today", "spent_today", "today_burn"]) != null) return false;
    return true;
  }

  function showUnavailable(rec) {
    var reason = safeText(rec && rec.reason) || (BRIDGE + " is missing");
    var detail = safeText(rec && rec.detail) || "Token Center status is unavailable. No balance is shown.";
    var reasonNode = $("unavailable-reason");
    var detailNode = $("unavailable-detail");
    if (reasonNode) reasonNode.textContent = reason;
    if (detailNode) detailNode.textContent = detail;
    var bridge = $("unavailable-bridge");
    if (bridge) bridge.textContent = BRIDGE;
    setMode("unavailable");
  }

  function showEmpty() {
    var detail = $("empty-detail");
    if (detail) {
      detail.textContent = "No Token Center account is connected. Sign in there if you want a balance, then refresh. Nothing is filled in here.";
    }
    setMode("empty");
  }

  function showError(rec) {
    var detail = $("error-detail");
    if (detail) detail.textContent = actionableError(rec);
    setMode("error");
  }

  function showReady(rec) {
    var gate = gateOf(rec);
    var sources = [gate, rec];
    var identity = readIdentity(sources);
    var balance = readAmount(sources, ["balance", "token_balance", "tokens_remaining", "remaining"]);
    var burn = readAmount(sources, ["burn_today", "spent_today", "today_burn"]);
    var note = safeText(gate.note || rec.note);
    $("status-identity").textContent = identity || "Not reported";
    $("status-balance").textContent = formatAmount(balance);
    $("status-burn").textContent = formatAmount(burn);
    $("status-bridge").textContent = safeText(gate.bridge || rec.bridge) || BRIDGE;
    $("status-note").textContent = note || "Token Center reported this status. There is no cmSessions subscription.";
    setMode("ready");
  }

  function paint(rec) {
    if (!rec || typeof rec !== "object" || Array.isArray(rec)) {
      showError({ error: "bad-body" });
      return;
    }
    if (bridgeMissing(rec)) {
      showUnavailable(rec.status === "unavailable" ? rec : window.cmAccountStatus());
      return;
    }
    if (rec.status === "error" || rec.error) {
      showError(rec);
      return;
    }
    var verb = String(rec.verb || rec.action || "");
    var kind = String(rec.kind || gateOf(rec).kind || "").toUpperCase();
    var status = String(rec.status || gateOf(rec).status || "").toLowerCase();
    if (kind === "EMPTY" || status === "empty") {
      showEmpty();
      return;
    }
    if (verb !== "account_status" || (kind && kind !== "OK")) {
      showUnavailable(window.cmAccountStatus());
      return;
    }
    if (accountIsEmpty(rec)) {
      showEmpty();
      return;
    }
    showReady(rec);
  }

  function requestAccountStatus() {
    var mine = ++generation;
    setMode("loading");
    var pending;
    if (typeof fetch !== "function") {
      pending = Promise.resolve(window.cmAccountStatus());
    } else {
      pending = fetch("/api/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action: "account_status", verb: "account_status" })
      }).then(function (res) {
        return res.json().then(function (rec) {
          if (!rec || typeof rec !== "object" || Array.isArray(rec)) {
            return { status: "error", error: "bad-body", balance: null, burn_today: null };
          }
          if (bridgeMissing(rec)) return rec;
          if (!res.ok || rec.error) {
            return { status: "error", error: "http", balance: null, burn_today: null };
          }
          return rec;
        }, function () {
          return { status: "error", error: "bad-body", balance: null, burn_today: null };
        });
      }, function () {
        return { status: "error", error: "network", balance: null, burn_today: null };
      });
    }
    pending.then(function (rec) {
      if (mine !== generation) return;
      paint(rec);
    });
  }

  function boot() {
    var button = $("account-refresh");
    if (!button) return;
    button.addEventListener("click", requestAccountStatus);
    requestAccountStatus();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
