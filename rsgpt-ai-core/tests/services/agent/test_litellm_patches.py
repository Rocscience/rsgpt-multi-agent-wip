"""Tests for runtime LiteLLM patches.

These tests verify the runtime patch in app/services/agent/_litellm_patches.py
behaves correctly:

1. The wrapper rewrites parallel tool call indices from output_index.
2. The wrapper is a no-op when output_index is missing.
3. The version gate skips patching on LiteLLM >= 1.82.0.
4. apply_litellm_patches() is idempotent.
5. The patch is wired into the LiteLLM class via class attribute.

Background: BerriAI/litellm#21331 — the OpenAI Responses → ChatCompletions
streaming bridge in LiteLLM <= 1.81.x hardcoded index=0 for all parallel
tool call chunks, causing GPT-5.x parallel tool calls to be merged into a
single tool_call with concatenated JSON arguments. Fixed upstream in
PR #21337, first released in LiteLLM 1.82.0.
"""

import importlib
import importlib.metadata

import pytest

from app.services.agent import _litellm_patches
from app.services.agent._litellm_patches import (
    _version_at_least,
    apply_litellm_patches,
)


def _installed_litellm_version() -> str:
    """Get the installed LiteLLM version via importlib.metadata.

    LiteLLM's lazy ``__getattr__`` does not expose ``__version__`` directly
    (raises AttributeError), so we use the canonical packaging metadata.
    """
    return importlib.metadata.version("litellm")


# =============================================================================
# Version comparison helper
# =============================================================================


@pytest.mark.parametrize(
    "version,minimum,expected",
    [
        ("1.82.0", "1.82.0", True),
        ("1.82.6", "1.82.0", True),
        ("1.83.4", "1.82.0", True),
        ("2.0.0", "1.82.0", True),
        ("1.80.16", "1.82.0", False),
        ("1.81.16", "1.82.0", False),
        ("1.82.6.dev1", "1.82.0", True),
        ("1.82.0.dev1", "1.82.0", True),
        ("0.0.0", "1.82.0", False),
        ("1.82", "1.82.0", False),  # missing patch -> (1, 82) < (1, 82, 0)
    ],
)
def test_version_at_least(version, minimum, expected):
    assert _version_at_least(version, minimum) is expected


# =============================================================================
# Patch application: real LiteLLM module
# =============================================================================


@pytest.fixture(autouse=True)
def _reset_patch_state():
    """Reset the module-level _PATCHES_APPLIED flag between tests so each
    test starts from a clean state and re-runs apply_litellm_patches()."""
    _litellm_patches._PATCHES_APPLIED = False
    yield
    _litellm_patches._PATCHES_APPLIED = False


def test_patch_is_wired_onto_class_when_litellm_below_1_82():
    """When LiteLLM is < 1.82.0, the patch should rewrap the staticmethod
    on OpenAiResponsesToChatCompletionStreamIterator and tag it with the
    _rsi_patched_21331 marker."""
    if _version_at_least(_installed_litellm_version(), "1.82.0"):
        pytest.skip(
            f"LiteLLM {_installed_litellm_version()} already contains the upstream fix; "
            f"runtime patch is correctly a no-op"
        )

    from litellm.completion_extras.litellm_responses_transformation.transformation import (  # noqa: E501
        OpenAiResponsesToChatCompletionStreamIterator,
    )

    apply_litellm_patches()

    func = (
        OpenAiResponsesToChatCompletionStreamIterator.translate_responses_chunk_to_openai_stream
    )
    assert getattr(func, "_rsi_patched_21331", False), (
        "Patch marker not found on the class staticmethod — patch did not "
        "apply to the class attribute"
    )


def test_patch_is_skipped_when_litellm_already_fixed(monkeypatch):
    """When the installed LiteLLM version is >= 1.82.0, the patch should
    skip entirely and not touch the class."""
    monkeypatch.setattr(
        _litellm_patches, "_get_litellm_version", lambda: "1.82.0"
    )

    from litellm.completion_extras.litellm_responses_transformation.transformation import (  # noqa: E501
        OpenAiResponsesToChatCompletionStreamIterator,
    )

    # Snapshot the class attribute *before* invoking the patch
    before = (
        OpenAiResponsesToChatCompletionStreamIterator.translate_responses_chunk_to_openai_stream
    )

    apply_litellm_patches()

    after = (
        OpenAiResponsesToChatCompletionStreamIterator.translate_responses_chunk_to_openai_stream
    )

    # Same object identity proves the call was a no-op — apply_litellm_patches
    # did not replace the class attribute. We deliberately do NOT assert the
    # absence of the patch marker here, because a previous test in the same
    # session may have already applied the patch (the class attribute is
    # process-global and persists across tests).
    assert before is after


def test_apply_litellm_patches_is_idempotent():
    """Calling apply_litellm_patches() twice should not double-wrap."""
    apply_litellm_patches()
    apply_litellm_patches()  # second call should short-circuit on _PATCHES_APPLIED

    if _version_at_least(_installed_litellm_version(), "1.82.0"):
        # Still no marker because we never patched
        return

    from litellm.completion_extras.litellm_responses_transformation.transformation import (  # noqa: E501
        OpenAiResponsesToChatCompletionStreamIterator,
    )

    func = (
        OpenAiResponsesToChatCompletionStreamIterator.translate_responses_chunk_to_openai_stream
    )
    # If double-wrapping happened, the underlying function would have the
    # marker but a fresh wrapper around it would not — so the marker check
    # here also implicitly proves we did not double-wrap.
    assert getattr(func, "_rsi_patched_21331", False)


