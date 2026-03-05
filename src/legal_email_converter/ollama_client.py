from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass
class OllamaClient:
    base_url: str = "http://localhost:11434/api"
    timeout_seconds: int = 30

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                return json.loads(raw) if raw else {}
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Ollama request failed for {url}: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Ollama returned non-JSON response for {url}") from exc

    def embed(self, *, model: str, input_text: str | list[str], truncate: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": model,
            "input": input_text,
            "truncate": truncate,
        }
        return self._post("embed", payload)

    def generate(self, *, model: str, prompt: str, system: str | None = None, stream: bool = False) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": stream,
        }
        if system:
            payload["system"] = system
        return self._post("generate", payload)


def query_date_signal_with_ollama(
    *,
    client: OllamaClient,
    model: str,
    kind: str,
    relative_path: str,
    metadata: dict[str, str],
    content: str,
) -> dict[str, object]:
    snippet = (content or "")[:4000]
    prompt = (
        "Extract the single best document date. Return JSON only with keys "
        'date (YYYY-MM-DD or empty), confidence (0..1), source (metadata|path|content|none).\\n\\n'
        f"kind: {kind}\\n"
        f"relative_path: {relative_path}\\n"
        f"metadata: {json.dumps(metadata, ensure_ascii=False)}\\n"
        f"content_snippet: {snippet}"
    )

    result = client.generate(model=model, prompt=prompt, stream=False)
    raw = str(result.get("response", "")).strip()
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {"value": "", "source": "query.invalid_json", "confidence": 0.0}

    value = str(parsed.get("date", "") or "").strip()
    source = str(parsed.get("source", "none") or "none")
    try:
        confidence = float(parsed.get("confidence", 0.0) or 0.0)
    except (TypeError, ValueError):
        confidence = 0.0
    return {
        "value": value,
        "source": f"query.{source}",
        "confidence": max(0.0, min(1.0, confidence)),
    }
