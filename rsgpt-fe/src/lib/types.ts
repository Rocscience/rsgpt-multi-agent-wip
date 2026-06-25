import { UUID } from "crypto";

// Model options for AI requests
export enum ModelName {
    // OpenAI Models
    GPT5_2 = "gpt-5.2-2025-12-11",
    
    // Anthropic Models
    // CLAUDE_SONNET_4_5 = "claude-sonnet-4-5-20250929", // Disabled
    CLAUDE_HAIKU_4_5 = "claude-haiku-4-5-20251001",
    // CLAUDE_OPUS_4_5 = "claude-opus-4-5-20251101", // Disabled
    
    // Perplexity Models (Disabled)
    // PERPLEXITY_SONAR = "sonar",
    // PERPLEXITY_SONAR_REASONING = "sonar-reasoning",

    // xAI Models (model name changes based on reasoning level)
    XAI_GROK_4_1_FAST = "grok-4-1-fast",

    // Google Models
    GEMINI_3_FLASH = "gemini-3-flash-preview",
}

// Model modes - which modes a model can be used in
export enum ModelMode {
    AGENT = "agent",
    REGULAR = "regular",
    BOTH = "both"
}

// Reasoning levels
export enum ReasoningLevel {
    NONE = "none",
    LOW = "low",
    MEDIUM = "medium",
    HIGH = "high"
}

// Maps frontend reasoning levels to backend reasoning effort values
export const REASONING_LEVEL_TO_EFFORT: Record<ReasoningLevel, string> = {
    [ReasoningLevel.NONE]: "none",
    [ReasoningLevel.LOW]: "low",
    [ReasoningLevel.MEDIUM]: "medium",
    [ReasoningLevel.HIGH]: "high"
};

// Provider types
export enum Provider {
    OPENAI = "openai",
    ANTHROPIC = "anthropic",
    PERPLEXITY = "perplexity",
    XAI = "xai",
    GOOGLE = "google"
}

// Comprehensive model configuration
export interface ModelConfig {
    id: ModelName;
    displayName: string;
    description: string;
    provider: Provider;
    model: string;
    reasoning: ReasoningLevel;
    modes: ModelMode[];
    max_input_tokens: number;
}

// Model configurations
export const MODEL_CONFIGS: Partial<Record<ModelName, ModelConfig>> = {
    // [ModelName.CLAUDE_OPUS_4_5]: {
    //     id: ModelName.CLAUDE_OPUS_4_5,
    //     displayName: "Claude Opus 4.5",
    //     description: "Anthropic's most powerful model for complex reasoning and analysis.",
    //     provider: Provider.ANTHROPIC,
    //     model: "claude-opus-4-5-20251101",
    //     reasoning: ReasoningLevel.HIGH, // Default reasoning level
    //     modes: [ModelMode.AGENT, ModelMode.REGULAR],
    //     max_input_tokens: 200000,
    // },
    // [ModelName.CLAUDE_SONNET_4_5]: {
    //     id: ModelName.CLAUDE_SONNET_4_5,
    //     displayName: "Claude Sonnet 4.5",
    //     description: "Anthropic's most capable model with extended thinking.",
    //     provider: Provider.ANTHROPIC,
    //     model: "claude-sonnet-4-5-20250929",
    //     reasoning: ReasoningLevel.MEDIUM, // Default reasoning level
    //     modes: [ModelMode.AGENT, ModelMode.REGULAR],
    //     max_input_tokens: 200000,
    // },
    [ModelName.CLAUDE_HAIKU_4_5]: {
        id: ModelName.CLAUDE_HAIKU_4_5,
        displayName: "Claude Haiku 4.5",
        description: "Anthropic's fastest model with extended thinking capability.",
        provider: Provider.ANTHROPIC,
        model: "claude-haiku-4-5-20251001",
        reasoning: ReasoningLevel.LOW, // Default reasoning level
        modes: [ModelMode.AGENT, ModelMode.REGULAR],
        max_input_tokens: 200000,
    },
    [ModelName.GPT5_2]: {
        id: ModelName.GPT5_2,
        displayName: "GPT-5.2",
        description: "OpenAI's latest model with improved reasoning capabilities.",
        provider: Provider.OPENAI,
        model: "gpt-5.2-2025-12-11",
        reasoning: ReasoningLevel.NONE, // Default reasoning level
        modes: [ModelMode.AGENT, ModelMode.REGULAR],
        max_input_tokens: 400000,
    },
    // [ModelName.PERPLEXITY_SONAR]: {
    //     id: ModelName.PERPLEXITY_SONAR,
    //     displayName: "Perplexity Sonar",
    //     description: "Perplexity's fast model with real-time web search.",
    //     provider: Provider.PERPLEXITY,
    //     model: "sonar",
    //     reasoning: ReasoningLevel.NONE,
    //     modes: [ModelMode.REGULAR],
    //     max_input_tokens: 1000000, // Not functional yet
    // },
    // [ModelName.PERPLEXITY_SONAR_REASONING]: {
    //     id: ModelName.PERPLEXITY_SONAR_REASONING,
    //     displayName: "Perplexity Sonar (Reasoning)",
    //     description: "Perplexity's reasoning model with web-search and problem solving.",
    //     provider: Provider.PERPLEXITY,
    //     model: "sonar-reasoning",
    //     reasoning: ReasoningLevel.NONE,
    //     modes: [ModelMode.REGULAR],
    //     max_input_tokens: 128000,
    // },
    [ModelName.XAI_GROK_4_1_FAST]: {
        id: ModelName.XAI_GROK_4_1_FAST,
        displayName: "xAI Grok 4.1 Fast",
        description: "xAI's fast model with optional reasoning capabilities.",
        provider: Provider.XAI,
        model: "grok-4-1-fast",  // Base model name - transformed based on reasoning level
        reasoning: ReasoningLevel.MEDIUM, // Default to reasoning
        modes: [ModelMode.AGENT],
        max_input_tokens: 350000,
    },
    [ModelName.GEMINI_3_FLASH]: {
        id: ModelName.GEMINI_3_FLASH,
        displayName: "Gemini 3 Flash",
        description: "Google's frontier-class model with fast performance at reduced cost.",
        provider: Provider.GOOGLE,
        model: "gemini-3-flash-preview",
        reasoning: ReasoningLevel.MEDIUM,
        modes: [ModelMode.AGENT, ModelMode.REGULAR],
        max_input_tokens: 1000000,
    }
};

