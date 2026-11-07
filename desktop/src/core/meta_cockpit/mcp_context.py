"""显式启用的 MCP context provider；默认离线，不发起网络调用。"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from urllib.parse import urlparse

from . import json_asset
from . import schema_compat as jsonschema

BASE = Path(__file__).parent
SCHEMA = json_asset.load(BASE / "mcp_context_response.schema.json")
VALIDATOR = jsonschema.Draft202012Validator(SCHEMA)
MAX_CHARS = 320
IDENTIFIER = re.compile(r"^[A-Za-z0-9_.-]+$")


class MCPContextProvider:
    kind = "mcp-context"

    def __init__(self, server_id: str, tool: str, client, enabled: bool = False):
        if not IDENTIFIER.fullmatch(server_id) or not IDENTIFIER.fullmatch(tool):
            raise ValueError("invalid MCP server/tool identifier")
        self.server_id = server_id
        self.tool = tool
        self.client = client
        self.enabled = enabled
        self.provider_id = f"mcp:{server_id}:{tool}"
        self.digest = hashlib.sha256((f"{server_id}|{tool}|mcp-context/1").encode()).hexdigest()

    def search(self, query: str, limit: int = 1) -> list[dict]:
        if not self.enabled:
            raise PermissionError("MCP provider is disabled")
        response = self.client({"tool": self.tool, "query": query, "limit": limit})
        issues = [error.message for error in VALIDATOR.iter_errors(response)]
        if issues:
            raise ValueError("invalid MCP response: {}".format("; ".join(issues)))
        out = []
        for item in response["items"][:limit]:
            parsed = urlparse(item["uri"])
            if (
                parsed.scheme != "mcp"
                or parsed.netloc != self.server_id
                or ".." in parsed.path.split("/")
            ):
                raise ValueError("MCP URI does not belong to provider server")
            text = item["text"]
            truncated = len(text) > MAX_CHARS
            text = text[:MAX_CHARS]
            out.append(
                {
                    "source": "{}:{}".format(self.provider_id, item["id"]),
                    "role": "external-content",
                    "trust": "external-advisory",
                    "path": item["uri"],
                    "line": item["line"],
                    "text": text,
                    "truncated": truncated,
                    "char_start": 0,
                    "char_end": len(text),
                    "normalization": "none",
                    "matched_terms": [],
                    "content_digest": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                    "file_digest": item["resource_digest"],
                }
            )
        return out
