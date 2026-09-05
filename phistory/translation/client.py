from __future__ import annotations

import hashlib
import json
import random
import re
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from phistory.translation.config import TranslationConfig
from phistory.translation.prompts import SYSTEM_PROMPT
from phistory.translation.segments import Segment

_PROTECTED = re.compile(
    r"[ \t]*\r?\n[ \t]*|(?P<code>`+)[^`\n]+(?P=code)|\$\{[^\n{}]*(?:\{[^\n{}]*\}[^\n{}]*)*\}"
    r"|\{\{[^\n{}]*\}\}|\$[A-Z_][A-Z_0-9]*|\{[A-Za-z_][A-Za-z_0-9.]*\}"
    r"|(?P<url>[A-Za-z][A-Za-z0-9+.-]*://[^\s<>\]\)\"'，。；！？]+)"
    r"|(?P<path>(?<![\w/])(?:~/|/|\.\.?/)[\w.\-~/]+)"
    r"|<(?P<machine>name|id|location|path|url|uri|model|directory)(?:\s[^<>]*)?>[^<]*</(?P=machine)>"
    r"|</?[A-Za-z][^<>\n]*>"
    r"|(?<![\\\w])\*{1,3}|\*{1,3}(?!\w)|(?<![\\\w])_{1,3}|_{1,3}(?!\w)"
)
_PLACEHOLDER = re.compile(r"⟦PH[A-Za-z0-9_]*⟧")
_CJK = re.compile(r"[\u3400-\u9fff]")


class TranslationError(RuntimeError):
    pass


class PermanentTranslationError(TranslationError):
    """Configuration or request errors that another archive batch cannot resolve."""

    def __init__(self, message: str):
        super().__init__(message)
        self.partial: TranslationBatch | None = None


class AuthenticationError(PermanentTranslationError):
    pass


class InvalidTranslation(TranslationError):
    pass


@dataclass(frozen=True)
class TranslationBatch:
    texts: dict[str, str]
    input_tokens: int = 0
    output_tokens: int = 0
    errors: tuple[str, ...] = ()
    statuses: dict[str, str] = field(default_factory=dict)


def protect(text: str) -> tuple[str, dict[str, str]]:
    """Mask literal syntax before translation; punctuation stays part of the prose."""
    prefix = "PH"
    if _PLACEHOLDER.search(text):
        prefix += hashlib.sha256(text.encode()).hexdigest()[:12] + "_"
    replacements = {}

    def replace(match: re.Match) -> str:
        token = f"⟦{prefix}{len(replacements)}⟧"
        value = match.group()
        protected = value.rstrip(".,;:!?") if match.group("url") or match.group("path") else value
        replacements[token] = protected
        return token + value[len(protected) :]

    return _PROTECTED.sub(replace, text), replacements


def restore(text: str, source: str, replacements: dict[str, str], *, preserved: bool = False) -> str:
    """Reject structural damage and obvious summaries before restoring literals."""
    if preserved:
        if text != source:
            raise InvalidTranslation("preserved text must match the input exactly; otherwise use translated")
        for token, value in replacements.items():
            text = text.replace(token, value)
        return text
    expected, actual = Counter(_PLACEHOLDER.findall(source)), Counter(_PLACEHOLDER.findall(text))
    if actual != expected:
        raise InvalidTranslation(
            f"translation changed protected tokens; missing {dict(expected - actual)}, unexpected {dict(actual - expected)}. Copy every token exactly."
        )
    line_tokens = {token for token, value in replacements.items() if "\n" in value}
    if [token for token in _PLACEHOLDER.findall(text) if token in line_tokens] != [
        token for token in _PLACEHOLDER.findall(source) if token in line_tokens
    ]:
        raise InvalidTranslation("translation reordered source lines")
    emphasis = r"(?<!\\)(?:\*\*|__|\*|_)"
    if Counter(re.findall(emphasis, text)) != Counter(re.findall(emphasis, source)):
        raise InvalidTranslation("translation changed Markdown emphasis")
    numbers = r"\d+(?:\.\d+)*"
    missing = Counter(re.findall(numbers, _PLACEHOLDER.sub("", source))) - Counter(
        re.findall(numbers, _PLACEHOLDER.sub("", text))
    )
    if missing:
        raise InvalidTranslation(
            f"translation changed a numeric constraint; missing Arabic numerals and counts: {dict(missing)}. Keep these numbers in Arabic form while translating the surrounding prose."
        )
    if not _CJK.search(text):
        raise InvalidTranslation(
            "translation contains no Chinese prose. Translate the explanation; if the entire segment is code or an exact literal, use preserved and copy the input exactly."
        )
    # A deliberately loose floor catches dropped clauses, not normal Chinese compression.
    source_prose = _PLACEHOLDER.sub("", source).strip()
    translated_prose = _PLACEHOLDER.sub("", text).strip()
    if len(source_prose) > 250 and len(translated_prose) < len(source_prose) * 0.22:
        raise InvalidTranslation("translation appears to summarize or omit source prose")
    source_lines, translated_lines = source.split("\n"), text.split("\n")
    if len(source_lines) != len(translated_lines) or any(
        bool(original.strip()) != bool(translated.strip())
        for original, translated in zip(source_lines, translated_lines)
    ):
        raise InvalidTranslation("translation changed line breaks or blank lines")
    # Layout belongs to the source. Normalize incidental model whitespace without rewriting prose.
    text = "\n".join(
        (
            re.match(r"^[ \t]*", original).group()
            + translated.strip(" \t\r")
            + re.search(r"[ \t\r]*$", original).group()
            if original.strip()
            else original
        )
        for original, translated in zip(source_lines, translated_lines)
    )
    for token, value in replacements.items():
        if value in {"*", "**", "***", "_", "__", "___"}:
            # Spaces inside emphasis delimiters turn Markdown formatting into literal punctuation.
            position = source.index(token)
            following = position + len(token)
            if position and not source[position - 1].isspace():
                text = re.sub(r"[ \t]+(?=" + re.escape(token) + ")", "", text)
            if following < len(source) and not source[following].isspace():
                text = re.sub("(" + re.escape(token) + r")[ \t]+", r"\1", text)
    # Restore after cleanup so protected indentation and literal contents cannot be altered.
    for token, value in replacements.items():
        text = text.replace(token, value)
    return text


