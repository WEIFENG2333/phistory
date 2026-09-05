from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlsplit


@dataclass(frozen=True)
class TranslationConfig:
    base_url: str
    model: str
    api_key: str = field(repr=False)
    timeout: float = 180
    attempts: int = 5
    concurrency: int = 6
    batch_chars: int = 6000
    enable_thinking: bool = True
    thinking_budget: int = 4096

    def __post_init__(self) -> None:
        if not all(isinstance(value, str) and value.strip() for value in (self.base_url, self.model, self.api_key)):
            raise ValueError("translation requires nonempty base_url, model and api_key strings")
        try:
            url = urlsplit(self.base_url)
            port = url.port
        except ValueError:
            raise ValueError("translation base_url has an invalid hostname or port") from None
        if (
            url.scheme not in {"http", "https"}
            or not url.hostname
            or any(character.isspace() for character in self.base_url)
            or (port is not None and port == 0)
            or url.username
            or url.password
            or url.query
            or url.fragment
        ):
            raise ValueError(
                "translation base_url must be an HTTP(S) API base URL without credentials or query parameters"
            )
        if type(self.timeout) not in {int, float} or not 0 < self.timeout <= 3600:
            raise ValueError("translation timeout must be a number between 0 and 3600 seconds")
        if any(type(value) is not int for value in (self.attempts, self.concurrency, self.batch_chars)):
            raise ValueError("translation attempts, concurrency and batch_chars must be integers")
        if type(self.enable_thinking) is not bool:
            raise ValueError("translation enable_thinking must be a boolean")
        if type(self.thinking_budget) is not int or not 128 <= self.thinking_budget <= 32768:
            raise ValueError("translation thinking_budget must be an integer between 128 and 32768")
        if self.attempts < 1 or self.concurrency < 1 or self.batch_chars < 256:
            raise ValueError(
                "translation timeout, attempts and concurrency must be positive; batch_chars must be >= 256"
            )


def load_config(
    path: Path | None = None, *, model: str | None = None, concurrency: int | None = None
) -> TranslationConfig:
    path = (
        path or Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config"))) / "phistory" / "translation.toml"
    )
    values = {}
    if path.exists():
        try:
            values = tomllib.loads(path.read_text(encoding="utf-8")).get("translation", {})
        except (OSError, tomllib.TOMLDecodeError) as exc:
            raise ValueError("unable to read translation TOML configuration") from exc
    if not isinstance(values, dict):
        raise ValueError("translation configuration must be a TOML table")
    for name in ("base_url", "api_key", "model"):
        value = os.environ.get(f"PHISTORY_TRANSLATION_{name.upper()}")
        if value:
            values[name] = value
    if model is not None:
        values["model"] = model
    if concurrency is not None:
        values["concurrency"] = concurrency
    missing = [name for name in ("base_url", "api_key", "model") if not values.get(name)]
    if missing:
        raise ValueError("missing translation configuration: " + ", ".join(missing))
    return TranslationConfig(
        **{name: values[name] for name in TranslationConfig.__dataclass_fields__ if name in values}
    )
