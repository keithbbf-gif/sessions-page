"""cmSessions Scale Indexer Engine.

Implements Pillar 1 of cmSessions Architecture:
- 7-Day Hot Window scanning (mtime filter) for sub-350ms scans across 167k+ files.
- High-water mark delta scanner (only scans files modified since last scan).
- Atomic disk cache (var/index.json) for sub-40ms cold boots.
- Throttled background backfill for historical sessions.
"""

from __future__ import annotations
import os
import time
import json
import threading
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable, Iterator, Set


class ScaleIndexer:
    """High-performance scale indexer and delta cache for multi-harness sessions."""

    def __init__(
        self,
        cache_path: Optional[str] = None,
        hot_days: int = 7,
        backfill_batch_size: int = 500,
        backfill_sleep_s: float = 0.02
    ):
        self.hot_days = hot_days
        self.backfill_batch_size = backfill_batch_size
        self.backfill_sleep_s = backfill_sleep_s
        self.cache_path = Path(cache_path) if cache_path else Path("var/index.json")
        self.state_path = self.cache_path.parent / "scan_state.json"
        
        self._lock = threading.RLock()
        self._catalog: Dict[str, Dict[str, Any]] = {}  # session_id -> metadata record
        self._high_water_marks: Dict[str, float] = {}  # harness_key -> last_mtime
        self._backfill_thread: Optional[threading.Thread] = None
        self._stop_backfill = threading.Event()

    # -------------------------------------------------------------------------
    # 1. Disk Cache Operations (Sub-40ms Cold Boot)
    # -------------------------------------------------------------------------

    def load_cache(self) -> int:
        """Loads cached index from disk into memory. Returns number of sessions loaded."""
        with self._lock:
            if not self.cache_path.is_file():
                return 0
            try:
                raw = self.cache_path.read_text(encoding="utf-8")
                data = json.loads(raw)
                if isinstance(data, dict) and "sessions" in data:
                    self._catalog = {s["id"]: s for s in data["sessions"] if "id" in s}
                elif isinstance(data, list):
                    self._catalog = {s["id"]: s for s in data if isinstance(s, dict) and "id" in s}
                
                # Load high water marks
                if self.state_path.is_file():
                    try:
                        self._high_water_marks = json.loads(self.state_path.read_text(encoding="utf-8"))
                    except Exception:
                        self._high_water_marks = {}
                return len(self._catalog)
            except Exception:
                return 0

    def save_cache_atomic(self) -> bool:
        """Persists the in-memory catalog atomically using a temporary file and replace."""
        with self._lock:
            try:
                self.cache_path.parent.mkdir(parents=True, exist_ok=True)
                tmp_cache = self.cache_path.with_suffix(".tmp")
                tmp_state = self.state_path.with_suffix(".tmp")

                payload = {
                    "version": "1.0",
                    "updated_at": time.time(),
                    "count": len(self._catalog),
                    "sessions": list(self._catalog.values())
                }
                tmp_cache.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
                tmp_state.write_text(json.dumps(self._high_water_marks), encoding="utf-8")

                # Atomic replace
                os.replace(tmp_cache, self.cache_path)
                os.replace(tmp_state, self.state_path)
                return True
            except Exception:
                return False

    # -------------------------------------------------------------------------
    # 2. 7-Day Hot Window & Delta Scanner (<350ms Scan)
    # -------------------------------------------------------------------------

    def scan_hot_window(
        self,
        homes: Dict[str, Path],
        extract_fn: Optional[Callable[[str, Path], List[Dict[str, Any]]]] = None
    ) -> List[Dict[str, Any]]:
        """Scans session directories restricted to the 7-day hot window.
        
        Applies mtime filtering before inspecting file bodies.
        """
        now = time.time()
        cutoff = now - (self.hot_days * 86400.0)
        new_hits: List[Dict[str, Any]] = []

        with self._lock:
            for harness, root in homes.items():
                if root is None or not root.exists():
                    continue
                root_path = Path(root)
                harness_key = f"{harness}:{root_path.resolve()}"
                last_mtime = self._high_water_marks.get(harness_key, 0.0)
                effective_cutoff = max(cutoff, last_mtime)

                harness_max_mtime = last_mtime
                harness_hits = self._scan_directory_fast(
                    harness=harness,
                    root=root_path,
                    cutoff=cutoff,
                    last_mtime=last_mtime,
                    extract_fn=extract_fn
                )

                for hit in harness_hits:
                    sid = hit.get("id")
                    if sid:
                        self._catalog[sid] = hit
                        new_hits.append(hit)
                        mtime = hit.get("updated") or hit.get("mtime") or 0.0
                        if mtime > harness_max_mtime:
                            harness_max_mtime = mtime

                self._high_water_marks[harness_key] = harness_max_mtime

            # Update cache after hot scan
            self.save_cache_atomic()
            return new_hits

    def _scan_directory_fast(
        self,
        harness: str,
        root: Path,
        cutoff: float,
        last_mtime: float = 0.0,
        extract_fn: Optional[Callable[[str, Path], List[Dict[str, Any]]]] = None
    ) -> List[Dict[str, Any]]:
        """Traverses a directory evaluating mtime before opening file contents."""
        hits: List[Dict[str, Any]] = []
        if not root.exists():
            return hits

        # If custom extraction function provided, delegate with cutoff awareness
        if extract_fn:
            try:
                candidates = extract_fn(harness, root)
                min_mtime = max(cutoff, last_mtime)
                return [c for c in candidates if (c.get("updated") or c.get("mtime") or 0.0) > last_mtime and (c.get("updated") or c.get("mtime") or 0.0) >= cutoff]
            except Exception:
                return []

        # Default high-performance traversal
        try:
            stack = [root]
            while stack:
                current = stack.pop()
                try:
                    entries = os.scandir(current)
                except OSError:
                    continue

                with entries:
                    for entry in entries:
                        try:
                            # Prune heavy non-session dirs immediately
                            if entry.is_dir(follow_symlinks=False):
                                if entry.name in ("node_modules", ".git", "__pycache__", ".pytest_cache", ".ruff_cache"):
                                    continue
                                stack.append(Path(entry.path))
                                continue

                            # File inspection: check mtime filter
                            st = entry.stat()
                            if last_mtime > 0:
                                if st.st_mtime <= last_mtime:
                                    continue
                            elif st.st_mtime < cutoff:
                                continue

                            # Standard session file extensions
                            name_lower = entry.name.lower()
                            if name_lower.endswith((".jsonl", ".json", ".sqlite", ".db", ".zst")):
                                sid = f"{harness}-{entry.name}"
                                if sid in self._catalog and self._catalog[sid].get("updated") == st.st_mtime:
                                    continue
                                hits.append({
                                    "id": sid,
                                    "vendor_id": entry.name,
                                    "harness": harness,
                                    "path": str(Path(entry.path).resolve()),
                                    "updated": st.st_mtime,
                                    "nbytes": st.st_size,
                                    "title": "",
                                    "cwd": ""
                                })
                        except OSError:
                            continue
        except Exception:
            pass

        return hits

    # -------------------------------------------------------------------------
    # 3. Query & Slice Methods
    # -------------------------------------------------------------------------

    def query(
        self,
        limit: int = 250,
        harness: Optional[str] = None,
        search: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Returns sorted sessions from catalog (newest first) matching criteria."""
        with self._lock:
            rows = list(self._catalog.values())

            if harness:
                rows = [r for r in rows if r.get("harness") == harness]

            if search:
                needle = search.lower()
                rows = [
                    r for r in rows
                    if needle in (r.get("title") or "").lower()
                    or needle in (r.get("id") or "").lower()
                    or needle in (r.get("cwd") or "").lower()
                ]

            rows.sort(key=lambda x: (-(x.get("updated") or x.get("mtime") or 0.0), x.get("id", "")))
            return rows[:max(0, limit)]

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Fetches a single session record by ID."""
        with self._lock:
            return self._catalog.get(session_id)

    @property
    def total_count(self) -> int:
        with self._lock:
            return len(self._catalog)

    # -------------------------------------------------------------------------
    # 4. Throttled Background Backfill
    # -------------------------------------------------------------------------

    def start_backfill(
        self,
        homes: Dict[str, Path],
        on_batch_complete: Optional[Callable[[int], None]] = None
    ) -> None:
        """Launches background thread to progressively index historical files (>7 days)."""
        with self._lock:
            if self._backfill_thread and self._backfill_thread.is_alive():
                return
            self._stop_backfill.clear()
            self._backfill_thread = threading.Thread(
                target=self._run_backfill,
                args=(homes, on_batch_complete),
                daemon=True,
                name="cmSessions-Backfill"
            )
            self._backfill_thread.start()

    def stop_backfill(self) -> None:
        """Signals backfill thread to terminate."""
        self._stop_backfill.set()
        if self._backfill_thread:
            self._backfill_thread.join(timeout=2.0)

    def _run_backfill(
        self,
        homes: Dict[str, Path],
        on_batch_complete: Optional[Callable[[int], None]] = None
    ) -> None:
        """Crawls historical records in throttled batches."""
        batch: List[Dict[str, Any]] = []

        for harness, root in homes.items():
            if self._stop_backfill.is_set():
                break
            if root is None or not root.exists():
                continue

            try:
                for entry in self._walk_all_files(root):
                    if self._stop_backfill.is_set():
                        break

                    st = entry.stat()
                    sid = f"{harness}-{entry.name}"
                    
                    with self._lock:
                        if sid in self._catalog:
                            continue

                    batch.append({
                        "id": sid,
                        "vendor_id": entry.name,
                        "harness": harness,
                        "path": str(Path(entry.path).resolve()),
                        "updated": st.st_mtime,
                        "nbytes": st.st_size,
                        "title": "",
                        "cwd": ""
                    })

                    if len(batch) >= self.backfill_batch_size:
                        with self._lock:
                            for item in batch:
                                self._catalog[item["id"]] = item
                        self.save_cache_atomic()
                        if on_batch_complete:
                            on_batch_complete(len(self._catalog))
                        batch = []
                        time.sleep(self.backfill_sleep_s)
            except Exception:
                continue

        if batch and not self._stop_backfill.is_set():
            with self._lock:
                for item in batch:
                    self._catalog[item["id"]] = item
            self.save_cache_atomic()
            if on_batch_complete:
                on_batch_complete(len(self._catalog))

    def _walk_all_files(self, root: Path) -> Iterator[os.DirEntry]:
        """Low-level generator walking all files."""
        stack = [root]
        while stack and not self._stop_backfill.is_set():
            curr = stack.pop()
            try:
                with os.scandir(curr) as it:
                    for e in it:
                        try:
                            if e.is_dir(follow_symlinks=False):
                                if e.name not in (".git", "node_modules", "__pycache__"):
                                    stack.append(Path(e.path))
                            elif e.is_file():
                                yield e
                        except OSError:
                            continue
            except OSError:
                continue
