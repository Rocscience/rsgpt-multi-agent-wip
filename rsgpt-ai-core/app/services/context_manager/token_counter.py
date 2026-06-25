"""Accurate token counting utilities using tiktoken"""

import logging
import os
from typing import Any, Dict, Optional

import tiktoken
import yaml

logger = logging.getLogger(__name__)

# Pre-load and cache configuration at module import time for performance
_CONFIG_CACHE: Optional[Dict[str, Any]] = None
_SUPPORTED_MODELS: Optional[Dict[str, str]] = None
_MODEL_CONFIGS: Optional[Dict[str, Dict[str, Any]]] = None
_MODEL_MAX_INPUT_TOKENS: Optional[Dict[str, int]] = None
_MODEL_MAX_OUTPUT_TOKENS: Optional[Dict[str, int]] = None


def _load_config_once() -> Dict[str, Any]:
    """Load configuration once and cache it"""
    global _CONFIG_CACHE
    if _CONFIG_CACHE is not None:
        return _CONFIG_CACHE

    config_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "..", "config.yml"
    )
    try:
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)
        _CONFIG_CACHE = config
        return config
    except Exception as e:
        logger.error(f"Failed to load config.yml: {e}")
        _CONFIG_CACHE = {"supported_models": {}}
        return _CONFIG_CACHE


def _initialize_model_mappings():
    """Initialize all model mappings from config at startup"""
    global _SUPPORTED_MODELS, _MODEL_CONFIGS, _MODEL_MAX_INPUT_TOKENS, _MODEL_MAX_OUTPUT_TOKENS

    if _SUPPORTED_MODELS is not None:
        return  # Already initialized

    config = _load_config_once()
    supported_models = config.get("supported_models", {})

    # Build all mappings
    _SUPPORTED_MODELS = {}
    _MODEL_CONFIGS = {}
    _MODEL_MAX_INPUT_TOKENS = {}
    _MODEL_MAX_OUTPUT_TOKENS = {}

    for model_key, model_config in supported_models.items():
        encoding = model_config.get("encoding", "cl100k_base")
        _SUPPORTED_MODELS[model_key] = encoding
        _MODEL_CONFIGS[model_key] = model_config

        max_input = model_config.get("max_input_tokens", 4096)
        _MODEL_MAX_INPUT_TOKENS[model_key] = max_input

        max_output = model_config.get("max_output_tokens", 4096)
        _MODEL_MAX_OUTPUT_TOKENS[model_key] = max_output


# Initialize mappings at module import time
_initialize_model_mappings()


