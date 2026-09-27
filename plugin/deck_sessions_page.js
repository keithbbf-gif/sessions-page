/* Later plug. One script tag. Does not edit app.js, header.js, or Mesh #win.
   Talks to the standalone sessions page on 127.0.0.1:8786.
   Mounts only when #panel-sessions-page is already on the page. */
(function () {
  var HOST = "http://127.0.0.1:8786";

  function paint(host, text) {
    var pre = host.querySelector("pre");
    if (!pre) {
      pre = document.createElement("pre");
      host.appendChild(pre);
    }
    pre.textContent = text;
  }

  function mount() {
    var host = document.getElementById("panel-sessions-page");
    if (!host || host.getAttribute("data-sessions-page") === "1") return;
    host.setAttribute("data-sessions-page", "1");
    var bar = document.createElement("div");
    ["find", "index", "resume"].forEach(function (action) {
      var btn = document.createElement("button");
      btn.type = "button";
      btn.textContent = action;
      btn.addEventListener("click", function () {
        fetch(HOST + "/api/run", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ action: action, limit: 50 })
        }).then(function (res) { return res.json(); }).then(function (rec) {
          paint(host, JSON.stringify(rec, null, 2));
        }).catch(function (err) {
          paint(host, "sessions page offline (" + HOST + ") — " + err);
        });
      });
      bar.appendChild(btn);
    });
    host.appendChild(bar);
    paint(host, "Sessions page tools. Start sessions_page.py serve, then use these buttons.");
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mount);
  } else {
    mount();
  }
})();
