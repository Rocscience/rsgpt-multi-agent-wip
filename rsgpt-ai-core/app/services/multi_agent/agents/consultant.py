"""Pinecone/Cohere RAG-backed software workflow consultant for MCP specialists."""

from __future__ import annotations

import json
import logging

from agents import Agent, Runner

from app.services.multi_agent.model_resolver import agent_model
from autogen_core import AgentId, MessageContext, RoutedAgent, rpc

from app.models.channels import SourceChannel
from app.services.multi_agent.app_context import AppContext
from app.services.multi_agent.messages import ConsultantQuery, ConsultantResponse
from app.services.search.rag_service import get_rag_service

logger = logging.getLogger(__name__)

_AGENT_KEY = "default"
CONSULTANT_AGENT_TYPE = "software_consultant"


class SoftwareConsultantAgent(RoutedAgent):
    """Answers workflow / product how-to questions via production Pinecone RAG."""

    def __init__(self, app: AppContext) -> None:
        super().__init__("Software consultant (RAG)")
        self._app = app

    @rpc
    async def handle_consultant_query(
        self,
        message: ConsultantQuery,
        ctx: MessageContext,
    ) -> ConsultantResponse:
        self._app.activity.emit(
            "consultant_query_received",
            from_server=message.from_server,
            request_id=message.request_id,
            question=message.question,
            software=message.software,
        )
        try:
            answer, sources = await _retrieve_and_synthesize(
                question=message.question,
                software=message.software,
                app=self._app,
            )
            ok = bool(answer.strip())
        except Exception as exc:
            logger.exception("Consultant RAG failed")
            answer = f"Knowledge search failed: {exc}"
            sources = []
            ok = False

        self._app.activity.emit(
            "consultant_response_sent",
            to_server=message.from_server,
            request_id=message.request_id,
            answer_excerpt=(answer or "")[:800],
            sources=sources[:5],
        )
        return ConsultantResponse(
            answer=answer,
            request_id=message.request_id,
            ok=ok,
            sources=sources,
        )


async def _retrieve_and_synthesize(
    *,
    question: str,
    software: str,
    app: AppContext,
) -> tuple[str, list[str]]:
    rag = get_rag_service()
    top_k = max(1, app.cfg.consultant.top_k)
    query = question.strip()
    if software:
        query = f"{software}: {query}"

    rag_result = await rag.retrieve_and_rerank(
        query=query,
        source_channels=app.source_channels or [SourceChannel.ROC],
        user_permission=app.user_permission,
        top_k=top_k,
    )

    contexts = rag_result.contexts or []
    if not contexts:
        return (
            "No relevant documentation found in the knowledge base for this question.",
            [],
        )

    context_lines: list[str] = []
    sources: list[str] = []
    for ctx in contexts:
        title = ctx.get("Title") or ctx.get("file_name") or "Document"
        url = ctx.get("URL_Link") or ctx.get("url") or ""
        text = ctx.get("text") or ""
        src_label = f"{title} ({url})" if url else str(title)
        sources.append(src_label)
        context_lines.append(f"### {src_label}\n{text}\n")

    context_block = "\n".join(context_lines)
    model = app.cfg.consultant.effective_model(app.cfg.model)
    answer = await _synthesize_answer(
        question=question,
        software=software,
        context_block=context_block,
        model=model,
    )
    return answer, sources


async def _synthesize_answer(
    *,
    question: str,
    software: str,
    context_block: str,
    model: str,
) -> str:
    instructions = (
        "You are a Rocscience software workflow consultant. "
        "Answer ONLY from the retrieved documentation excerpts — do not invent menu paths, "
        "parameter names, or step orders. "
        "When the user asks about MCP tool order or creating a model from scratch, "
        "give a numbered workflow with prerequisites first. "
        "If excerpts are insufficient, say what is missing. "
        "Keep answers concise and actionable."
    )
    agent = Agent(
        name="software-consultant",
        instructions=instructions,
        model=agent_model(model),
    )
    user_input = (
        f"Specialist product context: {software or 'general Rocscience'}\n"
        f"Question:\n{question.strip()}\n\n"
        f"Documentation excerpts:\n{context_block}"
    )
    try:
        result = await Runner.run(agent, input=user_input, max_turns=4)
    except TypeError:
        result = await Runner.run(agent, input=user_input)
    final = getattr(result, "final_output", None)
    if isinstance(final, str) and final.strip():
        return final.strip()
    return str(result)


async def register_consultant(runtime, app: AppContext) -> AgentId:
    agent_id = AgentId(type=CONSULTANT_AGENT_TYPE, key=_AGENT_KEY)
    agent = SoftwareConsultantAgent(app)
    await agent.register_instance(runtime, agent_id)
    app.consultant_agent_id = agent_id
    app.activity.emit(
        "consultant_registered",
        agent_id=str(agent_id),
        backend="pinecone_cohere",
    )
    return agent_id
