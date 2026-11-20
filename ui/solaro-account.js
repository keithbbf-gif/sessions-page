/* <solaro-account> — shared Shadow DOM account panel.
   Zero dependencies. No style bleed. No payment-detail fields.
   Mount: <script src="solaro-account.js"></script>
          <solaro-account mode="local" endpoint="/api/run" app-name="SolaroLabs"></solaro-account>
   Web:   <solaro-account mode="web" endpoint="https://api.tokenctr.com/v1" app-name="SolaroLabs"></solaro-account>
   Themes set --solaro-bg, --solaro-surface, --solaro-accent, --solaro-text on the host. */
(function () {
  "use strict";

  var TABS = ["account", "usage", "logs", "billing", "settings", "keys", "models"];
  var DECLINE_KEY = "solaro.decline";
  var PROMISES = [
    "essentials free forever",
    "toll-free under $100/mo",
    "provider discounts pass at full value",
    "data opt-in, anonymized, never sold"
  ];
  var HARNESSES = ["grok", "claude", "codex", "gemini", "cursor", "hermes"];
  var AXES = ["coding", "agentic", "long_context"];
  var MDATA_BOARD = "https://mdata.modelraters.com/v1/leaderboard.json";
  var AUTO_DEFAULT = false;

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function money(n) {
    var x = Number(n);
    if (!isFinite(x)) return "—";
    return "$" + x.toFixed(4);
  }

  function badge(prov) {
    var p = prov || "estimate";
    if (p !== "estimate" && p !== "measured" && p !== "billed") p = "estimate";
    return '<span class="badge ' + esc(p) + '">' + esc(p) + "</span>";
  }

  function declined() {
    try {
      return window.localStorage.getItem(DECLINE_KEY) === "1";
    } catch (err) {
      return false;
    }
  }

  function setDeclined(on) {
    try {
      if (on) window.localStorage.setItem(DECLINE_KEY, "1");
      else window.localStorage.removeItem(DECLINE_KEY);
    } catch (err) {
      return;
    }
  }

  function cmToken() {
    var meta = document.querySelector('meta[name="cm-token"]');
    if (!meta) return "";
    return meta.getAttribute("content") || "";
  }

  function joinUrl(base, path) {
    var b = String(base || "");
    var p = String(path || "");
    if (!p || p.indexOf("://") !== -1 || p.indexOf("//") === 0) return "";
    if (b.charAt(b.length - 1) === "/") b = b.slice(0, -1);
    if (p.charAt(0) !== "/") p = "/" + p;
    return b + p;
  }

  function readBody(res) {
    return res.text().then(function (text) {
      var data = {};
      try {
        data = text ? JSON.parse(text) : {};
      } catch (err) {
        data = {};
      }
      if (!data || typeof data !== "object") data = {};
      data._status = res.status;
      return data;
    });
  }

  function request(el, path, opts) {
    opts = opts || {};
    var mode = String(el.getAttribute("mode") || "local").toLowerCase();
    var endpoint = el.getAttribute("endpoint");
    if (!endpoint) {
      endpoint = mode === "web" ? "https://api.tokenctr.com/v1" : "/api/run";
    }
    if (/^\s*javascript:/i.test(endpoint)) {
      return Promise.reject(new Error("refused"));
    }
    var method = String(opts.method || "GET").toUpperCase();
    if (mode === "local") {
      var headers = { "Accept": "application/json", "Content-Type": "application/json" };
      var token = cmToken();
      if (token) headers["X-CM-Token"] = token;
      return fetch(endpoint, {
        method: "POST",
        headers: headers,
        body: JSON.stringify({ path: path, method: method, body: opts.body || null })
      }).then(readBody);
    }
    var suffix = path;
    if (/\/v1$/i.test(String(endpoint).replace(/\/+$/, "")) && suffix.indexOf("/v1/") === 0) {
      suffix = suffix.slice(3);
    }
    var url = joinUrl(endpoint, suffix);
    if (!url) return Promise.reject(new Error("refused"));
    var webHeaders = { "Accept": "application/json" };
    if (method === "POST") webHeaders["Content-Type"] = "application/json";
    return fetch(url, {
      method: method,
      headers: webHeaders,
      body: method === "POST" ? JSON.stringify(opts.body || {}) : undefined
    }).then(readBody);
  }

  function last4(value) {
    var text = String(value || "");
    if (text.length < 8) return null;
    return text.slice(-4);
  }

  var CSS = [
    ":host {",
    "  background: var(--solaro-bg, #0e141b);",
    "  color: var(--solaro-text, #d7e0ea);",
    "  accent-color: var(--solaro-accent, #8fd6ff);",
    "  outline-color: var(--solaro-surface, #121a22);",
    "  display: block;",
    "  box-sizing: border-box;",
    "  font-family: Consolas, \"Courier New\", monospace;",
    "  font-size: 13px;",
    "  border: 1px solid #243140;",
    "  padding: 12px 14px 16px;",
    "}",
    ":host * { box-sizing: border-box; }",
    "h2 { margin: 0 0 8px; font-size: 13px; letter-spacing: 0.08em; font-weight: 600; color: var(--solaro-accent, #8fd6ff); }",
    ".row { display: flex; flex-wrap: wrap; gap: 8px; margin: 8px 0; }",
    ".tile { background: var(--solaro-surface, #121a22); border: 1px solid #2a3a4a; padding: 8px 10px; min-width: 140px; flex: 1 1 160px; }",
    ".tile b { color: #e8eef4; font-weight: 600; }",
    ".muted { color: #8ea0b3; }",
    "button, select, input { font: inherit; color: #e8eef4; background: #1a2733; border: 1px solid #3a5166; padding: 4px 8px; }",
    "button { cursor: pointer; }",
    "button:disabled { opacity: 0.45; cursor: default; }",
    "button[aria-current=\"true\"] { border-color: var(--solaro-accent, #8fd6ff); color: var(--solaro-accent, #8fd6ff); }",
    "button.danger { border-color: #8a3a3a; color: #ffb4b4; }",
    "table { width: 100%; border-collapse: collapse; margin-top: 6px; }",
    "th, td { text-align: left; padding: 3px 6px; border-bottom: 1px solid #243140; vertical-align: top; }",
    ".badge { display: inline-block; padding: 0 6px; border: 1px solid #3a5166; font-size: 11px; }",
    ".badge.estimate { color: #c5cdd6; }",
    ".badge.measured { color: #9dffb0; border-color: #2f6b45; }",
    ".badge.billed { color: #9fd4ff; border-color: #2a5570; }",
    ".err { color: #ffb4b4; }",
    ".ok { color: #9dffb0; }",
    ".promises { color: #8ea0b3; font-size: 12px; margin: 8px 0; padding-left: 18px; }",
    ".once { font-family: Consolas, monospace; background: #0b1016; padding: 6px 8px; border: 1px dashed #3a5166; word-break: break-all; }",
    "nav { display: flex; flex-wrap: wrap; gap: 6px; margin: 8px 0 12px; }"
  ].join("\n");

  function navHtml(current) {
    var buttons = [
      '<button type="button" data-tab="account" aria-current="false">account</button>',
      '<button type="button" data-tab="usage" aria-current="false">usage</button>',
      '<button type="button" data-tab="logs" aria-current="false">logs</button>',
      '<button type="button" data-tab="billing" aria-current="false">billing</button>',
      '<button type="button" data-tab="settings" aria-current="false">settings</button>',
      '<button type="button" data-tab="keys" aria-current="false">keys</button>',
      '<button type="button" data-tab="models" aria-current="false">models</button>'
    ];
    return buttons.map(function (html, index) {
      if (TABS[index] === current) return html.replace('aria-current="false"', 'aria-current="true"');
      return html;
    }).join("");
  }

  function promiseList() {
    return "<ul class=\"promises\">" + PROMISES.map(function (item) {
      return "<li>" + esc(item) + "</li>";
    }).join("") + "</ul>";
  }

  function shell(appName) {
    return "<style>" + CSS + "</style>" +
      "<h2>" + esc(appName || "SolaroLabs") + "</h2>" +
      "<nav class=\"tc-nav\">" + navHtml("account") + "</nav>" +
      "<section id=\"view\"></section>";
  }

  function paintAccount(state) {
    var plan = state.localOnly ? "local" : (state.plan || "local");
    var skip = state.localOnly
      ? '<p class="muted">Skip remembered. Connect stays optional.</p>'
      : '<button type="button" data-action="skip">Skip — local only</button>';
    return '<div class="row">' +
      '<div class="tile"><div class="muted">plan</div><b>' + esc(plan) + "</b></div>" +
      '<div class="tile"><div class="muted">credits</div><b>' + money(state.credits) + " " + badge("estimate") + "</b></div>" +
      '<div class="tile"><div class="muted">app</div><b>' + esc(state.appName) + "</b></div>" +
      "</div>" +
      promiseList() +
      '<p class="muted">Essentials stay free. The core never gates. Connect is optional.</p>' +
      '<div class="row"><button type="button" data-action="connect">Connect</button>' + skip + "</div>" +
      '<div id="msg" class="muted"></div>';
  }

  function paintUsage(usage) {
    usage = usage || {};
    var rows = (usage.rollup || []).map(function (row) {
      return "<tr><td>" + esc(row.lane) + "</td><td>" + esc(row.model) + "</td><td>" + esc(row.runs) +
        "</td><td>" + money(row.measured_usd) + " " + badge(row.provenance || "measured") + "</td></tr>";
    }).join("");
    var prov = usage._live ? "measured" : "estimate";
    return '<div class="row">' +
      '<div class="tile"><div class="muted">free used today</div><b>' + money(usage.free_used_face_usd) + " " + badge(prov) + "</b></div>" +
      '<div class="tile"><div class="muted">free quota</div><b>' + money(usage.free_quota_face_usd) + " " + badge(prov) + "</b></div>" +
      '<div class="tile"><div class="muted">credits</div><b>' + money(usage.credits_face_usd) + " " + badge(prov) + "</b></div>" +
      "</div>" +
      '<div class="row"><button type="button" data-action="period" data-period="today">Today</button>' +
      '<button type="button" data-action="period" data-period="month">This month</button></div>' +
      "<table><thead><tr><th>lane</th><th>model</th><th>runs</th><th>measured</th></tr></thead><tbody>" +
      (rows || '<tr><td colspan="4" class="muted">no runs today</td></tr>') + "</tbody></table>" +
      '<p class="muted">Lane C is shown when present and billed never. Estimates never bill.</p>' +
      '<p class="muted">Toll position uses the local ledger first.</p>';
  }

  function paintLogs(list) {
    var rows = ((list && list.data) || []).map(function (event) {
      var cost = event.cost || {};
      return "<tr><td>" + esc(event.at) + "</td><td>" + esc(event.event) + "</td><td>" + esc(event.model) +
        "</td><td>" + money(cost.measured_usd) + " " + badge(cost.provenance) + "</td><td>" +
        esc(event.event_id) + "</td></tr>";
    }).join("");
    return "<p class=\"muted\">Provenance: " + badge("estimate") + " never billed · " +
      badge("measured") + " bills · " + badge("billed") + " settled.</p>" +
      "<table><thead><tr><th>at</th><th>event</th><th>model</th><th>cost</th><th>id</th></tr></thead><tbody>" +
      (rows || '<tr><td colspan="5" class="muted">no receipts</td></tr>') + "</tbody></table>" +
      '<div class="row"><button type="button" data-action="export">Export JSON</button></div>' +
      '<div id="msg" class="muted"></div>';
  }

  function paintBilling() {
    return '<div class="tile"><div class="muted">billing</div><b>External processor</b></div>' +
      "<p>Checkout opens on the processor. This panel never asks for payment details.</p>" +
      '<div class="row">' +
      '<button type="button" data-action="portal">Manage billing</button>' +
      '<label>Amount $<input id="amt" type="number" min="1" step="1" value="10"></label>' +
      '<button type="button" data-action="buy">Buy credits</button>' +
      "</div>" +
      '<p class="muted">Auto-top-up stays off. A purchase is a separate opt-in.</p>' +
      '<div id="msg" class="muted"></div>';
  }

  function paintSettings(settings) {
    var auto = (settings && settings.autotopup) || { enabled: AUTO_DEFAULT, cap_usd: 0 };
    var data = (settings && settings.data_contribution) || { aggregates: true, per_run: false };
    var enabled = auto.enabled === true;
    return '<p class="muted">Auto-top-up is off unless you opt in with a hard cap.</p>' +
      '<div class="row"><label><input type="checkbox" id="auto"' + (enabled ? " checked" : "") + "> auto-top-up</label>" +
      '<label>cap $<input id="cap" type="number" min="0" step="1" value="' + esc(auto.cap_usd || 0) + '"></label>' +
      '<button type="button" data-action="save-auto">Save</button></div>' +
      '<div class="row"><label><input type="checkbox" id="agg"' + (data.aggregates !== false ? " checked" : "") + "> share aggregates</label>" +
      '<label><input type="checkbox" id="detail"' + (data.per_run === true ? " checked" : "") + "> share per-run detail</label>" +
      '<button type="button" data-action="save-data">Save data</button></div>' +
      '<div class="row"><button type="button" data-action="export-all">Export everything</button></div>' +
      '<div id="msg" class="muted"></div>';
  }

  function paintKeys(state) {
    var meta = state.keyMeta || { present: false, last4: null };
    var present = meta.present ? "present" : "absent";
    var tail = meta.last4 ? esc(meta.last4) : "—";
    var once = "";
    if (state.onceKey) {
      once = '<p class="ok">Shown once. Copy it now. It will not be stored on this machine.</p>' +
        '<div class="once">' + esc(state.onceKey) + "</div>";
    }
    return '<div class="row">' +
      '<div class="tile"><div class="muted">key</div><b>' + esc(present) + "</b></div>" +
      '<div class="tile"><div class="muted">last4</div><b>' + tail + "</b></div>" +
      "</div>" +
      '<p class="muted">Values are never stored or echoed after this view.</p>' +
      '<div class="row"><button type="button" data-action="issue">Issue key</button>' +
      '<button type="button" class="danger" data-action="forget">Forget local key state</button></div>' +
      once +
      '<div id="msg" class="muted"></div>';
  }

  function paintModels(board) {
    var header = "<p class=\"muted\">Axes: " + AXES.map(function (axis) {
      return esc(axis);
    }).join(" · ") + ". Harnesses: " + HARNESSES.map(function (name) {
      return esc(name);
    }).join(" · ") + ".</p>";
    var rows = "";
    var list = (board && board.leaderboard) || [];
    var shown = 0;
    for (var i = 0; i < list.length && shown < 8; i++) {
      var row = list[i] || {};
      rows += "<tr><td>" + esc(row.rank) + "</td><td>" + esc(row.name) + "</td><td>" + esc(row.family) +
        "</td><td>" + esc(row.context_length) + "</td><td>" + badge("estimate") + "</td></tr>";
      shown += 1;
    }
    var empty = board && board._error
      ? '<tr><td colspan="5" class="muted">Catalog unavailable. Local work still runs.</td></tr>'
      : (rows || '<tr><td colspan="5" class="muted">No catalog rows.</td></tr>');
    return header +
      "<table><thead><tr><th>rank</th><th>name</th><th>family</th><th>context</th><th>provenance</th></tr></thead><tbody>" +
      (rows || empty) + "</tbody></table>" +
      '<div id="msg" class="muted"></div>';
  }

  class SolaroAccount extends HTMLElement {
    constructor() {
      super();
      this.attachShadow({ mode: "open" });
      this._tab = "account";
      this._usage = null;
      this._logs = null;
      this._settings = { autotopup: { enabled: AUTO_DEFAULT, cap_usd: 0 }, data_contribution: { aggregates: true, per_run: false } };
      this._keyMeta = { present: false, last4: null };
      this._onceKey = "";
      this._board = null;
    }

    static get observedAttributes() {
      return ["mode", "endpoint", "app-name"];
    }

    connectedCallback() {
      this._renderShell();
      this._show("account");
    }

    attributeChangedCallback() {
      if (this.shadowRoot && this.shadowRoot.getElementById("view")) {
        var title = this.shadowRoot.querySelector("h2");
        if (title) title.textContent = this._appName();
      }
    }

    _appName() {
      return this.getAttribute("app-name") || "SolaroLabs";
    }

    _renderShell() {
      this.shadowRoot.innerHTML = shell(this._appName());
      var root = this.shadowRoot;
      var self = this;
      root.addEventListener("click", function (event) {
        var node = event.target;
        if (!node || !node.getAttribute) return;
        var tab = node.getAttribute("data-tab");
        if (tab && TABS.indexOf(tab) !== -1) {
          self._show(tab);
          return;
        }
        var action = node.getAttribute("data-action");
        if (action) self._onAction(action, node);
      });
    }

    _view() {
      return this.shadowRoot.getElementById("view");
    }

    _setNav(name) {
      var buttons = this.shadowRoot.querySelectorAll("nav button");
      for (var i = 0; i < buttons.length; i++) {
        var on = buttons[i].getAttribute("data-tab") === name;
        buttons[i].setAttribute("aria-current", on ? "true" : "false");
      }
    }

    _state() {
      return {
        appName: this._appName(),
        localOnly: declined(),
        plan: declined() ? "local" : "free",
        credits: null,
        keyMeta: this._keyMeta,
        onceKey: this._onceKey
      };
    }

    _show(name) {
      if (TABS.indexOf(name) === -1) name = "account";
      this._tab = name;
      this._setNav(name);
      var view = this._view();
      if (!view) return;
      if (name === "account") {
        view.innerHTML = paintAccount(this._state());
        this._onceKey = "";
        return;
      }
      if (name === "usage") {
        view.innerHTML = paintUsage(this._usage);
        this._loadUsage();
        return;
      }
      if (name === "logs") {
        view.innerHTML = paintLogs(this._logs);
        this._loadLogs();
        return;
      }
      if (name === "billing") {
        view.innerHTML = paintBilling();
        return;
      }
      if (name === "settings") {
        view.innerHTML = paintSettings(this._settings);
        return;
      }
      if (name === "keys") {
        view.innerHTML = paintKeys(this._state());
        this._onceKey = "";
        return;
      }
      view.innerHTML = paintModels(this._board);
      this._loadModels();
    }

    _msg(text, bad) {
      var box = this.shadowRoot.getElementById("msg");
      if (!box) return;
      box.textContent = text;
      box.className = bad ? "err" : "muted";
    }

    _loadUsage() {
      var self = this;
      request(this, "/v1/usage/today").then(function (data) {
        if (self._tab !== "usage") return;
        if (!data || data._status !== 200) {
          self._usage = { _live: false };
          self._view().innerHTML = paintUsage(self._usage);
          return;
        }
        data._live = true;
        self._usage = data;
        self._view().innerHTML = paintUsage(data);
      }).catch(function () {
        if (self._tab !== "usage") return;
        self._usage = { _live: false };
        self._view().innerHTML = paintUsage(self._usage);
      });
    }

    _loadLogs() {
      var self = this;
      request(this, "/v1/logs").then(function (data) {
        if (self._tab !== "logs") return;
        if (!data || data._status !== 200) {
          self._view().innerHTML = paintLogs({ data: [] });
          return;
        }
        self._logs = data;
        self._view().innerHTML = paintLogs(data);
      }).catch(function () {
        if (self._tab !== "logs") return;
        self._view().innerHTML = paintLogs({ data: [] });
      });
    }

    _loadModels() {
      var self = this;
      var ctrl = typeof AbortController === "function" ? new AbortController() : null;
      var timer = ctrl ? setTimeout(function () { ctrl.abort(); }, 6000) : null;
      fetch(MDATA_BOARD, { method: "GET", headers: { "Accept": "application/json" }, signal: ctrl ? ctrl.signal : undefined })
        .then(function (res) { return res.ok ? res.json() : Promise.reject(new Error("status")); })
        .then(function (data) {
          if (timer) clearTimeout(timer);
          if (self._tab !== "models") return;
          self._board = data && typeof data === "object" ? data : { _error: true };
          self._view().innerHTML = paintModels(self._board);
        })
        .catch(function () {
          if (timer) clearTimeout(timer);
          if (self._tab !== "models") return;
          self._board = { _error: true, leaderboard: [] };
          self._view().innerHTML = paintModels(self._board);
        });
    }

    _openExternal(url) {
      if (!url || !/^https:\/\//i.test(String(url))) {
        this._msg("Billing opens on the processor. No payment details are entered here.");
        return;
      }
      window.open(String(url), "_blank", "noopener,noreferrer");
      this._msg("Opened the billing portal in a new tab. This click does not grant credit.");
    }

    _rememberKey(value) {
      if (!value) return;
      var tail = last4(value);
      this._keyMeta = { present: true, last4: tail };
      this._onceKey = String(value);
    }

    _onAction(action, node) {
      var self = this;
      if (action === "skip") {
        setDeclined(true);
        this._show("account");
        return;
      }
      if (action === "connect") {
        if (declined()) {
          this._msg("Skip is still remembered. Connect remains optional.");
        }
        request(this, "/v1/account/create", { method: "POST", body: {} }).then(function (data) {
          if (data && data.key) self._rememberKey(data.key);
          if (data && data._status === 200) self._msg("Account response received. The key, if any, is shown once on Keys.");
          else self._msg("Sign-in is optional. The local profile still works.", true);
        }).catch(function () {
          self._msg("Account service unreachable. Local-only still works.", true);
        });
        return;
      }
      if (action === "portal") {
        request(this, "/v1/statement").then(function (data) {
          var url = data && (data.portal_url || (data.checkout && data.checkout.url));
          self._openExternal(url);
        }).catch(function () {
          self._openExternal("");
        });
        return;
      }
      if (action === "buy") {
        var amtEl = this.shadowRoot.getElementById("amt");
        var amt = amtEl ? Number(amtEl.value || 10) : 10;
        if (!isFinite(amt) || amt <= 0) {
          this._msg("Enter an amount. Payment details stay on the processor.", true);
          return;
        }
        request(this, "/v1/statement", { method: "POST", body: { amount_usd: amt } }).then(function (data) {
          var url = data && data.checkout && data.checkout.url;
          if (url) self._openExternal(url);
          else self._msg("No checkout URL. The processor opens outside this panel.");
        }).catch(function () {
          self._msg("Billing service unreachable. Nothing was charged.");
        });
        return;
      }
      if (action === "save-auto") {
        var box = this.shadowRoot.getElementById("auto");
        var capEl = this.shadowRoot.getElementById("cap");
        var enabled = !!(box && box.checked);
        var cap = capEl ? Number(capEl.value || 0) : 0;
        if (enabled && !(cap > 0)) {
          this._msg("Opt-in requires a hard cap.");
          return;
        }
        this._settings.autotopup = { enabled: enabled, cap_usd: cap };
        request(this, "/v1/account", { method: "POST", body: { autotopup: this._settings.autotopup } }).catch(function () { return null; });
        this._msg(enabled ? "Auto-top-up saved with a cap." : "Auto-top-up is off.");
        return;
      }
      if (action === "save-data") {
        var agg = this.shadowRoot.getElementById("agg");
        var detail = this.shadowRoot.getElementById("detail");
        this._settings.data_contribution = {
          aggregates: !!(agg && agg.checked),
          per_run: !!(detail && detail.checked)
        };
        this._msg("Data sharing preference saved on this page.");
        return;
      }
      if (action === "export" || action === "export-all") {
        var blob = new Blob([JSON.stringify({ promises: PROMISES, usage: this._usage, logs: this._logs }, null, 2)], { type: "application/json" });
        var link = document.createElement("a");
        link.href = URL.createObjectURL(blob);
        link.download = "solaro-export.json";
        link.click();
        this._msg("Export downloaded.");
        return;
      }
      if (action === "issue") {
        request(this, "/v1/account", { method: "POST", body: { op: "issue" } }).then(function (data) {
          if (data && data.key) {
            self._rememberKey(data.key);
            self._show("keys");
            return;
          }
          self._msg("No key was issued. Nothing was stored.", true);
        }).catch(function () {
          self._msg("Key service unreachable.", true);
        });
        return;
      }
      if (action === "forget") {
        this._keyMeta = { present: false, last4: null };
        this._onceKey = "";
        this._show("keys");
        this._msg("Local key state cleared. No secret was written to storage.");
        return;
      }
      if (action === "period") {
        this._msg(node && node.getAttribute("data-period") === "month" ? "Month view uses the same local ledger." : "Today view.");
      }
    }
  }

  if (typeof customElements !== "undefined" && !customElements.get("solaro-account")) {
    customElements.define("solaro-account", SolaroAccount);
  }
})();
