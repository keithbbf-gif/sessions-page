/* Local settings only.
   localStorage key: cmSessions.settings
   Shape: { theme: "dark"|"light", rowDensity: "compact"|"regular"|"comfortable", pageSize: 25|50|100|200 }
   Reads legacy "density" if "rowDensity" is absent. Does not write it.
   Calls window.cmPersistSettings(settings, key) when that function exists.
*/
(function () {
  var KEY = "cmSessions.settings";
  var THEMES = { dark: 1, light: 1 };
  var DENSITIES = { compact: 1, regular: 1, comfortable: 1 };
  var PAGE_SIZES = { 25: 1, 50: 1, 100: 1, 200: 1 };
  // Default page size is 100, not 250.
  var DEFAULTS = { theme: "dark", rowDensity: "regular", pageSize: 100 };

  function numericPageSize(value) {
    if (typeof value === "number" && isFinite(value) && value === Math.floor(value)) return value;
    if (typeof value === "string" && /^\d+$/.test(value.trim())) return Number(value.trim());
    return null;
  }

  function clone(src) {
    return {
      theme: src.theme,
      rowDensity: src.rowDensity,
      pageSize: src.pageSize
    };
  }

  function normalize(raw) {
    var src = raw && typeof raw === "object" && !Array.isArray(raw) ? raw : {};
    var theme = String(src.theme == null ? "" : src.theme).toLowerCase();
    var densitySource = src.rowDensity != null ? src.rowDensity : src.density;
    var density = String(densitySource == null ? "" : densitySource).toLowerCase();
    var pageSize = numericPageSize(src.pageSize);
    if (!THEMES[theme]) theme = DEFAULTS.theme;
    if (!DENSITIES[density]) density = DEFAULTS.rowDensity;
    if (pageSize == null || !PAGE_SIZES[pageSize]) pageSize = DEFAULTS.pageSize;
    return { theme: theme, rowDensity: density, pageSize: pageSize };
  }

  function readRaw() {
    var raw;
    try {
      raw = localStorage.getItem(KEY);
    } catch (err) {
      return { value: null, found: false, bad: true, text: null };
    }
    if (raw == null || raw === "") return { value: null, found: false, bad: false, text: raw };
    try {
      var parsed = JSON.parse(raw);
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
        return { value: null, found: false, bad: true, text: raw };
      }
      return { value: parsed, found: true, bad: false, text: raw };
    } catch (err) {
      return { value: null, found: false, bad: true, text: raw };
    }
  }

  function paint(settings) {
    var root = document.documentElement;
    if (!root) return;
    root.setAttribute("data-theme", settings.theme);
    root.setAttribute("data-density", settings.rowDensity);
    root.setAttribute("data-page-size", String(settings.pageSize));
    root.style.colorScheme = settings.theme;
  }

  function writeLocal(settings) {
    try {
      localStorage.setItem(KEY, JSON.stringify(settings));
      return true;
    } catch (err) {
      return false;
    }
  }

  function callPersist(settings) {
    var fn = window.cmPersistSettings;
    if (typeof fn !== "function") return false;
    try {
      var result = fn(clone(settings), KEY);
      if (result && typeof result.then === "function") {
        result.then(function () {}, function () {});
      }
      return true;
    } catch (err) {
      return false;
    }
  }

  function sentence(settings) {
    var theme = settings.theme === "light" ? "Light" : "Dark";
    var density = settings.rowDensity.charAt(0).toUpperCase() + settings.rowDensity.slice(1);
    return theme + " theme. " + density + " row density. " + settings.pageSize + " rows per page.";
  }

  function setStatus(text) {
    var node = document.getElementById("status");
    if (node) node.textContent = text;
  }

  function syncForm() {
    var form = document.getElementById("settings-form");
    if (!form) return;
    var fields = ["theme", "rowDensity", "pageSize"];
    var i;
    for (i = 0; i < fields.length; i += 1) {
      var name = fields[i];
      var value = String(current[name]);
      var input = form.querySelector('input[name="' + name + '"][value="' + value + '"]');
      if (input) input.checked = true;
    }
    var readout = document.getElementById("page-readout");
    if (readout) readout.textContent = sentence(current);
  }

  function readForm() {
    var form = document.getElementById("settings-form");
    var next = clone(current);
    if (!form) return next;
    var theme = form.querySelector('input[name="theme"]:checked');
    var density = form.querySelector('input[name="rowDensity"]:checked');
    var pageSize = form.querySelector('input[name="pageSize"]:checked');
    if (theme) next.theme = theme.value;
    if (density) next.rowDensity = density.value;
    if (pageSize) next.pageSize = pageSize.value;
    return next;
  }

  var loaded = readRaw();
  var current = normalize(loaded.value);
  paint(current);
  if (loaded.found && loaded.text !== JSON.stringify(current)) writeLocal(current);

  function commit(next, opts) {
    opts = opts || {};
    var incoming = next && typeof next === "object" ? next : {};
    if (incoming.pageSize != null && numericPageSize(incoming.pageSize) == null) {
      var kept = {
        theme: incoming.theme != null ? incoming.theme : current.theme,
        pageSize: current.pageSize
      };
      if (incoming.rowDensity != null) kept.rowDensity = incoming.rowDensity;
      else if (incoming.density != null) kept.density = incoming.density;
      else kept.rowDensity = current.rowDensity;
      incoming = kept;
    }
    current = normalize(incoming);
    paint(current);
    var saved = true;
    if (!opts.skipWrite) saved = writeLocal(current);
    if (!opts.skipPersist) callPersist(current);
    if (!opts.skipEvent) {
      try {
        window.dispatchEvent(new CustomEvent("cmSessions:settings", { detail: clone(current) }));
      } catch (err) {}
    }
    syncForm();
    return { settings: clone(current), saved: saved };
  }

  function loadStatus() {
    if (loaded.bad) return "Stored settings were unreadable. Defaults are showing.";
    if (loaded.found) return "Saved on this machine.";
    return "Defaults are in use. Changes save on this machine.";
  }

  function onReady() {
    var form = document.getElementById("settings-form");
    syncForm();
    setStatus(loadStatus());
    callPersist(current);
    if (!form) return;
    form.addEventListener("change", function () {
      var result = commit(readForm());
      setStatus(result.saved
        ? "Saved on this machine."
        : "Showing this choice here. The browser did not store it.");
    });
    var reset = document.getElementById("reset-settings");
    if (reset) {
      reset.addEventListener("click", function () {
        var result = commit(DEFAULTS);
        setStatus(result.saved
          ? "Defaults restored on this machine."
          : "Defaults are showing. The browser did not store them.");
      });
    }
    window.addEventListener("storage", function (event) {
      if (event.key !== KEY) return;
      if (!event.newValue) {
        commit(null, { skipWrite: true, skipPersist: true });
        setStatus("Settings were cleared in another view.");
        return;
      }
      try {
        var parsed = JSON.parse(event.newValue);
        if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) throw new Error("shape");
        commit(parsed, { skipWrite: true, skipPersist: true });
        setStatus("Updated from another view on this machine.");
      } catch (err) {
        setStatus("Another view wrote settings this page could not read.");
      }
    });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", onReady);
  else onReady();

  window.cmSessionsSettings = {
    key: KEY,
    defaults: clone(DEFAULTS),
    themes: ["dark", "light"],
    rowDensities: ["compact", "regular", "comfortable"],
    pageSizes: [25, 50, 100, 200],
    get: function () { return clone(current); },
    set: function (partial) {
      var merged = clone(current);
      var rejectedPageSize = false;
      if (partial && typeof partial === "object") {
        if (partial.theme != null) merged.theme = partial.theme;
        if (partial.rowDensity != null) merged.rowDensity = partial.rowDensity;
        else if (partial.density != null) merged.rowDensity = partial.density;
        if (partial.pageSize != null) {
          if (numericPageSize(partial.pageSize) == null) rejectedPageSize = true;
          else merged.pageSize = partial.pageSize;
        }
      }
      var saved = commit(merged).settings;
      if (rejectedPageSize) setStatus("Page size must be a number.");
      return saved;
    },
    save: function (partial) {
      if (partial == null) return commit(current).settings;
      return this.set(partial);
    },
    reset: function () { return commit(DEFAULTS).settings; }
  };
})();
