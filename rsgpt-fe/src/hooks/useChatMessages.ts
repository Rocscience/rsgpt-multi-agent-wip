'use client';

import { create } from 'zustand';
import type { MediaData, ConversationTurnDto, UserMessageDto, AIResponseDto, ModelName } from '@/lib/types';

export type ToolExecutionState = 'running' | 'completed' | 'failed' | 'cancelled';

export type ToolExecution = {
  toolCallId: string;
  toolName: string;
  toolArgs: Record<string, any>;
  state: ToolExecutionState;
  startedAt: number;
  completedAt?: number;
  error?: string;
  output?: any;
};

// Timeline event types for interleaving text and tool executions
export type TimelineEventType = 'text' | 'tool_start' | 'tool_complete' | 'tool_fail' | 'thinking' | 'summarization_start' | 'summarization_complete' | 'summarization_cancelled' | 'summarization_failed';

export type TimelineEvent = {
  type: TimelineEventType;
  timestamp: number;
  sequence: number;
} & (
  | { type: 'text'; content: string }
  | { type: 'tool_start'; toolCallId: string; toolName: string; toolArgs: Record<string, any> }
  | { type: 'tool_complete'; toolCallId: string; toolName: string; output?: any }
  | { type: 'tool_fail'; toolCallId: string; toolName: string; error: string }
  | { type: 'thinking'; agent: string; text: string; isComplete?: boolean }
  | { type: 'summarization_start' }
  | { type: 'summarization_complete' }
  | { type: 'summarization_cancelled' }
  | { type: 'summarization_failed'; error: string }
);

export type WorkflowTask = {
  id: number;
  description: string;
  status: 'pending' | 'in_progress' | 'completed' | 'failed';
  success_criteria?: string;
  validation?: string;
  hints?: string;
  risk?: string;
};

export type WorkflowPlan = {
  goal: string;
  assumptions?: string[];
  tasks: WorkflowTask[];
  requires_followup?: boolean;
  notes?: string;
};

export type WorkflowThinking = {
  agent: string;
  text: string;
  isComplete: boolean;
};

export type WorkflowTaskProgress = {
  currentTaskId: number;
  currentTaskIndex: number;
  totalTasks: number;
  taskDescription: string;
  status: string;
};

export type WorkflowState = {
  status?: 'CLASSIFYING' | 'KNOWLEDGE_SEARCH' | 'PLANNING' | 'EXECUTING' | 'EVALUATING' | 'SUMMARIZING' | 'COMPLETED' | 'OUT_OF_SCOPE' | 'FAILED';
  agentName?: string;
  traceId?: string;
  error?: string;
};

export type StreamingAIResponse = {
  id: string;
  text: string;
  isLoading?: boolean;
  isComplete?: boolean;
  isCancelled?: boolean; // NEW: Track if user cancelled the stream
  error?: string; // Track error messages from backend
  lookingForMedia?: boolean;
  mediaData?: MediaData;
  lastSeq?: number; // Last sequence number received (for streaming)
  meta?: Record<string, any>; // Additional metadata (token_count, finish_reason, etc.)
  // Track all tool executions (for agent mode) - ordered by start time
  toolExecutions?: ToolExecution[];
  // Timeline of events for rendering in order
  timeline?: TimelineEvent[];
  searchResults?: Array<{
    title?: string,
    url?: string,
    date?: string,
    lastUpdated?: string,
    snippet?: string,
    source?: string,
  }>;
  
  // === Multi-Agent Workflow State (Ephemeral, cleared after completion) ===
  workflowState?: WorkflowState;
  currentThinking?: WorkflowThinking;
  currentPlan?: WorkflowPlan;
  taskProgress?: WorkflowTaskProgress;
  
  // === Context Summarization State ===
  summarizationStatus?: {
    status: 'in_progress' | 'completed' | 'cancelled' | 'failed';
    startedAt: number;
    completedAt?: number;
    error?: string;
  };
};

export type CurrentStreamingTurn = {
  userMessage: UserMessageDto;
  aiResponse?: StreamingAIResponse;
};

type StreamState = {
  isStreaming: boolean;
  streamAbortController?: AbortController;
  streamCancelFunction?: () => void; // Function to properly cancel the stream
  streamSessionId?: string;
};

