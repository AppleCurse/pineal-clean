"""Bounded, fail-open compression for LLM tool output.

The optimizer operates only on recognized tool-result fields. User prompts,
system instructions, tool schemas, tool calls, and explicit error results are
never rewritten. Built-in defaults are structural transformations; lossy
engines require an explicit policy opt-in.
"""

from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Callable, Iterable, Mapping, MutableMapping, Optional, Protocol


class OptimizerError(ValueError):
    """Invalid optimizer configuration or engine registration."""


@dataclass(frozen=True)
class EngineMetadata:
    id: str
    description: str
    lossy: bool
    cache_impact: str

    def __post_init__(self) -> None:
        if not self.id or any(char not in "abcdefghijklmnopqrstuvwxyz0123456789-_" for char in self.id):
            raise OptimizerError("engine id must be a lowercase slug")
        if self.cache_impact not in {"none", "low", "moderate", "high"}:
            raise OptimizerError("cache_impact must be none, low, moderate, or high")
        if not self.description.strip():
            raise OptimizerError("engine description must be non-empty")


@dataclass(frozen=True)
class ToolOutputContext:
    shape: str
    options: Mapping[str, Any]


class CompressionEngine(Protocol):
    metadata: EngineMetadata

    def compress(self, text: str, context: ToolOutputContext) -> str:
        """Return compressed text or the input when the engine does not apply."""


@dataclass(frozen=True)
class FunctionEngine:
    metadata: EngineMetadata
    transform: Callable[[str, ToolOutputContext], str]

    def compress(self, text: str, context: ToolOutputContext) -> str:
        return self.transform(text, context)


class EngineRegistry:
    """Immutable-snapshot registry used by preview and execution paths."""

    def __init__(self, engines: Iterable[CompressionEngine] = ()):
        registered: dict[str, CompressionEngine] = {}
        for engine in engines:
            engine_id = engine.metadata.id
            if engine_id in registered:
                raise OptimizerError(f"duplicate compression engine: {engine_id}")
            if not callable(getattr(engine, "compress", None)):
                raise OptimizerError(f"compression engine {engine_id!r} is not callable")
            registered[engine_id] = engine
        self._engines = MappingProxyType(registered)

    def __len__(self) -> int:
        return len(self._engines)

    def get(self, engine_id: str) -> CompressionEngine:
        try:
            return self._engines[engine_id]
        except KeyError as exc:
            raise OptimizerError(f"unknown compression engine: {engine_id}") from exc

    def metadata(self) -> tuple[EngineMetadata, ...]:
        return tuple(engine.metadata for engine in self._engines.values())

    def with_engine(self, engine: CompressionEngine) -> "EngineRegistry":
        return EngineRegistry((*self._engines.values(), engine))


@dataclass(frozen=True)
class OptimizationPolicy:
    enabled: bool = False
    engine_ids: tuple[str, ...] = ("strip-ansi", "compact-json")
    allow_lossy: bool = False
    min_item_chars: int = 256
    max_item_bytes: int = 1_000_000
    max_total_bytes: int = 4_000_000
    engine_options: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if len(self.engine_ids) > 32:
            raise OptimizerError("at most 32 compression engines may run in one policy")
        if len(set(self.engine_ids)) != len(self.engine_ids):
            raise OptimizerError("compression policy contains duplicate engines")
        if not 0 <= self.min_item_chars <= 1_000_000:
            raise OptimizerError("min_item_chars is outside the allowed range")
        if not 1 <= self.max_item_bytes <= 16_000_000:
            raise OptimizerError("max_item_bytes is outside the allowed range")
        if not 1 <= self.max_total_bytes <= 64_000_000:
            raise OptimizerError("max_total_bytes is outside the allowed range")


@dataclass(frozen=True)
class EngineSavings:
    applications: int = 0
    bytes_before: int = 0
    bytes_after: int = 0

    @property
    def bytes_saved(self) -> int:
        return self.bytes_before - self.bytes_after


