"""Multi-agent YAML configuration models."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

_ENV_BRACE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def expand_env_placeholders(value: str) -> str:
    def repl(m: re.Match[str]) -> str:
        key = m.group(1)
        return os.environ[key] if key in os.environ else m.group(0)

    return _ENV_BRACE.sub(repl, value)


class BootstrapCall(BaseModel):
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ServerEntry(BaseModel):
    """One logical MCP server (tools filtered from desktop gateway)."""

    display_name: str = ""
    capabilities: str = ""
    integration_hints: str = ""
    peer_offers: str = ""
    peer_needs: str = ""
    agent_playbook: str = ""
    file_extensions: list[str] = Field(default_factory=list)
    # Regex patterns (matched case-insensitively) for tool names that belong to
    # this logical server when the desktop gateway aggregates every product's
    # tools onto one device. Keeps product-specific routing in config, not code.
    tool_patterns: list[str] = Field(default_factory=list)
    open_tool: str = ""
    open_path_arg: str = "path"
    state_tool: str = ""
    state_tool_arguments: dict[str, Any] = Field(default_factory=dict)
    default_file_path: str = ""
    scratch_model_path: str = ""
    agent_type: str = ""
    bootstrap_tools: list[BootstrapCall] = Field(default_factory=list)

    # Legacy stdio fields (ignored in production WebSocket mode)
    command: str = ""
    args: list[str] = Field(default_factory=list)
    cwd: str = ""
    env: dict[str, str] = Field(default_factory=dict)
    env_file: str = ""


class ConsultantSettings(BaseModel):
    enabled: bool = True
    top_k: int = 6
    model: str = ""
    display_name: str = "Software Consultant"

    def effective_model(self, default: str) -> str:
        return self.model or default


class OrchestratorSettings(BaseModel):
    validate_specialist_outputs: bool = True
    strict_validation: bool = True
    require_successful_open: bool = True
    require_mcp_tool_success: bool = False
    max_specialist_retries: int = 1
    retry_on_validation_failure: bool = True
    stop_on_validation_failure: bool = False
    stop_on_specialist_failure: bool = False
    keep_desktop_apps_open: bool = True


class CrossProductScenario(BaseModel):
    id: str
    title: str = ""
    servers: list[str] = Field(default_factory=list)
    goal_template: str = ""
    notes: str = ""


class MultiAgentConfig(BaseModel):
    model: str = "gpt-4o"
    planner_model: str = ""
    summarizer_model: str = ""
    peer_rpc_timeout_seconds: float = 180.0
    servers: dict[str, ServerEntry]
    bootstrap_tool_calls: dict[str, list[BootstrapCall]] = Field(default_factory=dict)
    agent_types: dict[str, str] = Field(default_factory=dict)
    cross_product_scenarios: list[CrossProductScenario] = Field(default_factory=list)
    orchestrator: OrchestratorSettings = Field(default_factory=OrchestratorSettings)
    consultant: ConsultantSettings = Field(default_factory=ConsultantSettings)

    @property
    def effective_planner_model(self) -> str:
        return self.planner_model or self.model

    @property
    def effective_summarizer_model(self) -> str:
        return self.summarizer_model or self.model


# Backward-compatible alias used by ported workflow code
V2DemoConfig = MultiAgentConfig


def load_demo_config(path: str | Path) -> MultiAgentConfig:
    import yaml

    p = Path(path)
    with p.open(encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return MultiAgentConfig.model_validate(raw)


def resolve_paths(cfg: MultiAgentConfig, config_path: str | Path) -> MultiAgentConfig:
    base = Path(config_path).resolve().parent
    servers: dict[str, ServerEntry] = {}
    for sid, entry in cfg.servers.items():
        raw_default = expand_env_placeholders((entry.default_file_path or "").strip())
        default_fp = ""
        if raw_default:
            p = Path(raw_default)
            default_fp = (
                str(p.resolve())
                if p.is_absolute()
                else str((base / raw_default).resolve())
            )
        raw_scratch = expand_env_placeholders((entry.scratch_model_path or "").strip())
        scratch_fp = ""
        if raw_scratch:
            p_scratch = Path(raw_scratch)
            scratch_fp = (
                str(p_scratch.resolve())
                if p_scratch.is_absolute()
                else str((base / raw_scratch).resolve())
            )
        bootstrap = list(entry.bootstrap_tools)
        if not bootstrap and sid in cfg.bootstrap_tool_calls:
            bootstrap = list(cfg.bootstrap_tool_calls[sid])
        servers[sid] = entry.model_copy(
            update={
                "default_file_path": default_fp,
                "scratch_model_path": scratch_fp,
                "bootstrap_tools": bootstrap,
            }
        )
    return cfg.model_copy(update={"servers": servers})


def default_config_path() -> Path:
    return Path(__file__).resolve().parent.parent.parent / "config" / "multi_agent_servers.yaml"


def load_default_config() -> MultiAgentConfig:
    path = default_config_path()
    cfg = load_demo_config(path)
    return resolve_paths(cfg, path)
