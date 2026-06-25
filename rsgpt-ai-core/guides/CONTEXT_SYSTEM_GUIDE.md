# Context Retrieval System Guide

## Overview

This implementation provides a context retrieval system using Pinecone embeddings for the rsgpt-ai-core service. It **exactly matches** the channel system architecture from RSGPT-App, including the source channel mapping and conductor pattern.

## Architecture

```
Context System Flow:
Query → Source Channels (ROC, DIANA, etc.) → Conductor (permission-based mapping)
     → Internal Channels → Embedding Service → Vector Search → Pinecone → Results
```

### Core Components

1. **Models** (`app/models/`)
   - `channels.py`: Source channel definitions (ROC, DIANA, 3GSM, 2SI), internal channels, and permission mappings
   - `context.py`: Request/response models

2. **Services** (`app/services/`)
   - `conductor_service.py`: Maps source channels to internal channels based on user permissions
   - `embedding_service.py`: OpenAI text embeddings
   - `pinecone_service.py`: Vector database operations
   - `context_service.py`: Unified context operations

3. **API Endpoints**
   - **Context** (`app/api/routes/context.py`)
     - `POST /api/v1/context/search`: Search for relevant context
     - `POST /api/v1/context/store`: Store new context
     - `GET /api/v1/context/stats`: Get system statistics
     - `GET /api/v1/context/health`: Health check
   - **Config** (`app/api/routes/config.py`)
     - `GET /api/v1/config/channels`: Get all channel configurations
     - `GET /api/v1/config/channels/{channel}`: Get specific channel config
     - `POST /api/v1/config/reload`: Reload config.yml without restart
     - `GET /api/v1/config/health`: Config system health check

## Configuration

### Environment Variables

Add to your `.env` file:

```env
# OpenAI (Required for embeddings)
OPENAI_API_KEY=your-openai-api-key-here

# Pinecone (Required for vector storage)
PINECONE_API_KEY=your-pinecone-api-key-here
PINECONE_DEFAULT_TOP_K=20

# Encryption (Required for encrypted channels like tech_support)
AES_ENCRYPTOR_KEY=your-base64-fernet-key-here
```

### Channel Configuration (config.yml)

The system uses a `config.yml` file in the project root to define channel-specific settings:

```yaml
context_stores:
  documentation:
    type: PineconeContextStore
    namespace: Rocumentation-0304
    index_name: rsgpt-feb
    top_k: 30

  tech_support:
    type: PineconeContextStore
    namespace: TechSupport-0214
    index_name: rsgpt-feb
    top_k: 30
    encrypted: true  # Text data is AES encrypted

  diana:
    type: PineconeContextStore
    namespace: Diana-0205
    index_name: rsgpt-feb
    top_k: 30

  three_gsm:
    type: PineconeContextStore
    namespace: ThreeGSM-05-23
    index_name: rsgpt-may
    top_k: 30

  two_si:
    type: PineconeContextStore
    namespace: TwoSI-0915-2
    index_name: rsgpt-feb
    top_k: 30

defaults:
  top_k: 20
  embedding_model: text-embedding-3-large
  similarity_threshold: 0.7
```

### Pinecone Setup

1. Create a Pinecone account and get your API key
2. Create indexes as specified in config.yml:
   - **rsgpt-feb**: Main index for most channels
   - **rsgpt-may**: Index for 3GSM channel
   - **Dimension**: 3072 (for text-embedding-3-large)
   - **Metric**: cosine

3. The namespaces are created automatically when data is uploaded

## Encrypted Channels

Some channels store sensitive data that is encrypted at rest in Pinecone. The system automatically decrypts this data when retrieving results.

### Configuration

To enable decryption for a channel, add `encrypted: true` to the channel configuration in `config.yml`:

```yaml
context_stores:
  tech_support:
    type: PineconeContextStore
    namespace: TechSupport-1015
    index_name: rsgpt-feb
    top_k: 30
    encrypted: true  # Text data is AES encrypted
```

### Encryption Key Setup

1. The encryption key must be set in your `.env` file:
   ```env
   AES_ENCRYPTOR_KEY=your-base64-fernet-key-here
   ```

2. The key must be a valid Fernet key (base64-encoded 32-byte key)

3. **IMPORTANT**: The key must match the one used when the data was originally encrypted and uploaded to Pinecone

4. If the key is not configured, the system will log a warning and return encrypted text as-is (graceful degradation)

### Encryption Service

The `AESEncryptor` class in `app/services/search/encryption_service.py` handles decryption:
- Uses Fernet symmetric encryption (from cryptography library)
- Automatically applied to channels marked as `encrypted: true`
- Decryption happens after retrieving results from Pinecone
- Individual decryption failures are logged but don't stop the entire search

### Currently Encrypted Channels

- `tech_support`: Technical support content (contains sensitive customer information)