def retry_delay(attempt: int, retry_after: str | None = None) -> float:
    if retry_after:
        try:
            seconds = float(retry_after)
        except ValueError:
            try:
                when = parsedate_to_datetime(retry_after)
                if when.tzinfo is None:
                    when = when.replace(tzinfo=timezone.utc)
                seconds = (when - datetime.now(timezone.utc)).total_seconds()
            except (ValueError, TypeError, OverflowError):
                seconds = 0
        if seconds > 0:
            return min(seconds, 120)
    return min(2**attempt, 30) + random.uniform(0, 1)


class TranslationClient:
    def __init__(self, config: TranslationConfig):
        self.config = config

    def translate(self, segments: list[Segment], *, feedback: dict[str, dict] | None = None) -> TranslationBatch:
        """Translate with up to two corrections, retaining accepted entries.

        Optional review feedback is keyed by source ID; previous text uses the protected input form.
        """
        identifiers = {str(index): segment.id for index, segment in enumerate(segments)}
        protected = {str(index): protect(segment.text) for index, segment in enumerate(segments)}
        pending = {
            str(index): {"id": str(index), "text": protected[str(index)][0], "context": segment.context}
            for index, segment in enumerate(segments)
        }
        # Reviewers can seed the same correction loop with a source-specific issue.
        for identifier, segment in pending.items():
            if feedback and identifiers[identifier] in feedback:
                segment["feedback"] = feedback[identifiers[identifier]]
        texts, statuses = {}, {}
        errors = {}
        input_tokens = output_tokens = 0
        for _ in range(3):
            if not pending:
                break
            try:
                response = self._request(self._payload(list(pending.values())))
            except PermanentTranslationError as exc:
                exc.partial = TranslationBatch(texts, input_tokens, output_tokens, statuses=statuses)
                raise
            except TranslationError as exc:
                # HTTP retries already ran; keep accepted siblings without multiplying transport retries.
                errors.update((identifier, str(exc)) for identifier in pending)
                break
            usage = response.get("usage") if isinstance(response, dict) else None
            input_tokens += _token_count(usage, "prompt_tokens")
            output_tokens += _token_count(usage, "completion_tokens")
            try:
                items = _response_items(response)
            except InvalidTranslation as exc:
                for identifier, segment in pending.items():
                    errors[identifier] = str(exc)
                    segment["feedback"] = {"issue": str(exc)}
                continue
            # Missing IDs receive feedback independently; unsolicited IDs never enter the archive.
            for identifier in list(pending):
                item = items.get(identifier)
                try:
                    if identifier not in items:
                        raise InvalidTranslation(f"missing entry {identifier}; return its complete text and status")
                    if (
                        not isinstance(item, dict)
                        or item.keys() != {"text", "status"}
                        or not isinstance(item["status"], str)
                        or item["status"] not in {"translated", "preserved"}
                        or not isinstance(item["text"], str)
                        or not item["text"].strip()
                    ):
                        raise InvalidTranslation("return a nonempty text and status translated or preserved")
                    translated = restore(item["text"], *protected[identifier], preserved=item["status"] == "preserved")
                except InvalidTranslation as exc:
                    errors[identifier] = str(exc)
                    pending[identifier]["feedback"] = {"previous": item, "issue": str(exc)}
                else:
                    key = identifiers[identifier]
                    texts[key] = translated
                    statuses[key] = item["status"]
                    del pending[identifier]
                    errors.pop(identifier, None)
        return TranslationBatch(
            texts,
            input_tokens,
            output_tokens,
            tuple(f"segment {identifiers[key][:12]}: {issue}" for key, issue in errors.items()),
            statuses,
        )

    def _payload(self, segments: list[dict]) -> dict:
        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": json.dumps({"segments": segments}, ensure_ascii=False),
                },
            ],
            "temperature": 0.2,
            "max_tokens": 8192,
            "enable_thinking": self.config.enable_thinking,
            "response_format": _response_format([segment["id"] for segment in segments]),
        }
        if self.config.enable_thinking:
            payload["thinking_budget"] = self.config.thinking_budget
        return payload

    def _request(self, payload: dict) -> dict:
        request = Request(
            self.config.base_url.rstrip("/") + "/chat/completions",
            data=json.dumps(payload, ensure_ascii=False).encode(),
            headers={"Authorization": "Bearer " + self.config.api_key, "Content-Type": "application/json"},
        )
        for attempt in range(self.config.attempts):
            retry_after = None
            try:
                deadline = time.monotonic() + self.config.timeout
                with urlopen(request, timeout=self.config.timeout) as response:
                    return _read_response(response, deadline)
            except HTTPError as exc:
                if exc.code in {401, 403}:
                    raise AuthenticationError(f"translation API authentication failed (HTTP {exc.code})") from None
                if exc.code not in {408, 409, 425, 429, 500, 502, 503, 504}:
                    raise PermanentTranslationError(f"translation API request failed (HTTP {exc.code})") from None
                retry_after = exc.headers.get("Retry-After")
                error = f"translation API temporarily unavailable (HTTP {exc.code})"
            except (URLError, TimeoutError, ConnectionError, OSError, HTTPException):
                error = "translation API connection failed or timed out"
            except (json.JSONDecodeError, UnicodeDecodeError):
                error = "translation API returned malformed JSON"
            if attempt + 1 == self.config.attempts:
                raise TranslationError(f"{error}; exhausted {self.config.attempts} attempts")
            time.sleep(retry_delay(attempt, retry_after))
        raise AssertionError("unreachable")


