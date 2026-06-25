"""Unit tests for chat instructions templates"""

import pytest

from app.services.streaming.chat_instructions import (
    BASIC_USERS_CHAT_RESPONSE_TEMPLATE,
    FLEXIBLE_USERS_CHAT_RESPONSE_TEMPLATE,
    PERPLEXITY_CHAT_RESPONSE_TEMPLATE,
)

# Note: The actual code uses .safe_substitute() not .substitute()
# safe_substitute() doesn't raise errors for missing keys or unescaped $ symbols


class TestBasicUsersChatResponseTemplate:
    """Test BASIC_USERS_CHAT_RESPONSE_TEMPLATE functionality"""

    def test_template_substitution_with_relevant_context(self):
        """Test basic template substitution with relevant context"""
        relevant_context = "RSPile is a powerful geotechnical software."
        result = BASIC_USERS_CHAT_RESPONSE_TEMPLATE.safe_substitute(
            relevant_context=relevant_context
        )

        assert relevant_context in result
        assert "$relevant_context" not in result

    def test_template_contains_key_instructions(self):
        """Test that substituted template contains key instruction text"""
        relevant_context = "Test context"
        result = BASIC_USERS_CHAT_RESPONSE_TEMPLATE.safe_substitute(
            relevant_context=relevant_context
        )

        # Check for key instruction phrases
        assert "Rocscience knowledge assistant" in result
        assert "do not have access to real-time web search" in result.lower()
        assert "Source priority & scope" in result
        assert "Quoting" in result
        assert "Formatting" in result
        assert "For citations:" in result
        assert "Right-sized answers" in result

    def test_template_with_empty_context(self):
        """Test template substitution with empty context"""
        result = BASIC_USERS_CHAT_RESPONSE_TEMPLATE.safe_substitute(relevant_context="")

        assert "$relevant_context" not in result
        assert "Relevant context:" in result

    def test_template_with_multiline_context(self):
        """Test template substitution with multiline context"""
        relevant_context = """Context line 1
Context line 2
Context line 3"""
        result = BASIC_USERS_CHAT_RESPONSE_TEMPLATE.safe_substitute(
            relevant_context=relevant_context
        )

        assert "Context line 1" in result
        assert "Context line 2" in result
        assert "Context line 3" in result

    def test_template_with_special_characters_in_context(self):
        """Test template substitution with special characters"""
        relevant_context = "Context with $special & <characters>"
        result = BASIC_USERS_CHAT_RESPONSE_TEMPLATE.safe_substitute(
            relevant_context=relevant_context
        )

        assert relevant_context in result

    def test_template_missing_parameter_leaves_placeholder(self):
        """Test that missing required parameter leaves placeholder with safe_substitute"""
        result = BASIC_USERS_CHAT_RESPONSE_TEMPLATE.safe_substitute()
        # safe_substitute leaves undefined placeholders in place
        assert "$relevant_context" in result

    def test_template_vendor_restrictions(self):
        """Test that template includes vendor restrictions"""
        result = BASIC_USERS_CHAT_RESPONSE_TEMPLATE.safe_substitute(
            relevant_context="test"
        )

        assert "Rocscience" in result
        assert "DIANA" in result
        assert "2Si" in result
        assert "Rockfield" in result
        assert "Aquanty" in result


