(function () {
  var state = { harness: "", drive: "", hits: [], selected: null, viewed: false, stripFor: "", findGen: 0, selectGen: 0 };

  var MARK = '<svg viewBox="0 0 16 16" aria-hidden="true">' +
    '<path d="M2 5.5h4l1.2-1.5H14v8H2z" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>' +
    '</svg>';

  function bytes(n) {
    if (n == null || n === "") return "";
    var units = ["B", "KB", "MB", "GB", "TB"];
    var value = Number(n);
    var i = 0;
    while (value >= 1024 && i < units.length - 1) { value /= 1024; i += 1; }
    return (i ? value.toFixed(1) : String(Math.round(value))) + " " + units[i];
  }

  function showStage(name) {
    var overview = name === "overview";
    document.getElementById("overview").hidden = !overview;
    document.getElementById("sessions").hidden = overview;
    document.getElementById("nav-overview").className = "nav" + (overview ? " on" : "");
    document.getElementById("nav-sessions").className = "nav" + (overview ? "" : " on");
  }

  function placeCard(home) {
    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "seat" + (home.present ? " live" : " quiet");
    var where = home.path || home.candidate || "No documented path";
    btn.innerHTML = '<span class="led"></span><span class="ico">' + MARK + '</span><span class="copy"><strong></strong><span class="path"></span></span><span class="tag"></span>';
    btn.querySelector("strong").textContent = home.harness;
    btn.querySelector(".path").textContent = where.replace(/\\/g, "\\\u200b");
    btn.querySelector(".tag").textContent = home.present ? "PRESENT" : "ABSENT";
    btn.addEventListener("click", function () {
      state.harness = home.harness;
      state.drive = home.drive || "";
      state.viewed = true;
      showStage("sessions");
      document.getElementById("lead").textContent = home.harness + " · " + where;
      find(true);
    });
    return btn;
  }

  function driveCard(drive) {
    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "seat drive" + (drive.ready ? " live" : " quiet");
    var title = drive.label ? drive.label : ((drive.id || "Drive") + " drive");
    var bits = [drive.kind || "", drive.fs || ""];
    if (drive.free != null && drive.total) bits.push(bytes(drive.free) + " free");
    else if (drive.total) bits.push(bytes(drive.total));
    var used = (drive.total && drive.free != null) ? Math.max(0, Math.min(100, (1 - (drive.free / drive.total)) * 100)) : null;
    btn.innerHTML = '<span class="led"></span><span class="copy"><span class="letter"></span><strong></strong><span class="path"></span><span class="meter" hidden><i></i></span></span><span class="tag"></span>';
    btn.querySelector(".letter").textContent = drive.id || drive.path || "";
    btn.querySelector("strong").textContent = title;
    btn.querySelector(".path").textContent = bits.filter(Boolean).join(" · ");
    btn.querySelector(".tag").textContent = drive.ready ? "READY" : "NOT READY";
    if (used != null) {
      var meter = btn.querySelector(".meter");
      meter.hidden = false;
      meter.querySelector("i").style.width = used.toFixed(0) + "%";
    }
    btn.addEventListener("click", function () {
      state.harness = "";
      state.drive = drive.id || "";
      state.viewed = true;
      showStage("sessions");
      document.getElementById("lead").textContent = title + " " + (drive.id || "");
      find(true);
    });
    return btn;
  }

  function paintPlaces(rec) {
    var homes = rec.homes || [];
    var present = homes.filter(function (h) { return h.present; });
    var absent = homes.filter(function (h) { return !h.present; });
    var places = document.getElementById("place-grid");
    var absentGrid = document.getElementById("absent-grid");
    var drives = document.getElementById("drive-grid");
    places.innerHTML = "";
    absentGrid.innerHTML = "";
    drives.innerHTML = "";
    present.forEach(function (home) { places.appendChild(placeCard(home)); });
    absent.forEach(function (home) { absentGrid.appendChild(placeCard(home)); });
    document.getElementById("absent-sum").textContent = "Not on this machine (" + absent.length + ")";
    (rec.drives || []).forEach(function (drive) { drives.appendChild(driveCard(drive)); });
    document.getElementById("lead").textContent =
      (rec.drives || []).length + " drives. " + present.length + " default locations present.";
  }

  function loadPlaces() {
    document.getElementById("lead").textContent = "Scanning drives and default locations…";
    fetch("/api/places").then(function (res) { return res.json(); }).then(function (rec) {
      paintPlaces(rec);
    }).catch(function (err) {
      document.getElementById("lead").textContent = "Could not scan drives. " + err;
    });
  }
  var list = document.getElementById("list");
  var count = document.getElementById("count");
  var chips = document.getElementById("harness");
  var say = document.getElementById("say");
  var out = document.getElementById("out");

  function show(rec, tone) {
    say.className = "say" + (tone ? " " + tone : "");
    say.textContent = sentence(rec);
    out.textContent = typeof rec === "string" ? rec : JSON.stringify(rec, null, 2);
  }

  function sentence(rec) {
    if (!rec || typeof rec === "string") return String(rec || "");
    if (rec.error) return rec.error + (rec.detail ? " — " + rec.detail : "");
    var g = rec.gate || {};
    if (rec.verb === "find") {
      return g.n + " sessions. Showing " + g.n_shown +
        (rec.legal_omitted ? ". Legal left closed: " + rec.legal_omitted : ".");
    }
    if (rec.verb === "resume") {
      if (g.argv && g.argv.length) return (g.launched ? "Launched. " : "") + g.argv.join(" ");
      return g.detail || rec.kind;
    }
    if (rec.verb === "import") {
      return rec.kind + (rec.written ? " — " + rec.written.jsonl : "");
    }
    if (rec.verb === "export") return rec.kind + (g.out ? " — " + g.out : "");
    if (rec.verb === "preview") {
      if (g.n_turns == null) return "First " + g.shown + " turns.";
      var line = "Showing " + g.shown + " of " + g.n_turns + " turns.";
      return rec.kind === "TRUNCATED" ? line + " The file ended early." : line;
    }
    if (rec.verb === "strip_dry") {
      return "Strip would keep " + g.kept + " turns and drop " + g.dropped_markers + ". Nothing was written.";
    }
    if (rec.verb === "strip") {
      var stripOut = rec.written && rec.written.jsonl;
      return "Stripped copy written. Original unchanged." + (stripOut ? " " + stripOut : "");
    }
    if (rec.verb === "anonymize") {
      var anonOut = rec.written && rec.written.jsonl;
      return "Anonymized copy written. " + (g.n_redactions || 0) + " redactions. Original unchanged." +
        (anonOut ? " " + anonOut : "");
    }
    if (rec.verb === "index") return "Index of " + g.n + (g.out ? " — " + g.out : "");
    if (rec.verb === "recover" || rec.verb === "crash-recover") {
      if (rec.kind === "ALREADY_OK") return "File checks out. Nothing was changed.";
      if (rec.kind === "NO_BAK") return "File needs a backup. None was found beside it, so it was left alone.";
      if (rec.kind === "DRY_RUN") return "A backup is ready. Nothing was copied.";
      if (rec.kind === "BUSY") return "The file is in use. Nothing was changed.";
      if (rec.kind === "OK") return "Restored from the backup." + (g.bak_path ? " " + g.bak_path : "") + " The previous file was staged.";
      return rec.kind;
    }
    return rec.kind || "done";
  }

  function when(stamp) {
    var n = Number(stamp);
    if (!n) return "";
    var ms = n > 100000000000 ? n : n * 1000;
    try { return new Date(ms).toLocaleString(); } catch (e) { return ""; }
  }

  function post(body) {
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

  function paintChips(families) {
    chips.innerHTML = "";
    var all = document.createElement("button");
    all.type = "button";
    all.className = "chip" + (state.harness ? "" : " on");
    all.textContent = "all";
    all.addEventListener("click", function () { state.harness = ""; find(); });
    chips.appendChild(all);
    (families || []).forEach(function (fam) {
      if (fam.status === "ABSENT") return;
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "chip" + (state.harness === fam.family ? " on" : "");
      var mark = fam.n == null ? (fam.status && fam.status !== "OK" ? " " + fam.status : "") : " " + fam.n;
      btn.textContent = fam.family + mark;
      btn.addEventListener("click", function () {
        state.harness = fam.family;
        find();
      });
      chips.appendChild(btn);
    });
  }

  function paintList(hits) {
    list.innerHTML = "";
    state.hits = hits || [];
    if (!state.hits.length) return;
    state.hits.forEach(function (hit) {
      var li = document.createElement("li");
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "row" + (state.selected && state.selected.id === hit.id ? " on" : "");
      var label = hit.legal ? "Legal — not opened" : (hit.title || hit.vendor_id || hit.id);
      btn.innerHTML = '<span class="harness"></span><span><strong></strong><br><span class="when"></span></span>';
      btn.querySelector(".harness").textContent = hit.harness;
      btn.querySelector("strong").textContent = label;
      btn.querySelector(".when").textContent = when(hit.updated);
      btn.addEventListener("click", function () { select(hit); });
      li.appendChild(btn);
      list.appendChild(li);
    });
  }

  function setDisabled(ids, disabled) {
    ids.forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.disabled = disabled;
    });
  }

  function paintPreview(rec) {
    var box = document.getElementById("preview");
    if (!rec || rec.error) {
      box.textContent = sentence(rec);
      return;
    }
    var turns = (rec.gate && rec.gate.turns) || [];
    if (!turns.length) {
      box.textContent = "No dialogue in this preview.";
      return;
    }
    box.textContent = turns.map(function (turn) {
      return (turn.role || "turn") + "\n" + (turn.text || "");
    }).join("\n\n");
  }

  function toneOf(rec) {
    if (!rec || typeof rec === "string" || rec.error) return "bad";
    var kind = rec.kind || "";
    if (kind === "TRUNCATED" || kind === "OPENWORK_FOCUS" || kind === "DRY_RUN") return "warn";
    if (kind === "OK" || kind === "LAUNCHED" || kind === "ALREADY_OK" || kind === "VERIFIED") return "good";
    return kind ? "bad" : "";
  }

  function endsWith(path, suffixes) {
    var text = String(path || "").toLowerCase();
    return suffixes.some(function (suffix) { return text.endsWith(suffix); });
  }

  function readable(hit) {
    if (!hit || hit.legal || !hit.path) return false;
    if (hit.harness === "openwork") return endsWith(hit.path, [".db", ".sqlite"]);
    if (hit.harness === "cowork") return endsWith(hit.path, [".md", ".txt", ".jsonl"]);
    return endsWith(hit.path, [".jsonl", ".json"]);
  }

  function restorable(hit) {
    return readable(hit) && hit.harness !== "openwork" && !endsWith(hit.path, [".db", ".sqlite"]);
  }

  function paintActions(hit) {
    if (!hit) {
      setDisabled(["resume", "launch", "import", "export", "recover", "restore", "strip-dry", "anonymize", "strip"], true);
      return;
    }
    setDisabled(["resume"], !!hit.legal);
    setDisabled(["import", "export", "strip-dry", "anonymize"], !readable(hit));
    setDisabled(["recover", "restore"], !restorable(hit));
    document.getElementById("strip").disabled = state.stripFor !== hit.id;
    if (hit.legal) document.getElementById("launch").disabled = true;
  }

  function clearSelection() {
    state.selected = null;
    state.stripFor = "";
    state.selectGen += 1;
    document.getElementById("d-title").textContent = "No session selected";
    document.getElementById("d-meta").textContent = "Choose one from the list. Legal sessions stay closed.";
    document.getElementById("d-cmd").hidden = true;
    document.getElementById("preview").textContent = "Select a session to preview it. Legal sessions stay closed.";
    paintActions(null);
  }

  function paintScope() {
    var box = document.getElementById("scope");
    if (!box) return;
    box.innerHTML = "";
    if (!state.drive) return;
    var btn = document.createElement("button");
    btn.type = "button";
    btn.className = "chip on";
    btn.textContent = "Drive " + state.drive + " \u00d7";
    btn.addEventListener("click", function () {
      state.drive = "";
      find(true);
    });
    box.appendChild(btn);
  }

  function select(hit) {
    var gen = ++state.selectGen;
    state.selected = hit;
    state.stripFor = "";
    document.getElementById("d-title").textContent = hit.legal
      ? "Legal session"
      : (hit.title || hit.vendor_id || hit.id);
    document.getElementById("d-meta").textContent = hit.harness + " · " + hit.id +
      (hit.legal ? "" : (hit.cwd ? " · " + hit.cwd : ""));
    document.getElementById("launch").disabled = true;
    paintActions(hit);
    document.getElementById("d-cmd").hidden = true;
    paintList(state.hits);
    if (hit.legal) {
      document.getElementById("preview").textContent = "Legal session stays closed.";
      show({ verb: "resume", kind: "LEGAL_OMITTED", gate: { detail: "Legal session stays closed." } }, "bad");
      return;
    }
    if (!readable(hit)) {
      document.getElementById("preview").textContent = "No transcript preview for this store.";
      showResume(false, true);
      return;
    }
    document.getElementById("preview").textContent = "Reading a short preview…";
    showResume(false, true);
    post({ action: "preview", id: hit.id }).then(function (rec) {
      if (gen !== state.selectGen || !state.selected || state.selected.id !== hit.id) return;
      show(rec, toneOf(rec));
      paintPreview(rec);
    }).catch(function (err) {
      if (gen !== state.selectGen) return;
      document.getElementById("preview").textContent = String(err);
    });
  }

  function selectedId() {
    return state.selected && state.selected.id;
  }

  function find(fresh) {
    var gen = ++state.findGen;
    count.textContent = "Looking…";
    post({
      action: "find",
      query: document.getElementById("q").value.trim(),
      harness: state.harness,
      drive: state.drive,
      limit: 40,
      fresh: !!fresh
    }).then(function (rec) {
      if (gen !== state.findGen) return;
      paintScope();
      if (rec.error || !rec.hits) {
        count.textContent = sentence(rec);
        return;
      }
      paintChips(rec.gate && rec.gate.families);
      paintList(rec.hits);
      count.textContent = sentence(rec);
      if (state.selected && !state.hits.some(function (hit) { return hit.id === state.selected.id; })) {
        clearSelection();
      }
    }).catch(function (err) {
      if (gen !== state.findGen) return;
      count.textContent = String(err);
    });
  }

  function showResume(launch, quiet) {
    var id = selectedId();
    if (!id) return;
    var gen = state.selectGen;
    post({ action: "resume", id: id, launch: !!launch }).then(function (rec) {
      if (gen !== state.selectGen || selectedId() !== id) return;
      if (!quiet) show(rec, toneOf(rec));
      var cmd = document.getElementById("d-cmd");
      var argv = rec.gate && rec.gate.argv;
      if (argv && argv.length) {
        cmd.hidden = false;
        cmd.textContent = argv.join(" ");
      } else {
        cmd.hidden = true;
      }
      var binary = rec.gate && rec.gate.binary;
      var blocked = rec.kind === "OPENWORK_FOCUS" || rec.kind === "LEGAL_OMITTED" || rec.kind === "UNMEASURED";
      document.getElementById("launch").disabled = !(binary && !blocked);
    }).catch(function (err) {
      if (!quiet && gen === state.selectGen) show(String(err), "bad");
    });
  }

  function act(action, extra, done) {
    var id = selectedId();
    if (!id) { show("Select a session first.", "bad"); return; }
    var gen = state.selectGen;
    var body = Object.assign({ action: action, id: id }, extra || {});
    if ((action === "recover" || action === "crash-recover") && state.selected && state.selected.path) {
      body.target = state.selected.path;
      body.path = state.selected.path;
      body.apply = action === "crash-recover";
    }
    post(body).then(function (rec) {
      if (gen !== state.selectGen || selectedId() !== id) return;
      show(rec, toneOf(rec));
      if (done) done(rec, id);
      paintActions(state.selected);
    }).catch(function (err) { show(String(err), "bad"); });
  }

  document.getElementById("q").addEventListener("keydown", function (ev) {
    if (ev.key === "Enter") find(false);
  });
  document.getElementById("q").addEventListener("search", function () { find(false); });
  document.getElementById("resume").addEventListener("click", function () { showResume(false); });
  document.getElementById("launch").addEventListener("click", function () { showResume(true); });
  document.getElementById("import").addEventListener("click", function () { act("import"); });
  document.getElementById("export").addEventListener("click", function () { act("export"); });
  document.getElementById("recover").addEventListener("click", function () { act("recover"); });
  document.getElementById("restore").addEventListener("click", function () {
    if (!restorable(state.selected)) return;
    if (!window.confirm("Replace this session file with the newest good backup beside it?")) return;
    act("crash-recover");
  });
  document.getElementById("strip-dry").addEventListener("click", function () {
    act("strip_dry", {}, function (rec, id) {
      if (rec && rec.verb === "strip_dry" && rec.kind === "OK" && selectedId() === id) {
        state.stripFor = id;
      }
    });
  });
  document.getElementById("strip").addEventListener("click", function () {
    if (state.stripFor !== selectedId()) {
      show("Check strip first. Nothing was written.", "bad");
      return;
    }
    act("strip");
  });
  document.getElementById("anonymize").addEventListener("click", function () { act("anonymize"); });
  document.getElementById("refresh").addEventListener("click", function () {
    showStage("overview");
    loadPlaces();
  });
  document.getElementById("nav-overview").addEventListener("click", function () {
    showStage("overview");
    loadPlaces();
  });
  document.getElementById("nav-sessions").addEventListener("click", function () {
    showStage("sessions");
    if (!state.viewed) find(true);
    state.viewed = true;
  });
  document.getElementById("quit").addEventListener("click", function () {
    document.getElementById("lead").textContent = "Sessions closed. You can close this tab.";
    fetch("/api/shutdown", { method: "POST" }).catch(function () {});
    show("Sessions closed.");
    document.querySelectorAll("button").forEach(function (btn) { btn.disabled = true; });
  });
  document.getElementById("index").addEventListener("click", function () {
    document.getElementById("lead").textContent = "Building the index…";
    count.textContent = "Building the index…";
    post({ action: "index" }).then(function (rec) {
      show(rec, toneOf(rec));
      var line = sentence(rec);
      count.textContent = line;
      document.getElementById("lead").textContent = line;
    }).catch(function (err) {
      show(String(err), "bad");
      document.getElementById("lead").textContent = String(err);
    });
  });

  showStage("overview");
  loadPlaces();
})();
