"""Runtime patches for known LiteLLM bugs we haven't upgraded past.

Each patch is version-gated and idempotent — once we bump LiteLLM past
the fixed version, the patch becomes a no-op and the corresponding
function in this module can be removed.
"""

import logging

logger = logging.getLogger(__name__)

_PATCHES_APPLIED = False


def apply_litellm_patches() -> None:
    """Apply runtime patches to LiteLLM. Idempotent.

    Call once at startup BEFORE any LiteLLM call. Safe to call multiple
    times — re-invocations short-circuit.
    """
    global _PATCHES_APPLIED
    if _PATCHES_APPLIED:
        return
    _PATCHES_APPLIED = True
    _patch_responses_parallel_tool_call_indices()


def _patch_responses_parallel_tool_call_indices() -> None:
    """Fix BerriAI/litellm#21331 — parallel tool call index collision.

    The OpenAI Responses API → ChatCompletions streaming bridge in LiteLLM
    1.81.x and earlier hardcoded ``index=0`` for ALL parallel tool call
    chunks emitted by ``translate_responses_chunk_to_openai_stream``.
    Downstream consumers (the openai-agents SDK stream handler) use
    ``index`` to distinguish parallel calls, so all parallel tool calls
    were merged into a single ``tool_call`` with concatenated JSON
    arguments. GPT-5.x models that emit parallel tool calls would then
    loop until ``max_turns`` trying to retry a tool call that the JSON
    validator kept rejecting as malformed (RSI-252).

    Fixed upstream in BerriAI/litellm#21337, first released in LiteLLM
    1.82.0. Remove this patch (and the ``apply_litellm_patches()`` import
    in ``agent_config.py``) once ``pyproject.toml`` requires
    ``litellm >= 1.82.0``.
    """
    version = _get_litellm_version()
    if version is None:
        logger.warning("litellm not installed; skipping #21331 patch")
        return
    if _version_at_least(version, "1.82.0"):
        logger.info(
            f"LiteLLM {version} already contains fix for #21331; "
            f"runtime patch is a no-op (safe to remove this code)"
        )
        return

    try:
        from litellm.completion_extras.litellm_responses_transformation.transformation import (  # noqa: E501
            OpenAiResponsesToChatCompletionStreamIterator,
        )
    except ImportError:
        logger.warning(
            "Could not import OpenAiResponsesToChatCompletionStreamIterator "
            "from litellm; skipping #21331 patch"
        )
        return

    func_name = "translate_responses_chunk_to_openai_stream"
    original = getattr(
        OpenAiResponsesToChatCompletionStreamIterator, func_name, None
    )
    if original is None:
        logger.warning(
            f"Could not find {func_name} on "
            f"OpenAiResponsesToChatCompletionStreamIterator; "
            f"skipping #21331 patch"
        )
        return
    if getattr(original, "_rsi_patched_21331", False):
        return  # already patched (e.g. module re-imported)

    def patched(parsed_chunk, *args, **kwargs):
        result = original(parsed_chunk, *args, **kwargs)
        if result is None or not isinstance(parsed_chunk, dict):
            return result
        output_index = parsed_chunk.get("output_index")
        if output_index is None:
            return result
        # Override the hardcoded index=0 in any tool_call deltas. The
        # original LiteLLM code constructs ChatCompletionToolCallChunk
        # with index=0 regardless of which parallel call this chunk
        # belongs to; we re-stamp it from the parsed_chunk's output_index
        # (matching what BerriAI/litellm#21337 does upstream).
        for choice in getattr(result, "choices", None) or []:
            delta = getattr(choice, "delta", None)
            if delta is None:
                continue
            for tc in getattr(delta, "tool_calls", None) or []:
                # ChatCompletionToolCallChunk is a TypedDict at runtime
                # (a plain dict). Defensively support attribute access too
                # in case LiteLLM swaps in a Pydantic model later.
                if isinstance(tc, dict):
                    tc["index"] = output_index
                elif hasattr(tc, "index"):
                    tc.index = output_index
        return result

    patched._rsi_patched_21331 = True  # type: ignore[attr-defined]
    # The original is a @staticmethod on the class. Re-wrap with
    # staticmethod() so attribute access on the class returns the bare
    # function (not a bound method) — preserving the original calling
    # convention used by LiteLLM at the call site (line 1105 of
    # transformation.py: ClassName.translate_responses_chunk_to_openai_stream(chunk)).
    setattr(
        OpenAiResponsesToChatCompletionStreamIterator,
        func_name,
        staticmethod(patched),
    )
    logger.info(
        f"Applied LiteLLM #21331 runtime patch "
        f"(litellm={version}, fixed upstream in 1.82.0)"
    )


def _get_litellm_version() -> str | None:
    """Return the installed LiteLLM version string, or None if missing.

    Uses importlib.metadata rather than ``litellm.__version__`` because
    LiteLLM's lazy ``__getattr__`` does not expose ``__version__`` as a
    normal attribute (raises AttributeError).
    """
    try:
        import importlib.metadata as metadata

        return metadata.version("litellm")
    except metadata.PackageNotFoundError:
        return None
    except Exception as e:  # pragma: no cover - defensive
        logger.warning(f"Could not determine LiteLLM version: {e}")
        return None


def _version_at_least(version: str, minimum: str) -> bool:
    """Compare dotted version strings; True if version >= minimum.

    Lenient: only looks at the numeric prefix of each segment, so
    ``1.82.6.dev1`` parses as ``(1, 82, 6, 0)``.
    """

    def parse(v: str) -> tuple[int, ...]:
        out = []
        for seg in v.split("."):
            num = ""
            for ch in seg:
                if ch.isdigit():
                    num += ch
                else:
                    break
            out.append(int(num) if num else 0)
        return tuple(out)

    return parse(version) >= parse(minimum)