@dataclass(frozen=True)
class OptimizationStats:
    enabled: bool
    items_seen: int = 0
    items_changed: int = 0
    bytes_before: int = 0
    bytes_after: int = 0
    skipped_error_items: int = 0
    skipped_immutable_items: int = 0
    skipped_small_items: int = 0
    skipped_oversize_items: int = 0
    skipped_total_limit_items: int = 0
    skipped_lossy_engines: tuple[str, ...] = ()
    failed_engines: tuple[str, ...] = ()
    engine_savings: Mapping[str, EngineSavings] = field(default_factory=dict)

    @property
    def bytes_saved(self) -> int:
        return self.bytes_before - self.bytes_after

    def as_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "items_seen": self.items_seen,
            "items_changed": self.items_changed,
            "bytes_before": self.bytes_before,
            "bytes_after": self.bytes_after,
            "bytes_saved": self.bytes_saved,
            "skipped_error_items": self.skipped_error_items,
            "skipped_immutable_items": self.skipped_immutable_items,
            "skipped_small_items": self.skipped_small_items,
            "skipped_oversize_items": self.skipped_oversize_items,
            "skipped_total_limit_items": self.skipped_total_limit_items,
            "skipped_lossy_engines": list(self.skipped_lossy_engines),
            "failed_engines": list(self.failed_engines),
            "engine_savings": {
                engine_id: {
                    "applications": savings.applications,
                    "bytes_before": savings.bytes_before,
                    "bytes_after": savings.bytes_after,
                    "bytes_saved": savings.bytes_saved,
                }
                for engine_id, savings in self.engine_savings.items()
            },
        }


@dataclass(frozen=True)
class OptimizationResult:
    body: dict[str, Any]
    stats: OptimizationStats


@dataclass
class _MutableStats:
    enabled: bool
    items_seen: int = 0
    items_changed: int = 0
    bytes_before: int = 0
    bytes_after: int = 0
    skipped_error_items: int = 0
    skipped_immutable_items: int = 0
    skipped_small_items: int = 0
    skipped_oversize_items: int = 0
    skipped_total_limit_items: int = 0
    skipped_lossy_engines: set[str] = field(default_factory=set)
    failed_engines: set[str] = field(default_factory=set)
    engine_savings: dict[str, EngineSavings] = field(default_factory=dict)

    def freeze(self) -> OptimizationStats:
        return OptimizationStats(
            enabled=self.enabled,
            items_seen=self.items_seen,
            items_changed=self.items_changed,
            bytes_before=self.bytes_before,
            bytes_after=self.bytes_after,
            skipped_error_items=self.skipped_error_items,
            skipped_immutable_items=self.skipped_immutable_items,
            skipped_small_items=self.skipped_small_items,
            skipped_oversize_items=self.skipped_oversize_items,
            skipped_total_limit_items=self.skipped_total_limit_items,
            skipped_lossy_engines=tuple(sorted(self.skipped_lossy_engines)),
            failed_engines=tuple(sorted(self.failed_engines)),
            engine_savings=MappingProxyType(dict(self.engine_savings)),
        )


@dataclass(frozen=True)
class _TextSlot:
    owner: MutableMapping[str, Any]
    key: str
    shape: str
    explicit_error: bool

    @property
    def text(self) -> str:
        value = self.owner.get(self.key)
        return value if isinstance(value, str) else ""

    def set_text(self, value: str) -> None:
        self.owner[self.key] = value


