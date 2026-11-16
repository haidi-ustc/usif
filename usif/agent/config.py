"""LLM settings: an OpenAI-compatible endpoint, DeepSeek by default.

Settings come from, in increasing priority: the defaults below, the ``[llm]``
table of ``~/.usif/config.toml``, the ``USIF_LLM_*`` environment variables,
and explicit arguments.

``~/.usif`` (or ``$USIF_HOME``) is the per-user USIF directory::

    ~/.usif/
      config.toml        [llm] settings
      plans/             change plans saved for review (not yet applied)
      plans/applied/     a copy of every applied plan, by id (the change journal)

Nothing is created until something is saved there.

The API key itself is never stored in the configuration: ``api_key_env`` names
the environment variable that holds it, and only the HTTP client reads it.
"""

from __future__ import annotations

import os
import sys
from dataclasses import asdict, dataclass, fields, replace
from pathlib import Path
from typing import Any, Dict, Mapping, Optional
from urllib.parse import urlsplit

from usif.errors import AgentError

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - exercised on Python 3.10
    import tomli as tomllib

__all__ = ["DEFAULT_CONFIG", "LLMConfig", "config_path", "load_config", "plans_dir", "usif_home"]

_LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
_ENV = {
    "base_url": "USIF_LLM_BASE_URL",
    "model": "USIF_LLM_MODEL",
    "api_key_env": "USIF_LLM_API_KEY_ENV",
    "temperature": "USIF_LLM_TEMPERATURE",
    "timeout": "USIF_LLM_TIMEOUT",
}


@dataclass(frozen=True)
class LLMConfig:
    """Where and how to reach an OpenAI-compatible chat-completions service."""

    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-flash"
    api_key_env: str = "DEEPSEEK_API_KEY"
    temperature: float = 0.0
    timeout: float = 120.0

    def __post_init__(self) -> None:
        url = urlsplit(self.base_url)
        if url.scheme not in ("https", "http") or not url.hostname:
            raise AgentError(f"llm base_url must be an http(s) URL, got {self.base_url!r}")
        if url.scheme == "http" and url.hostname not in _LOCAL_HOSTS:
            # The key travels in a header: only a server on this machine may see it unencrypted.
            raise AgentError(
                f"llm base_url must use https unless the server is local: {self.base_url}"
            )
        if not self.model:
            raise AgentError("llm model must not be empty")
        if not self.api_key_env.replace("_", "").isalnum():
            raise AgentError("llm api_key_env must name an environment variable")
        if self.timeout <= 0:
            raise AgentError("llm timeout must be positive")

    def api_key(self) -> str:
        """The key from the environment; never logged, printed or sent to the model."""
        key = os.environ.get(self.api_key_env, "").strip()
        if not key:
            raise AgentError(f"set {self.api_key_env} to the API key of {self.base_url}")
        if any(c.isspace() or not c.isprintable() for c in key):
            # Never echo it: a malformed key would otherwise appear in HTTP error messages.
            raise AgentError(f"{self.api_key_env} contains spaces or control characters")
        return key

    def describe(self) -> Dict[str, Any]:
        """The settings with the key reduced to whether it is set."""
        return {**asdict(self), "api_key_set": bool(os.environ.get(self.api_key_env))}


DEFAULT_CONFIG = LLMConfig()


def usif_home() -> Path:
    """The per-user USIF directory: ``$USIF_HOME`` or ``~/.usif``."""
    return Path(os.environ.get("USIF_HOME") or Path.home() / ".usif").expanduser()


def config_path() -> Path:
    return usif_home() / "config.toml"


def plans_dir(applied: bool = False) -> Path:
    """Where unapproved plans (or, with ``applied``, applied plans) are kept."""
    path = usif_home() / "plans"
    return path / "applied" if applied else path


def _coerce(name: str, value: Any) -> Any:
    kind = {f.name: f.type for f in fields(LLMConfig)}[name]
    try:
        return float(value) if kind in ("float", float) else str(value)
    except (TypeError, ValueError):
        raise AgentError(f"llm {name} must be a number, got {value!r}") from None


def load_config(overrides: Optional[Mapping[str, Any]] = None) -> LLMConfig:
    """The effective settings (file, then environment, then ``overrides``)."""
    values: Dict[str, Any] = {}
    path = config_path()
    if path.is_file():
        try:
            table = tomllib.loads(path.read_text(encoding="utf-8")).get("llm", {})
        except tomllib.TOMLDecodeError as exc:
            raise AgentError(f"{path}: {exc}") from None
        if "api_key" in table:
            raise AgentError(f"{path}: store the key in an environment variable (api_key_env)")
        unknown = set(table) - set(_ENV)
        if unknown:
            raise AgentError(f"{path}: unknown [llm] settings {sorted(unknown)}")
        values.update(table)
    values.update({key: os.environ[env] for key, env in _ENV.items() if os.environ.get(env)})
    values.update({k: v for k, v in (overrides or {}).items() if v is not None})
    return replace(DEFAULT_CONFIG, **{k: _coerce(k, v) for k, v in values.items()})
