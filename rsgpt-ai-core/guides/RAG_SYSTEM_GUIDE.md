# RAG System Guide

## Overview

The RAG (Retrieval-Augmented Generation) system provides a unified approach to context retrieval and reranking for both regular LLM requests and agentic workflows. This guide explains the architecture, implementation, and usage patterns.

## Architecture

### Components

1. **RAG Service** (`app/services/search/rag_service.py`)
   - Central orchestrator for the RAG pipeline
   - Combines context retrieval and reranking
   - Returns reusable `RAGResult` objects

2. **Context Service** (`app/services/search/context_service.py`)
   - Handles Pinecone vector search
   - Manages channel-based retrieval
   - Uses conductor for permission-based channel mapping

3. **Reranker Service** (`app/services/reranker/reranker_service.py`)
   - Reranks retrieved contexts using Cohere API
   - Falls back to simple top-k reranker if Cohere is unavailable
   - Returns relevance scores for each result

### Data Flow

```
User Query
    ↓
RAG Service
    ↓
Context Service → Embedding → Pinecone Search → Initial Results (3x top_k)
    ↓
Reranker Service → Cohere/Backup → Final Results (top_k)
    ↓
RAGResult (contexts + scores + metadata)
```'

## Use Cases

### Use Case 1: Regular LLM Requests with RAG

For regular chat/completion requests, RAG can be enabled via request parameters to augment the prompt with relevant context.

#### Request Model

```python
class ChatRequest(BaseModel):
    messages: List[ChatMessage]

    # RAG parameters
    use_rag: bool = False  # Enable RAG
    rag_source_channels: Optional[List[SourceChannel]] = None  # Channels to search
    rag_user_permission: UserPermission = UserPermission.BASIC  # Permission level
    rag_top_k: int = 5  # Number of contexts to retrieve
```

#### Example Usage

```python
# API Request
POST /api/v1/chat/completions
{
    "messages": [
        {"role": "user", "content": "How do I configure the system?"}
    ],
    "provider": "anthropic",
    "model": "claude-3-5-sonnet-20241022",
    "use_rag": true,
    "rag_source_channels": ["ROC"],
    "rag_user_permission": "flexible",
    "rag_top_k": 5
}
```

#### Implementation Flow

1. **Streaming Service** receives the request
2. If `use_rag=True`, it calls **RAG Service**:
   ```python
   rag_result = await self.rag_service.retrieve_and_rerank(
       query=query,
       source_channels=request.rag_source_channels,
       user_permission=request.rag_user_permission,
       top_k=request.rag_top_k,
   )
   ```
3. Retrieved contexts are formatted and prepended to the prompt:
   ```python
   if rag_result.contexts:
       context_text = rag_result.format_context()
       augmented_prompt = f"{context_text}\n\n{prompt}"
   ```
4. LLM receives the augmented prompt with relevant context

#### Context Format

The retrieved context is formatted as:

```markdown
## Retrieved Context

**[1]** (Score: 0.9500)
First relevant context from documentation...

**[2]** (Score: 0.8700)
Second relevant context from tech support...
```

### Use Case 2: Agent Tool for Knowledge Search

The agentic workflow can use the `search_knowledge` tool to dynamically retrieve information from the knowledge base.

#### Tool Definition

```python
@function_tool()
async def search_knowledge(
    query: str,
    channels: Optional[List[str]] = None,
    user_permission: str = "basic",
    top_k: int = 5,
) -> str:
    """
    Search the knowledge base using RAG.

    Args:
        query: The search query
        channels: ["ROC", "DIANA", "3GSM", "2SI"]
        user_permission: "basic" or "flexible"
        top_k: Number of results (1-20)

    Returns:
        JSON with contexts, scores, and metadata
    """
```

#### Example Agent Usage

The agent can call the tool as needed:

```python
# Agent decides to search for information
tool_call = {
    "tool_name": "search_knowledge",
    "arguments": {
        "query": "How to reset user password",
        "channels": ["ROC"],
        "top_k": 3
    }
}
```

#### Tool Response

