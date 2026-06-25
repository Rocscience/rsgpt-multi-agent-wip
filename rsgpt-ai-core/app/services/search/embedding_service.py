"""OpenAI embedding service for text vectorization"""

import logging
from typing import List, Optional

from openai import AsyncOpenAI

from app.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service for generating text embeddings using OpenAI's API"""

    def __init__(self):
        """Initialize the embedding service with OpenAI client"""
        if not settings.openai_api_key:
            raise ValueError("OpenAI API key is required for embedding service")

        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = "text-embedding-3-small"  # 1536 dimensions to match Pinecone index

    async def embed_text(self, text: str) -> List[float]:
        """
        Generate embedding vector for the given text.

        Args:
            text: Input text to embed

        Returns:
            List of floats representing the embedding vector

        Raises:
            ValueError: If text is empty or embedding fails
            Exception: For other API errors
        """
        if not text or not text.strip():
            raise ValueError("Text cannot be empty")

        try:
            logger.debug(f"Generating embedding for text of length {len(text)}")

            response = await self.client.embeddings.create(
                input=text.strip(), model=self.model
            )

            if not response.data or len(response.data) == 0:
                raise ValueError("No embedding data received from OpenAI")

            embedding = response.data[0].embedding
            logger.debug(f"Generated embedding with {len(embedding)} dimensions")

            return embedding

        except Exception as e:
            logger.error(f"Failed to generate embedding: {str(e)}")
            raise

    async def embed_batch(self, texts: List[str]) -> List[Optional[List[float]]]:
        """
        Generate embedding vectors for multiple texts in batch.

        Args:
            texts: List of input texts to embed

        Returns:
            List of embedding vectors (None for empty/invalid texts)

        Raises:
            ValueError: If texts list is empty or contains empty strings
            Exception: For API errors
        """
        if not texts:
            raise ValueError("Texts list cannot be empty")

        # Filter out empty texts and keep track of indices
        valid_texts = []
        valid_indices = []

        for i, text in enumerate(texts):
            if text and text.strip():
                valid_texts.append(text.strip())
                valid_indices.append(i)

        if not valid_texts:
            raise ValueError("No valid texts found in input")

        try:
            logger.debug(f"Generating embeddings for {len(valid_texts)} texts")

            response = await self.client.embeddings.create(
                input=valid_texts, model=self.model
            )

            if not response.data or len(response.data) != len(valid_texts):
                raise ValueError("Incomplete embedding data received from OpenAI")

            # Create result list with None for invalid texts
            embeddings: List[Optional[List[float]]] = [None] * len(texts)
            for i, embedding_data in enumerate(response.data):
                original_index = valid_indices[i]
                embeddings[original_index] = embedding_data.embedding

            logger.debug(f"Generated {len(valid_texts)} embeddings successfully")

            return embeddings

        except Exception as e:
            logger.error(f"Failed to generate batch embeddings: {str(e)}")
            raise


# Global instance for dependency injection
_embedding_service = None


def get_embedding_service() -> EmbeddingService:
    """Get the global embedding service instance"""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service
