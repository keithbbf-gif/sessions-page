"""cmSessions Deterministic Failover Kernel.

Enforces the Law of Local Silicon:
- Local CPU / OS execution is free (sub-millisecond).
- Model conversational tokens are expensive ($0.01 - $0.05 per retry).

When a low-level driver or database throws an exception (e.g., SQLite 'unknown tokenizer: mozporter'),
this kernel intercepts the error BEFORE the LLM sees it, executes a deterministic local CPU fallback
(e.g., raw mbox / regex parsing), and returns clean structured data. The model never wastes 30+ turns guessing.
"""

from __future__ import annotations
import os
import sqlite3
import mailbox
from typing import Dict, Any, List, Optional


class DeterministicFailoverKernel:
    """Intercepts tool exceptions and executes zero-token CPU fallbacks."""

    @staticmethod
    def query_thunderbird_emails(db_path: str, mbox_dir: str, pattern: str) -> Dict[str, Any]:
        """Queries Thunderbird messages.
        
        If global-messages-db.sqlite fails due to Mozilla's custom 'mozporter' tokenizer,
        the CPU instantly and deterministically falls back to parsing raw mbox files in mbox_dir.
        """
        # Attempt 1: Fast SQLite DB read
        try:
            if os.path.exists(db_path):
                conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
                cur = conn.cursor()
                cur.execute(
                    "SELECT c1subject, c0body FROM messagesText_content WHERE c1subject LIKE ? LIMIT 50",
                    (f"%{pattern}%",)
                )
                rows = cur.fetchall()
                conn.close()
                return {
                    "status": "SUCCESS",
                    "source": "SQLITE_FTS",
                    "hits_count": len(rows),
                    "data": rows
                }
        except sqlite3.OperationalError as e:
            if "unknown tokenizer" in str(e).lower() or "mozporter" in str(e).lower():
                # DO NOT SHOW THIS STACK TRACE TO THE MODEL!
                # It will trigger a 33-turn hallucination loop.
                # Fall back immediately to local CPU mbox scan.
                return DeterministicFailoverKernel._fallback_mbox_scan(mbox_dir, pattern)
            raise

        # If DB didn't exist or failed with other error, attempt local mbox
        return DeterministicFailoverKernel._fallback_mbox_scan(mbox_dir, pattern)

    @staticmethod
    def _fallback_mbox_scan(mbox_dir: str, pattern: str) -> Dict[str, Any]:
        """Pure-CPU mbox text scanner with zero model overhead."""
        hits = []
        pattern_lower = pattern.lower()

        if not os.path.exists(mbox_dir):
            return {
                "status": "NOT_FOUND",
                "source": "CPU_MBOX_SCAN",
                "hits_count": 0,
                "data": [],
                "note": f"Directory not found: {mbox_dir}"
            }

        for root, _, files in os.walk(mbox_dir):
            for f in files:
                # Skip index and cache files
                if f.endswith(('.msf', '.dat', '.json')):
                    continue
                mbox_path = os.path.join(root, f)
                try:
                    mb = mailbox.mbox(mbox_path)
                    for key, msg in mb.items():
                        subject = str(msg.get("subject", ""))
                        date = str(msg.get("date", ""))
                        sender = str(msg.get("from", ""))
                        if pattern_lower in subject.lower() or pattern_lower in sender.lower():
                            hits.append({
                                "file": f,
                                "subject": subject,
                                "date": date,
                                "from": sender
                            })
                            if len(hits) >= 100:
                                break
                except Exception:
                    continue

        return {
            "status": "SUCCESS",
            "source": "CPU_MBOX_DETERMINISTIC_FALLBACK",
            "hits_count": len(hits),
            "data": hits,
            "tokens_saved_estimate": 12500  # Avoided ~30 model tool iterations
        }