## Channels and Permissions

### Source Channels (User-Facing)
These are the high-level channels that users request:
- `ROC`: Rocscience documentation and support
- `DIANA`: DIANA-specific documentation
- `3GSM`: 3GSM documentation
- `2SI`: 2SI documentation

### Internal Channels (Pinecone Namespaces)
These are the actual channels mapped to Pinecone namespaces:
- `documentation`: General documentation → `Rocumentation-0304` namespace in `rsgpt-feb`
- `tech_support`: Technical support content → `TechSupport-0214` namespace in `rsgpt-feb`
- `scripting`: Scripting documentation (placeholder, not yet implemented) → `Scripting-0304` namespace in `rsgpt-feb`
- `diana`: DIANA-specific documentation → `Diana-0205` namespace in `rsgpt-feb`
- `three_gsm`: 3GSM documentation → `ThreeGSM-05-23` namespace in `rsgpt-may`
- `two_si`: 2SI documentation → `TwoSI-0915-2` namespace in `rsgpt-feb`

### Permission Levels
- `basic`: Limited access (documentation only for ROC)
- `flexible`: Full access (documentation + tech_support for ROC)

### Two-Level Channel Mapping (Conductor Pattern)
The system uses a conductor to map source channels to internal channels based on user permission:

```python
ROC + BASIC      → [documentation]
ROC + FLEXIBLE   → [documentation, tech_support]
DIANA + BASIC    → [diana]
DIANA + FLEXIBLE → [diana]
3GSM + BASIC     → [three_gsm]
3GSM + FLEXIBLE  → [three_gsm]
2SI + BASIC      → [two_si]
2SI + FLEXIBLE   → [two_si]
```

This matches the `SimpleConductor` behavior from the original RSGPT-App system.

### Configuration Benefits
- **Multiple Indexes**: Different channels can use different Pinecone indexes
- **Flexible Namespaces**: Historical namespace names preserved
- **Per-Channel Settings**: Different `top_k` values per channel
- **Runtime Reload**: Update configurations without restarting service
- **Permission-Based Access**: Two-level mapping ensures users only access authorized channels

## Usage Examples

### 1. Search for Context (Default ROC)

```bash
# Default behavior: searches ROC with BASIC permission (documentation only)
curl -X POST "http://localhost:8090/api/v1/context/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "How to calculate slope stability factors?",
    "user_permission": "basic"
  }'
```

### 2. Search ROC with FLEXIBLE Permission

```bash
# FLEXIBLE permission gives access to documentation + tech_support
curl -X POST "http://localhost:8090/api/v1/context/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "How to calculate slope stability factors?",
    "source_channels": ["ROC"],
    "user_permission": "flexible",
    "top_k": 10
  }'
```

### 3. Search DIANA Documentation

```bash
curl -X POST "http://localhost:8090/api/v1/context/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "DIANA material properties",
    "source_channels": ["DIANA"],
    "user_permission": "basic",
    "top_k": 5
  }'
```

### 4. Search Multiple Source Channels

```bash
# Search across multiple source channels
curl -X POST "http://localhost:8090/api/v1/context/search" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "geotechnical analysis",
    "source_channels": ["ROC", "DIANA"],
    "user_permission": "flexible",
    "top_k": 15
  }'
```

### 5. Store New Context

```bash
curl -X POST "http://localhost:8090/api/v1/context/store" \
  -H "Content-Type: application/json" \
  -d '{
    "text": "The factor of safety is calculated using...",
    "channel": "documentation",
    "metadata": {
      "title": "Slope Stability Analysis",
      "software": "Slide3",
      "file_name": "user_guide.pdf"
    }
  }'
```

### 6. Python SDK Usage

```python
import httpx

async def search_context(query: str, source_channels=None, permission="basic"):
    """Search for context using the new source_channels approach"""
    async with httpx.AsyncClient() as client:
        request_data = {
            "query": query,
            "user_permission": permission,
            "top_k": 5
        }

        # Add source_channels if specified (defaults to ["ROC"] on server)
        if source_channels:
            request_data["source_channels"] = source_channels

        response = await client.post(
            "http://localhost:8090/api/v1/context/search",
            json=request_data
        )
        return response.json()

# Example 1: Search ROC with BASIC permission (documentation only)
results = await search_context("slope stability analysis")
for item in results["results"]:
    print(f"Score: {item['score']:.3f}")
    print(f"Text: {item['text'][:200]}...")
    print("---")

# Example 2: Search ROC with FLEXIBLE permission (documentation + tech_support)
results = await search_context(
    "slope stability analysis",
    source_channels=["ROC"],
    permission="flexible"
)

# Example 3: Search DIANA documentation
results = await search_context(
    "material properties",
    source_channels=["DIANA"],
    permission="basic"
)

# Example 4: Search across multiple source channels
results = await search_context(
    "geotechnical analysis",
    source_channels=["ROC", "DIANA", "3GSM"],
    permission="flexible"
)
```

