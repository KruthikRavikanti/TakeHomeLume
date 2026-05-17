from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from src.schemas import DecisionLogRecord


class DecisionLogger:
    def __init__(self, log_path: str = "logs/decisions.jsonl"):
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, record: DecisionLogRecord | dict) -> None:
        payload = _to_dict(record)
        if isinstance(payload.get("tool_call"), dict):
            payload["tool_call"].pop("raw_tool_result", None)
            payload["tool_call"].pop("safe_tool_result", None)
        with self.log_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(payload, default=str, ensure_ascii=False) + "\n")

    def read_last(self, n: int = 5) -> list[dict]:
        if n <= 0 or not self.log_path.exists():
            return []

        lines = self.log_path.read_text(encoding="utf-8").splitlines()
        records = []
        for line in lines[-n:]:
            if not line.strip():
                continue
            records.append(json.loads(line))
        return records


def _to_dict(record: DecisionLogRecord | dict | BaseModel) -> dict[str, Any]:
    if isinstance(record, dict):
        return record
    if isinstance(record, BaseModel):
        return record.model_dump(mode="json")
    raise TypeError(f"Unsupported decision log record type: {type(record)!r}")
