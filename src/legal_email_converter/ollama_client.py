from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


class OllamaError(RuntimeError):
    pass


class OllamaUnavailableError(OllamaError):
    pass


class OllamaModelNotFoundError(OllamaError):
    pass


class OllamaProtocolError(OllamaError):
    pass


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
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace") if hasattr(exc, "read") else ""
            if exc.code == 404 and "model" in body.lower():
                raise OllamaModelNotFoundError(body or f"Ollama model not found at {url}") from exc
            raise OllamaError(f"Ollama HTTP error {exc.code} for {url}: {body}") from exc
        except urllib.error.URLError as exc:
            raise OllamaUnavailableError(f"Ollama request failed for {url}: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise OllamaProtocolError(f"Ollama returned non-JSON response for {url}") from exc

    def _get(self, path: str) -> dict[str, Any]:
        url = f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"
        req = urllib.request.Request(url, headers={"Content-Type": "application/json"}, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                return json.loads(raw) if raw else {}
        except urllib.error.URLError as exc:
            raise OllamaUnavailableError(f"Ollama request failed for {url}: {exc}") from exc
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace") if hasattr(exc, "read") else ""
            raise OllamaError(f"Ollama HTTP error {exc.code} for {url}: {body}") from exc
        except json.JSONDecodeError as exc:
            raise OllamaProtocolError(f"Ollama returned non-JSON response for {url}") from exc

    def ping(self) -> bool:
        data = self._get("tags")
        return isinstance(data, dict)

    def list_models(self) -> list[str]:
        data = self._get("tags")
        models = data.get("models", []) if isinstance(data, dict) else []
        out: list[str] = []
        if isinstance(models, list):
            for row in models:
                if isinstance(row, dict):
                    name = str(row.get("name", "")).strip()
                    if name:
                        out.append(name)
        return out

    def embed(self, *, model: str, input_text: str | list[str], truncate: bool = True) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": model,
            "input": input_text,
            "truncate": truncate,
        }
        return self._post("embed", payload)

    def generate(
        self,
        *,
        model: str,
        prompt: str,
        system: str | None = None,
        stream: bool = False,
        format_json: bool = False,
        temperature: float | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": stream,
        }
        if system:
            payload["system"] = system
        if format_json:
            payload["format"] = "json"
        if temperature is not None:
            payload["options"] = {"temperature": temperature}
        return self._post("generate", payload)


_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)


def _parse_json_loose(raw: str) -> dict[str, Any] | None:
    text = (raw or "").strip()
    if not text:
        return None
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        pass

    match = _JSON_BLOCK_RE.search(text)
    if not match:
        return None
    snippet = match.group(0)
    try:
        parsed = json.loads(snippet)
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        return None


def query_date_signal_with_ollama(
    *,
    client: OllamaClient,
    model: str,
    kind: str,
    relative_path: str,
    metadata: dict[str, str],
    content: str,
) -> dict[str, object]:
    snippet = (content or "")[:3000]
    system = (
        "Return strict JSON only. No markdown. No code fences. "
        'Schema: {"date":"YYYY-MM-DD or empty","confidence":0..1,"source":"metadata|path|content|none"}.'
    )
    prompt = (
        "Extract the single best document date. Return JSON only with keys "
        'date (YYYY-MM-DD or empty), confidence (0..1), source (metadata|path|content|none).\\n\\n'
        f"kind: {kind}\\n"
        f"relative_path: {relative_path}\\n"
        f"metadata: {json.dumps(metadata, ensure_ascii=False)}\\n"
        f"content_snippet: {snippet}"
    )

    result = client.generate(
        model=model,
        prompt=prompt,
        system=system,
        stream=False,
        format_json=True,
        temperature=0.0,
    )
    raw = str(result.get("response", "")).strip()
    parsed = _parse_json_loose(raw)
    if parsed is None:
        # One short repair attempt with stricter instruction.
        repair = client.generate(
            model=model,
            prompt="Return valid JSON object only for this content:\\n" + raw[:2000],
            system=system,
            stream=False,
            format_json=True,
            temperature=0.0,
        )
        parsed = _parse_json_loose(str(repair.get("response", "")).strip())
    if parsed is None:
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
