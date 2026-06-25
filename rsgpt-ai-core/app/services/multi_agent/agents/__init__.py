"""Agent implementations (shared classes; MCP servers are configured in YAML, not one folder per agent)."""

from app.services.multi_agent.agents.consultant import SoftwareConsultantAgent, register_consultant
from app.services.multi_agent.agents.specialist import MCPSpecialistAgent, register_specialists

__all__ = [
    "MCPSpecialistAgent",
    "register_specialists",
    "SoftwareConsultantAgent",
    "register_consultant",
]