class TokenOptimizer:
    def __init__(self, registry: Optional[EngineRegistry] = None):
        self.registry = registry or builtin_engine_registry()

    def optimize(
        self,
        body: Mapping[str, Any],
        policy: Optional[OptimizationPolicy] = None,
    ) -> OptimizationResult:
        """Return a deep-copied request and exact byte-savings statistics.

        Every engine invocation is fail-open. A transform is accepted only when
        it returns a non-empty string whose UTF-8 representation is smaller than
        its input. Exception messages are intentionally not retained in stats,
        because third-party engines may include request content in them.
        """
        selected_policy = policy or OptimizationPolicy()
        if not isinstance(body, Mapping):
            raise OptimizerError("optimizer body must be a mapping")
        cloned = copy.deepcopy(dict(body))
        stats = _MutableStats(enabled=selected_policy.enabled)
        if not selected_policy.enabled:
            return OptimizationResult(cloned, stats.freeze())

        engines = tuple(self.registry.get(engine_id) for engine_id in selected_policy.engine_ids)
        processed_bytes = 0
        for slot in _iter_tool_output_slots(cloned):
            stats.items_seen += 1
            original = slot.text
            original_bytes = len(original.encode("utf-8"))
            stats.bytes_before += original_bytes
            stats.bytes_after += original_bytes

            if slot.explicit_error:
                stats.skipped_error_items += 1
                continue
            if _contains_fenced_code(original) or _contains_immutable_evidence(original):
                stats.skipped_immutable_items += 1
                continue
            if len(original) < selected_policy.min_item_chars:
                stats.skipped_small_items += 1
                continue
            if original_bytes > selected_policy.max_item_bytes:
                stats.skipped_oversize_items += 1
                continue
            if processed_bytes + original_bytes > selected_policy.max_total_bytes:
                stats.skipped_total_limit_items += 1
                continue
            processed_bytes += original_bytes

            current = original
            for engine in engines:
                metadata = engine.metadata
                if metadata.lossy and not selected_policy.allow_lossy:
                    stats.skipped_lossy_engines.add(metadata.id)
                    continue
                context = ToolOutputContext(
                    shape=slot.shape,
                    options=selected_policy.engine_options.get(metadata.id, {}),
                )
                before_size = len(current.encode("utf-8"))
                try:
                    candidate = engine.compress(current, context)
                except Exception:
                    stats.failed_engines.add(metadata.id)
                    continue
                if not isinstance(candidate, str) or not candidate:
                    stats.failed_engines.add(metadata.id)
                    continue
                after_size = len(candidate.encode("utf-8"))
                if after_size >= before_size:
                    continue
                previous = stats.engine_savings.get(metadata.id, EngineSavings())
                stats.engine_savings[metadata.id] = EngineSavings(
                    applications=previous.applications + 1,
                    bytes_before=previous.bytes_before + before_size,
                    bytes_after=previous.bytes_after + after_size,
                )
                current = candidate

            if current != original:
                final_size = len(current.encode("utf-8"))
                slot.set_text(current)
                stats.items_changed += 1
                stats.bytes_after -= original_bytes - final_size

        return OptimizationResult(cloned, stats.freeze())


_ANSI_ESCAPE = re.compile(
    r"[\x1B\x9B](?:[\[\]()#;?]*(?:(?:(?:[a-zA-Z\d]*(?:;[-a-zA-Z\d\/#&.:=?%@~_]+)*)?\x07)"
    r"|(?:(?:\d{1,4}(?:[;:]\d{0,4})*)?[\dA-PR-TZcf-nq-uy=><~])))"
)


def _strip_ansi(text: str, _context: ToolOutputContext) -> str:
    return _ANSI_ESCAPE.sub("", text)


class _DuplicateJsonKey(ValueError):
    pass


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateJsonKey(key)
        result[key] = value
    return result


def _compact_json(text: str, _context: ToolOutputContext) -> str:
    stripped = text.strip()
    if not stripped.startswith(("{", "[")):
        return text
    try:
        parsed = json.loads(stripped, object_pairs_hook=_reject_duplicate_keys)
    except (json.JSONDecodeError, _DuplicateJsonKey):
        return text
    return json.dumps(parsed, ensure_ascii=False, separators=(",", ":"))


def _contains_fenced_code(text: str) -> bool:
    return bool(re.search(r"(?m)^\s*(?:```|~~~)", text))


_IMMUTABLE_EVIDENCE_FIELD = re.compile(
    r"(?i)(?:\"|')?(?:display_url|shortcode|taken_at)(?:\"|')?\s*[:=]"
)


def _contains_immutable_evidence(text: str) -> bool:
    return bool(_IMMUTABLE_EVIDENCE_FIELD.search(text))


def _collapse_repeated_lines(text: str, context: ToolOutputContext) -> str:
    if _contains_fenced_code(text):
        return text
    minimum_repeats = _bounded_option(context.options, "minimum_repeats", 3, 2, 1000)
    lines = text.splitlines()
    if len(lines) < minimum_repeats:
        return text
    result: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        end = index + 1
        while end < len(lines) and lines[end] == line:
            end += 1
        count = end - index
        result.append(line)
        if count >= minimum_repeats:
            result.append(f"[previous line repeated {count - 1} times]")
        else:
            result.extend([line] * (count - 1))
        index = end
    suffix = "\n" if text.endswith("\n") else ""
    return "\n".join(result) + suffix