class TokenCounter:
    """Utility class for accurate token counting using tiktoken"""

    @staticmethod
    def get_encoding_for_model(model_name: str):
        """
        Get the appropriate tiktoken encoding for a supported model.

        Args:
            model_name: The model name (must be one of the supported models)

        Returns:
            The tiktoken encoding object

        Raises:
            ValueError: If the model is not supported
        """
        # Extract model name if it has a provider prefix
        clean_model = model_name.split("/")[-1] if "/" in model_name else model_name

        # Use pre-computed supported models mapping (O(1) lookup)
        if _SUPPORTED_MODELS is None:
            raise RuntimeError("Model mappings not initialized")

        # Check if model is supported
        if clean_model not in _SUPPORTED_MODELS:
            supported = list(_SUPPORTED_MODELS.keys())
            raise ValueError(
                f"Model '{model_name}' is not supported for context management. "
                f"Supported models: {', '.join(supported)}"
            )

        # Get the encoding for supported models
        encoding_name = _SUPPORTED_MODELS[clean_model]

        try:
            return tiktoken.get_encoding(encoding_name)
        except Exception as e:
            logger.error(
                f"Failed to get encoding '{encoding_name}' for model '{model_name}': {e}"
            )
            raise ValueError(f"Failed to initialize encoding for model '{model_name}'")

    @staticmethod
    def count_tokens(text: str, model_name: str) -> int:
        """
        Count the number of tokens in a text string using tiktoken.

        Args:
            text: The text to count tokens for
            model_name: Model name to determine encoding (must be supported)

        Returns:
            Number of tokens in the text

        Raises:
            ValueError: If model is not supported
        """
        if not text:
            return 0

        if not model_name:
            raise ValueError("model_name is required for token counting")

        # Get the appropriate encoding (will raise ValueError if unsupported)
        encoding = TokenCounter.get_encoding_for_model(model_name)

        # Encode and count tokens
        tokens = encoding.encode(text)
        return len(tokens)

    @staticmethod
    def count_tokens_in_messages(messages: list, model_name: str) -> int:
        """
        Count total tokens in a list of messages.

        Args:
            messages: List of message dictionaries with 'role' and 'content' keys
            model_name: Model name for encoding selection (must be supported)

        Returns:
            Total number of tokens across all messages including formatting overhead

        Raises:
            ValueError: If model is not supported
        """
        total_tokens = 0

        # Determine tokens per message based on model
        # These values account for message wrapper formatting tokens
        # Based on OpenAI's message format: <im_start>{role/name}\n{content}<im_end>\n
        if model_name.startswith(("gpt-5", "gpt-4o")):
            # GPT-4o family and GPT-5 family use 3 tokens per message
            tokens_per_message = 3
            tokens_per_name = 1  # if there's a name field
        elif model_name.startswith(("gpt-3.5", "gpt-4")):
            # Older GPT models use 4 tokens per message
            tokens_per_message = 4
            tokens_per_name = -1  # role is always required and always 1 token
        else:
            # Default to newer model format (3 tokens per message)
            tokens_per_message = 3
            tokens_per_name = 1

        for message in messages:
            # Add per-message formatting overhead
            total_tokens += tokens_per_message

            # Add tokens for name field if present
            if message.get("name"):
                total_tokens += tokens_per_name

            # Count tokens in the content
            content = message.get("content", "")
            if isinstance(content, str):
                total_tokens += TokenCounter.count_tokens(content, model_name)
            elif isinstance(content, list):
                # Handle structured content (e.g., from agent framework)
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "input_text":
                        total_tokens += TokenCounter.count_tokens(
                            item.get("text", ""), model_name
                        )
                    elif isinstance(item, str):
                        total_tokens += TokenCounter.count_tokens(item, model_name)

        # Add tokens to prime the assistant's response
        if messages:
            total_tokens += 3

        return total_tokens

    @staticmethod
    def estimate_max_tokens(model_name: str) -> int:
        """
        Get the maximum input tokens for a supported model.

        Args:
            model_name: The model name (must be supported)

        Returns:
            Maximum input tokens for the model

        Raises:
            ValueError: If the model is not supported
        """
        # Extract clean model name
        clean_model = model_name.split("/")[-1] if "/" in model_name else model_name

        # Use pre-computed mapping (O(1) lookup)
        if _MODEL_MAX_INPUT_TOKENS is None:
            raise RuntimeError("Model mappings not initialized")

        if clean_model not in _MODEL_MAX_INPUT_TOKENS:
            supported = list(_MODEL_MAX_INPUT_TOKENS.keys())
            raise ValueError(
                f"Model '{model_name}' is not supported for context management. "
                f"Supported models: {', '.join(supported)}"
            )

        return _MODEL_MAX_INPUT_TOKENS[clean_model]

    @staticmethod
    def estimate_max_output_tokens(model_name: str) -> int:
        """
        Get the maximum output tokens for a supported model.

        Args:
            model_name: The model name (must be supported)

        Returns:
            Maximum output tokens for the model

        Raises:
            ValueError: If the model is not supported
        """
        # Extract clean model name
        clean_model = model_name.split("/")[-1] if "/" in model_name else model_name

        # Use pre-computed mapping (O(1) lookup)
        if _MODEL_MAX_OUTPUT_TOKENS is None:
            raise RuntimeError("Model mappings not initialized")

        if clean_model not in _MODEL_MAX_OUTPUT_TOKENS:
            supported = list(_MODEL_MAX_OUTPUT_TOKENS.keys())
            raise ValueError(
                f"Model '{model_name}' is not supported for context management. "
                f"Supported models: {', '.join(supported)}"
            )

        return _MODEL_MAX_OUTPUT_TOKENS[clean_model]

    @staticmethod
    def count_tokens_for_tools(functions: list, messages: list, model_name: str) -> int:
        """
        Count tokens for messages that contain tools/function calls.

        This handles the complex tokenization of function schemas which have
        special formatting requirements for different models.

        Args:
            functions: List of function/tool definitions
            messages: List of message dictionaries
            model_name: Model name to determine tokenization rules

        Returns:
            Total token count including messages and function schemas
        """
        # Initialize function token settings based on model
        if model_name in ["gpt-4o", "gpt-4o-mini"]:
            func_init = 7
            prop_init = 3
            prop_key = 3
            enum_init = -3
            enum_item = 3
            func_end = 12
        elif model_name in ["gpt-3.5-turbo", "gpt-4"]:
            func_init = 10
            prop_init = 3
            prop_key = 3
            enum_init = -3
            enum_item = 3
            func_end = 12
        else:
            logger.warning(
                f"num_tokens_for_tools() not fully implemented for model "
                f"{model_name}. Using gpt-4o defaults."
            )
            # Use gpt-4o defaults as fallback
            func_init = 7
            prop_init = 3
            prop_key = 3
            enum_init = -3
            enum_item = 3
            func_end = 12

        try:
            encoding = TokenCounter.get_encoding_for_model(model_name)
        except (KeyError, ValueError) as e:
            logger.warning(
                f"Failed to get encoding for model {model_name}: {e}. Using o200k_base encoding."
            )
            try:
                encoding = tiktoken.get_encoding("o200k_base")
            except Exception as fallback_error:
                logger.error(
                    f"Failed to get fallback encoding: {fallback_error}. "
                    "Using basic token estimation."
                )
                # Return a conservative estimate based on message length
                return TokenCounter._estimate_tokens_fallback(functions, messages)

        func_token_count = 0
        if functions and len(functions) > 0:
            try:
                for f in functions:
                    try:
                        func_token_count += (
                            func_init  # Add tokens for start of each function
                        )

                        # Handle different function formats (OpenAI vs others)
                        if "function" in f:
                            function = f["function"]
                        else:
                            function = f

                        f_name = function.get("name", "")
                        f_desc = function.get("description", "")
                        if f_desc and f_desc.endswith("."):
                            f_desc = f_desc[:-1]

                        line = f"{f_name}:{f_desc}"
                        func_token_count += len(
                            encoding.encode(line)
                        )  # Add tokens for name and description

                        # Handle function parameters
                        parameters = function.get("parameters", {})
                        if not isinstance(parameters, dict):
                            logger.warning(
                                f"Function parameters not a dict, skipping: {parameters}"
                            )
                            continue

                        properties = parameters.get("properties", {})
                        if not isinstance(properties, dict):
                            logger.warning(
                                f"Function properties not a dict, skipping: {properties}"
                            )
                            continue

                        if properties:
                            func_token_count += (
                                prop_init  # Add tokens for start of each property
                            )

                            for key in properties.keys():
                                try:
                                    func_token_count += (
                                        prop_key  # Add tokens for each property
                                    )

                                    p_name = key
                                    prop_def = properties[key]

                                    if not isinstance(prop_def, dict):
                                        logger.warning(
                                            f"Property definition not a dict for {key}, skipping"
                                        )
                                        continue

                                    p_type = prop_def.get("type", "")
                                    p_desc = prop_def.get("description", "")

                                    # Handle enum values
                                    if "enum" in prop_def and isinstance(
                                        prop_def["enum"], list
                                    ):
                                        func_token_count += enum_init  # Add enum tokens
                                        for item in prop_def["enum"]:
                                            try:
                                                func_token_count += enum_item
                                                func_token_count += len(
                                                    encoding.encode(str(item))
                                                )
                                            except Exception as enum_error:
                                                logger.warning(
                                                    f"Failed to encode enum item {item}: "
                                                    f"{enum_error}"
                                                )
                                                continue

                                    if p_desc and p_desc.endswith("."):
                                        p_desc = p_desc[:-1]

                                    line = f"{p_name}:{p_type}:{p_desc}"
                                    func_token_count += len(encoding.encode(line))

                                except Exception as prop_error:
                                    logger.warning(
                                        f"Error processing property {key}: {prop_error}"
                                    )
                                    continue

                        func_token_count += func_end

                    except Exception as func_error:
                        logger.warning(
                            f"Error processing function {f.get('name', 'unknown')}: {func_error}"
                        )
                        continue

            except Exception as functions_error:
                logger.error(f"Error processing functions list: {functions_error}")
                # Continue with messages only

        # Count tokens in messages
        try:
            messages_token_count = TokenCounter.count_tokens_in_messages(
                messages, model_name
            )
        except Exception as msg_error:
            logger.warning(
                f"Error counting tokens in messages: {msg_error}. Using fallback estimation."
            )
            messages_token_count = TokenCounter._estimate_tokens_fallback_messages(
                messages
            )

        total_tokens = messages_token_count + func_token_count

        return total_tokens

    @staticmethod
    def _estimate_tokens_fallback(functions: list, messages: list) -> int:
        """Fallback token estimation when encoding fails"""
        # Conservative fallback: assume ~4 characters per token
        total_chars = 0

        # Count function schema characters
        if functions:
            for f in functions:
                try:
                    func_str = str(f)
                    total_chars += len(func_str)
                except Exception:
                    total_chars += 1000  # Conservative estimate for complex schemas

        # Count message characters
        for msg in messages:
            try:
                if isinstance(msg, dict):
                    content = msg.get("content", "")
                    if isinstance(content, str):
                        total_chars += len(content)
                    elif isinstance(content, list):
                        for item in content:
                            if isinstance(item, dict) and "text" in item:
                                total_chars += len(item["text"])
                elif isinstance(msg, str):
                    total_chars += len(msg)
            except Exception:
                total_chars += 100  # Conservative estimate

        # Conservative token estimate: ~4 chars per token
        estimated_tokens = total_chars // 4
        logger.info(f"Using fallback token estimation: {estimated_tokens} tokens")
        return max(estimated_tokens, 1)

    @staticmethod
    def _estimate_tokens_fallback_messages(messages: list) -> int:
        """Fallback token estimation for messages only"""
        total_chars = 0

        for msg in messages:
            try:
                if isinstance(msg, dict):
                    content = msg.get("content", "")
                    if isinstance(content, str):
                        total_chars += len(content)
                    elif isinstance(content, list):
                        for item in content:
                            if isinstance(item, dict) and "text" in item:
                                total_chars += len(item["text"])
                elif isinstance(msg, str):
                    total_chars += len(msg)
            except Exception:
                total_chars += 100  # Conservative estimate

        # Conservative token estimate: ~4 chars per token
        estimated_tokens = total_chars // 4
        return max(estimated_tokens, 1)