// Helper functions to get models by mode
export const getModelsByMode = (mode: ModelMode): ModelConfig[] => {
    return Object.values(MODEL_CONFIGS).filter(config => 
        config.modes.includes(mode) || config.modes.includes(ModelMode.BOTH)
    );
};

export const getAgentModeModels = (): ModelConfig[] => {
    return getModelsByMode(ModelMode.AGENT);
};

export const getRegularModeModels = (): ModelConfig[] => {
    return getModelsByMode(ModelMode.REGULAR);
};

export interface ResponseSearchResultsEvent {
    sequence_number: number;
    response_id: string;
    search_results: Array<{
      title?: string;
      url?: string;
      date?: string;
      lastUpdated?: string;
      snippet?: string;
      source?: string;
    }>
}

export interface ContextUsageUpdateEvent {
  sequence_number: number;
  session_id: string;
  total_tokens: number;
  max_tokens: number;
  usage_percentage: number;
  model_name: string;
}

// Legacy event types (kept for backwards compatibility)
export interface ContextSummaryInitiationEvent {
  sequence_number: number;
  session_id: string;
  model_name: string;
  total_tokens: number;
  max_tokens: number;
  usage_percentage: number;
}

export interface ContextSummaryCompletionEvent {
  sequence_number: number;
  session_id: string;
  model_name: string;
  token_count: number;
  replaced_messages: number;
  summary: Record<string, any>;
}

// New context pruning events
export interface ContextSummarizingEvent {
  sequence_number: number;
  session_id: string;
  message_count: number;
}

export interface ContextPruningCompletedEvent {
  sequence_number: number;
  session_id: string;
  items_after_pruning: number;
}

export interface ContextPruningErrorEvent {
  sequence_number: number;
  session_id: string;
  error: string;
}

// List of Chat Sessions response
export interface GetChatSessionsListResponse {
    sessions: GetChatSessionMetaResponse[];
    total_count: number;
    page: number;
    page_size: number;
    total_pages: number;
    has_next: boolean;
    has_previous: boolean;
}

export interface GetChatSessionMetaResponse {
    user_id: UUID;
    chat_session_id: UUID;
    title: string;
    message_count: number;
    created_at: Date;
    updated_at: Date;
}

