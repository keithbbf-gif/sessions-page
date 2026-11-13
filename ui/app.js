(function () {
  var ACTIVE_MS = 15 * 60 * 1000;
  var RECENT_KEY = "cmsessions.recents";
  var VENDOR_LABEL = {
    claude: "Claude",
    codex: "Codex",
    grok: "Grok",
    antigravity: "Antigravity",
    gemini: "Gemini",
    other: "Other"
  };
  var state = {
    hits: [],
    indexed: null,
    selected: null,
    turns: [],
    handoff: "",
    group: "flat",
    project: null,
    findGen: 0,
    selectGen: 0,
    stripOk: ""
  };

  function $(id) { return document.getElementById(id); }

  function vendorOf(hit) {
    var name = String((hit && hit.harness) || "").toLowerCase();
    if (name === "claude" || name === "claude_desktop") return "claude";
    if (name === "antigravity" || name === "antigravity-ide" || name === "antigravity-cli" || name === "agy") return "antigravity";
    if (name === "grok" || name === "codex" || name === "gemini") return name;
    return "other";
  }

  function vendorLabel(id) { return VENDOR_LABEL[id] || "Other"; }

  function stampMs(stamp) {
    var n = Number(stamp);
    if (!n) return 0;
    return n > 100000000000 ? n : n * 1000;
  }

  function whenText(stamp) {
    var ms = stampMs(stamp);
    if (!ms) return "\u2014";
    var date = new Date(ms);
    var time = date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    if (date.toDateString() === new Date().toDateString()) return time;
    return date.toLocaleDateString([], { month: "short", day: "numeric" }) + " " + time;
  }

  function tokenCount(hit) {
    if (!hit) return null;
    var keys = ["tokens", "token_count", "total_tokens", "context_tokens"];
    var i;
    for (i = 0; i < keys.length; i += 1) {
      if (hit[keys[i]] != null && hit[keys[i]] !== "" && isFinite(Number(hit[keys[i]]))) return Number(hit[keys[i]]);
    }
    var usage = hit.usage;
    if (usage && typeof usage === "object") {
      if (usage.total != null && usage.total !== "" && isFinite(Number(usage.total))) return Number(usage.total);
      if (usage.total_tokens != null && isFinite(Number(usage.total_tokens))) return Number(usage.total_tokens);
      var inn = usage.input != null ? usage.input : usage.input_tokens;
      var out = usage.output != null ? usage.output : usage.output_tokens;
      if ((inn != null || out != null) && isFinite(Number(inn || 0) + Number(out || 0))) {
        return Number(inn || 0) + Number(out || 0);
      }
    }
    return null;
  }

  function formatTokens(n) {
    var value = Number(n);
    if (!isFinite(value)) return "\u2014";
    return Math.round(value).toLocaleString();
  }

  function tokenLabel(hit) {
    var n = tokenCount(hit);
    return n == null ? "\u2014" : formatTokens(n);
  }

  function ageText(stamp) {
    var ms = stampMs(stamp);
    if (!ms) return "\u2014";
    var mins = Math.max(0, Math.floor((Date.now() - ms) / 60000));
    if (mins < 60) return mins + "m";
    var hours = Math.floor(mins / 60);
    if (hours < 24) return hours + "hr";
    var days = Math.floor(hours / 24);
    if (days < 14) return days + (days === 1 ? " day" : " days");
    var weeks = Math.floor(days / 7);
    if (weeks < 8) return weeks + " wks";
    var months = Math.floor(days / 30);
    return months + (months === 1 ? " month" : " months");
  }

  function showView(name) {
    Array.prototype.forEach.call(document.querySelectorAll("[data-view-panel]"), function (panel) {
      panel.hidden = panel.getAttribute("data-view-panel") !== name;
    });
    Array.prototype.forEach.call(document.querySelectorAll("[data-view]"), function (btn) {
      btn.classList.toggle("on", btn.getAttribute("data-view") === name);
    });
  }

  function contextOf(hit) {
    if (!hit) return { empty: true, pct: 0, label: "Context unknown" };
    var n = tokenCount(hit);
    var pct = null;
    if (hit.context_pct != null && hit.context_pct !== "" && isFinite(Number(hit.context_pct))) {
      pct = Number(hit.context_pct);
      if (pct > 0 && pct <= 1) pct *= 100;
    } else if (n != null && hit.context_window && Number(hit.context_window) > 0) {
      pct = Math.min(100, (n / Number(hit.context_window)) * 100);
    }
    if (n == null && pct == null) return { empty: true, pct: 0, label: "Context unknown" };
    if (pct == null) return { empty: true, pct: 0, label: formatTokens(n) + " tokens" };
    var label = Math.round(pct) + "%";
    if (n != null) label += " \u00b7 " + formatTokens(n) + " tokens";
    return { empty: false, pct: pct, label: label };
  }

  function statusOf(hit) {
    var raw = String((hit && (hit.status || hit.state || hit.stream)) || "").toLowerCase();
    if (raw === "crashed" || raw === "crash") return "crashed";
    if (raw === "active" || raw === "running" || raw === "live") return "active";
    if (raw === "idle") return "idle";
    var ms = stampMs(hit && hit.updated);
    if (ms && (Date.now() - ms) <= ACTIVE_MS) return "active";
    return "idle";
  }

  function projectKey(hit) {
    if (!hit || hit.legal) return "";
    return String(hit.cwd || "").replace(/\//g, "\\").replace(/\\+$/, "");
  }

  function projectLabel(cwd) {
    if (!cwd) return "No project";
    var parts = String(cwd).split("\\").filter(Boolean);
    return parts.length ? parts[parts.length - 1] : cwd;
  }

  function checkedValues(name) {
    var set = {};
    var nodes = document.querySelectorAll('input[name="' + name + '"]:checked');
    Array.prototype.forEach.call(nodes, function (el) { set[el.value] = true; });
    return set;
  }

  function passVendor(hit) { return !!checkedValues("vendor")[vendorOf(hit)]; }
  function passStatus(hit) { return !!checkedValues("status")[statusOf(hit)]; }
  function passProject(hit) { return state.project == null || projectKey(hit) === state.project; }

  function byUpdated(a, b) {
    var delta = (Number(b.updated) || 0) - (Number(a.updated) || 0);
    if (delta) return delta;
    return String(a.id || "").localeCompare(String(b.id || ""));
  }

  function post(body) {
    if (typeof fetch !== "function") return Promise.reject(new Error("No network"));
    return fetch("/api/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    }).then(function (res) {
      return res.json().then(function (rec) {
        if (!res.ok && rec && !rec.error) rec.error = "HTTP " + res.status;
        return rec;
      });
    });
  }

  function say(text, tone) {
    var el = $("say");
    el.className = "say" + (tone ? " " + tone : "");
    el.textContent = text || "";
  }

  function toneOf(rec) {
    if (!rec || rec.error) return "bad";
    var kind = rec.kind || "";
    if (kind === "TRUNCATED" || kind === "DRY_RUN" || kind === "OPENWORK_FOCUS") return "warn";
    if (kind === "OK" || kind === "ALREADY_OK" || kind === "VERIFIED") return "good";
    return kind ? "bad" : "";
  }

  function sentence(rec) {
    if (!rec) return "";
    if (typeof rec === "string") return rec;
    if (rec.error) return rec.error + (rec.detail ? " \u2014 " + rec.detail : "");
    var gate = rec.gate || {};
    if (rec.verb === "export") return "Markdown written." + (gate.out ? " " + gate.out : "");
    if (rec.verb === "import") {
      var jsonl = rec.written && rec.written.jsonl;
      return "Imported." + (jsonl ? " " + jsonl : "");
    }
    if (rec.verb === "anonymize") {
      return "Anonymized copy written. " + (gate.n_redactions || 0) + " redactions. Original unchanged.";
    }
    if (rec.verb === "crash-recover" || rec.verb === "recover") {
      if (rec.kind === "OK") return "Restored from the backup.";
      if (rec.kind === "NO_BAK") return "No backup was found beside the file.";
      if (rec.kind === "ALREADY_OK") return "File checks out. Nothing was changed.";
      if (rec.kind === "DRY_RUN") return "A backup is ready. Nothing was copied.";
      if (rec.kind === "BUSY") return "The file is in use. Nothing was changed.";
      return rec.kind || "Restore finished.";
    }
    if (rec.verb === "preview") {
      var shown = gate.shown;
      var nTurns = gate.n_turns;
      if (typeof nTurns === "number") return "Showing " + shown + " of " + nTurns + " turns.";
      return "First " + shown + " turns.";
    }
    if (rec.verb === "index") {
      var indexed = gate.n;
      var indexOut = gate.out || "";
      if (typeof indexed !== "number") return rec.kind || "Index";
      return indexOut ? ("Index of " + indexed + " — " + indexOut) : ("Index of " + indexed);
    }
    if (rec.verb === "formats") {
      var rows = gate.formats || [];
      return rows.length + " formats.";
    }
    if (rec.verb === "strip_dry") {
      return "Strip would keep " + gate.kept + " turns and drop " + gate.dropped_markers + ". Nothing was written.";
    }
    if (rec.verb === "strip") {
      var stripPath = rec.written && rec.written.jsonl;
      return "Stripped copy written. Original unchanged." + (stripPath ? " " + stripPath : "");
    }
    return rec.kind || "Done.";
  }

  function titleOf(hit) {
    if (!hit) return "Untitled";
    if (hit.legal) return "Legal session";
    return hit.title || hit.vendor_id || hit.id || "Untitled";
  }

  function paintContext(hit) {
    var info = contextOf(hit);
    var bar = $("context-bar");
    var fill = $("context-fill");
    $("context-label").textContent = info.label;
    bar.classList.toggle("empty", !!info.empty || !info.pct);
    fill.style.width = info.empty || !info.pct ? "0" : (Math.max(0, Math.min(100, info.pct)) + "%");
    fill.className = !info.empty && info.pct >= 85 ? "hot" : (!info.empty && info.pct >= 65 ? "warn" : "");
    bar.setAttribute("aria-valuenow", info.empty ? "0" : String(Math.round(info.pct || 0)));
    bar.setAttribute("aria-valuetext", info.label);
  }

  function paintActions(hit) {
    var on = !!(hit && !hit.legal);
    ["continue", "handoff", "copy", "export-md", "export-json", "import", "anonymize", "restore", "preview-btn", "recover-btn", "strip-dry-btn", "strip-btn"].forEach(function (id) {
      var el = $(id);
      if (el) el.disabled = !on;
    });
    if (on && hit && !hit.path) {
      if ($("restore")) $("restore").disabled = true;
      if ($("recover-btn")) $("recover-btn").disabled = true;
    }
  }

  function paintDetail(resetArgv) {
    var hit = state.selected;
    var argv = $("argv");
    if (!hit) {
      if ($("d-title")) $("d-title").textContent = "No session selected";
      if ($("d-meta")) $("d-meta").textContent = "";
      $("handoff-line").textContent = "";
      argv.hidden = true;
      argv.textContent = "";
      paintContext(null);
      paintActions(null);
      return;
    }
    var vendor = vendorOf(hit);
    var mark = $("app-mark");
    if (mark) {
      mark.textContent = vendorLabel(vendor);
      mark.className = "app-mark v-" + vendor;
    }
    if ($("fact-date")) {
      var ms = stampMs(hit.updated);
      var whenDate = ms ? new Date(ms) : null;
      $("fact-date").textContent = whenDate ? whenDate.toLocaleDateString() : "\u2014";
      $("fact-start").textContent = whenDate ? whenDate.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "\u2014";
      $("fact-end").textContent = "\u2014";
      $("fact-size").textContent = hit.bytes ? (Math.max(1, Math.round(hit.bytes / 1024)) + " KB") : "\u2014";
      $("fact-tokens").textContent = "input / output / total " + tokenLabel(hit);
      $("fact-time").textContent = ageText(hit.updated);
      $("fact-topic").textContent = projectLabel(projectKey(hit));
      $("fact-path").textContent = hit.legal ? "\u2014" : (hit.path || hit.cwd || "\u2014");
      $("fact-keys").textContent = hit.legal ? "\u2014" : (titleOf(hit).split(/\s+/).slice(0, 6).join(" ") || "\u2014");
      $("chain-harness").textContent = (hit.harness || vendor) + " / harness";
      $("chain-model").textContent = hit.model || "Model / agent";
    }
    if ($("session-preview")) {
      $("session-preview").textContent = hit.legal ? "Legal session stays closed." : (titleOf(hit) + "\n" + (hit.cwd || ""));
    }
    $("d-title") && ($("d-title").textContent = titleOf(hit));
    var bits = [vendorLabel(vendorOf(hit))];
    if (!hit.legal && hit.cwd) bits.push(projectLabel(projectKey(hit)));
    var when = whenText(hit.updated);
    if (when !== "\u2014") bits.push(when);
    bits.push(statusOf(hit));
    if ($("d-meta")) $("d-meta").textContent = bits.join(" \u00b7 ");
    $("handoff-line").textContent = state.handoff ? ("Hand off to " + state.handoff) : "";
    if (resetArgv) {
      argv.hidden = true;
      argv.textContent = "";
    }
    paintContext(hit);
    paintActions(hit);
  }

  function paintPreview(turns, note) {
    var box = $("preview");
    box.textContent = "";
    if (!turns || !turns.length) {
      if (note) box.textContent = note;
      return;
    }
    turns.forEach(function (turn) {
      var role = turn.role || "turn";
      var tool = role === "tool_call" || role === "tool_result" || role === "tool";
      if (tool) {
        var details = document.createElement("details");
        details.className = "turn tool";
        var summary = document.createElement("summary");
        summary.textContent = role;
        var pre = document.createElement("pre");
        pre.textContent = turn.text || "";
        details.appendChild(summary);
        details.appendChild(pre);
        box.appendChild(details);
        return;
      }
      var block = document.createElement("div");
      var known = role === "user" || role === "assistant";
      block.className = "turn" + (known ? " " + role : "");
      var label = document.createElement("div");
      label.className = "role";
      label.textContent = role;
      var body = document.createElement("div");
      body.className = "text";
      body.textContent = turn.text || "";
      block.appendChild(label);
      block.appendChild(body);
      box.appendChild(block);
    });
  }

  function paintList(rows) {
    var list = $("list");
    var lastGroup = null;
    list.textContent = "";
    $("count").textContent = rows.length + " shown";
    if (!rows.length) {
      var empty = document.createElement("tr");
      var cell = document.createElement("td");
      cell.colSpan = 6;
      cell.textContent = "No sessions match.";
      empty.appendChild(cell);
      list.appendChild(empty);
      return;
    }
    rows.forEach(function (hit) {
      var vendor = vendorOf(hit);
      var group = groupLabel(hit);
      var tr, btn, title, sub;
      if (group && group !== lastGroup) {
        lastGroup = group;
        tr = document.createElement("tr");
        tr.className = "group";
        var head = document.createElement("td");
        head.colSpan = 6;
        head.textContent = group;
        tr.appendChild(head);
        list.appendChild(tr);
      }
      tr = document.createElement("tr");
      tr.className = "v-" + vendor + ((state.selected && state.selected.id === hit.id) ? " on" : "");
      btn = document.createElement("button");
      btn.type = "button";
      btn.className = "rowbtn";
      title = document.createElement("span");
      title.className = "title";
      title.textContent = titleOf(hit);
      sub = document.createElement("span");
      sub.className = "sub";
      sub.textContent = "Sub sessions from subagents";
      btn.appendChild(title);
      btn.appendChild(sub);
      btn.addEventListener("click", function () { select(hit); });
      addCell(tr, (hit.harness || vendor) + "  " + vendorLabel(vendor), "appcell");
      addCell(tr, ageText(hit.updated), "age col-time");
      var titleCell = document.createElement("td");
      titleCell.className = "col-title";
      titleCell.appendChild(btn);
      tr.appendChild(titleCell);
      addCell(tr, tokenLabel(hit), "col-size");
      addCell(tr, projectLabel(projectKey(hit)), "col-topic");
      addCell(tr, hit.legal ? "\u2014" : projectLabel(projectKey(hit)), "col-project");
      list.appendChild(tr);
    });
  }

  function addCell(tr, text, className) {
    var td = document.createElement("td");
    td.className = className || "";
    td.textContent = text;
    tr.appendChild(td);
  }

  function groupLabel(hit) {
    var mode = state.group || "flat";
    if (mode === "maker") return vendorLabel(vendorOf(hit));
    if (mode === "project") return projectLabel(projectKey(hit));
    if (mode === "topic") return projectLabel(projectKey(hit));
    return "";
  }

  function paintProjects(rows) {
    var counts = {};
    var order = [];
    rows.forEach(function (hit) {
      var key = projectKey(hit);
      if (!Object.prototype.hasOwnProperty.call(counts, key)) {
        counts[key] = 0;
        order.push(key);
      }
      counts[key] += 1;
    });
    order.sort(function (a, b) {
      if (!a) return 1;
      if (!b) return -1;
      return projectLabel(a).localeCompare(projectLabel(b));
    });
    var ul = $("projects");
    ul.textContent = "";
    var allItem = document.createElement("li");
    var allBtn = document.createElement("button");
    allBtn.type = "button";
    allBtn.className = "project" + (state.project == null ? " on" : "");
    allBtn.textContent = "All";
    allBtn.addEventListener("click", function () {
      state.project = null;
      render();
    });
    allItem.appendChild(allBtn);
    ul.appendChild(allItem);
    order.forEach(function (key) {
      var li = document.createElement("li");
      var btn = document.createElement("button");
      var name = document.createElement("span");
      var count = document.createElement("span");
      btn.type = "button";
      btn.className = "project" + (state.project === key ? " on" : "");
      name.textContent = projectLabel(key);
      count.className = "count";
      count.textContent = String(counts[key]);
      btn.appendChild(name);
      btn.appendChild(count);
      btn.addEventListener("click", function () {
        state.project = key;
        render();
      });
      li.appendChild(btn);
      ul.appendChild(li);
    });
  }

  function loadRecents() {
    try {
      var raw = sessionStorage.getItem(RECENT_KEY);
      var ids = raw ? JSON.parse(raw) : [];
      return Array.isArray(ids) ? ids.filter(Boolean).slice(0, 5) : [];
    } catch (err) {
      return [];
    }
  }

  function remember(id) {
    if (!id) return;
    var ids = loadRecents().filter(function (item) { return item !== id; });
    ids.unshift(id);
    try { sessionStorage.setItem(RECENT_KEY, JSON.stringify(ids.slice(0, 5))); } catch (err) {}
  }

  function findHit(id) {
    var i;
    for (i = 0; i < state.hits.length; i += 1) {
      if (state.hits[i] && state.hits[i].id === id) return state.hits[i];
    }
    return null;
  }

  function paintRecents() {
    var ul = $("recents");
    if (!ul) return;
    var ids = loadRecents();
    var rows = [];
    ul.textContent = "";
    if (ids.length) {
      ids.forEach(function (id) {
        var hit = findHit(id);
        if (hit) rows.push(hit);
      });
    }
    if (!rows.length) rows = state.hits.slice().sort(byUpdated).slice(0, 5);
    rows.slice(0, 5).forEach(function (hit) {
      var li = document.createElement("li");
      var btn = document.createElement("button");
      var dot = document.createElement("i");
      var name = document.createElement("span");
      var on = state.selected && state.selected.id === hit.id;
      btn.type = "button";
      btn.className = "recent" + (on ? " on" : "");
      dot.className = "dot v-" + vendorOf(hit);
      dot.setAttribute("aria-hidden", "true");
      name.textContent = titleOf(hit);
      btn.appendChild(dot);
      btn.appendChild(name);
      btn.addEventListener("click", function () { select(hit); });
      li.appendChild(btn);
      ul.appendChild(li);
    });
  }

  function tokensToday(hits) {
    var start = new Date();
    var sum = 0;
    var any = false;
    start.setHours(0, 0, 0, 0);
    (hits || []).forEach(function (hit) {
      var n = tokenCount(hit);
      var ms = stampMs(hit.updated);
      if (n == null || !ms || ms < start.getTime()) return;
      sum += n;
      any = true;
    });
    return any ? sum : null;
  }

  function paintStatus() {
    var indexed = state.indexed == null ? "\u2014" : String(state.indexed);
    var active = 0;
    state.hits.forEach(function (hit) {
      if (statusOf(hit) === "active") active += 1;
    });
    var spend = tokensToday(state.hits);
    var spendText = spend == null ? "Tokens today \u2014" : ("Tokens today " + formatTokens(spend));
    $("status").textContent = indexed + " sessions indexed \u00b7 " + active + " active now \u00b7 " + spendText;
  }

  function render() {
    var pool = state.hits.filter(function (hit) { return passVendor(hit) && passStatus(hit); });
    if (state.project != null && !pool.some(function (hit) { return projectKey(hit) === state.project; })) {
      state.project = null;
    }
    var shown = pool.filter(passProject).sort(byUpdated);
    if (state.group && state.group !== "flat") {
      shown.sort(function (a, b) {
        var ga = groupLabel(a);
        var gb = groupLabel(b);
        if (ga !== gb) return ga.localeCompare(gb);
        return byUpdated(a, b);
      });
    }
    paintProjects(pool);
    paintCards(pool);
    paintList(shown);
    paintGlance(pool);
    paintCalendar(pool);
    paintPlan(pool);
    paintRecents();
    paintStatus();
  }

  function clearSelection() {
    state.selected = null;
    state.turns = [];
    state.handoff = "";
    state.selectGen += 1;
    setMenu(false);
    paintDetail(true);
    paintPreview(null, "");
    say("");
  }

  function select(hit) {
    var gen = ++state.selectGen;
    state.selected = hit;
    state.turns = [];
    state.handoff = "";
    setMenu(false);
    remember(hit.id);
    showView("session");
    paintDetail(true);
    say("");
    render();
    if (hit.legal) {
      paintPreview(null, "Legal session stays closed.");
      return;
    }
    paintPreview(null, "Reading\u2026");
    post({ action: "preview", id: hit.id }).then(function (rec) {
      if (gen !== state.selectGen || !state.selected || state.selected.id !== hit.id) return;
      if (!rec || rec.error) {
        paintPreview(null, sentence(rec));
        return;
      }
      state.turns = (rec.gate && rec.gate.turns) || rec.turns || [];
      paintPreview(state.turns, state.turns.length ? "" : "No dialogue in this preview.");
    }).catch(function (err) {
      if (gen !== state.selectGen) return;
      paintPreview(null, String(err && err.message || err));
    });
  }

  function find() {
    var gen = ++state.findGen;
    var query = $("q").value.trim();
    $("count").textContent = "Looking\u2026";
    post({ action: "find", limit: 200, query: query }).then(function (rec) {
      if (gen !== state.findGen) return;
      if (!rec || rec.error || !rec.hits) {
        $("count").textContent = sentence(rec) || "Could not list sessions.";
        paintStatus();
        return;
      }
      state.hits = rec.hits.slice().sort(byUpdated);
      state.indexed = rec.n != null ? rec.n : state.hits.length;
      if (state.selected && !findHit(state.selected.id)) clearSelection();
      render();
    }).catch(function (err) {
      if (gen !== state.findGen) return;
      $("count").textContent = "Could not reach sessions.";
      say(String(err && err.message || err), "bad");
      paintStatus();
    });
  }

  function showArgv(argv) {
    return argv.map(function (part) {
      var text = String(part);
      if (/[\s"]/.test(text)) return '"' + text.replace(/"/g, '\\"') + '"';
      return text;
    }).join(" ");
  }

  function onContinue() {
    var hit = state.selected;
    var gen;
    if (!hit || hit.legal) return;
    gen = state.selectGen;
    $("argv").hidden = false;
    $("argv").textContent = "Reading resume\u2026";
    post({ action: "resume", id: hit.id, launch: false }).then(function (rec) {
      var argv;
      var gate;
      if (gen !== state.selectGen || !state.selected || state.selected.id !== hit.id) return;
      gate = rec && rec.gate;
      argv = gate && gate.argv;
      $("argv").hidden = false;
      if (argv && argv.length) $("argv").textContent = showArgv(argv);
      else $("argv").textContent = (gate && gate.detail) || (rec && rec.kind) || "No resume command.";
      say(sentence(rec), toneOf(rec));
    }).catch(function (err) {
      if (gen !== state.selectGen) return;
      $("argv").textContent = String(err && err.message || err);
      say(String(err && err.message || err), "bad");
    });
  }

  function setMenu(open) {
    $("handoff-menu").hidden = !open;
    $("handoff").setAttribute("aria-expanded", open ? "true" : "false");
  }

  function act(action, extra) {
    var hit = state.selected;
    var gen;
    if (!hit || hit.legal) return;
    gen = state.selectGen;
    post(Object.assign({ action: action, id: hit.id }, extra || {})).then(function (rec) {
      if (gen !== state.selectGen || !state.selected || state.selected.id !== hit.id) return;
      say(sentence(rec), toneOf(rec));
    }).catch(function (err) {
      say(String(err && err.message || err), "bad");
    });
  }

  function turnsToText(turns) {
    return (turns || []).map(function (turn) {
      return (turn.role || "turn") + "\n" + (turn.text || "");
    }).join("\n\n");
  }

  function copyTranscript() {
    var text = state.turns && state.turns.length ? turnsToText(state.turns) : ($("preview").textContent || "");
    if (!text) {
      say("Nothing to copy.", "warn");
      return;
    }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(function () {
        say("Copied.", "good");
      }, function () { fallbackCopy(text); });
      return;
    }
    fallbackCopy(text);
  }

  function fallbackCopy(text) {
    var area = document.createElement("textarea");
    area.value = text;
    document.body.appendChild(area);
    area.select();
    try {
      document.execCommand("copy");
      say("Copied.", "good");
    } catch (err) {
      say("Could not copy.", "bad");
    }
    area.remove();
  }

  function downloadJson(hit, turns) {
    var payload = {
      id: hit.id,
      harness: hit.harness,
      vendor: vendorOf(hit),
      title: hit.legal ? "" : (hit.title || ""),
      cwd: hit.legal ? "" : (hit.cwd || ""),
      updated: hit.updated,
      path: hit.path,
      turns: turns || []
    };
    var blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    var link = document.createElement("a");
    var url = URL.createObjectURL(blob);
    link.href = url;
    link.download = String(hit.id || "session").replace(/[\\/:*?"<>|]+/g, "_") + ".json";
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    say("Exported JSON for " + hit.id + ".", "good");
  }

  function exportJson() {
    var hit = state.selected;
    if (!hit || hit.legal) return;
    if (state.turns && state.turns.length) {
      downloadJson(hit, state.turns);
      return;
    }
    post({ action: "preview", id: hit.id }).then(function (rec) {
      var turns = (rec && rec.gate && rec.gate.turns) || [];
      if (state.selected && state.selected.id === hit.id) state.turns = turns;
      downloadJson(hit, turns);
    }).catch(function () {
      downloadJson(hit, []);
    });
  }

  function onRestore() {
    var hit = state.selected;
    if (!hit || hit.legal || !hit.path) return;
    if (!window.confirm("Replace this file with the backup beside it?")) return;
    act("crash-recover", { target: hit.path, path: hit.path, apply: true });
  }

  function onPreview() {
    var hit = state.selected;
    var gen;
    if (!hit) {
      say("Select a session first.", "warn");
      return;
    }
    if (hit.legal) {
      paintPreview(null, "Legal session stays closed.");
      say("Legal session stays closed.", "bad");
      return;
    }
    gen = state.selectGen;
    paintPreview(null, "Reading…");
    post({ action: "preview", id: hit.id, turns: 6, chars: 400 }).then(function (rec) {
      if (gen !== state.selectGen || !state.selected || state.selected.id !== hit.id) return;
      if (!rec || rec.error) {
        paintPreview(null, sentence(rec));
        say(sentence(rec), "bad");
        return;
      }
      state.turns = (rec.gate && rec.gate.turns) || [];
      paintPreview(state.turns, state.turns.length ? "" : "No dialogue in this preview.");
      say(sentence(rec), toneOf(rec));
    }).catch(function (err) {
      if (gen !== state.selectGen) return;
      say(String(err && err.message || err), "bad");
    });
  }

  function onIndex() {
    say("Indexing…");
    post({ action: "index" }).then(function (rec) {
      if (rec && rec.gate && typeof rec.gate.n === "number") state.indexed = rec.gate.n;
      say(sentence(rec), toneOf(rec));
      paintStatus();
    }).catch(function (err) {
      say(String(err && err.message || err), "bad");
    });
  }

  function onFormats() {
    post({ action: "formats" }).then(function (rec) {
      var rows = (rec && rec.gate && rec.gate.formats) || [];
      var lines = rows.map(function (row) {
        return (row.harness || "") + "  " + (row.load || "") + "  " + (row.resume || "");
      });
      say(sentence(rec), toneOf(rec));
      var box = $("preview");
      if (box) box.textContent = lines.join("\n") || sentence(rec);
    }).catch(function (err) {
      say(String(err && err.message || err), "bad");
    });
  }

  function onRecover() {
    var hit = state.selected;
    if (!hit || hit.legal) return;
    if (!hit.path) {
      say("This session has no path.", "warn");
      return;
    }
    act("recover", { target: hit.path, path: hit.path, apply: false });
  }

  function onStripDry() {
    var hit = state.selected;
    var id;
    var gen;
    if (!hit || hit.legal) return;
    id = hit.id;
    gen = state.selectGen;
    post({ action: "strip_dry", id: id }).then(function (rec) {
      if (gen !== state.selectGen || !state.selected || state.selected.id !== id) return;
      if (rec && rec.kind === "OK") state.stripOk = id;
      else if (state.stripOk === id) state.stripOk = "";
      say(sentence(rec), toneOf(rec));
    }).catch(function (err) {
      if (gen !== state.selectGen) return;
      say(String(err && err.message || err), "bad");
    });
  }

  function onStrip() {
    var hit = state.selected;
    if (!hit || hit.legal) return;
    if (state.stripOk !== hit.id) {
      say("Check strip has to succeed first.", "warn");
      return;
    }
    act("strip");
  }

  function ensureVerbButtons() {
    var host = document.querySelector(".actions");
    if (!host || host.getAttribute("data-verbs") === "1") return;
    host.setAttribute("data-verbs", "1");
    [
      ["preview-btn", "Preview", onPreview],
      ["index-btn", "Index", onIndex],
      ["formats-btn", "Formats", onFormats],
      ["recover-btn", "Check recovery", onRecover],
      ["strip-dry-btn", "Check strip", onStripDry],
      ["strip-btn", "Write strip", onStrip]
    ].forEach(function (spec) {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.id = spec[0];
      btn.textContent = spec[1];
      btn.addEventListener("click", spec[2]);
      host.appendChild(btn);
    });
  }

  function paintCards(rows) {
    var host = $("project-cards");
    var counts = {};
    var order = [];
    if (!host) return;
    rows.forEach(function (hit) {
      var key = projectKey(hit);
      if (!counts[key]) {
        counts[key] = { n: 0, tokens: 0, start: 0, end: 0 };
        order.push(key);
      }
      counts[key].n += 1;
      var tokens = tokenCount(hit);
      if (tokens != null) counts[key].tokens += tokens;
      var ms = stampMs(hit.updated);
      if (ms && (!counts[key].start || ms < counts[key].start)) counts[key].start = ms;
      if (ms > counts[key].end) counts[key].end = ms;
    });
    host.textContent = "";
    order.sort(function (a, b) { return projectLabel(a).localeCompare(projectLabel(b)); });
    order.slice(0, 12).forEach(function (key, index) {
      var card = document.createElement("article");
      var item = counts[key];
      card.className = "card";
      card.innerHTML = "<strong>Pr " + (index + 1) + "</strong><span>" + projectLabel(key) + "</span><span>" + item.n + " sessions</span><span>Token count " + (item.tokens ? formatTokens(item.tokens) : "\u2014") + "</span><span>Project start " + (item.start ? new Date(item.start).toLocaleDateString() : "\u2014") + "</span><span>End " + (item.end ? new Date(item.end).toLocaleDateString() : "\u2014") + "</span>";
      host.appendChild(card);
    });
  }

  function paintGlance(rows) {
    var week = $("glance-week");
    var now = Date.now();
    var day = 86400000;
    var in7 = 0;
    var inWeek = 0;
    var inMonth = 0;
    var inQuarter = 0;
    if (!week) return;
    week.textContent = "";
    rows.forEach(function (hit) {
      var ms = stampMs(hit.updated);
      if (!ms) return;
      var age = now - ms;
      if (age <= 7 * day) in7 += 1;
      if (age <= 7 * day) inWeek += 1;
      if (age <= 30 * day) inMonth += 1;
      if (age <= 90 * day) inQuarter += 1;
      if (age <= 7 * day && week.children.length < 8) {
        var li = document.createElement("li");
        li.textContent = ageText(hit.updated) + "  " + titleOf(hit);
        li.style.color = "var(--v-" + vendorOf(hit) + ")";
        week.appendChild(li);
      }
    });
    if ($("glance-this-week")) $("glance-this-week").textContent = inWeek + " sessions this week.";
    if ($("glance-month")) $("glance-month").textContent = inMonth + " sessions this month.";
    if ($("glance-quarter")) $("glance-quarter").textContent = inQuarter + " sessions this quarter.";
  }

  function paintCalendar(rows) {
    var host = $("calendar");
    var plan = $("plan-row");
    var now = new Date();
    var year = now.getFullYear();
    var month = now.getMonth();
    var start = $("span-start") && $("span-start").value;
    var end = $("span-end") && $("span-end").value;
    var term = ($("span-q") && $("span-q").value || "").toLowerCase();
    var first, gridStart, i, cell, label, marks;
    if (!host) return;
    host.textContent = "";
    if (plan) plan.textContent = "";
    first = new Date(year, month, 1);
    gridStart = new Date(first);
    gridStart.setDate(1 - first.getDay());
    for (i = 0; i < 42; i += 1) {
      cell = new Date(gridStart);
      cell.setDate(gridStart.getDate() + i);
      label = document.createElement("div");
      label.className = "day";
      if (cell.getMonth() !== month) label.style.opacity = "0.45";
      marks = rows.filter(function (hit) {
        var ms = stampMs(hit.updated);
        var day = ms ? new Date(ms) : null;
        var text = (titleOf(hit) + " " + projectKey(hit)).toLowerCase();
        if (!day || day.toDateString() !== cell.toDateString()) return false;
        if (term && text.indexOf(term) < 0) return false;
        if (start && day < new Date(start + "T00:00:00")) return false;
        if (end && day > new Date(end + "T23:59:59")) return false;
        return true;
      });
      if (marks.length) label.classList.add("in");
      label.innerHTML = "<div class='n'>" + cell.getDate() + "</div>";
      marks.slice(0, 3).forEach(function (hit) {
        var btn = document.createElement("button");
        btn.type = "button";
        btn.className = "mark";
        btn.textContent = titleOf(hit);
        btn.addEventListener("click", function () { select(hit); });
        label.appendChild(btn);
      });
      host.appendChild(label);
    }
    if (!plan) return;
    for (i = -3; i <= 3; i += 1) {
      cell = new Date(now);
      cell.setDate(now.getDate() + i);
      label = document.createElement("div");
      label.innerHTML = "<strong>" + cell.toLocaleDateString([], { weekday: "short", month: "numeric", day: "numeric" }) + "</strong><span>" + (i < 0 ? "sessions" : (i === 0 ? "today" : "Plans")) + "</span>";
      plan.appendChild(label);
    }
  }

  function paintPlan(rows) {
    var crashed = rows.filter(function (hit) { return statusOf(hit) === "crashed"; });
    var idle = rows.filter(function (hit) { return statusOf(hit) === "idle"; });
    if ($("plan-summary")) $("plan-summary").textContent = rows.length + " sessions in the current filter.";
    if ($("plan-loose")) $("plan-loose").textContent = idle.length ? (idle.length + " idle sessions still open.") : "No idle sessions in this filter.";
    if ($("plan-next")) $("plan-next").textContent = crashed.length ? (crashed.length + " crashed, then the oldest unfinished.") : "Crashed first, then the oldest unfinished.";
  }

  function bind() {
    ensureVerbButtons();
    $("search-form").addEventListener("submit", function (ev) {
      ev.preventDefault();
      find();
    });
    $("command-form").addEventListener("submit", function (ev) {
      ev.preventDefault();
      $("q").value = $("command").value;
      find();
    });
    Array.prototype.forEach.call(document.querySelectorAll('input[name="vendor"], input[name="status"]'), function (el) {
      el.addEventListener("change", render);
    });
    $("continue").addEventListener("click", onContinue);
    $("handoff").addEventListener("click", function (ev) {
      ev.stopPropagation();
      if ($("handoff").disabled) return;
      setMenu($("handoff-menu").hidden);
    });
    $("handoff-menu").addEventListener("click", function (ev) {
      var item = ev.target.closest("button[data-harness]");
      if (!item || !state.selected) return;
      state.handoff = item.getAttribute("data-harness");
      $("handoff-line").textContent = "Hand off to " + state.handoff;
      setMenu(false);
    });
    document.addEventListener("click", function (ev) {
      if ($("handoff-menu").hidden) return;
      if ($("handoff").contains(ev.target) || $("handoff-menu").contains(ev.target)) return;
      setMenu(false);
    });
    document.addEventListener("keydown", function (ev) {
      if (ev.key === "Escape") setMenu(false);
    });
    $("copy").addEventListener("click", copyTranscript);
    $("export-md").addEventListener("click", function () { act("export"); });
    $("export-json").addEventListener("click", exportJson);
    $("import").addEventListener("click", function () { act("import"); });
    $("anonymize").addEventListener("click", function () { act("anonymize"); });
    $("restore").addEventListener("click", onRestore);
    Array.prototype.forEach.call(document.querySelectorAll("[data-view]"), function (btn) {
      btn.addEventListener("click", function () { showView(btn.getAttribute("data-view")); });
    });
    Array.prototype.forEach.call(document.querySelectorAll("[data-group]"), function (btn) {
      btn.addEventListener("click", function () {
        state.group = btn.getAttribute("data-group");
        Array.prototype.forEach.call(document.querySelectorAll("[data-group]"), function (other) {
          other.classList.toggle("on", other === btn);
        });
        render();
      });
    });
    Array.prototype.forEach.call(document.querySelectorAll("[data-col]"), function (box) {
      box.addEventListener("change", function () {
        document.body.classList.toggle("hide-" + box.getAttribute("data-col"), !box.checked);
      });
    });
    var printBtn = $("print");
    if (printBtn) printBtn.addEventListener("click", function () { window.print(); });
    var summaries = $("summaries");
    if (summaries) summaries.addEventListener("click", function () {
      say("Create summaries uses the title and project already on the row. A model summary is not part of this pass.", "warn");
    });
    ["span-q", "span-start", "span-end"].forEach(function (id) {
      var el = $(id);
      if (el) el.addEventListener("input", render);
    });
  }

  bind();
  paintDetail(true);
  paintStatus();
  find();
})();