def _response_items(response) -> dict:
    try:
        choices = response.get("choices") if isinstance(response, dict) else None
        if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
            raise InvalidTranslation("translation response has an invalid choices structure")
        choice = choices[0]
        if choice.get("finish_reason") != "stop":
            raise InvalidTranslation("translation was truncated or did not finish; return every complete entry")
        message = choice.get("message")
        if not isinstance(message, dict) or not isinstance(message.get("content"), str):
            raise InvalidTranslation("translation response has an invalid message structure")
        content = json.loads(message["content"], object_pairs_hook=_unique_object)
        if not isinstance(content, dict) or content.keys() != {"translations"}:
            raise InvalidTranslation("return only the translations object required by the schema")
        items = content["translations"]
        if not isinstance(items, dict):
            raise InvalidTranslation("translations must be an object keyed by the requested IDs")
        return items
    except (KeyError, IndexError, TypeError, ValueError) as exc:
        raise InvalidTranslation(
            "translation response has an invalid JSON structure; follow the response schema"
        ) from exc


def _token_count(usage, field: str) -> int:
    value = usage.get(field) if isinstance(usage, dict) else None
    return value if isinstance(value, int) and value >= 0 else 0


def _read_response(response, deadline: float) -> dict:
    # Some providers send whitespace while thinking; it must not reset the response time budget.
    chunks = []
    while True:
        if time.monotonic() >= deadline:
            raise TimeoutError("translation response deadline exceeded")
        chunk = response.read1(65536)
        if not chunk:
            return json.loads(b"".join(chunks))
        chunks.append(chunk)


def _unique_object(pairs: list[tuple]) -> dict:
    result = dict(pairs)
    if len(result) != len(pairs):
        raise InvalidTranslation("translation JSON contains duplicate keys")
    return result


def _response_format(identifiers: list[str]) -> dict:
    # Required ID keys prevent omissions and duplicates more directly than an array of ID/text pairs.
    translations = {
        "type": "object",
        "properties": {
            identifier: {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "status": {"type": "string", "enum": ["translated", "preserved"]},
                },
                "required": ["text", "status"],
                "additionalProperties": False,
            }
            for identifier in identifiers
        },
        "required": identifiers,
        "additionalProperties": False,
    }
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "prompt_translations",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {"translations": translations},
                "required": ["translations"],
                "additionalProperties": False,
            },
        },
    }