## Key Features

### ✅ Exact RSGPT-App Parity
- Conductor pattern for source channel → internal channel mapping
- Two-level permission system (source channels + user permission)
- Matches `SimpleConductor` behavior exactly
- ROC source channel with BASIC/FLEXIBLE permission levels

### ✅ Permission-Based Access
- Simple enum-based permission system
- Channel access controlled by user permission level
- Clear two-level mapping: source_channels + permission → internal_channels

### ✅ Async-First
- Built for FastAPI async patterns
- Non-blocking operations throughout
- Efficient batch operations support

### ✅ Error Handling
- Graceful degradation when services fail
- Detailed logging for debugging
- Clear error messages in API responses

### ✅ Clean Architecture
- No legacy/deprecated code
- Single pattern for all requests: source_channels + permission
- Environment variable based configuration
- Sensible defaults

## Migration from RSGPT-App

The new system provides **exact functional parity** with the original RSGPT-App channel system:

### Component Mapping

| RSGPT-App Component | rsgpt-ai-core Component | Status |
|---------------------|------------------------|--------|
| `ChannelSystem` | `ContextService` | ✅ Exact match |
| `SimpleConductor` | `ConductorService` | ✅ Exact match |
| `BaseConductor.conduct()` | `ConductorService.conduct()` | ✅ Same logic |
| `PineconeContextStore` | `PineconeService` | ✅ Equivalent |
| `OpenAIEmbedding` | `EmbeddingService` | ✅ Same model |
| Source channels (ROC, DIANA, etc.) | `SourceChannel` enum | ✅ Added |
| Internal channels | `Channel` enum | ✅ Same channels |
| `User_Permission_Enum` | `UserPermission` | ✅ Same levels |

### API Changes

- **Search**:
  - Old: `channel_system.get_channel_system_output(message, permission, source_channels=["ROC"])`
  - New: `POST /context/search` with `{"query": "...", "source_channels": ["ROC"], "user_permission": "basic"}`

- **Store**:
  - Old: `retrieval_service.add_to_knowledge(text, metadata)`
  - New: `POST /context/store` with `{"text": "...", "channel": "documentation", "metadata": {...}}`

- **Stats**:
  - New feature: `GET /context/stats` - view channel and Pinecone statistics

### Channel Mapping Parity

The conductor mapping is **exactly the same**:

```python
# Old RSGPT-App SimpleConductor
ROC + BASIC → [E_Doc]
ROC + FLEXIBLE → [E_Doc, E_Tech]
DIANA + (any) → [E_DIANA]
3GSM + (any) → [E_3GSM]
2SI + (any) → [E_2SI]

# New rsgpt-ai-core ConductorService
ROC + BASIC → [documentation]
ROC + FLEXIBLE → [documentation, tech_support]
DIANA + (any) → [diana]
3GSM + (any) → [three_gsm]
2SI + (any) → [two_si]
```

## Testing

### Health Check
```bash
curl http://localhost:8090/api/v1/context/health
```

### Service Statistics
```bash
curl http://localhost:8090/api/v1/context/stats
```

### Configuration Management
```bash
# Get all channel configurations
curl http://localhost:8090/api/v1/config/channels

# Get specific channel config
curl http://localhost:8090/api/v1/config/channels/documentation

# Reload configuration without restart
curl -X POST http://localhost:8090/api/v1/config/reload
```

## Troubleshooting

### Common Issues

1. **Import Error: "pinecone" could not be resolved**
   - Expected warning - pinecone package installed via poetry
   - Run: `poetry install` to install dependencies

2. **"Pinecone API key is required"**
   - Set `PINECONE_API_KEY` in your `.env` file
   - Verify API key is valid in Pinecone dashboard

3. **"Index 'rsgpt-feb' does not exist"**
   - Create the required indexes in Pinecone (see config.yml)
   - Verify index names match those in config.yml
   - Use `GET /config/channels` to see current configuration

4. **"No accessible channels found"**
   - Check user permission level in request
   - Verify channel permissions in `PERMISSION_CHANNELS`

5. **Empty search results**
   - Verify data exists in specified namespaces (check config.yml)
   - Use `GET /context/stats` to see namespace statistics
   - Ensure embedding model consistency (text-embedding-3-large)

## Next Steps

1. **Data Migration**: Migrate existing vectors from RSGPT-App to new index
2. **Authentication**: Add JWT token validation for production
3. **Rate Limiting**: Implement request rate limiting
4. **Monitoring**: Add metrics and monitoring endpoints
5. **Caching**: Add embedding caching for common queries

## API Documentation

Once running, visit:
- Development: http://localhost:8090/docs
- Health: http://localhost:8090/health