class TestFlexibleUsersChatResponseTemplate:
    """Test FLEXIBLE_USERS_CHAT_RESPONSE_TEMPLATE functionality"""

    def test_template_substitution_with_all_parameters(self):
        """Test template substitution with all required parameters"""
        relevant_context = "Documentation context"
        expert_opinion = "Expert opinion from tech support"

        result = FLEXIBLE_USERS_CHAT_RESPONSE_TEMPLATE.safe_substitute(
            relevant_context=relevant_context, expert_opinion=expert_opinion
        )

        assert relevant_context in result
        assert expert_opinion in result
        assert "$relevant_context" not in result
        assert "$expert_opinion" not in result

    def test_template_contains_key_instructions(self):
        """Test that substituted template contains key instruction text"""
        result = FLEXIBLE_USERS_CHAT_RESPONSE_TEMPLATE.safe_substitute(
            relevant_context="test", expert_opinion="test"
        )

        # Check for key instruction phrases
        assert "Rocscience Assistant" in result
        assert "do not have access to real-time web search" in result.lower()
        assert "tech-support container" in result
        assert "Prompt-injection safety" in result
        assert "Citations:" in result
        assert "[Expert Opinion]" in result

    def test_template_with_empty_parameters(self):
        """Test template substitution with empty parameters"""
        result = FLEXIBLE_USERS_CHAT_RESPONSE_TEMPLATE.safe_substitute(
            relevant_context="", expert_opinion=""
        )

        assert "$relevant_context" not in result
        assert "$expert_opinion" not in result

    def test_template_missing_relevant_context_leaves_placeholder(self):
        """Test that missing relevant_context leaves placeholder with safe_substitute"""
        result = FLEXIBLE_USERS_CHAT_RESPONSE_TEMPLATE.safe_substitute(
            expert_opinion="test opinion"
        )
        # safe_substitute leaves undefined placeholders in place
        assert "$relevant_context" in result
        assert "test opinion" in result

    def test_template_missing_expert_opinion_leaves_placeholder(self):
        """Test that missing expert_opinion leaves placeholder with safe_substitute"""
        result = FLEXIBLE_USERS_CHAT_RESPONSE_TEMPLATE.safe_substitute(
            relevant_context="test context"
        )
        # safe_substitute leaves undefined placeholders in place
        assert "$expert_opinion" in result
        assert "test context" in result

    def test_template_priority_order(self):
        """Test that template includes source priority order"""
        result = FLEXIBLE_USERS_CHAT_RESPONSE_TEMPLATE.safe_substitute(
            relevant_context="test", expert_opinion="test"
        )

        # Check priority mentions
        assert "strict order of priority" in result
        assert "tech-support" in result
        assert "product documentation" in result
        assert "pre-retrieved web content" in result

    def test_template_vendor_restrictions(self):
        """Test that template includes vendor restrictions"""
        result = FLEXIBLE_USERS_CHAT_RESPONSE_TEMPLATE.safe_substitute(
            relevant_context="test", expert_opinion="test"
        )

        assert "Rocscience" in result
        assert "DIANA" in result
        assert "2Si" in result
        assert "Rockfield" in result
        assert "Aquanty" in result

    def test_template_with_multiline_parameters(self):
        """Test template with multiline parameters"""
        relevant_context = """Line 1 of context
Line 2 of context"""
        expert_opinion = """Expert line 1
Expert line 2"""

        result = FLEXIBLE_USERS_CHAT_RESPONSE_TEMPLATE.safe_substitute(
            relevant_context=relevant_context, expert_opinion=expert_opinion
        )

        assert "Line 1 of context" in result
        assert "Line 2 of context" in result
        assert "Expert line 1" in result
        assert "Expert line 2" in result


class TestPerplexityChatResponseTemplate:
    """Test PERPLEXITY_CHAT_RESPONSE_TEMPLATE functionality"""

    def test_template_substitution_with_relevant_context(self):
        """Test template substitution with relevant context"""
        relevant_context = "Perplexity context"
        result = PERPLEXITY_CHAT_RESPONSE_TEMPLATE.safe_substitute(
            relevant_context=relevant_context
        )

        assert relevant_context in result
        assert "$relevant_context" not in result

    def test_template_contains_key_instructions(self):
        """Test that substituted template contains key instruction text"""
        result = PERPLEXITY_CHAT_RESPONSE_TEMPLATE.safe_substitute(
            relevant_context="test"
        )

        # Check for key instruction phrases
        assert "REAL-TIME WEB SEARCH ACCESS" in result
        assert "Rules:" in result
        assert "Formatting:" in result
        assert "Citations:" in result

    def test_template_with_empty_context(self):
        """Test template substitution with empty context"""
        result = PERPLEXITY_CHAT_RESPONSE_TEMPLATE.safe_substitute(relevant_context="")

        assert "$relevant_context" not in result
        assert "Relevant context from documentation:" in result

    def test_template_missing_parameter_leaves_placeholder(self):
        """Test that missing required parameter leaves placeholder with safe_substitute"""
        result = PERPLEXITY_CHAT_RESPONSE_TEMPLATE.safe_substitute()
        # safe_substitute leaves undefined placeholders in place
        assert "$relevant_context" in result

    def test_template_web_search_capability(self):
        """Test that template mentions web search capability"""
        result = PERPLEXITY_CHAT_RESPONSE_TEMPLATE.safe_substitute(
            relevant_context="test"
        )

        assert "real-time" in result.lower()
        assert "web search" in result.lower()
        assert "search the web" in result.lower()

    def test_template_citation_handling(self):
        """Test that template includes proper citation handling"""
        result = PERPLEXITY_CHAT_RESPONSE_TEMPLATE.safe_substitute(
            relevant_context="test"
        )

        assert "DO NOT include URLs in your response" in result
        assert "relevant_context sources" in result
        assert "web search sources" in result

    def test_template_vendor_restrictions(self):
        """Test that template includes vendor restrictions"""
        result = PERPLEXITY_CHAT_RESPONSE_TEMPLATE.safe_substitute(
            relevant_context="test"
        )

        assert "Rocscience" in result
        assert "avoid citing competing geotechnical software vendors" in result

    def test_template_with_multiline_context(self):
        """Test template with multiline context"""
        relevant_context = """Context line 1
Context line 2
Context line 3"""

        result = PERPLEXITY_CHAT_RESPONSE_TEMPLATE.safe_substitute(
            relevant_context=relevant_context
        )

        assert "Context line 1" in result
        assert "Context line 2" in result
        assert "Context line 3" in result

    def test_template_injection_safety(self):
        """Test that template includes injection safety instructions"""
        result = PERPLEXITY_CHAT_RESPONSE_TEMPLATE.safe_substitute(
            relevant_context="test"
        )

        assert "Injection safety" in result


