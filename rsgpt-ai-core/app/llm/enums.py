"""Enums for LLM module"""

from enum import Enum


class LLMProvider(str, Enum):
    """Supported LLM providers"""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    PERPLEXITY = "perplexity"
    LITELLM = "litellm"


class OpenAIModel(str, Enum):
    """Supported OpenAI models"""

    GPT_5 = "gpt-5-2025-08-07"
    GPT_5_1 = "gpt-5.1-2025-11-13"
    GPT_5_2 = "gpt-5.2-2025-12-11"
    GPT_5_MINI = "gpt-5-mini-2025-08-07"
    GPT_5_NANO = "gpt-5-nano-2025-08-07"
    GPT_4_1 = "gpt-4.1-2025-04-14"
