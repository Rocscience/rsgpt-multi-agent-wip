"""Unit tests for agent tools"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from agents.tool import FunctionTool

from app.models.agent import AgentContext
from app.models.channels import SourceChannel
from app.models.context import (
    SearchKnowledgeResult,
    SearchResultContext,
    SearchResultMetadata,
    SearchResultSource,
)

# Import the decorated tools
from app.services.agent.tools import base_tools as agent_tools


class TestAgentToolsConfiguration:
    """Test agent tools are properly configured"""

    def test_search_knowledge_exists(self):
        """Test that search_knowledge tool exists and is a FunctionTool"""
        assert hasattr(agent_tools, "search_knowledge")
        assert isinstance(agent_tools.search_knowledge, FunctionTool)

    def test_search_knowledge_has_correct_name(self):
        """Test that search_knowledge has the correct name"""
        assert agent_tools.search_knowledge.name == "search_knowledge"

    def test_search_knowledge_has_description(self):
        """Test that search_knowledge has a description"""
        assert agent_tools.search_knowledge.description is not None
        assert len(agent_tools.search_knowledge.description) > 0

    def test_search_knowledge_has_params_schema(self):
        """Test that search_knowledge has parameter schema"""
        assert agent_tools.search_knowledge.params_json_schema is not None
        # Should have query parameter
        assert "properties" in agent_tools.search_knowledge.params_json_schema
        assert "query" in agent_tools.search_knowledge.params_json_schema["properties"]

    def test_search_web_exists(self):
        """Test that search_web exists and is a FunctionTool"""
        assert hasattr(agent_tools, "search_web")
        assert isinstance(agent_tools.search_web, FunctionTool)

    def test_search_web_has_correct_name(self):
        """Test that search_web has the correct name"""
        assert agent_tools.search_web.name == "search_web"

    def test_search_web_has_description(self):
        """Test that search_web has a description"""
        assert agent_tools.search_web.description is not None
        assert len(agent_tools.search_web.description) > 0

    def test_search_web_has_params_schema(self):
        """Test that search_web has parameter schema"""
        assert agent_tools.search_web.params_json_schema is not None
        # Should have query parameter
        assert "properties" in agent_tools.search_web.params_json_schema
        assert "query" in agent_tools.search_web.params_json_schema["properties"]

    def test_both_tools_have_on_invoke_tool(self):
        """Test that both tools have the on_invoke_tool method"""
        assert callable(agent_tools.search_knowledge.on_invoke_tool)
        assert callable(agent_tools.search_web.on_invoke_tool)


class TestSearchKnowledgeResultFormat:
    """Test search_knowledge result format structure using strongly typed models"""

    @pytest.fixture
    def mock_context(self):
        """Create a mock agent context"""
        context = MagicMock(spec=AgentContext)
        context.source_channels = [SourceChannel.ROC]
        context.user_permission = "default"
        return context

    @pytest.fixture
    def mock_wrapper(self, mock_context):
        """Create a mock wrapper with context"""
        wrapper = MagicMock()
        wrapper.context = mock_context
        return wrapper

    @pytest.fixture
    def mock_rag_result(self):
        """Create a mock RAG result with the expected structure"""
        mock_result = MagicMock()
        mock_result.query = "test query"
        mock_result.contexts = [
            {
                "text": "Context text 1",
                "score": 0.95,
                "rerank_score": 0.92,
                "channel": "documentation",
                "Title": "RSPile User Guide",
                "URL_Link": "https://example.com/guide",
                "file_name": "rspile_guide.pdf",
                "Page_Number": 42,
            },
            {
                "text": "Context text 2",
                "score": 0.88,
                "rerank_score": 0.85,
                "channel": "tech_support",
                "title": "Technical Support Article",
                "URL": "https://example.com/article",
                "file_name": "support.md",
                "Page_Number": None,
            },
            {
                "text": "Context text 3",
                "score": "0.75",  # String to test _safe_float
                "rerank_score": None,  # None to test _safe_float default
                "channel": "diana",
                "title": None,
                "URL_Link_With_Page": "https://example.com/doc#page5",
                "file_name": None,
                "Page_Number": 5,
            },
        ]
        mock_result.total_retrieved = 10
        mock_result.channels_searched = ["documentation", "tech_support", "diana"]
        mock_result.reranker_used = "cohere"
        return mock_result

    @pytest.mark.asyncio
    async def test_result_has_required_top_level_fields(
        self, mock_wrapper, mock_rag_result
    ):
        """Test that result has query, contexts, and metadata fields"""
        with patch(
            "app.services.agent.tools.base_tools.get_rag_service"
        ) as mock_get_rag_service:
            mock_rag_service = AsyncMock()
            mock_rag_service.retrieve_and_rerank.return_value = mock_rag_result
            mock_get_rag_service.return_value = mock_rag_service

            result_json = await agent_tools.search_knowledge.on_invoke_tool(
                mock_wrapper, json.dumps({"query": "test query"})
            )
            result_dict = json.loads(result_json)

            assert "query" in result_dict
            assert "contexts" in result_dict
            assert "metadata" in result_dict

    @pytest.mark.asyncio
    async def test_result_query_field(self, mock_wrapper, mock_rag_result):
        """Test that query field is properly set"""
        with patch(
            "app.services.agent.tools.base_tools.get_rag_service"
        ) as mock_get_rag_service:
            mock_rag_service = AsyncMock()
            mock_rag_service.retrieve_and_rerank.return_value = mock_rag_result
            mock_get_rag_service.return_value = mock_rag_service

            result_json = await agent_tools.search_knowledge.on_invoke_tool(
                mock_wrapper, json.dumps({"query": "test query"})
            )
            result_dict = json.loads(result_json)
            assert result_dict["query"] == "test query"

    @pytest.mark.asyncio
    async def test_result_contexts_structure(self, mock_wrapper, mock_rag_result):
        """Test that contexts have correct structure with required fields"""
        with patch(
            "app.services.agent.tools.base_tools.get_rag_service"
        ) as mock_get_rag_service:
            mock_rag_service = AsyncMock()
            mock_rag_service.retrieve_and_rerank.return_value = mock_rag_result
            mock_get_rag_service.return_value = mock_rag_service

            result_json = await agent_tools.search_knowledge.on_invoke_tool(
                mock_wrapper, json.dumps({"query": "test query"})
            )
            result_dict = json.loads(result_json)

            assert len(result_dict["contexts"]) == 3

            # Check first context has all required fields
            context = result_dict["contexts"][0]
            assert "text" in context
            assert "score" in context
            assert "rerank_score" in context
            assert "rank" in context
            assert "channel" in context
            assert "source" in context
            assert "title" in context["source"]
            assert "url" in context["source"]
            assert "file_name" in context["source"]
            assert "page" in context["source"]

    @pytest.mark.asyncio
    async def test_result_context_source_structure(self, mock_wrapper, mock_rag_result):
        """Test that context source has correct structure"""
        with patch(
            "app.services.agent.tools.base_tools.get_rag_service"
        ) as mock_get_rag_service:
            mock_rag_service = AsyncMock()
            mock_rag_service.retrieve_and_rerank.return_value = mock_rag_result
            mock_get_rag_service.return_value = mock_rag_service

            result_json = await agent_tools.search_knowledge.on_invoke_tool(
                mock_wrapper, json.dumps({"query": "test query"})
            )
            result_dict = json.loads(result_json)

            # Check source structure
            source = result_dict["contexts"][0]["source"]
            assert "title" in source
            assert "url" in source
            assert "file_name" in source
            assert "page" in source

    @pytest.mark.asyncio
    async def test_result_context_values(self, mock_wrapper, mock_rag_result):
        """Test that context values are correctly extracted"""
        with patch(
            "app.services.agent.tools.base_tools.get_rag_service"
        ) as mock_get_rag_service:
            mock_rag_service = AsyncMock()
            mock_rag_service.retrieve_and_rerank.return_value = mock_rag_result
            mock_get_rag_service.return_value = mock_rag_service

            result_json = await agent_tools.search_knowledge.on_invoke_tool(
                mock_wrapper, json.dumps({"query": "test query"})
            )
            result_dict = json.loads(result_json)

            # Check first context values
            context1 = result_dict["contexts"][0]
            assert context1["text"] == "Context text 1"
            assert context1["score"] == 0.95
            assert context1["rerank_score"] == 0.92
            assert context1["rank"] == 1
            assert context1["channel"] == "documentation"
            assert context1["source"]["title"] == "RSPile User Guide"
            assert context1["source"]["url"] == "https://example.com/guide"
            assert context1["source"]["file_name"] == "rspile_guide.pdf"
            assert context1["source"]["page"] == 42

    @pytest.mark.asyncio
    async def test_result_context_rank_ordering(self, mock_wrapper, mock_rag_result):
        """Test that contexts have sequential rank values"""
        with patch(
            "app.services.agent.tools.base_tools.get_rag_service"
        ) as mock_get_rag_service:
            mock_rag_service = AsyncMock()
            mock_rag_service.retrieve_and_rerank.return_value = mock_rag_result
            mock_get_rag_service.return_value = mock_rag_service

            result_json = await agent_tools.search_knowledge.on_invoke_tool(
                mock_wrapper, json.dumps({"query": "test query"})
            )
            result_dict = json.loads(result_json)

            # Check rank ordering
            assert result_dict["contexts"][0]["rank"] == 1
            assert result_dict["contexts"][1]["rank"] == 2
            assert result_dict["contexts"][2]["rank"] == 3

    @pytest.mark.asyncio
    async def test_result_title_fallback(self, mock_wrapper, mock_rag_result):
        """Test that title falls back from Title -> title"""
        with patch(
            "app.services.agent.tools.base_tools.get_rag_service"
        ) as mock_get_rag_service:
            mock_rag_service = AsyncMock()
            mock_rag_service.retrieve_and_rerank.return_value = mock_rag_result
            mock_get_rag_service.return_value = mock_rag_service

            result_json = await agent_tools.search_knowledge.on_invoke_tool(
                mock_wrapper, json.dumps({"query": "test query"})
            )
            result_dict = json.loads(result_json)

            # First has Title
            assert result_dict["contexts"][0]["source"]["title"] == "RSPile User Guide"
            # Second has title (lowercase)
            assert (
                result_dict["contexts"][1]["source"]["title"]
                == "Technical Support Article"
            )
            # Third has neither
            assert result_dict["contexts"][2]["source"]["title"] is None

    @pytest.mark.asyncio
    async def test_result_url_fallback(self, mock_wrapper, mock_rag_result):
        """Test that url falls back from URL_Link -> URL -> URL_Link_With_Page"""
        with patch(
            "app.services.agent.tools.base_tools.get_rag_service"
        ) as mock_get_rag_service:
            mock_rag_service = AsyncMock()
            mock_rag_service.retrieve_and_rerank.return_value = mock_rag_result
            mock_get_rag_service.return_value = mock_rag_service

            result_json = await agent_tools.search_knowledge.on_invoke_tool(
                mock_wrapper, json.dumps({"query": "test query"})
            )
            result_dict = json.loads(result_json)

            # First has URL_Link
            assert (
                result_dict["contexts"][0]["source"]["url"]
                == "https://example.com/guide"
            )
            # Second has URL
            assert (
                result_dict["contexts"][1]["source"]["url"]
                == "https://example.com/article"
            )
            # Third has URL_Link_With_Page
            assert (
                result_dict["contexts"][2]["source"]["url"]
                == "https://example.com/doc#page5"
            )

    @pytest.mark.asyncio
    async def test_result_safe_float_conversion(self, mock_wrapper, mock_rag_result):
        """Test that _safe_float properly converts values"""
        with patch(
            "app.services.agent.tools.base_tools.get_rag_service"
        ) as mock_get_rag_service:
            mock_rag_service = AsyncMock()
            mock_rag_service.retrieve_and_rerank.return_value = mock_rag_result
            mock_get_rag_service.return_value = mock_rag_service

            result_json = await agent_tools.search_knowledge.on_invoke_tool(
                mock_wrapper, json.dumps({"query": "test query"})
            )
            result_dict = json.loads(result_json)

            # Third context has string score and None rerank_score
            context3 = result_dict["contexts"][2]
            assert context3["score"] == 0.75  # String "0.75" converted to float
            assert context3["rerank_score"] == 0.0  # None converted to default 0.0
            assert isinstance(context3["score"], float)
            assert isinstance(context3["rerank_score"], float)

    @pytest.mark.asyncio
    async def test_result_metadata_structure(self, mock_wrapper, mock_rag_result):
        """Test that metadata has correct structure and values"""
        with patch(
            "app.services.agent.tools.base_tools.get_rag_service"
        ) as mock_get_rag_service:
            mock_rag_service = AsyncMock()
            mock_rag_service.retrieve_and_rerank.return_value = mock_rag_result
            mock_get_rag_service.return_value = mock_rag_service

            result_json = await agent_tools.search_knowledge.on_invoke_tool(
                mock_wrapper, json.dumps({"query": "test query"})
            )
            result_dict = json.loads(result_json)

            metadata = result_dict["metadata"]
            assert "total_retrieved" in metadata
            assert "channels_searched" in metadata
            assert "reranker_used" in metadata
            assert "results_returned" in metadata

            assert metadata["total_retrieved"] == 10
            assert metadata["channels_searched"] == [
                "documentation",
                "tech_support",
                "diana",
            ]
            assert metadata["reranker_used"] == "cohere"
            assert metadata["results_returned"] == 3