```json
{
    "query": "How to reset user password",
    "contexts": [
        {
            "text": "To reset a user password, navigate to...",
            "score": 0.95,
            "rank": 1
        },
        {
            "text": "Password reset requires admin privileges...",
            "score": 0.87,
            "rank": 2
        },
        {
            "text": "For security, passwords must meet...",
            "score": 0.82,
            "rank": 3
        }
    ],
    "metadata": {
        "total_retrieved": 9,
        "channels_searched": ["documentation"],
        "reranker_used": "cohere",
        "results_returned": 3
    }
}
```

## RAG Service API

### Core Method: `retrieve_and_rerank`

```python
async def retrieve_and_rerank(
    query: str,
    source_channels: Optional[List[SourceChannel]] = None,
    user_permission: UserPermission = UserPermission.BASIC,
    top_k: int = 5,
    initial_retrieval_k: Optional[int] = None,
) -> RAGResult
```

#### Parameters

- **query** (str): The search query
- **source_channels** (Optional[List[SourceChannel]]): Channels to search (defaults to `[ROC]`)
- **user_permission** (UserPermission): User's permission level (`BASIC` or `FLEXIBLE`)
- **top_k** (int): Final number of results to return after reranking
- **initial_retrieval_k** (Optional[int]): Number of results to retrieve before reranking (defaults to `top_k * 3`)

#### Returns

**RAGResult** object with:
- `query`: Original search query
- `contexts`: List of reranked context strings
- `scores`: List of relevance scores (higher = more relevant)
- `reranker_used`: Which reranker was used ("cohere", "backup", "none")
- `total_retrieved`: Total number of contexts retrieved before reranking
- `channels_searched`: List of channels that were searched

### RAGResult Helper Methods

```python
# Format contexts for prompt injection
formatted_context = rag_result.format_context()
```

Returns a markdown-formatted string ready to be injected into prompts.

## Channel System

### Source Channels (User-Facing)

- **ROC**: Rockwell Automation documentation
- **DIANA**: DIANA-specific resources
- **3GSM**: Three GSM resources
- **2SI**: Two SI resources

### Permission Levels

- **BASIC**: Limited access to essential channels
- **FLEXIBLE**: Extended access to additional channels (e.g., tech support)

### Channel Mapping

The conductor service maps source channels to internal channels based on permission:

```python
# Example: ROC with flexible permission
ROC + FLEXIBLE → [DOCUMENTATION, TECH_SUPPORT]
ROC + BASIC → [DOCUMENTATION]
```

## Configuration

### Required Environment Variables

```bash
# Pinecone Configuration
PINECONE_API_KEY=your_pinecone_key
PINECONE_INDEX_NAME=your_index_name

# Embedding Service
OPENAI_API_KEY=your_openai_key  # For embeddings

# Reranking (Optional - falls back to backup if not provided)
COHERE_API_KEY=your_cohere_key
```

### Channel Configuration (config.yml)

```yaml
context_stores:
  default:
    top_k: 10
    namespace: "default"
    index_name: ${PINECONE_INDEX_NAME}

  channels:
    documentation:
      namespace: "rockwell-docs"
      top_k: 15

    tech_support:
      namespace: "tech-support"
      top_k: 10
```

## Performance Considerations

### Retrieval Strategy

The RAG service retrieves **3x the desired number of results** (by default) before reranking. This ensures:

1. Better quality after reranking
2. More diverse contexts to choose from
3. Higher chance of finding relevant information

Example:
- If `top_k=5`, it retrieves 15 results
- Reranker selects the best 5 from those 15

### Reranking Fallback

The system has a robust fallback mechanism:

1. **Primary**: Cohere rerank-english-v3.0 (if API key configured)
2. **Fallback**: Simple top-k reranker (keeps original order)
3. **On Error**: Gracefully falls back to backup

### Caching

Services are singletons to avoid repeated initialization:

```python
rag_service = get_rag_service()  # Returns cached instance
```

## Error Handling

### RAG Pipeline Errors

If the RAG pipeline fails in streaming mode:

```python
try:
    rag_result = await self.rag_service.retrieve_and_rerank(...)
except Exception as e:
    logger.error(f"RAG pipeline failed: {e}")
    # Continue with original prompt (graceful degradation)
```

### Agent Tool Errors

The `search_knowledge` tool returns error information in the response:

```json
{
    "contexts": [],
    "error": "Invalid channel. Valid channels: ROC, DIANA, 3GSM, 2SI"
}
```

