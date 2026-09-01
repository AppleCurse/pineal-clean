"""Tool-output optimizer safety and protocol-shape regressions."""

from __future__ import annotations

import copy

import pytest

from agent_core.services.token_optimizer import (
    EngineMetadata,
    EngineRegistry,
    FunctionEngine,
    OptimizationPolicy,
    OptimizerError,
    TokenOptimizer,
    builtin_engine_registry,
)


def _policy(*engines: str, allow_lossy: bool = False, **kwargs) -> OptimizationPolicy:
    return OptimizationPolicy(
        enabled=True,
        engine_ids=tuple(engines) or ("strip-ansi", "compact-json"),
        allow_lossy=allow_lossy,
        min_item_chars=0,
        **kwargs,
    )


def test_default_is_disabled_and_returns_an_independent_copy():
    body = {"messages": [{"role": "tool", "content": "\x1b[31mred\x1b[0m"}]}
    result = TokenOptimizer().optimize(body)

    assert result.body == body
    assert result.body is not body
    assert result.body["messages"] is not body["messages"]
    assert result.stats.enabled is False
    assert result.stats.items_seen == 0


def test_safe_engines_compress_tool_output_without_mutating_request():
    tool_json = '\x1b[32m{\n  "ok": true,\n  "items": [1, 2, 3]\n}\x1b[0m'
    body = {
        "messages": [
            {"role": "system", "content": "Keep  all  spacing exactly."},
            {"role": "user", "content": tool_json},
            {"role": "assistant", "tool_calls": [{"function": {"name": "probe"}}]},
            {"role": "tool", "tool_call_id": "call-1", "content": tool_json},
        ],
        "tools": [{"type": "function", "function": {"name": "probe", "description": tool_json}}],
    }
    original = copy.deepcopy(body)

    result = TokenOptimizer().optimize(body, _policy())

    assert body == original
    assert result.body["messages"][0]["content"] == "Keep  all  spacing exactly."
    assert result.body["messages"][1]["content"] == tool_json
    assert result.body["tools"] == body["tools"]
    assert result.body["messages"][3]["content"] == '{"ok":true,"items":[1,2,3]}'
    assert result.stats.items_seen == 1
    assert result.stats.items_changed == 1
    assert result.stats.bytes_saved > 0
    assert set(result.stats.engine_savings) == {"strip-ansi", "compact-json"}
    assert result.stats.as_dict()["bytes_saved"] == result.stats.bytes_saved


def test_explicit_tool_errors_are_never_compressed_in_supported_shapes():
    noisy = "\x1b[31mERROR\x1b[0m\n" * 20
    body = {
        "messages": [
            {"role": "tool", "status": "error", "content": noisy},
            {
                "role": "user",
                "content": [{"type": "tool_result", "is_error": True, "content": noisy}],
            },
        ],
        "input": [
            {"type": "function_call_output", "status": "failed", "output": noisy},
        ],
    }

    result = TokenOptimizer().optimize(body, _policy())
    assert result.body == body
    assert result.stats.items_seen == 3
    assert result.stats.skipped_error_items == 3
    assert result.stats.items_changed == 0


def test_openai_responses_and_anthropic_array_forms_are_supported():
    json_text = '{\n  "value": 1,\n  "nested": {"ok": true}\n}'
    body = {
        "messages": [{
            "role": "user",
            "content": [{
                "type": "tool_result",
                "content": [{"type": "text", "text": json_text}],
            }],
        }],
        "input": [{
            "type": "function_call_output",
            "output": [{"type": "input_text", "text": json_text}],
        }],
    }

    result = TokenOptimizer().optimize(body, _policy("compact-json"))
    expected = '{"value":1,"nested":{"ok":true}}'
    assert result.body["messages"][0]["content"][0]["content"][0]["text"] == expected
    assert result.body["input"][0]["output"][0]["text"] == expected
    assert result.stats.items_seen == result.stats.items_changed == 2


def test_duplicate_json_keys_fail_open_instead_of_changing_meaning():
    duplicate = '{\n  "status": "first",\n  "status": "second"\n}'
    body = {"messages": [{"role": "tool", "content": duplicate}]}

    result = TokenOptimizer().optimize(body, _policy("compact-json"))
    assert result.body == body
    assert result.stats.items_changed == 0
    assert result.stats.failed_engines == ()