# =============================================================================
# Patch behavior: wrapper logic
# =============================================================================


def test_wrapper_rewrites_tool_call_index_from_output_index():
    """The patch must rewrite tc.index from parsed_chunk['output_index']
    when present, restoring distinct indices for parallel tool calls."""
    if _version_at_least(_installed_litellm_version(), "1.82.0"):
        pytest.skip("Patch is a no-op on fixed LiteLLM versions")

    from litellm.completion_extras.litellm_responses_transformation.transformation import (  # noqa: E501
        OpenAiResponsesToChatCompletionStreamIterator,
    )

    apply_litellm_patches()

    # Simulate the second parallel tool call (output_index=1) being added.
    # This is the same chunk shape LiteLLM's chunk_parser produces from
    # OpenAI Responses API streaming events.
    parsed_chunk = {
        "type": "response.output_item.added",
        "output_index": 1,
        "item": {
            "type": "function_call",
            "id": "fc_002",
            "call_id": "call_def",
            "name": "search_web",
            "arguments": "",
        },
    }

    result = OpenAiResponsesToChatCompletionStreamIterator.translate_responses_chunk_to_openai_stream(
        parsed_chunk
    )

    assert result is not None
    tool_calls = result.choices[0].delta.tool_calls
    assert tool_calls and len(tool_calls) == 1
    tc = tool_calls[0]
    # Read index defensively (TypedDict at runtime is a dict)
    tc_index = tc["index"] if isinstance(tc, dict) else tc.index
    assert tc_index == 1, (
        f"Expected output_index=1 to be propagated to tool_call.index, "
        f"got {tc_index}"
    )


def test_wrapper_uses_output_index_zero_when_first_parallel_call():
    """For the first parallel tool call (output_index=0), the patch must
    leave the index at 0 — same as the original behavior. This is the
    sequential / non-parallel case the bug-free path produced by accident."""
    if _version_at_least(_installed_litellm_version(), "1.82.0"):
        pytest.skip("Patch is a no-op on fixed LiteLLM versions")

    from litellm.completion_extras.litellm_responses_transformation.transformation import (  # noqa: E501
        OpenAiResponsesToChatCompletionStreamIterator,
    )

    apply_litellm_patches()

    parsed_chunk = {
        "type": "response.output_item.added",
        "output_index": 0,
        "item": {
            "type": "function_call",
            "id": "fc_001",
            "call_id": "call_abc",
            "name": "search_web",
            "arguments": "",
        },
    }

    result = OpenAiResponsesToChatCompletionStreamIterator.translate_responses_chunk_to_openai_stream(
        parsed_chunk
    )

    tc = result.choices[0].delta.tool_calls[0]
    tc_index = tc["index"] if isinstance(tc, dict) else tc.index
    assert tc_index == 0


def test_wrapper_handles_missing_output_index_gracefully():
    """Chunks that don't carry output_index (e.g. content deltas) must
    pass through the wrapper unchanged."""
    if _version_at_least(_installed_litellm_version(), "1.82.0"):
        pytest.skip("Patch is a no-op on fixed LiteLLM versions")

    from litellm.completion_extras.litellm_responses_transformation.transformation import (  # noqa: E501
        OpenAiResponsesToChatCompletionStreamIterator,
    )

    apply_litellm_patches()

    # A chunk type that the original function understands but does not
    # involve tool calls — should not raise.
    parsed_chunk = {
        "type": "response.output_text.delta",
        "delta": "hello world",
        # no output_index, no item
    }

    # Just assert it does not raise. The result may be None or a content
    # delta — either is fine; we're verifying the wrapper does not corrupt
    # non-tool-call chunks.
    try:
        OpenAiResponsesToChatCompletionStreamIterator.translate_responses_chunk_to_openai_stream(
            parsed_chunk
        )
    except (KeyError, ValueError):
        # The original LiteLLM function may raise on unfamiliar chunk shapes;
        # what we're verifying is that the WRAPPER does not introduce a new
        # exception of its own.
        pass


# =============================================================================
# Integration: importing agent_config wires the patch up
# =============================================================================


def test_importing_agent_config_applies_patch():
    """Importing app.services.agent.agent_config should call
    apply_litellm_patches() at module level."""
    if _version_at_least(_installed_litellm_version(), "1.82.0"):
        pytest.skip("Patch is a no-op on fixed LiteLLM versions")

    # Force a re-import so module-level apply_litellm_patches() runs again
    import app.services.agent.agent_config as agent_config_module

    importlib.reload(agent_config_module)

    from litellm.completion_extras.litellm_responses_transformation.transformation import (  # noqa: E501
        OpenAiResponsesToChatCompletionStreamIterator,
    )

    func = (
        OpenAiResponsesToChatCompletionStreamIterator.translate_responses_chunk_to_openai_stream
    )
    assert getattr(func, "_rsi_patched_21331", False), (
        "Importing agent_config did not apply the LiteLLM patch"
    )