## Testing

### Running RAG Tests

```bash
# Run RAG-specific tests
poetry run pytest tests/services/test_rag_service.py -v

# Run all tests
poetry run pytest tests/ -v
```

### Test Coverage

The RAG service has comprehensive test coverage including:

- RAGResult creation and formatting
- Successful pipeline execution
- Empty results handling
- Default channel behavior
- Custom retrieval parameters
- Error handling
- Singleton pattern

## Code Examples

### Direct RAG Service Usage

```python
from app.services.search.rag_service import get_rag_service
from app.models.channels import SourceChannel, UserPermission

# Get the service
rag_service = get_rag_service()

# Execute RAG pipeline
result = await rag_service.retrieve_and_rerank(
    query="How to configure network settings",
    source_channels=[SourceChannel.ROC],
    user_permission=UserPermission.FLEXIBLE,
    top_k=5,
)

# Access results
print(f"Found {len(result.contexts)} contexts")
print(f"Reranker used: {result.reranker_used}")

for i, (context, score) in enumerate(zip(result.contexts, result.scores), 1):
    print(f"\n[{i}] Score: {score:.4f}")
    print(context[:200])
```

### Using RAG in Custom Code

```python
from app.services.search.rag_service import get_rag_service

async def get_relevant_docs(user_query: str):
    """Get relevant documentation for a user query"""
    rag_service = get_rag_service()

    result = await rag_service.retrieve_and_rerank(
        query=user_query,
        top_k=3,
    )

    # Format for display
    docs = []
    for context, score in zip(result.contexts, result.scores):
        docs.append({
            "content": context,
            "relevance": score,
        })

    return docs
```

## Best Practices

### 1. Choose Appropriate `top_k`

- **3-5**: Good for focused, specific answers
- **5-10**: Better for comprehensive responses
- **10-20**: Maximum for exploratory queries

### 2. Use Flexible Permission When Needed

If users need access to tech support or additional channels:

```python
rag_user_permission="flexible"
```

### 3. Handle Empty Results

Always check if contexts were retrieved:

```python
if rag_result.contexts:
    # Use contexts
    formatted = rag_result.format_context()
else:
    # No relevant context found
    logger.warning("No context retrieved")
```

### 4. Monitor Reranker Usage

Track which reranker is being used:

```python
if rag_result.reranker_used == "backup":
    logger.warning("Using backup reranker - Cohere may be unavailable")
```

### 5. Optimize Initial Retrieval

For better quality, increase initial retrieval:

```python
result = await rag_service.retrieve_and_rerank(
    query=query,
    top_k=5,
    initial_retrieval_k=20,  # Retrieve more for better reranking
)
```

## Troubleshooting

### Issue: No contexts retrieved

**Possible causes:**
- Query doesn't match any documents
- Wrong channel selected
- User permission too restrictive

**Solution:**
- Try with `flexible` permission
- Check if documents exist in the channel
- Verify Pinecone index has data

### Issue: Low relevance scores

**Possible causes:**
- Query too vague
- Cohere reranker not available (using backup)

**Solution:**
- Make queries more specific
- Configure Cohere API key for better reranking
- Increase `initial_retrieval_k` for more candidates

### Issue: RAG pipeline timeout

**Possible causes:**
- Pinecone API slow
- Too many channels searched

**Solution:**
- Reduce number of channels
- Decrease `initial_retrieval_k`
- Check Pinecone service health

## Future Enhancements

Potential improvements to consider:

1. **Caching**: Cache frequently requested queries
2. **Async Parallel Search**: Search multiple channels in parallel
3. **Context Filtering**: Filter by date, source, or other metadata
4. **Hybrid Search**: Combine vector search with keyword search
5. **User Feedback**: Track which contexts are most useful

## Summary

The RAG system provides a clean, maintainable architecture for context retrieval that:

- **Eliminates code duplication** through a shared RAG service
- **Supports multiple use cases** (streaming LLM and agent tools)
- **Handles errors gracefully** with fallbacks and logging
- **Scales well** with singleton services and configurable parameters
- **Is thoroughly tested** with comprehensive test coverage

For questions or issues, refer to the test files in `tests/services/test_rag_service.py` for usage examples.
