"""Enums for the application"""

from enum import Enum


class ProviderEnum(str, Enum):
    """AI Provider names"""
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    PERPLEXITY = "perplexity"
    XAI = "xai"
    GOOGLE = "google"

class OpenAIModelEnum(str, Enum):
    """OpenAI model names"""
    GPT_5 = "gpt-5-2025-08-07"
    GPT_5_1 = "gpt-5.1-2025-11-13"
    GPT_5_2 = "gpt-5.2-2025-12-11"


class AnthropicModelEnum(str, Enum):
    """Anthropic model names"""
    CLAUDE_SONNET_4_5 = "claude-sonnet-4-5-20250929"
    CLAUDE_HAIKU_4_5 = "claude-haiku-4-5-20251001"
    CLAUDE_OPUS_4_5 = "claude-opus-4-5-20251101"


class PerplexityModelEnum(str, Enum):
    """Perplexity model names"""
    SONAR = "sonar"
    SONAR_REASONING = "sonar-reasoning"


class XAIModelEnum(str, Enum):
    """xAI model names"""
    GROK_4_1_FAST_REASONING = "grok-4-1-fast-reasoning"
    GROK_4_1_FAST_NON_REASONING = "grok-4-1-fast-non-reasoning"


class GoogleModelEnum(str, Enum):
    """Google Gemini model names"""
    GEMINI_3_FLASH_PREVIEW = "gemini-3-flash-preview"


# Provider to models mapping
PROVIDER_MODELS = {
    ProviderEnum.OPENAI: [model.value for model in OpenAIModelEnum],
    ProviderEnum.ANTHROPIC: [model.value for model in AnthropicModelEnum],
    ProviderEnum.PERPLEXITY: [model.value for model in PerplexityModelEnum],
    ProviderEnum.XAI: [model.value for model in XAIModelEnum],
    ProviderEnum.GOOGLE: [model.value for model in GoogleModelEnum],
}

# Providers allowed in agent mode
AGENT_MODE_PROVIDERS = [ProviderEnum.OPENAI, ProviderEnum.ANTHROPIC, ProviderEnum.XAI, ProviderEnum.GOOGLE]


class User_Permission_Enum(str, Enum):
  BASIC = "BASIC"
  FLEXIBLE = "FLEXIBLE"