class TestTemplateConsistency:
    """Test consistency across templates"""

    def test_all_templates_mention_markdown(self):
        """Test that all templates mention Markdown formatting"""
        basic = BASIC_USERS_CHAT_RESPONSE_TEMPLATE.safe_substitute(
            relevant_context="test"
        )
        flexible = FLEXIBLE_USERS_CHAT_RESPONSE_TEMPLATE.safe_substitute(
            relevant_context="test", expert_opinion="test"
        )
        perplexity = PERPLEXITY_CHAT_RESPONSE_TEMPLATE.safe_substitute(
            relevant_context="test"
        )

        assert "Markdown" in basic
        assert "Markdown" in flexible
        assert "Markdown" in perplexity

    def test_all_templates_mention_equations(self):
        """Test that all templates mention equation formatting"""
        basic = BASIC_USERS_CHAT_RESPONSE_TEMPLATE.safe_substitute(
            relevant_context="test"
        )
        flexible = FLEXIBLE_USERS_CHAT_RESPONSE_TEMPLATE.safe_substitute(
            relevant_context="test", expert_opinion="test"
        )
        perplexity = PERPLEXITY_CHAT_RESPONSE_TEMPLATE.safe_substitute(
            relevant_context="test"
        )

        # Check for equation formatting instructions
        # Note: In Template, $$ is an escape sequence for a literal $
        # So "$$" in the template becomes "$" after safe_substitute()
        assert "$" in basic or "equation" in basic.lower()
        assert "$" in flexible or "equation" in flexible.lower()
        assert "$" in perplexity or "equation" in perplexity.lower()

    def test_all_templates_mention_citations(self):
        """Test that all templates include citation instructions"""
        basic = BASIC_USERS_CHAT_RESPONSE_TEMPLATE.safe_substitute(
            relevant_context="test"
        )
        flexible = FLEXIBLE_USERS_CHAT_RESPONSE_TEMPLATE.safe_substitute(
            relevant_context="test", expert_opinion="test"
        )
        perplexity = PERPLEXITY_CHAT_RESPONSE_TEMPLATE.safe_substitute(
            relevant_context="test"
        )

        assert "citation" in basic.lower() or "cite" in basic.lower()
        assert "citation" in flexible.lower() or "cite" in flexible.lower()
        assert "citation" in perplexity.lower() or "cite" in perplexity.lower()

    def test_all_templates_mention_rocscience(self):
        """Test that all templates mention Rocscience"""
        basic = BASIC_USERS_CHAT_RESPONSE_TEMPLATE.safe_substitute(
            relevant_context="test"
        )
        flexible = FLEXIBLE_USERS_CHAT_RESPONSE_TEMPLATE.safe_substitute(
            relevant_context="test", expert_opinion="test"
        )
        perplexity = PERPLEXITY_CHAT_RESPONSE_TEMPLATE.safe_substitute(
            relevant_context="test"
        )

        assert "Rocscience" in basic
        assert "Rocscience" in flexible
        assert "Rocscience" in perplexity
