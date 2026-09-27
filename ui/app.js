(function () {
  var state = { harness: "", hits: [], selected: null };
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
    if (rec.verb === "index") return "Index of " + g.n + (g.out ? " — " + g.out : "");
    if (rec.verb === "recover" || rec.verb === "crash-recover") {
      if (rec.kind === "ALREADY_OK") return "File checks out. Nothing was changed.";
      if (rec.kind === "NO_BAK") return "File needs a backup. None was found beside it, so it was left alone.";
      if (rec.kind === "DRY_RUN") return "A backup is ready. Nothing was copied.";
      if (rec.kind === "OK") return "Restored from the backup. The previous file was staged.";
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
      if (fam.n == null && fam.status !== "OK") return;
      var btn = document.createElement("button");
      btn.type = "button";
      btn.className = "chip" + (state.harness === fam.family ? " on" : "");
      btn.textContent = fam.family + (fam.n == null ? "" : " " + fam.n);
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
    if (!state.hits.length) {
      count.textContent = "No sessions in this view.";
      return;
    }
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

  function select(hit) {
    state.selected = hit;
    document.getElementById("d-title").textContent = hit.legal
      ? "Legal session"
      : (hit.title || hit.vendor_id || hit.id);
    document.getElementById("d-meta").textContent = hit.harness + " · " + hit.id +
      (hit.legal ? "" : (hit.cwd ? " · " + hit.cwd : ""));
    ["resume", "launch", "import", "export", "recover"].forEach(function (id) {
      document.getElementById(id).disabled = false;
    });
    document.getElementById("d-cmd").hidden = true;
    paintList(state.hits);
    if (!hit.legal) showResume(false);
    else show({ verb: "resume", kind: "LEGAL_OMITTED", gate: { detail: "Legal session stays closed." } }, "bad");
  }

  function selectedId() {
    return state.selected && state.selected.id;
  }

  function find() {
    count.textContent = "Looking…";
    post({
      action: "find",
      query: document.getElementById("q").value.trim(),
      harness: state.harness,
      limit: 40
    }).then(function (rec) {
      show(rec, rec.error ? "bad" : "");
      if (rec.hits) {
        paintChips(rec.gate && rec.gate.families);
        paintList(rec.hits);
        count.textContent = sentence(rec);
      }
    }).catch(function (err) {
      count.textContent = String(err);
      show(String(err), "bad");
    });
  }

  function showResume(launch) {
    var id = selectedId();
    if (!id) return;
    post({ action: "resume", id: id, launch: !!launch }).then(function (rec) {
      show(rec, rec.error || rec.kind === "LEGAL_OMITTED" ? "bad" : "good");
      var cmd = document.getElementById("d-cmd");
      var argv = rec.gate && rec.gate.argv;
      if (argv && argv.length) {
        cmd.hidden = false;
        cmd.textContent = argv.join(" ");
      }
    }).catch(function (err) { show(String(err), "bad"); });
  }

  function act(action, extra) {
    var id = selectedId();
    if (!id) { show("Select a session first.", "bad"); return; }
    var body = Object.assign({ action: action, id: id }, extra || {});
    if (action === "recover" && state.selected && state.selected.path) {
      body.target = state.selected.path;
      body.path = state.selected.path;
      body.apply = false;
    }
    post(body).then(function (rec) {
      show(rec, rec.error ? "bad" : "good");
    }).catch(function (err) { show(String(err), "bad"); });
  }

  document.getElementById("q").addEventListener("keydown", function (ev) {
    if (ev.key === "Enter") find();
  });
  document.getElementById("resume").addEventListener("click", function () { showResume(false); });
  document.getElementById("launch").addEventListener("click", function () { showResume(true); });
  document.getElementById("import").addEventListener("click", function () { act("import"); });
  document.getElementById("export").addEventListener("click", function () { act("export"); });
  document.getElementById("recover").addEventListener("click", function () { act("recover"); });
  document.getElementById("index").addEventListener("click", function () {
    count.textContent = "Building the index…";
    post({ action: "index" }).then(function (rec) {
      show(rec, rec.error ? "bad" : "good");
      count.textContent = sentence(rec);
    }).catch(function (err) { show(String(err), "bad"); });
  });

  find();
})();
