import json
import os
from typing import Any, Dict, List

import httpx


class TinyFishClient:
    """Minimal async TinyFish API client used by hackathon workflows."""

    def __init__(self) -> None:
        self.api_key = os.getenv("TINYFISH_API_KEY", "")
        self.base_url = os.getenv("TINYFISH_API_BASE_URL", "https://agent.tinyfish.ai")
        self.execute_path = os.getenv("TINYFISH_EXECUTE_PATH", "/v1/automation/run-sse")
        self.timeout_seconds = float(os.getenv("TINYFISH_TIMEOUT_SECONDS", "90"))

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key and self.base_url)

    def _build_headers(self) -> Dict[str, str]:
        headers = {
            "X-API-Key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "text/event-stream, application/json",
        }

        workspace_id = os.getenv("TINYFISH_WORKSPACE_ID")
        if workspace_id:
            headers["X-Workspace-Id"] = workspace_id

        return headers

    @staticmethod
    def _parse_sse_events(raw_text: str) -> List[Any]:
        """Extract event data payloads from SSE text/event-stream responses."""
        events: List[Any] = []
        for line in raw_text.splitlines():
            stripped = line.strip()
            if not stripped.startswith("data:"):
                continue

            payload = stripped[len("data:") :].strip()
            if not payload:
                continue

            try:
                events.append(json.loads(payload))
            except json.JSONDecodeError:
                events.append(payload)
        return events

    async def execute_web_task(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not self.api_key:
            raise ValueError("TinyFish is not configured. Set TINYFISH_API_KEY in your environment.")

        url = f"{self.base_url.rstrip('/')}{self.execute_path}"

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(url, headers=self._build_headers(), json=payload)

        # Bubble up response details for easier debugging during the hackathon.
        if response.status_code >= 400:
            return {
                "success": False,
                "status_code": response.status_code,
                "error": response.text,
                "request_url": url,
            }

        content_type = response.headers.get("content-type", "")
        if "text/event-stream" in content_type:
            data: Any = {
                "events": self._parse_sse_events(response.text),
                "raw": response.text,
            }
        else:
            data = response.json() if response.content else {}

        return {
            "success": True,
            "status_code": response.status_code,
            "request_url": url,
            "content_type": content_type,
            "data": data,
        }


tinyfish_client = TinyFishClient()