# Convenience functions for easy usage
def num_tokens_from_string(string: str, model_name: str) -> int:
    """
    Returns the number of tokens in a text string for a given supported model.

    Args:
        string: Text to count tokens for
        model_name: Supported model name

    Returns:
        Number of tokens

    Raises:
        ValueError: If model is not supported
    """
    return TokenCounter.count_tokens(string, model_name)


def num_tokens_from_messages(messages: list, model_name: str) -> int:
    """
    Returns the total number of tokens in a list of messages for a given supported model.

    Args:
        messages: List of message dictionaries
        model_name: Supported model name

    Returns:
        Total number of tokens

    Raises:
        ValueError: If model is not supported
    """
    return TokenCounter.count_tokens_in_messages(messages, model_name)


def num_tokens_for_tools(functions: list, messages: list, model_name: str) -> int:
    """
    Returns the number of tokens for messages containing tools/function calls.

    This function provides graceful error handling and fallback estimation
    for unsupported models or malformed function schemas.

    Args:
        functions: List of function/tool definitions
        messages: List of message dictionaries
        model_name: Model name (supported models preferred, graceful fallback for others)

    Returns:
        Total token count including tools (conservative estimate if errors occur)
    """
    return TokenCounter.count_tokens_for_tools(functions, messages, model_name)