def _head_tail(text: str, context: ToolOutputContext) -> str:
    if _contains_fenced_code(text):
        return text
    max_lines = _bounded_option(context.options, "max_lines", 400, 20, 20_000)
    head_lines = _bounded_option(context.options, "head_lines", max_lines // 2, 10, max_lines - 10)
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return text
    tail_lines = max_lines - head_lines
    omitted = len(lines) - max_lines
    marker = f"[... {omitted} lines omitted by explicit lossy policy ...]"
    return "\n".join((*lines[:head_lines], marker, *lines[-tail_lines:]))


def builtin_engine_registry() -> EngineRegistry:
    """Return built-ins without optional dependencies or model downloads."""
    return EngineRegistry((
        FunctionEngine(
            metadata=EngineMetadata(
                id="strip-ansi",
                description="Remove terminal control sequences from tool output.",
                lossy=False,
                cache_impact="none",
            ),
            transform=_strip_ansi,
        ),
        FunctionEngine(
            metadata=EngineMetadata(
                id="compact-json",
                description="Minify complete JSON tool output while rejecting duplicate keys.",
                lossy=False,
                cache_impact="low",
            ),
            transform=_compact_json,
        ),
        FunctionEngine(
            metadata=EngineMetadata(
                id="collapse-repeated-lines",
                description="Replace consecutive duplicate log lines with a count marker.",
                lossy=True,
                cache_impact="moderate",
            ),
            transform=_collapse_repeated_lines,
        ),
        FunctionEngine(
            metadata=EngineMetadata(
                id="head-tail",
                description="Keep bounded head and tail windows from very long tool output.",
                lossy=True,
                cache_impact="high",
            ),
            transform=_head_tail,
        ),
    ))


def _bounded_option(
    options: Mapping[str, Any],
    key: str,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    try:
        value = int(options.get(key, default))
    except (TypeError, ValueError):
        return default
    return max(minimum, min(value, maximum))


def _explicit_error(value: Mapping[str, Any]) -> bool:
    return value.get("is_error") is True or str(value.get("status", "")).lower() in {
        "error",
        "failed",
        "failure",
    }


def _append_text_parts(
    slots: list[_TextSlot],
    parts: object,
    *,
    shape: str,
    explicit_error: bool,
    allowed_types: frozenset[str],
) -> None:
    if not isinstance(parts, list):
        return
    for part in parts:
        if not isinstance(part, dict):
            continue
        if part.get("type") in allowed_types and isinstance(part.get("text"), str):
            slots.append(_TextSlot(part, "text", shape, explicit_error or _explicit_error(part)))


def _iter_tool_output_slots(body: MutableMapping[str, Any]) -> tuple[_TextSlot, ...]:
    slots: list[_TextSlot] = []

    messages = body.get("messages")
    if isinstance(messages, list):
        for message in messages:
            if not isinstance(message, dict):
                continue
            message_error = _explicit_error(message)
            if message.get("role") in {"tool", "function"}:
                if isinstance(message.get("content"), str):
                    slots.append(_TextSlot(message, "content", "openai-tool", message_error))
                else:
                    _append_text_parts(
                        slots,
                        message.get("content"),
                        shape="openai-tool-array",
                        explicit_error=message_error,
                        allowed_types=frozenset({"text", "input_text"}),
                    )
                continue

            content = message.get("content")
            if not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, dict) or block.get("type") != "tool_result":
                    continue
                block_error = message_error or _explicit_error(block)
                if isinstance(block.get("content"), str):
                    slots.append(_TextSlot(block, "content", "anthropic-tool-result", block_error))
                else:
                    _append_text_parts(
                        slots,
                        block.get("content"),
                        shape="anthropic-tool-result-array",
                        explicit_error=block_error,
                        allowed_types=frozenset({"text"}),
                    )

    responses_input = body.get("input")
    if isinstance(responses_input, list):
        for item in responses_input:
            if not isinstance(item, dict) or item.get("type") != "function_call_output":
                continue
            item_error = _explicit_error(item)
            if isinstance(item.get("output"), str):
                slots.append(_TextSlot(item, "output", "openai-responses-output", item_error))
            else:
                _append_text_parts(
                    slots,
                    item.get("output"),
                    shape="openai-responses-output-array",
                    explicit_error=item_error,
                    allowed_types=frozenset({"input_text", "text"}),
                )

    return tuple(slots)
