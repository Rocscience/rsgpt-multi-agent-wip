"""
Context Manager Package

Provides context management for AI conversations including:
- Token counting and usage tracking
- Agent lifecycle hooks
- Summarization triggers
- Database persistence for token tracking
"""

from .context_manager_hooks import (
    ContextManagerHooks,
    create_context_manager_hooks,
    load_token_count_from_db,
    persist_token_count_to_db,
)
from .token_counter import (
    TokenCounter,
    num_tokens_for_tools,
    num_tokens_from_messages,
    num_tokens_from_string,
)

__all__ = [
    # Main classes
    "ContextManagerHooks",
    "TokenCounter",
    # Factory functions
    "create_context_manager_hooks",
    # Database persistence
    "load_token_count_from_db",
    "persist_token_count_to_db",
    # Token counting utilities
    "num_tokens_from_string",
    "num_tokens_from_messages",
    "num_tokens_for_tools",
]