type ChatMessagesState = {
  // Conversation turns by session ID
  conversationsBySession: Record<string, ConversationTurnDto[]>;
  
  // Current streaming turn by session ID
  currentStreamingTurnBySession: Record<string, CurrentStreamingTurn>;
  
  // Stream state
  streamState: StreamState;
  
  // ID mapping for temp -> real ID swaps
  tempToRealMap: Record<string, string>;
  
  // Actions
  setConversationTurns: (sessionId: string, turns: ConversationTurnDto[]) => void;
  mergeConversationTurns: (sessionId: string, turns: ConversationTurnDto[]) => void;
  addConversationTurn: (sessionId: string, turn: ConversationTurnDto) => void;
  updateTurn: (sessionId: string, userMessageId: string, updates: Partial<ConversationTurnDto>) => void;
  
  // Streaming actions
  setStreamingTurn: (sessionId: string, turn: CurrentStreamingTurn) => void;
  updateStreamingAIResponse: (sessionId: string, updates: Partial<StreamingAIResponse>) => void;
  updateCompletedAIResponse: (sessionId: string, responseId: string, updates: Partial<AIResponseDto>) => void;
  appendToStreamingAIResponse: (sessionId: string, text: string, seq?: number) => void;
  completeStreamingTurn: (sessionId: string) => void;
  clearStreamingTurn: (sessionId: string) => void;
  cancelStreaming: (sessionId: string) => void;
  
  // Tool execution management (for agent mode)
  addToolExecution: (sessionId: string, toolCallId: string, toolName: string, toolArgs: Record<string, any>) => void;
  completeToolExecution: (sessionId: string, toolCallId: string, output?: any) => void;
  failToolExecution: (sessionId: string, toolCallId: string, error: string) => void;
  clearToolExecutions: (sessionId: string) => void;
  
  // Summarization event handlers
  startSummarization: (sessionId: string) => void;
  completeSummarization: (sessionId: string) => void;
  failSummarization: (sessionId: string, error: string) => void;
  
  // Workflow event handlers
  updateWorkflowState: (sessionId: string, workflowState: Partial<WorkflowState>) => void;
  updateThinking: (sessionId: string, thinking: WorkflowThinking) => void;
  updatePlan: (sessionId: string, plan: WorkflowPlan) => void;
  updateTaskProgress: (sessionId: string, progress: WorkflowTaskProgress) => void;
  clearWorkflowState: (sessionId: string) => void;
  
  // Getters
  getConversationTurns: (sessionId: string) => ConversationTurnDto[];
  getCurrentStreamingTurn: (sessionId: string) => CurrentStreamingTurn | undefined;
  clearSession: (sessionId: string) => void;
  
  // ID swapping for new streaming protocol
  swapMessageId: (sessionId: string, tempId: string, realId: string) => void;
  
  // Stream actions
  setStreamState: (state: Partial<StreamState>) => void;
  clearStreamState: () => void;
  isSessionStreaming: (sessionId: string) => boolean;
  
  // Clear all (for logout)
  clear: () => void;
};

