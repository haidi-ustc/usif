"""A minimal client for OpenAI-compatible ``/chat/completions`` with tool calling.

Only the standard library is used. The API key goes into the ``Authorization``
header and nowhere else: it is not part of any message, and it is removed from
every error text before that text can reach a user or a model.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Protocol, Sequence

from usif.agent.config import LLMConfig
from usif.errors import AgentError

__all__ = ["ChatClient", "ChatModel"]

Message = Dict[str, Any]
_RETRY_STATUS = {429, 500, 502, 503, 504}


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse redirects: urllib would resend the Authorization header to the new location."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def,unused-ignore]
        raise urllib.error.HTTPError(
            req.full_url, code, f"redirect to {newurl} refused", headers, fp
        )


_OPENER = urllib.request.build_opener(_NoRedirect)


class ChatModel(Protocol):
    """Anything that answers a conversation, optionally with tool calls."""

    def complete(self, messages: Sequence[Message], tools: Sequence[Dict[str, Any]]) -> Message:
        """Return the assistant message (``content`` and/or ``tool_calls``)."""


class ChatClient:
    """Chat completions over HTTP(S) for DeepSeek, OpenAI, vLLM, Ollama, ..."""

    def __init__(self, config: LLMConfig, *, retries: int = 2) -> None:
        self.config = config
        self.retries = retries
        self.usage: Dict[str, int] = {"prompt_tokens": 0, "completion_tokens": 0}

    def _redact(self, text: str) -> str:
        try:
            key = self.config.api_key()
        except AgentError:
            return text
        return text.replace(key, "***")

    def _post(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = self.config.base_url.rstrip("/") + "/chat/completions"
        body = json.dumps(payload).encode("utf-8")
        # LLMConfig only accepts http(s) URLs, so urlopen cannot open file: or other schemes.
        request = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.config.api_key()}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        delay = 1.0
        for attempt in range(self.retries + 1):
            try:
                with _OPENER.open(request, timeout=self.config.timeout) as response:
                    return dict(json.loads(response.read().decode("utf-8")))
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", "replace")[:500]
                if exc.code in _RETRY_STATUS and attempt < self.retries:
                    time.sleep(delay)
                    delay *= 2
                    continue
                raise AgentError(self._redact(f"{url}: HTTP {exc.code}: {detail}")) from None
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                if attempt < self.retries:
                    time.sleep(delay)
                    delay *= 2
                    continue
                raise AgentError(self._redact(f"{url}: {exc}")) from None
            except (json.JSONDecodeError, UnicodeDecodeError):
                raise AgentError(f"{url}: the response is not JSON") from None
            except ValueError as exc:  # e.g. http.client rejecting a header value
                raise AgentError(self._redact(f"{url}: {exc}")) from None
        raise AgentError(f"{url}: no response")  # pragma: no cover - loop always returns

    def complete(
        self, messages: Sequence[Message], tools: Sequence[Dict[str, Any]] = ()
    ) -> Message:
        payload: Dict[str, Any] = {
            "model": self.config.model,
            "messages": list(messages),
            "temperature": self.config.temperature,
        }
        if tools:
            payload["tools"] = list(tools)
        data = self._post(payload)
        try:
            message = dict(data["choices"][0]["message"])
        except (KeyError, IndexError, TypeError):
            raise AgentError(f"unexpected response from {self.config.base_url}") from None
        usage: Optional[Dict[str, Any]] = data.get("usage")
        if usage:
            for key in self.usage:
                self.usage[key] += int(usage.get(key, 0) or 0)
        return message


def tool_spec(name: str, description: str, properties: Dict[str, Any], required: List[str]) -> Dict:
    """An OpenAI ``tools`` entry for a function taking a JSON object."""
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
                "additionalProperties": False,
            },
        },
    }
