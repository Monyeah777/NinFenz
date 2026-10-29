"""模型无关文件 adapter：逐轮写上下文包，读取受限 JSONL 响应。"""

from __future__ import annotations

import json
from pathlib import Path

from . import atomic_io, json_asset

MAX_BYTES = 1_048_576
MAX_RESPONSES = 64


class FileModelAdapter:
    def __init__(
        self,
        response_path: str | Path,
        context_dir: str | Path | None = None,
        max_responses: int = MAX_RESPONSES,
    ):
        self.response_path = Path(response_path)
        self.context_dir = Path(context_dir) if context_dir else None
        self.responses = []
        if not self.response_path.is_file():
            raise ValueError("response file missing")
        if self.response_path.stat().st_size > MAX_BYTES:
            raise ValueError("response file too large")
        for line in self.response_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    self.responses.append(json_asset.loads(line, None, what="model response"))
                except ValueError as exc:
                    raise ValueError("invalid response json") from exc
                if len(self.responses) > max_responses:
                    raise ValueError("too many responses")
        if not self.responses:
            raise ValueError("response file empty")
        self.index = 0
        if self.context_dir is not None:
            self.context_dir.mkdir(parents=True, exist_ok=True)

    def __call__(self, payload: dict) -> dict:
        if self.context_dir is not None:
            path = self.context_dir / f"turn-{self.index + 1:03d}.json"
            atomic_io.write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        if self.index >= len(self.responses):
            raise ValueError("response file exhausted")
        response = self.responses[self.index]
        self.index += 1
        return response

    def assert_consumed(self) -> None:
        if self.index != len(self.responses):
            raise ValueError(f"unused responses: {len(self.responses) - self.index}")