export interface CreateChatSessionResponse {
    id: UUID;
    user_id: UUID;
    title: string;
    message_count: number;
}

export type StreamPromptRequest = {
    prompt: string;
    source_selections: string[];
    client_temp_id: string;
    idempotency_key: string;
    model_name: string; 
    provider_name: string;  // e.g. anthropic, openai, perplexity
    is_agent_mode: boolean;  // default false
    device_id: string | null;  // optional
    is_web_search_enabled: boolean;  // default false
    reasoning: string | null;  // e.g. none, minimal, medium, high (optional)
};



export type GetQuotaInfoResponse = {
    organization_name: string;
    question_quota: number;
    questions_used: number;
    quota_reset_date: Date | null;
    agent_quota: number;
    agent_quota_used: number;
}

export type GetRocPortalStatusResponse = {
    rocportal_status: boolean;
    message: string | null;
}

export interface MessageFeedbackRequest {
  helpfulness_feedback: boolean; // true for helpful (like), false for not helpful (dislike)
  feedback_text?: string;
}

export interface MessageFeedbackResponse {
  success: boolean;
  message: string;
}

export type UserSettingsRequest = {
  theme: string;
  preferred_sources: string[];
  language: string;
  timezone: string;
  agent_mode_opt_in: boolean;
}

export type UserSettingsResponse = {
  preferred_sources: string[];
  theme: string;
  language: string;
  timezone: string;
  agent_mode_opt_in: boolean;
}

export type DeviceResponse = {
  device_id: string;
  device_token: string;
  device_name: string;
  device_type: string;
  os_name: string;
  os_version: string;
  app_version: string;
  mcp_servers: string[];
  last_active: string;
  is_active: boolean;
  created_at: string;
}

export type DeviceListResponse = {
  devices: DeviceResponse[];
  total_count: number;
}

export type MediaImage = {
  image_url: string;
  source_url: string;
}

export type MediaData = {
  images: MediaImage[];
  videos: string[];
}

export type MediaSearchStartEvent = {
  server_id: string;
}

export type MediaSearchCompletedEvent = {
  server_id: string;
  media_data: MediaData;
}

// New conversation history types to match the restructured backend
export interface UserMessageDto {
  id: string;
  message_text: string;
  status: string;
  sources_requested: string[];
  created_at: Date;
  client_temp_id?: string;
  idempotency_key?: string;
}

export interface AIResponseDto {
  id: string;
  message_text: string;
  status: string;
  response_time_ms?: number;
  sources_used: string[];
  model_used: string;
  token_count?: number;
  run_id?: string;
  created_at: Date;
  is_latest: boolean;
  media_links?: MediaData;
  lookingForMedia?: boolean;
  is_agent_mode?: boolean;
  search_results?: Array<{
    title?: string;
    url?: string;
    date?: string;
    lastUpdated?: string;
    snippet?: string;
    source?: string;
  }>;
  timeline?: {blocks: TimelineBlock[]};
  // Note: Tool executions are embedded in message_text using HTML comment markers
}

// Timeline block types for coalesced event storage
export interface TimelineBlock {
  id: string;
  sequence: number;
  timestamp_start: number;
  timestamp_end: number;
  type: TimelineBlockType;
  // Type-specific fields below
}

export type TimelineBlockType =
  | 'workflow_start'
  | 'workflow_end'
  | 'thinking_block'
  | 'message_block'
  | 'tool_execution_block'
  | 'status_block'
  | 'error_block'
  | 'summarization_block'
  | 'agent_transition_block';

// Specific block type interfaces
export interface WorkflowStartBlock extends TimelineBlock {
  type: 'workflow_start';
  trace_id: string;
  agent_name: string;
}

export interface WorkflowEndBlock extends TimelineBlock {
  type: 'workflow_end';
  trace_id: string;
  status: 'completed' | 'failed';
  total_duration_ms: number;
  error?: string;
}

export interface ThinkingBlock extends TimelineBlock {
  type: 'thinking_block';
  agent_name: string;
  content: string;
  is_complete: boolean;
  is_cancelled?: boolean; // Set to true when thinking was interrupted/cancelled
}

export interface MessageBlock extends TimelineBlock {
  type: 'message_block';
  agent_name: string;
  content: string;
}

export interface ToolExecutionBlock extends TimelineBlock {
  type: 'tool_execution_block';
  tool_call_id: string;
  tool_name: string;
  tool_args: Record<string, any>;
  status: 'running' | 'completed' | 'failed' | 'success' | 'cancelled'; // Note: backend uses 'status', not 'state'
  output?: any;
  error?: string;
}

