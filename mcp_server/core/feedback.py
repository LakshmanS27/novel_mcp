from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite

from mcp_server.utils.logger import get_logger


logger = get_logger(__name__)


DEFAULT_WEIGHTS = {
    "keyword": 0.35,
    "semantic": 0.25,
    "graph": 0.2,
    "metadata": 0.2,
}


@dataclass
class FeedbackStore:
    db_path: Path

    async def initialize(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    path TEXT NOT NULL,
                    label TEXT NOT NULL CHECK(label IN ('TP', 'FP')),
                    notes TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS model_weights (
                    key TEXT PRIMARY KEY,
                    value REAL NOT NULL
                )
                """
            )
            for key, value in DEFAULT_WEIGHTS.items():
                await db.execute(
                    "INSERT OR IGNORE INTO model_weights(key, value) VALUES (?, ?)",
                    (key, value),
                )
            await db.commit()
        logger.info("feedback store initialized at %s", self.db_path)

    async def submit_feedback(self, path: str, label: str, notes: str | None = None) -> dict[str, str]:
        await self.initialize()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO feedback(path, label, notes, created_at) VALUES (?, ?, ?, ?)",
                (path, label, notes, datetime.now(timezone.utc).isoformat()),
            )
            await db.commit()
        return {"status": "stored"}

    async def get_weights(self) -> dict[str, float]:
        await self.initialize()
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("SELECT key, value FROM model_weights")
            rows = await cursor.fetchall()
        return {key: float(value) for key, value in rows}

    async def update_risk_model(self) -> dict[str, float]:
        await self.initialize()
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                """
                SELECT
                    SUM(CASE WHEN label = 'TP' THEN 1 ELSE 0 END),
                    SUM(CASE WHEN label = 'FP' THEN 1 ELSE 0 END)
                FROM feedback
                """
            )
            tp_count, fp_count = await cursor.fetchone()
            tp = tp_count or 0
            fp = fp_count or 0
            total = max(tp + fp, 1)
            precision = tp / total
            updated = {
                "keyword": min(max(0.2 + precision * 0.3, 0.1), 0.6),
                "semantic": min(max(0.15 + precision * 0.25, 0.1), 0.5),
                "graph": min(max(0.15 + (1 - precision) * 0.1, 0.05), 0.35),
                "metadata": min(max(1.0 - (0.2 + precision * 0.3 + 0.15 + precision * 0.25 + 0.15 + (1 - precision) * 0.1), 0.05), 0.4),
            }
            norm = sum(updated.values())
            normalized = {key: value / norm for key, value in updated.items()}
            await db.executemany(
                "INSERT OR REPLACE INTO model_weights(key, value) VALUES (?, ?)",
                list(normalized.items()),
            )
            await db.commit()
        logger.info("updated model weights: %s", json.dumps(normalized, sort_keys=True))
        return normalized