export const useChatMessages = create<ChatMessagesState>((set, get) => ({
    conversationsBySession: {},
    currentStreamingTurnBySession: {},
    streamState: { isStreaming: false },
    tempToRealMap: {},
  
  setConversationTurns: (sessionId, turns) => 
    set(state => ({
      conversationsBySession: {
        ...state.conversationsBySession,
        [sessionId]: turns
      }
    })),

  mergeConversationTurns: (sessionId, newTurns) => 
    set(state => {
      const existingTurns = state.conversationsBySession[sessionId] || [];
      
      // DEFENSIVE: If newTurns is empty but we have existing turns, preserve existing
      // This prevents data loss when server hasn't persisted latest turn yet
      if (newTurns.length === 0 && existingTurns.length > 0) {
        return state; // No changes needed
      }
      
      // If no existing turns, only clear streaming turn if it's actually completed and stale
      if (existingTurns.length === 0) {
        const streamingTurn = state.currentStreamingTurnBySession[sessionId];
        let updatedStreamingTurns = state.currentStreamingTurnBySession;
        
        if (streamingTurn) {
          // Check if the streaming turn's user message is now in the database
          const streamingUserMessageId = streamingTurn.userMessage.id;
          const existsInDatabase = newTurns.some(turn => turn.user_message.id === streamingUserMessageId);
          
          // Only clear if the streaming turn is completed AND exists in database
          if (existsInDatabase && streamingTurn.aiResponse?.isComplete) {
            const { [sessionId]: _, ...remainingStreaming } = state.currentStreamingTurnBySession;
            updatedStreamingTurns = remainingStreaming;
          } else {
            // If we're preserving the streaming turn, filter out the duplicate from database
            if (existsInDatabase) {
              newTurns = newTurns.filter(turn => turn.user_message.id !== streamingUserMessageId);
            }
          }
        }
        
        return {
          conversationsBySession: {
            ...state.conversationsBySession,
            [sessionId]: newTurns
          },
          currentStreamingTurnBySession: updatedStreamingTurns
        };
      }
      
      // Create a Set of existing message IDs for efficient lookup
      const existingMessageIds = new Set(
        existingTurns.map(turn => turn.user_message.id)
      );
      
      // Filter new turns to only include ones we don't already have
      const trulyNewTurns = newTurns.filter(
        turn => !existingMessageIds.has(turn.user_message.id)
      );
      
      // Merge and sort by user message creation date
      const mergedTurns = [...existingTurns, ...trulyNewTurns].sort(
        (a, b) => new Date(a.user_message.created_at).getTime() - new Date(b.user_message.created_at).getTime()
      );
      
      // Check if there's a streaming turn that should be cleared because the message exists in database
      const streamingTurn = state.currentStreamingTurnBySession[sessionId];
      let updatedStreamingTurns = state.currentStreamingTurnBySession;
      
      if (streamingTurn) {
        // Check if the streaming turn's user message is now in the database
        const streamingUserMessageId = streamingTurn.userMessage.id;
        const existsInDatabase = newTurns.some(turn => turn.user_message.id === streamingUserMessageId);
        
        // Only clear the streaming turn if it exists in database AND the AI response is marked as complete
        // This prevents clearing ongoing streams when returning to a session
        if (existsInDatabase && streamingTurn.aiResponse?.isComplete) {
          // Clear the streaming turn since it's now completed and in the database
          const { [sessionId]: _, ...remaining } = updatedStreamingTurns;
          updatedStreamingTurns = remaining;
        }
      }
      
      return {
        conversationsBySession: {
          ...state.conversationsBySession,
          [sessionId]: mergedTurns
        },
        currentStreamingTurnBySession: updatedStreamingTurns
      };
    }),
  
  addConversationTurn: (sessionId, turn) =>
    set(state => ({
      conversationsBySession: {
        ...state.conversationsBySession,
        [sessionId]: [...(state.conversationsBySession[sessionId] || []), turn]
      }
    })),
  
  updateTurn: (sessionId, userMessageId, updates) =>
    set(state => {
      const turns = state.conversationsBySession[sessionId] || [];
      const turnIndex = turns.findIndex(t => t.user_message.id === userMessageId);
      if (turnIndex === -1) return state;
      
      const updatedTurns = [...turns];
      updatedTurns[turnIndex] = { ...updatedTurns[turnIndex], ...updates };
      
      return {
        conversationsBySession: {
          ...state.conversationsBySession,
          [sessionId]: updatedTurns
        }
      };
    }),
  
  // Streaming turn methods
  setStreamingTurn: (sessionId, turn) =>
    set(state => ({
      currentStreamingTurnBySession: {
        ...state.currentStreamingTurnBySession,
        [sessionId]: turn
      }
    })),

  updateStreamingAIResponse: (sessionId, updates) =>
    set(state => {
      const currentTurn = state.currentStreamingTurnBySession[sessionId];
      if (!currentTurn) return state;
      
      return {
        currentStreamingTurnBySession: {
          ...state.currentStreamingTurnBySession,
          [sessionId]: {
            ...currentTurn,
            aiResponse: currentTurn.aiResponse ? {
              ...currentTurn.aiResponse,
              ...updates
            } : {
              id: '',
              text: '',
              isLoading: false,
              isComplete: false,
              ...updates
            }
          }
        }
      };
    }),

  updateCompletedAIResponse: (sessionId, responseId, updates) => {
    set(state => {
      const conversationTurns = state.conversationsBySession[sessionId] || [];

      // Since the streaming response ID doesn't match the database response ID,
      // update the most recent AI response in the most recent conversation turn
      let updated = false;
      const updatedTurns = conversationTurns.map((turn: ConversationTurnDto, turnIndex) => {
        // Only update the last turn (most recent)
        if (turnIndex === conversationTurns.length - 1 && turn.ai_responses.length > 0) {
          const lastResponseIndex = turn.ai_responses.length - 1;
          const lastResponse = turn.ai_responses[lastResponseIndex];

          const updatedResponse = {
            ...lastResponse,
            ...updates
          };

          const updatedAiResponses = [...turn.ai_responses];
          updatedAiResponses[lastResponseIndex] = updatedResponse;

          updated = true;
          return {
            ...turn,
            ai_responses: updatedAiResponses
          };
        }
        return turn;
      });

      const newState = {
        conversationsBySession: {
          ...state.conversationsBySession,
          [sessionId]: updatedTurns
        }
      };

      return newState;
    });
  },

  appendToStreamingAIResponse: (sessionId, text, seq) =>
    set(state => {
      const currentTurn = state.currentStreamingTurnBySession[sessionId];
      if (!currentTurn?.aiResponse) return state;
      
      const aiResponse = currentTurn.aiResponse;
      
      // Guard against out-of-order or duplicate frames
      const lastSeq = aiResponse.lastSeq ?? -1;
      if (seq !== undefined && seq <= lastSeq) return state;
      
      // Add text event to timeline
      const timeline = aiResponse.timeline || [];
      const newTextEvent: TimelineEvent = {
        type: 'text',
        timestamp: Date.now(),
        sequence: seq || lastSeq + 1,
        content: text
      };
      
      return {
        currentStreamingTurnBySession: {
          ...state.currentStreamingTurnBySession,
          [sessionId]: {
            ...currentTurn,
            aiResponse: {
              ...aiResponse,
              text: aiResponse.text + text,
              lastSeq: seq,
              timeline: [...timeline, newTextEvent]
              // Keep isLoading as-is (should remain true during streaming)
            }
          }
        }
      };
    }),

  completeStreamingTurn: (sessionId) =>
    set(state => {
      const streamingTurn = state.currentStreamingTurnBySession[sessionId];
      if (!streamingTurn) return state;
      
      // Reconstruct message text with embedded markers from timeline
      // Summarization, thinking, and tools are all embedded as HTML comment markers
      let finalMessageText = '';
      
      if (streamingTurn.aiResponse?.timeline) {
        streamingTurn.aiResponse.timeline.forEach(event => {
          if (event.type === 'text') {
            finalMessageText += event.content;
          } else if (event.type === 'tool_start') {
            const argsJson = JSON.stringify(event.toolArgs);
            finalMessageText += `\n<!-- TOOL_START:${event.toolName}:${event.toolCallId}:${argsJson}:${event.timestamp} -->\n`;
          } else if (event.type === 'tool_complete') {
            finalMessageText += `\n<!-- TOOL_COMPLETE:${event.toolCallId}:${event.timestamp} -->\n`;
          } else if (event.type === 'tool_fail') {
            finalMessageText += `\n<!-- TOOL_FAIL:${event.toolCallId}:${event.error}:${event.timestamp} -->\n`;
          } else if (event.type === 'thinking') {
            finalMessageText += `\n<!-- THINKING_START:${event.agent}:${event.sequence || 0}:${event.timestamp} -->\n`;
            finalMessageText += event.text;
            finalMessageText += `\n<!-- THINKING_COMPLETE:${event.agent}:${event.sequence || 0}:${event.timestamp} -->\n`;
          } else if (event.type === 'summarization_start') {
            // Embed summarization start marker (like thinking/tools)
            finalMessageText += `\n<!-- SUMMARIZATION_START:${event.timestamp}:${event.sequence || 0} -->\n`;
          } else if (event.type === 'summarization_complete') {
            finalMessageText += `\n<!-- SUMMARIZATION_COMPLETE:${event.timestamp} -->\n`;
          } else if (event.type === 'summarization_cancelled') {
            finalMessageText += `\n<!-- SUMMARIZATION_CANCELLED:${event.timestamp} -->\n`;
          } else if (event.type === 'summarization_failed') {
            finalMessageText += `\n<!-- SUMMARIZATION_FAILED:${event.timestamp}:${event.error || ''} -->\n`;
          }
        });
        
        // Fallback if timeline processing produced no text
        if (!finalMessageText && streamingTurn.aiResponse?.text) {
          finalMessageText = streamingTurn.aiResponse.text;
        }
      } else {
        finalMessageText = streamingTurn.aiResponse?.text || '';
      }
      
      // Determine status based on error/cancelled state
      const hasError = !!streamingTurn.aiResponse?.error;
      const isCancelled = !!streamingTurn.aiResponse?.isCancelled;
      const status = hasError ? 'errored' : isCancelled ? 'cancelled' : 'completed';
      
      // If there was an error and no message text, use the error as the message
      const messageText = hasError && !finalMessageText 
        ? streamingTurn.aiResponse?.error || 'An error occurred'
        : finalMessageText;
      
      // Convert streaming turn to conversation turn
      const conversationTurn: ConversationTurnDto = {
        user_message: streamingTurn.userMessage,
        ai_responses: streamingTurn.aiResponse ? [{
          id: streamingTurn.aiResponse.id,
          message_text: messageText,
          status,
          response_time_ms: undefined,
          sources_used: [],
          model_used: streamingTurn.aiResponse.meta?.model_used,
          token_count: streamingTurn.aiResponse.meta?.token_count,
          run_id: streamingTurn.aiResponse.meta?.run_id,
          created_at: new Date(),
          is_latest: true,
          media_links: streamingTurn.aiResponse.mediaData,
          lookingForMedia: streamingTurn.aiResponse.lookingForMedia || false,
          search_results: streamingTurn.aiResponse.searchResults
          // Summarization markers are embedded in message_text (like thinking/tools)
        }] : [],
        has_retries: false
      };
      
      const { [sessionId]: _, ...remainingStreaming } = state.currentStreamingTurnBySession;
      const existingTurns = state.conversationsBySession[sessionId] || [];
      const newTurns = [...existingTurns, conversationTurn];
      
      return {
        conversationsBySession: {
          ...state.conversationsBySession,
          [sessionId]: newTurns
        },
        currentStreamingTurnBySession: remainingStreaming
      };
    }),

  clearStreamingTurn: (sessionId) =>
    set(state => {
      const { [sessionId]: _, ...remaining } = state.currentStreamingTurnBySession;
      return {
        currentStreamingTurnBySession: remaining
      };
    }),
  
  cancelStreaming: (sessionId) =>
    set(state => {
      const currentTurn = state.currentStreamingTurnBySession[sessionId];
      if (!currentTurn?.aiResponse) return state;
      
      const timeline = currentTurn.aiResponse.timeline || [];
      
      // Mark any running tool executions as cancelled
      const updatedToolExecutions = currentTurn.aiResponse.toolExecutions?.map(tool =>
        tool.state === 'running'
          ? { ...tool, state: 'cancelled' as ToolExecutionState, completedAt: Date.now() }
          : tool
      );
      
      // Mark any in-progress summarization as cancelled and add timeline event
      const updatedSummarizationStatus = currentTurn.aiResponse.summarizationStatus?.status === 'in_progress'
        ? { ...currentTurn.aiResponse.summarizationStatus, status: 'cancelled' as const, completedAt: Date.now() }
        : currentTurn.aiResponse.summarizationStatus;
      
      // Add summarization_cancelled event to timeline if summarization was in progress
      const updatedTimeline = currentTurn.aiResponse.summarizationStatus?.status === 'in_progress'
        ? [...timeline, {
            type: 'summarization_cancelled' as const,
            timestamp: Date.now(),
            sequence: timeline.length
          } as TimelineEvent]
        : timeline;
      
      // Mark AI response as cancelled (not loading, not complete)
      return {
        currentStreamingTurnBySession: {
          ...state.currentStreamingTurnBySession,
          [sessionId]: {
            ...currentTurn,
            aiResponse: {
              ...currentTurn.aiResponse,
              isLoading: false,
              isComplete: false,
              isCancelled: true,
              toolExecutions: updatedToolExecutions,
              summarizationStatus: updatedSummarizationStatus,
              timeline: updatedTimeline
            }
          }
        },
        streamState: { isStreaming: false }
      };
    }),
  
  // Tool execution management methods
  addToolExecution: (sessionId, toolCallId, toolName, toolArgs) =>
    set(state => {
      const currentTurn = state.currentStreamingTurnBySession[sessionId];
      if (!currentTurn?.aiResponse) return state;
      
      const toolExecutions = currentTurn.aiResponse.toolExecutions || [];
      const timeline = currentTurn.aiResponse.timeline || [];
      const newExecution: ToolExecution = {
        toolCallId,
        toolName,
        toolArgs,
        state: 'running',
        startedAt: Date.now()
      };
      
      // Add to timeline
      const toolStartEvent: TimelineEvent = {
        type: 'tool_start',
        timestamp: Date.now(),
        sequence: timeline.length,
        toolCallId,
        toolName,
        toolArgs
      };
      
      return {
        currentStreamingTurnBySession: {
          ...state.currentStreamingTurnBySession,
          [sessionId]: {
            ...currentTurn,
            aiResponse: {
              ...currentTurn.aiResponse,
              toolExecutions: [...toolExecutions, newExecution],
              timeline: [...timeline, toolStartEvent]
            }
          }
        }
      };
    }),
  
  completeToolExecution: (sessionId, toolCallId, output) =>
    set(state => {
      const currentTurn = state.currentStreamingTurnBySession[sessionId];
      if (!currentTurn?.aiResponse?.toolExecutions) return state;
      
      const updatedExecutions = currentTurn.aiResponse.toolExecutions.map(tool =>
        tool.toolCallId === toolCallId
          ? { ...tool, state: 'completed' as ToolExecutionState, completedAt: Date.now(), output }
          : tool
      );
      
      const timeline = currentTurn.aiResponse.timeline || [];
      const toolName = updatedExecutions.find(t => t.toolCallId === toolCallId)?.toolName || '';
      const toolCompleteEvent: TimelineEvent = {
        type: 'tool_complete',
        timestamp: Date.now(),
        sequence: timeline.length,
        toolCallId,
        toolName,
        output
      };
      
      return {
        currentStreamingTurnBySession: {
          ...state.currentStreamingTurnBySession,
          [sessionId]: {
            ...currentTurn,
            aiResponse: {
              ...currentTurn.aiResponse,
              toolExecutions: updatedExecutions,
              timeline: [...timeline, toolCompleteEvent]
            }
          }
        }
      };
    }),
  
  failToolExecution: (sessionId, toolCallId, error) =>
    set(state => {
      const currentTurn = state.currentStreamingTurnBySession[sessionId];
      if (!currentTurn?.aiResponse?.toolExecutions) return state;
      
      const updatedExecutions = currentTurn.aiResponse.toolExecutions.map(tool =>
        tool.toolCallId === toolCallId
          ? { ...tool, state: 'failed' as ToolExecutionState, completedAt: Date.now(), error }
          : tool
      );
      
      const timeline = currentTurn.aiResponse.timeline || [];
      const toolName = updatedExecutions.find(t => t.toolCallId === toolCallId)?.toolName || '';
      const toolFailEvent: TimelineEvent = {
        type: 'tool_fail',
        timestamp: Date.now(),
        sequence: timeline.length,
        toolCallId,
        toolName,
        error
      };
      
      return {
        currentStreamingTurnBySession: {
          ...state.currentStreamingTurnBySession,
          [sessionId]: {
            ...currentTurn,
            aiResponse: {
              ...currentTurn.aiResponse,
              toolExecutions: updatedExecutions,
              timeline: [...timeline, toolFailEvent]
            }
          }
        }
      };
    }),
  
  clearToolExecutions: (sessionId) =>
    set(state => {
      const currentTurn = state.currentStreamingTurnBySession[sessionId];
      if (!currentTurn?.aiResponse) return state;
      
      return {
        currentStreamingTurnBySession: {
          ...state.currentStreamingTurnBySession,
          [sessionId]: {
            ...currentTurn,
            aiResponse: {
              ...currentTurn.aiResponse,
              toolExecutions: []
            }
          }
        }
      };
    }),
  
  // Workflow event handlers
  startSummarization: (sessionId) =>
    set(state => {
      const currentTurn = state.currentStreamingTurnBySession[sessionId];
      if (!currentTurn?.aiResponse) return state;
      
      const timeline = currentTurn.aiResponse.timeline || [];
      
      // Add to timeline
      const summarizationStartEvent: TimelineEvent = {
        type: 'summarization_start',
        timestamp: Date.now(),
        sequence: timeline.length
      };
      
      return {
        currentStreamingTurnBySession: {
          ...state.currentStreamingTurnBySession,
          [sessionId]: {
            ...currentTurn,
            aiResponse: {
              ...currentTurn.aiResponse,
              summarizationStatus: {
                status: 'in_progress',
                startedAt: Date.now()
              },
              timeline: [...timeline, summarizationStartEvent]
            }
          }
        }
      };
    }),
  
  completeSummarization: (sessionId) =>
    set(state => {
      const currentTurn = state.currentStreamingTurnBySession[sessionId];
      if (!currentTurn?.aiResponse?.summarizationStatus) return state;
      
      const timeline = currentTurn.aiResponse.timeline || [];
      
      // Add to timeline
      const summarizationCompleteEvent: TimelineEvent = {
        type: 'summarization_complete',
        timestamp: Date.now(),
        sequence: timeline.length
      };
      
      return {
        currentStreamingTurnBySession: {
          ...state.currentStreamingTurnBySession,
          [sessionId]: {
            ...currentTurn,
            aiResponse: {
              ...currentTurn.aiResponse,
              summarizationStatus: {
                ...currentTurn.aiResponse.summarizationStatus,
                status: 'completed',
                completedAt: Date.now()
              },
              timeline: [...timeline, summarizationCompleteEvent]
            }
          }
        }
      };
    }),

  failSummarization: (sessionId, error) =>
    set(state => {
      const currentTurn = state.currentStreamingTurnBySession[sessionId];
      if (!currentTurn?.aiResponse) return state;
      
      const timeline = currentTurn.aiResponse.timeline || [];
      const existingStatus = currentTurn.aiResponse.summarizationStatus;
      
      // Add to timeline
      const summarizationFailedEvent: TimelineEvent = {
        type: 'summarization_failed',
        timestamp: Date.now(),
        sequence: timeline.length,
        error
      };
      
      return {
        currentStreamingTurnBySession: {
          ...state.currentStreamingTurnBySession,
          [sessionId]: {
            ...currentTurn,
            aiResponse: {
              ...currentTurn.aiResponse,
              summarizationStatus: {
                status: 'failed' as const,
                startedAt: existingStatus?.startedAt ?? Date.now(),
                error,
                completedAt: Date.now()
              },
              timeline: [...timeline, summarizationFailedEvent]
            }
          }
        }
      };
    }),
  
  updateWorkflowState: (sessionId, workflowState) =>
    set(state => {
      const currentTurn = state.currentStreamingTurnBySession[sessionId];
      if (!currentTurn?.aiResponse) return state;
      
      return {
        currentStreamingTurnBySession: {
          ...state.currentStreamingTurnBySession,
          [sessionId]: {
            ...currentTurn,
            aiResponse: {
              ...currentTurn.aiResponse,
              workflowState: {
                ...currentTurn.aiResponse.workflowState,
                ...workflowState
              }
            }
          }
        }
      };
    }),
  
  updateThinking: (sessionId, thinking) =>
    set(state => {
      const currentTurn = state.currentStreamingTurnBySession[sessionId];
      if (!currentTurn?.aiResponse) return state;
      
      return {
        currentStreamingTurnBySession: {
          ...state.currentStreamingTurnBySession,
          [sessionId]: {
            ...currentTurn,
            aiResponse: {
              ...currentTurn.aiResponse,
              currentThinking: thinking
            }
          }
        }
      };
    }),
  
  updatePlan: (sessionId, plan) =>
    set(state => {
      const currentTurn = state.currentStreamingTurnBySession[sessionId];
      if (!currentTurn?.aiResponse) return state;
      
      return {
        currentStreamingTurnBySession: {
          ...state.currentStreamingTurnBySession,
          [sessionId]: {
            ...currentTurn,
            aiResponse: {
              ...currentTurn.aiResponse,
              currentPlan: plan
            }
          }
        }
      };
    }),
  
  updateTaskProgress: (sessionId, progress) =>
    set(state => {
      const currentTurn = state.currentStreamingTurnBySession[sessionId];
      if (!currentTurn?.aiResponse) return state;
      
      return {
        currentStreamingTurnBySession: {
          ...state.currentStreamingTurnBySession,
          [sessionId]: {
            ...currentTurn,
            aiResponse: {
              ...currentTurn.aiResponse,
              taskProgress: progress
            }
          }
        }
      };
    }),
  
  clearWorkflowState: (sessionId) =>
    set(state => {
      const currentTurn = state.currentStreamingTurnBySession[sessionId];
      if (!currentTurn?.aiResponse) return state;
      
      return {
        currentStreamingTurnBySession: {
          ...state.currentStreamingTurnBySession,
          [sessionId]: {
            ...currentTurn,
            aiResponse: {
              ...currentTurn.aiResponse,
              workflowState: undefined,
              currentThinking: undefined,
              currentPlan: undefined,
              taskProgress: undefined
            }
          }
        }
      };
    }),
  
  // Getters
  getConversationTurns: (sessionId) => get().conversationsBySession[sessionId] || [],
  
  getCurrentStreamingTurn: (sessionId) => get().currentStreamingTurnBySession[sessionId],
  
  swapMessageId: (sessionId, tempId, realId) =>
    set(state => {
      // Update streaming turn if it exists
      const streamingTurn = state.currentStreamingTurnBySession[sessionId];
      if (streamingTurn && streamingTurn.userMessage.id === tempId) {
        return {
          currentStreamingTurnBySession: {
            ...state.currentStreamingTurnBySession,
            [sessionId]: {
              ...streamingTurn,
              userMessage: {
                ...streamingTurn.userMessage,
                id: realId
              }
            }
          },
          tempToRealMap: {
            ...state.tempToRealMap,
            [tempId]: realId
          }
        };
      }
      
      // Update conversation turns if needed
      const turns = state.conversationsBySession[sessionId] || [];
      const turnIndex = turns.findIndex(t => t.user_message.id === tempId);
      if (turnIndex !== -1) {
        const updatedTurns = [...turns];
        updatedTurns[turnIndex] = {
          ...updatedTurns[turnIndex],
          user_message: {
            ...updatedTurns[turnIndex].user_message,
            id: realId
          }
        };
        
        return {
          conversationsBySession: {
            ...state.conversationsBySession,
            [sessionId]: updatedTurns
          },
          tempToRealMap: {
            ...state.tempToRealMap,
            [tempId]: realId
          }
        };
      }
      
      return {
        tempToRealMap: {
          ...state.tempToRealMap,
          [tempId]: realId
        }
      };
    }),
  
  clearSession: (sessionId) =>
    set(state => {
      const { [sessionId]: _, ...remainingConversations } = state.conversationsBySession;
      const { [sessionId]: __, ...remainingStreaming } = state.currentStreamingTurnBySession;
      return { 
        conversationsBySession: remainingConversations,
        currentStreamingTurnBySession: remainingStreaming
      };
    }),
  
  setStreamState: (streamState) =>
    set(state => ({
      streamState: { ...state.streamState, ...streamState }
    })),
  
  clearStreamState: () =>
    set({
      streamState: { isStreaming: false }
    }),
  
  isSessionStreaming: (sessionId) => {
    const state = get().streamState;
    return state.isStreaming && state.streamSessionId === sessionId;
  },
  
  clear: () => {
    // Abort any active streams before clearing
    const state = get();
    if (state.streamState.isStreaming && state.streamState.streamAbortController) {
      state.streamState.streamAbortController.abort();
    }
    
    set({ 
      conversationsBySession: {},
      currentStreamingTurnBySession: {},
      streamState: { isStreaming: false },
      tempToRealMap: {}
    });
  }
}));

// Export for logout cleanup
export const clearChatMessages = () => useChatMessages.getState().clear();