export interface StatusBlock extends TimelineBlock {
  type: 'status_block';
  status: string;
  agent_name: string;
  description?: string;
}

export interface ErrorBlock extends TimelineBlock {
  type: 'error_block';
  error_type: string;
  error_message: string;
  agent_name: string;
}

export interface SummarizationBlock extends TimelineBlock {
  type: 'summarization_block';
  status: 'in_progress' | 'completed' | 'cancelled' | 'failed';
  agent_name: string;
  error?: string;
}

export interface AgentTransitionBlock extends TimelineBlock {
  type: 'agent_transition_block';
  from_agent: string;
  to_agent: string;
  tool_name?: string;
  completed?: boolean;
}

export interface ConversationTurnDto {
  user_message: UserMessageDto;
  ai_responses: AIResponseDto[];
  has_retries: boolean;
}

export interface GetConversationHistoryResponse {
  conversation: ConversationTurnDto[];
  total_count: number;
  page: number;
  page_size: number;
  total_pages: number;
  has_next: boolean;
  has_previous: boolean;
  current_token_count?: number;  // Optional: Total tokens used in this session (for context tracking)
}

// Regular chat streaming events
export interface ResponseCreatedEvent {
  sequence_number: number;
  response: {
    id: string;
    created_at: number;
    model: string;
    provider: string;
    status: string;
  };
}

export interface ResponseOutputTextDeltaEvent {
  sequence_number: number;
  delta: string;
  response_id: string;
}

export interface ResponseCompletedEvent {
  sequence_number: number;
  response: {
    id: string;
    created_at: number;
    model: string;
    provider: string;
    status: string;
    usage?: {
      input_tokens: number;
      output_tokens: number;
      total_tokens: number;
    };
  };
}

export interface ResponseFailedEvent {
  sequence_number: number;
  response: {
    id: string;
    created_at: number;
    model: string;
    provider: string;
    status: string;
  };
  error: string;
}

// Agent streaming events
export interface AgentRunStartedEvent {
  sequence_number: number;
  run: {
    id: string;
    agent_name: string;
    status: string;
    turn_count: number;
    created_at: number;
  };
}

export interface AgentToolExecutionStartedEvent {
  sequence_number: number;
  tool_call_id: string;
  tool_name: string;
  tool_args: Record<string, any>;
}

export interface AgentToolExecutionCompletedEvent {
  sequence_number: number;
  tool_call_id: string;
  tool_name: string;
  output: any;
}

export interface AgentToolExecutionFailedEvent {
  sequence_number: number;
  tool_call_id: string;
  tool_name: string;
  error: string;
}

export interface AgentRunCompletedEvent {
  sequence_number: number;
  run: {
    id: string;
    agent_name: string;
    status: string;
    turn_count: number;
    created_at: number;
  };
  final_output: string;
}

export interface AgentRunFailedEvent {
  sequence_number: number;
  run: {
    id: string;
    agent_name: string;
    status: string;
    turn_count: number;
    created_at: number;
  };
  error: string;
}

// RSLog Integration Types
export interface RSLogConnectTokenRequest {
  username: string;
  password: string;
  company: string;
}

export interface RSLogVerifyRequest {
  username: string;
  password: string;
  company: string;
  twoFactorCode: string;
}

export interface RSLogTokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  refresh_token: string;
  scope: string;
}

export interface RSLogTwoFactorResponse {
  status: string;
  twoFactorProvider: string;
  maskedEmail: string;
  message: string;
}

export interface RSLogErrorResponse {
  error: string;
  errorDescription: string;
}

export interface RSLogConnectionStatus {
  is_connected: boolean;
  company?: string;
  username?: string;
  token_expires_at?: string;
  needs_refresh: boolean;
}

export interface RSLogSettingsResponse {
  id: string;
  user_id: string;
  company: string;
  username: string;
  is_connected: boolean;
  token_expires_at?: string;
  created_at: string;
  updated_at: string;
}

// Generic delete operation response
export interface DeleteResponse {
  message: string;
}

// Quota Request Types
export interface QuotaRequestCreate {
  requested_quota: number;
  reason: string;
}

export interface QuotaRequestResponse {
  success: boolean;
  message: string;
  request_id?: string;
}