"""SDK Session Factory for Agent Memory Persistence.

This module provides a factory for creating SQLAlchemySession instances
that integrate with the OpenAI Agent SDK's session memory system.

The SDK session enables:
- Automatic conversation history persistence
- Multi-turn context across requests
- Session-based memory pruning
"""

import logging
from typing import Optional

from agents.extensions.memory import SQLAlchemySession
from sqlalchemy.ext.asyncio import AsyncEngine

from app.db_models import async_engine

logger = logging.getLogger(__name__)


class SessionFactory:
    """
    Factory for creating SDK-compatible session instances.

    Uses the shared async engine from db_models for connection pooling
    and integrates with Alembic-managed schema.
    """

    def __init__(self, engine: Optional[AsyncEngine] = None):
        """
        Initialize the session factory.

        Args:
            engine: Optional async engine override. Uses shared async_engine by default.
        """
        self._engine = engine or async_engine

    def create_session(
        self,
        session_id: str,
        create_tables: bool = False,
    ) -> SQLAlchemySession:
        """
        Create a new SDK session for the given session ID.

        Args:
            session_id: Unique identifier for the conversation session.
                        Typically matches the chat session ID from the frontend.
            create_tables: Whether to auto-create tables. Set to False in production
                          (use Alembic migrations instead). Set to True for dev/testing.

        Returns:
            SQLAlchemySession instance ready for use with Runner.run()
        """
        logger.info(f"Creating SDK session for session_id: {session_id}")

        session = SQLAlchemySession(
            session_id=session_id,
            engine=self._engine,
            create_tables=create_tables,
            sessions_table="agent_sessions",
            messages_table="agent_messages",
        )

        return session


# Singleton factory instance using the shared async engine
session_factory = SessionFactory()


def create_sdk_session(
    session_id: str,
    create_tables: bool = False,
) -> SQLAlchemySession:
    """
    Convenience function to create an SDK session.

    Args:
        session_id: Unique identifier for the conversation session.
        create_tables: Whether to auto-create tables (default: False for prod).

    Returns:
        SQLAlchemySession instance
    """
    return session_factory.create_session(
        session_id=session_id,
        create_tables=create_tables,
    )
