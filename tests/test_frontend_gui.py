#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Headless Playwright walk of the sessions page.

Starts an ephemeral loopback ``sessions_page._serve`` against fixture homes,
then drives Edge (or the packaged headless shell) through the live UI.
Screenshots land in ``var/gui_verify/``.
"""
from __future__ import annotations

import json
import os
import shutil
import socket
import sys
import threading
import urllib.error
import urllib.request
import uuid
from datetime import date
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parents[1]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
SHOTS = HERE / "var" / "gui_verify"
EDGE_SHELL = (
    r"V:\pkg-cache\ms-playwright\chromium_headless_shell-1255"
    r"\chrome-headless-shell-win64\chrome-headless-shell.exe"
)
TAILWIND_URL = "https://www.gstatic.com/antigravity/web/dev/tailwindcss.min.js"

GROK_NORMAL = "11111111-1111-4111-8111-111111111111"
GROK_CEILING = "22222222-2222-4222-8222-222222222222"
CLAUDE_TOOL = "33333333-3333-4333-8333-333333333333"
CLAUDE_LEGAL = "44444444-4444-4444-8444-444444444444"
CODEX_ID = "55555555-5555-4555-8555-555555555555"

TITLE_NORMAL = "Grok Normal Twenty Five"
TITLE_CEILING = "Grok Over Ceiling"
TITLE_CLAUDE = "Claude tool session"
TITLE_CODEX = "Codex rollout fixture"
TITLE_RENAMED = "Grok Renamed Persist"
TAG_CUSTOM = "#gui-persist"
GOAL_TEXT = "GUI Persist Goal"
TRIGGER_TEXT = "GUI Persist Trigger"
LEGAL_SECRET = "Legal Case Brief"
BRIEF_MARK = "secret docket line"

MONTHS = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)
MONTHS_SHORT = (
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
)
SOLARO_TABS = ("account", "usage", "logs", "billing", "settings", "keys", "models")
PROMISES = (
    "essentials free forever",
    "toll-free under $100/mo",
    "provider discounts pass at full value",
    "data opt-in, anonymized, never sold",
)
OPTIONAL_HOSTS = (
    "gstatic.com",
    "fonts.googleapis.com",
    "fonts.gstatic.com",
    "mdata.modelraters.com",
    "tailwindcss",
    "favicon.ico",
)


def _under(path: str, root: Path) -> bool:
    try:
        Path(path).resolve().relative_to(root.resolve())
    except (OSError, ValueError):
        return False
    return True


def _write_exact(path: Path, header: str, target: int) -> None:
    """Pad a jsonl so ``len(bytes) / 4`` is an exact token estimate."""
    head = header.encode("utf-8")
    prefix = b'{"type":"user","text":"'
    suffix = b'"}\n'
    gap = target - len(head) - len(prefix) - len(suffix)
    if gap < 1:
        raise RuntimeError(f"header does not fit in {target} bytes")
    path.write_bytes(head + prefix + (b"x" * gap) + suffix)
    if path.stat().st_size != target:
        raise RuntimeError(f"size {path.stat().st_size} != {target}")


def _fixture(root: Path) -> None:
    normal = root / "grok" / "normal"
    normal.mkdir(parents=True)
    (normal / "summary.json").write_text(json.dumps({
        "info": {
            "id": GROK_NORMAL,
            "cwd": r"V:\work\gui-normal",
            "generated_title": TITLE_NORMAL,
            "current_model_id": "grok-test",
        }
    }), encoding="utf-8")
    _write_exact(
        normal / "chat_history.jsonl",
        '{"type":"user","text":"hello grok normal"}\n'
        '{"type":"assistant","text":"hi from grok"}\n',
        25_000 * 4,
    )

    ceiling = root / "grok" / "ceiling"
    ceiling.mkdir(parents=True)
    (ceiling / "summary.json").write_text(json.dumps({
        "info": {
            "id": GROK_CEILING,
            "cwd": r"V:\work\gui-ceiling",
            "generated_title": TITLE_CEILING,
            "current_model_id": "grok-test",
        }
    }), encoding="utf-8")
    _write_exact(
        ceiling / "chat_history.jsonl",
        '{"type":"user","text":"hello grok ceiling"}\n'
        '{"type":"assistant","text":"this session is over the hard stop"}\n',
        194_000 * 4,
    )

    tool = root / "claude" / "projects" / "gui-tools"
    tool.mkdir(parents=True)
    (tool / f"{CLAUDE_TOOL}.jsonl").write_text(
        "\n".join([
            json.dumps({
                "type": "user",
                "cwd": r"V:\work\gui-tools",
                "message": {"role": "user", "content": [{"type": "text", "text": TITLE_CLAUDE}]},
            }),
            json.dumps({
                "type": "assistant",
                "message": {"role": "assistant", "content": [{"type": "text", "text": "Running a tool."}]},
            }),
            json.dumps({
                "type": "tool_use",
                "message": {"role": "assistant", "content": [{"type": "text", "text": "Read the session notes"}]},
            }),
            json.dumps({
                "type": "tool_result",
                "message": {"role": "user", "content": [{"type": "text", "text": "notes are ready"}]},
            }),
        ]) + "\n",
        encoding="utf-8",
    )

    legal = root / "claude" / "projects" / "Legal_Vault"
    legal.mkdir(parents=True)
    (legal / f"{CLAUDE_LEGAL}.jsonl").write_text(
        json.dumps({
            "type": "user",
            "cwd": r"V:\Legal_Vault\case",
            "stream": "legal",
            "message": {
                "role": "user",
                "content": [{"type": "text", "text": f"{LEGAL_SECRET} {BRIEF_MARK}"}],
            },
        }) + "\n",
        encoding="utf-8",
    )

    codex = root / "codex" / "sessions" / "2026" / "11" / "19"
    codex.mkdir(parents=True)
    (codex / f"rollout-2026-11-19T12-00-00-{CODEX_ID}.jsonl").write_text(
        json.dumps({
            "type": "session_meta",
            "payload": {"id": CODEX_ID, "cwd": r"V:\work\codex", "source": "cli"},
        }) + "\n"
        + json.dumps({
            "type": "response_item",
            "payload": {
                "role": "user",
                "content": [{"type": "input_text", "text": TITLE_CODEX}],
            },
        }) + "\n",
        encoding="utf-8",
    )


def _free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = int(sock.getsockname()[1])
    sock.close()
    return port


def _post(port: int, path: str, body: dict | None = None, headers: dict | None = None, timeout: float = 30):
    data = json.dumps(body or {}).encode("utf-8")
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}",
        data=data,
        method="POST",
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            raw = res.read()
            return res.status, json.loads(raw.decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            payload = json.loads(raw.decode("utf-8") or "{}")
        except ValueError:
            payload = {"raw": raw.decode("utf-8", errors="replace")}
        return exc.code, payload


def _get(port: int, path: str, timeout: float = 20):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}{path}", timeout=timeout) as res:
        return res.status, json.loads(res.read().decode("utf-8"))


def _wait_server(port: int) -> None:
    last = "not up"
    for _ in range(80):
        try:
            status, body = _get(port, "/api/verbs", timeout=0.5)
        except (OSError, urllib.error.URLError, TimeoutError, ValueError) as exc:
            last = str(exc)
            threading.Event().wait(0.05)
            continue
        verbs = body.get("verbs") if isinstance(body, dict) else None
        if status == 200 and isinstance(verbs, list) and "find" in verbs:
            return
        last = str(body)[:180]
        threading.Event().wait(0.05)
    raise RuntimeError(f"server did not answer /api/verbs: {last}")


def _prefetch_tailwind() -> bytes | None:
    try:
        req = urllib.request.Request(TAILWIND_URL, headers={"User-Agent": "cmSessions-gui-test"})
        with urllib.request.urlopen(req, timeout=8) as res:
            data = res.read()
    except (OSError, urllib.error.URLError, TimeoutError, ValueError):
        return None
    if len(data) < 1000:
        return None
    return data


def _optional_url(url: str) -> bool:
    low = (url or "").lower()
    return any(host in low for host in OPTIONAL_HOSTS)


class Watch:
    """Page errors, unexpected console errors, and unexpected HTTP statuses."""

    def __init__(self) -> None:
        self.pageerrors: list[str] = []
        self.console: list[str] = []
        self.http: list[str] = []
        self.allow_places_500 = False

    def attach(self, page) -> None:
        page.on("pageerror", lambda exc: self.pageerrors.append(str(exc)))
        page.on("console", self._on_console)
        page.on("response", self._on_response)
        page.on("dialog", lambda dialog: dialog.dismiss())

    def _on_console(self, msg) -> None:
        if msg.type != "error":
            return
        text = msg.text or ""
        loc = ""
        try:
            loc = str((msg.location or {}).get("url") or "")
        except Exception:
            loc = ""
        blob = f"{text} {loc}".strip()
        if _optional_url(blob):
            return
        # Chromium logs failed fetches here. HTTP status is judged separately,
        # including the intentional 403, legal 400, and places 500.
        if text.startswith("Failed to load resource"):
            return
        self.console.append(blob)

    def _on_response(self, res) -> None:
        status = int(res.status)
        if status < 400:
            return
        url = res.url or ""
        if _optional_url(url):
            return
        path = url.split("?", 1)[0]
        if path.endswith("/favicon.ico"):
            return
        if path.endswith("/api/shutdown") and status == 403:
            return
        if path.endswith("/api/run") and status == 400:
            return
        if path.endswith("/api/places") and status == 500 and self.allow_places_500:
            return
        self.http.append(f"{status} {url}")

    def assert_clean(self, step: str) -> None:
        assert not self.pageerrors, f"{step} pageerrors: {self.pageerrors}"
        assert not self.console, f"{step} console errors: {self.console}"
        assert not self.http, f"{step} unexpected HTTP: {self.http}"


def _launch(p):
    """Edge channel, then the packaged headless shell, then default Chromium."""
    errors = []
    try:
        return p.chromium.launch(channel="msedge", headless=True), "msedge"
    except Exception as exc:
        errors.append(f"msedge: {exc}")
    if os.path.isfile(EDGE_SHELL):
        try:
            return p.chromium.launch(executable_path=EDGE_SHELL, headless=True), "headless-shell"
        except Exception as exc:
            errors.append(f"shell: {exc}")
    try:
        return p.chromium.launch(headless=True), "chromium"
    except Exception as exc:
        errors.append(f"chromium: {exc}")
    raise RuntimeError("browser launch failed: " + " | ".join(errors))


def _homes_for(root: Path):
    import engine

    def homes() -> dict:
        out = {name: None for name in engine.HARNESSES}
        out["grok"] = root / "grok"
        out["claude"] = root / "claude" / "projects"
        out["codex"] = root / "codex"
        return out

    return homes


def _install_routes(context, tailwind: bytes | None) -> None:
    """Stub optional CDNs. Leave the loopback page itself unrouted.

    A catch-all ``route.continue_()`` rewrote a later navigation as ``{}GET``
    and the page server answered 501.
    """
    def gstatic(route) -> None:
        if tailwind and "tailwindcss" in route.request.url:
            route.fulfill(
                status=200,
                content_type="text/javascript; charset=utf-8",
                body=tailwind,
            )
            return
        route.abort()

    context.route("**gstatic.com/**", gstatic)
    context.route("**fonts.googleapis.com/**", lambda route: route.abort())
    context.route("**mdata.modelraters.com/**", lambda route: route.abort())
    context.route("**/favicon.ico", lambda route: route.fulfill(status=204, body=b""))


class App:
    def __init__(self, port: int, root: Path, browser, context, page, watch: Watch, kind: str):
        self.port = port
        self.root = root
        self.browser = browser
        self.context = context
        self.page = page
        self.watch = watch
        self.kind = kind
        self.base = f"http://127.0.0.1:{port}"

    def goto(self, path: str):
        self.page.goto(self.base + path, wait_until="domcontentloaded", timeout=45000)
        return self.page


@pytest.fixture(scope="module")
def app():
    import engine
    import sessions_page
    from playwright.sync_api import sync_playwright

    root = Path(os.environ.get("TEMP") or os.environ.get("TMP") or ".") / f"cms_gui_{uuid.uuid4().hex[:8]}"
    if root.exists():
        shutil.rmtree(root, ignore_errors=True)
    root.mkdir(parents=True)
    _fixture(root)

    original_homes = engine.default_homes
    engine.default_homes = _homes_for(root)
    old_env = {
        "CMSESSIONS_TEST_MODE": os.environ.get("CMSESSIONS_TEST_MODE"),
        "CMSESSIONS_NO_PREWARM": os.environ.get("CMSESSIONS_NO_PREWARM"),
    }
    os.environ["CMSESSIONS_TEST_MODE"] = "1"
    os.environ["CMSESSIONS_NO_PREWARM"] = "1"

    port = _free_port()
    holder: dict = {}

    def serve() -> None:
        holder["rc"] = sessions_page._serve(port, open_browser=False)

    thread = threading.Thread(target=serve, name="cmsessions-gui", daemon=True)
    thread.start()

    playwright = None
    browser = None
    context = None
    try:
        _wait_server(port)
        status, found = _post(port, "/api/run", {"action": "find", "limit": 50})
        assert status == 200, found
        hits = found.get("hits") or []
        assert len(hits) == 5, [(h.get("title"), h.get("harness"), h.get("legal")) for h in hits]
        for hit in hits:
            assert _under(hit.get("path") or "", root), hit.get("path")
        titles = {h.get("title") for h in hits}
        assert TITLE_NORMAL in titles
        assert TITLE_CEILING in titles
        assert TITLE_CLAUDE in titles
        assert TITLE_CODEX in titles
        assert LEGAL_SECRET not in titles
        assert found.get("legal_omitted", 0) >= 1
        legal_hits = [h for h in hits if h.get("legal")]
        assert len(legal_hits) == 1 and legal_hits[0].get("title") == ""
        ceiling = next(h for h in hits if h.get("title") == TITLE_CEILING)
        normal = next(h for h in hits if h.get("title") == TITLE_NORMAL)
        assert ceiling.get("bytes") == 194_000 * 4
        assert normal.get("bytes") == 25_000 * 4
        claude = next(h for h in hits if h.get("title") == TITLE_CLAUDE)
        preview_status, preview = _post(port, "/api/run", {
            "action": "preview", "id": claude["id"], "turns": 20, "chars": 500,
        })
        assert preview_status == 200, preview
        roles = [t.get("role") for t in (preview.get("gate") or {}).get("turns") or []]
        assert "tool_call" in roles and "tool_result" in roles, roles
        legal_status, legal_body = _post(port, "/api/run", {
            "action": "preview", "id": legal_hits[0]["id"], "turns": 10, "chars": 400,
        })
        assert legal_status == 400, legal_body
        assert legal_body.get("error") == "LEGAL_OMITTED"
        assert LEGAL_SECRET not in json.dumps(legal_body)
        places_status, places = _get(port, "/api/places")
        assert places_status == 200 and isinstance(places.get("drives"), list)

        tailwind = _prefetch_tailwind()
        playwright = sync_playwright().start()
        browser, kind = _launch(playwright)
        context = browser.new_context(
            viewport={"width": 1800, "height": 1000},
            ignore_https_errors=True,
        )
        _install_routes(context, tailwind)
        page = context.new_page()
        page.set_default_timeout(20000)
        watch = Watch()
        watch.attach(page)
        yield App(port, root, browser, context, page, watch, kind)
    finally:
        if context is not None:
            try:
                context.close()
            except Exception:
                pass
        if browser is not None:
            try:
                browser.close()
            except Exception:
                pass
        if playwright is not None:
            try:
                playwright.stop()
            except Exception:
                pass
        try:
            _post(port, "/api/shutdown", {}, timeout=3)
        except Exception:
            pass
        thread.join(8)
        engine.default_homes = original_homes
        for key, value in old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        shutil.rmtree(root, ignore_errors=True)


def _wait_row(page, text: str, timeout: int = 30000) -> None:
    """Session titles also sit in hidden tabs. Wait for the ledger copy."""
    page.locator("#alignedRowsHost").get_by_text(text, exact=True).first.wait_for(
        state="visible", timeout=timeout,
    )


def _click_visible(page, text: str) -> None:
    loc = page.get_by_text(text, exact=True)
    count = loc.count()
    for i in range(count):
        item = loc.nth(i)
        try:
            if item.is_visible():
                item.click()
                return
        except Exception:
            continue
    raise AssertionError(f"no visible text {text!r} ({count} matches)")


def _shot(page, name: str) -> None:
    SHOTS.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(SHOTS / name), full_page=False)


def test_frontend_gui(app: App) -> None:
    page = app.page
    watch = app.watch
    today = date.today()
    month_title = f"{MONTHS[today.month - 1].upper()} {today.year}"
    day_label = f"{MONTHS_SHORT[today.month - 1]} {today.day}"

    page.goto(app.base + "/", wait_until="domcontentloaded", timeout=45000)
    page.evaluate("() => localStorage.clear()")
    page.reload(wait_until="domcontentloaded")
    _wait_row(page, TITLE_NORMAL)
    _wait_row(page, TITLE_CODEX)

    token = page.locator('meta[name="cm-token"]').get_attribute("content") or ""
    assert len(token) == 48 and all(c in "0123456789abcdefABCDEF" for c in token)
    forged = page.evaluate(
        """async () => {
          const res = await fetch('/api/shutdown', {
            method: 'POST',
            headers: {'Origin': 'http://evil.local', 'Content-Type': 'application/json'},
            body: '{}'
          });
          return res.status;
        }"""
    )
    assert forged == 403, forged
    assert page.get_by_text(TITLE_NORMAL).count() > 0
    pill = page.locator("#harnessPill")
    assert pill.inner_text().strip() == "No harness detected — Install cmCode"
    assert pill.is_hidden()
    watch.assert_clean("boot")

    page.goto(app.base + "/settings.html", wait_until="domcontentloaded")
    page.wait_for_selector("#settings-form")
    assert page.locator("html").get_attribute("data-page-size") == "100"
    assert page.locator('meta[name="cm-token"]').count() == 1
    page.locator("#theme-light").check()
    page.locator("#density-compact").check()
    page.locator("#page-size-25").check()
    page.wait_for_function(
        """() => {
          const raw = localStorage.getItem('cmSessions.settings');
          if (!raw) return false;
          const data = JSON.parse(raw);
          return data.theme === 'light' && data.rowDensity === 'compact' && data.pageSize === 25;
        }"""
    )
    stored = json.loads(page.evaluate("() => localStorage.getItem('cmSessions.settings')"))
    assert stored == {"theme": "light", "rowDensity": "compact", "pageSize": 25}
    assert page.locator("html").get_attribute("data-theme") == "light"
    assert page.locator("html").get_attribute("data-density") == "compact"
    assert page.locator("html").get_attribute("data-page-size") == "25"

    page.goto(app.base + "/", wait_until="domcontentloaded")
    _wait_row(page, TITLE_NORMAL)
    html = page.locator("html")
    assert html.get_attribute("data-theme") == "light"
    assert html.get_attribute("data-density") == "compact"
    assert html.get_attribute("data-page-size") == "25"
    assert page.evaluate("() => pageSize()") == 25
    row_style = page.locator("#alignedRowsHost > div").first.get_attribute("style") or ""
    assert "26px" in row_style
    slice_text = page.locator("#pageSlice").inner_text()
    assert "of 5" in slice_text
    assert page.locator("#pageLabel").inner_text().startswith("Page ")
    table_text = page.locator("#alignedRowsHost").inner_text()
    assert "$0.05 est" in table_text
    assert TITLE_CEILING in table_text
    watch.assert_clean("theme density cost")

    page.goto(app.base + "/settings.html", wait_until="domcontentloaded")
    page.locator("#reset-settings").click()
    page.wait_for_function(
        """() => {
          const data = JSON.parse(localStorage.getItem('cmSessions.settings') || '{}');
          return data.theme === 'dark' && data.rowDensity === 'regular' && data.pageSize === 100;
        }"""
    )
    _shot(page, "settings.png")
    page.goto(app.base + "/", wait_until="domcontentloaded")
    _wait_row(page, TITLE_NORMAL)
    assert page.locator("html").get_attribute("data-theme") == "dark"
    assert page.locator("html").get_attribute("data-density") == "regular"
    page.locator("#topBtnTable").click()
    _shot(page, "fullscreen_table.png")
    watch.assert_clean("reset table")

    _click_visible(page, TITLE_CLAUDE)
    page.wait_for_function(
        """() => {
          const pane = document.getElementById('activeSessionPane');
          return pane && pane.innerText.includes('Tool Action');
        }"""
    )
    pane = page.locator("#activeSessionPane").inner_text()
    assert "Tool Action" in pane
    assert "\u2699" in pane
    assert "notes are ready" in pane or "Tool Result" in pane
    options = " | ".join(page.locator("#handoffPicker option").all_inner_texts())
    assert "Claude" in options and "Grok" in options and "Codex" in options
    watch.assert_clean("claude tool card")

    page.locator("#topBtnTable").click()
    _click_visible(page, TITLE_CEILING)
    page.wait_for_function(
        """() => {
          const pane = document.getElementById('activeSessionPane');
          return pane && pane.innerText.includes('180k') && pane.innerText.includes('Hand Off');
        }"""
    )
    ceiling_html = page.locator("#activeSessionPane").inner_html()
    ceiling_text = page.locator("#activeSessionPane").inner_text()
    assert "180k Hard Ceiling" in ceiling_html
    assert "Primary Action" in ceiling_text
    assert "Hand Off" in ceiling_text
    assert "Force Resume" in ceiling_text
    assert "\u25b6 Resume in" not in ceiling_text
    assert page.locator("#toolbarResume").is_disabled()
    _shot(page, "inspector_180k.png")
    watch.assert_clean("180k ceiling")

    page.locator("#topBtnTable").click()
    legal_title = "Claude Session " + CLAUDE_LEGAL[:10]
    _click_visible(page, legal_title)
    page.wait_for_function(
        """() => {
          const pane = document.getElementById('activeSessionPane');
          return pane && /omitted/i.test(pane.innerText);
        }"""
    )
    body_text = page.locator("body").inner_text()
    assert LEGAL_SECRET not in body_text
    assert BRIEF_MARK not in body_text
    assert "omitted" in page.locator("#activeSessionPane").inner_text().lower()
    watch.assert_clean("legal omission")

    page.locator("#topBtnCalendar").click()
    page.wait_for_selector("#plannerStrip")
    cal = page.locator("#calendarPane").inner_text()
    assert month_title in cal
    page.locator("#calendarPane button[onclick^='openWeekView']").first.click()
    page.wait_for_function(
        """() => {
          const pane = document.getElementById('calendarPane');
          if (!pane) return false;
          const week = [...pane.querySelectorAll('button')]
            .find(b => (b.textContent || '').includes('Week View'));
          return !!(week && week.className.includes('bg-blue-600')
            && pane.innerText.includes('Special Focus'));
        }"""
    )
    page.locator("#calendarPane button[onclick='openMonthView()']").first.click()
    page.wait_for_function(
        """() => {
          const pane = document.getElementById('calendarPane');
          if (!pane) return false;
          const month = [...pane.querySelectorAll('button')]
            .find(b => (b.textContent || '').includes('Month View'));
          return !!(month && month.className.includes('bg-blue-600')
            && !pane.innerText.includes('Special Focus'));
        }"""
    )
    page.locator("#calendarPane button", has_text="Today").click()
    page.wait_for_function(
        """(label) => {
          const pane = document.getElementById('calendarPane');
          if (!pane) return false;
          const text = pane.innerText;
          return text.includes('TODAY') && text.includes(label);
        }""",
        arg=day_label,
    )
    page.locator("#newGoalInput").fill(GOAL_TEXT)
    page.locator("#addGoalBtn").click()
    page.wait_for_selector(f"#goalList >> text={GOAL_TEXT}")
    page.locator("#goalList label", has_text=GOAL_TEXT).locator("input").click()
    page.wait_for_function(
        """(goal) => {
          const label = [...document.querySelectorAll('#goalList label')]
            .find(el => (el.innerText || '').includes(goal));
          const box = label && label.querySelector('input');
          return !!(box && box.checked);
        }""",
        arg=GOAL_TEXT,
    )
    page.locator("#calendarPane button", has_text="Set Trigger").click()
    page.locator("#trigAnchorName").fill(TRIGGER_TEXT)
    page.locator("#triggerModal").get_by_text("Save & Arm", exact=False).click()
    page.wait_for_function(
        """(name) => {
          const list = document.getElementById('triggerList');
          return list && list.innerText.includes(name);
        }""",
        arg=TRIGGER_TEXT,
    )
    _shot(page, "calendar_today.png")
    page.reload(wait_until="domcontentloaded")
    _wait_row(page, TITLE_NORMAL)
    page.locator("#topBtnCalendar").click()
    page.wait_for_selector("#goalList")
    assert GOAL_TEXT in page.locator("#goalList").inner_text()
    assert TRIGGER_TEXT in page.locator("#triggerList").inner_text()
    checked = page.locator("#goalList label", has_text=GOAL_TEXT).locator("input")
    assert checked.is_checked()
    watch.assert_clean("calendar persistence")

    page.locator("#topBtnTable").click()
    _click_visible(page, TITLE_NORMAL)
    page.wait_for_selector("#inspectorTitle")
    page.locator("#inspectorTitle").dblclick()
    title_input = page.locator("input[id^='inlineInput_']")
    title_input.fill(TITLE_RENAMED)
    title_input.press("Enter")
    page.locator("#inspectorTitle", has_text=TITLE_RENAMED).wait_for()
    page.locator("#tagInline").fill(TAG_CUSTOM)
    page.locator("button[onclick='addTagToSelected()']").click()
    page.wait_for_function(
        """(tag) => document.body.innerText.includes(tag)""",
        arg=TAG_CUSTOM,
    )
    page.reload(wait_until="domcontentloaded")
    _wait_row(page, TITLE_RENAMED)
    assert TAG_CUSTOM in page.locator("body").inner_text()
    assert page.locator("#alignedRowsHost").inner_text().count(TITLE_RENAMED) >= 1
    watch.assert_clean("title tag persistence")

    status, places = _get(app.port, "/api/places")
    assert status == 200
    ready = [d.get("id") for d in places.get("drives") or [] if d.get("ready") and d.get("id")]
    assert ready, places.get("drives")
    page.locator("#tabDrives").click()
    page.wait_for_function(
        """() => {
          const host = document.getElementById('drivesListHost');
          return host && /[A-Z]:/.test(host.innerText || '');
        }""",
        timeout=25000,
    )
    drives_text = page.locator("#drivesListHost").inner_text()
    assert any(str(letter) in drives_text for letter in ready)
    assert "NET-LAB" not in drives_text
    watch.assert_clean("drives live")

    fail = app.browser.new_context(viewport={"width": 1800, "height": 1000})
    fail_page = fail.new_page()
    fail_page.set_default_timeout(20000)
    watch.attach(fail_page)
    watch.allow_places_500 = True
    fail_page.route("**gstatic.com/**", lambda r: r.abort())
    fail_page.route("**fonts.googleapis.com/**", lambda r: r.abort())
    fail_page.route(
        "**/api/places",
        lambda route: route.fulfill(status=500, content_type="text/plain", body="down"),
    )
    try:
        fail_page.goto(app.base + "/", wait_until="domcontentloaded", timeout=45000)
        _wait_row(fail_page, TITLE_CEILING)
        fail_page.locator("#tabDrives").click()
        fail_page.wait_for_selector("#drivesListHost >> text=No drives reported")
        failed = fail_page.locator("#drivesContainer").inner_text()
        assert "NET-LAB" not in failed
        for count in ("42", "31", "52"):
            assert f"{count} sessions" not in failed
        assert "No drives reported" in failed
    finally:
        watch.allow_places_500 = False
        fail.close()
    watch.assert_clean("places failure")

    page.goto(app.base + "/accounts.html", wait_until="domcontentloaded")
    page.wait_for_function(
        """() => {
          const el = document.querySelector('solaro-account');
          return !!(el && el.shadowRoot && el.shadowRoot.querySelector('nav button'));
        }"""
    )
    assert page.evaluate("() => document.querySelector('solaro-account').shadowRoot !== null")
    for tab in SOLARO_TABS:
        page.evaluate(
            """(name) => {
              const root = document.querySelector('solaro-account').shadowRoot;
              root.querySelector('[data-tab="' + name + '"]').click();
            }""",
            tab,
        )
        page.wait_for_function(
            """(name) => {
              const btn = document.querySelector('solaro-account').shadowRoot
                .querySelector('[data-tab="' + name + '"]');
              return btn && btn.getAttribute('aria-current') === 'true';
            }""",
            arg=tab,
        )
    page.evaluate(
        """() => {
          document.querySelector('solaro-account').shadowRoot
            .querySelector('[data-tab="account"]').click();
        }"""
    )
    promise_text = page.evaluate(
        "() => document.querySelector('solaro-account').shadowRoot.textContent || ''"
    ).lower()
    for phrase in PROMISES:
        assert phrase in promise_text
    audit = page.evaluate(
        """() => {
          const roots = [document];
          const host = document.querySelector('solaro-account');
          if (host && host.shadowRoot) roots.push(host.shadowRoot);
          let iframes = 0;
          let cards = 0;
          for (const root of roots) {
            iframes += root.querySelectorAll('iframe').length;
            root.querySelectorAll('input').forEach((el) => {
              const blob = [el.name, el.id, el.placeholder, el.autocomplete,
                el.getAttribute('aria-label'), el.type].join(' ').toLowerCase();
              if (/(card|cc-number|credit|cvv|cvc)/.test(blob)) cards += 1;
            });
          }
          return {iframes, cards};
        }"""
    )
    assert audit["iframes"] == 0
    assert audit["cards"] == 0
    _shot(page, "accounts_solaro.png")
    page.evaluate(
        """() => {
          const root = document.querySelector('solaro-account').shadowRoot;
          const btn = root.querySelector('[data-action="skip"]');
          if (btn) btn.click();
        }"""
    )
    page.wait_for_function("() => localStorage.getItem('solaro.decline') === '1'")
    assert page.evaluate("() => localStorage.getItem('solaro.decline')") == "1"
    watch.assert_clean("accounts")

    offline = app.browser.new_context(viewport={"width": 1800, "height": 1000})
    opage = offline.new_page()
    opage.set_default_timeout(20000)
    watch.attach(opage)
    opage.route("**gstatic.com/**", lambda r: r.abort())
    opage.route("**fonts.googleapis.com/**", lambda r: r.abort())
    opage.route("**mdata.modelraters.com/**", lambda r: r.abort())
    try:
        opage.goto(app.base + "/", wait_until="domcontentloaded", timeout=45000)
        _wait_row(opage, TITLE_CEILING)
        assert opage.locator("#appRoot").is_visible()
        assert opage.locator("#ledgerContainer").is_visible()
        assert opage.locator("#drivesContainer").is_hidden()
        assert opage.locator("#calendarViewContainer").is_hidden()
        assert opage.get_by_text(TITLE_CEILING).count() > 0
    finally:
        offline.close()
    watch.assert_clean("offline tailwind abort")

    for name in (
        "fullscreen_table.png",
        "inspector_180k.png",
        "calendar_today.png",
        "settings.png",
        "accounts_solaro.png",
    ):
        path = SHOTS / name
        assert path.is_file() and path.stat().st_size > 1000, path