def test_lossy_engines_require_explicit_opt_in():
    repeated = "progress\n" * 30
    body = {"messages": [{"role": "tool", "content": repeated}]}
    optimizer = TokenOptimizer()

    safe = optimizer.optimize(body, _policy("collapse-repeated-lines"))
    assert safe.body == body
    assert safe.stats.skipped_lossy_engines == ("collapse-repeated-lines",)

    lossy = optimizer.optimize(
        body,
        _policy(
            "collapse-repeated-lines",
            allow_lossy=True,
            engine_options={"collapse-repeated-lines": {"minimum_repeats": 2}},
        ),
    )
    assert "previous line repeated 29 times" in lossy.body["messages"][0]["content"]
    assert lossy.stats.items_changed == 1


def test_head_tail_is_bounded_and_only_runs_with_lossy_consent():
    text = "\n".join(f"line-{index}" for index in range(100))
    body = {"messages": [{"role": "tool", "content": text}]}
    policy = _policy(
        "head-tail",
        allow_lossy=True,
        engine_options={"head-tail": {"max_lines": 20, "head_lines": 10}},
    )

    result = TokenOptimizer().optimize(body, policy)
    output = result.body["messages"][0]["content"]
    assert output.startswith("line-0\n")
    assert output.endswith("line-99")
    assert "80 lines omitted by explicit lossy policy" in output


def test_lossy_engines_preserve_fenced_code_even_with_explicit_consent():
    fenced_code = "```python\n" + "print('keep exact')\n" * 500 + "```"
    body = {"messages": [{"role": "tool", "content": fenced_code}]}
    policy = _policy(
        "collapse-repeated-lines",
        "head-tail",
        allow_lossy=True,
        engine_options={"head-tail": {"max_lines": 20}},
    )

    result = TokenOptimizer().optimize(body, policy)
    assert result.body == body
    assert result.stats.items_changed == 0


def test_engine_failures_empty_outputs_and_growth_all_fail_open_without_error_text():
    request_secret = "tool-output-secret"

    def raises(text, context):
        raise RuntimeError(f"do not retain {text}")

    registry = EngineRegistry((
        FunctionEngine(EngineMetadata("raises", "Raises safely.", False, "none"), raises),
        FunctionEngine(EngineMetadata("empty", "Returns empty.", False, "none"), lambda t, c: ""),
        FunctionEngine(EngineMetadata("grows", "Returns more.", False, "none"), lambda t, c: t + t),
    ))
    body = {"messages": [{"role": "tool", "content": request_secret}]}
    result = TokenOptimizer(registry).optimize(body, _policy("raises", "empty", "grows"))

    assert result.body == body
    assert result.stats.failed_engines == ("empty", "raises")
    assert request_secret not in repr(result.stats)
    assert "grows" not in result.stats.failed_engines


def test_size_and_total_work_limits_skip_without_truncation():
    body = {"messages": [
        {"role": "tool", "content": "\x1b[31m" + "a" * 100 + "\x1b[0m"},
        {"role": "tool", "content": "\x1b[31m" + "b" * 100 + "\x1b[0m"},
        {"role": "tool", "content": "\x1b[31m" + "c" * 300 + "\x1b[0m"},
    ]}
    policy = _policy("strip-ansi", max_item_bytes=200, max_total_bytes=150)

    result = TokenOptimizer().optimize(body, policy)
    assert result.body["messages"][0]["content"] == "a" * 100
    assert result.body["messages"][1]["content"] == body["messages"][1]["content"]
    assert result.body["messages"][2]["content"] == body["messages"][2]["content"]
    assert result.stats.skipped_total_limit_items == 1
    assert result.stats.skipped_oversize_items == 1


def test_registry_rejects_duplicates_unknown_ids_and_invalid_metadata():
    registry = builtin_engine_registry()
    assert len(registry) == 4
    assert {metadata.id for metadata in registry.metadata()} == {
        "strip-ansi", "compact-json", "collapse-repeated-lines", "head-tail",
    }

    duplicate = FunctionEngine(
        EngineMetadata("strip-ansi", "Duplicate.", False, "none"),
        lambda text, context: text,
    )
    with pytest.raises(OptimizerError, match="duplicate compression engine"):
        registry.with_engine(duplicate)
    with pytest.raises(OptimizerError, match="unknown compression engine"):
        registry.get("missing")
    with pytest.raises(OptimizerError, match="lowercase slug"):
        EngineMetadata("Bad ID", "Invalid.", False, "none")
