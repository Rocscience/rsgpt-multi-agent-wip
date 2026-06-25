'use client'

import type {
  StreamPromptRequest,
  MediaSearchCompletedEvent,
  MediaSearchStartEvent,
  ResponseCreatedEvent,
  ResponseOutputTextDeltaEvent,
  ResponseCompletedEvent,
  ResponseFailedEvent,
  AgentRunStartedEvent,
  AgentToolExecutionStartedEvent,
  AgentToolExecutionCompletedEvent,
  AgentToolExecutionFailedEvent,
  AgentRunCompletedEvent,
  AgentRunFailedEvent,
  ResponseSearchResultsEvent,
  ContextUsageUpdateEvent,
  ContextSummarizingEvent,
  ContextPruningCompletedEvent,
  ContextPruningErrorEvent,
} from "@/lib/types";
import { useChatMessages } from "./useChatMessages";
import { useModelSelection } from "./useModelSelection";
import { useSourceList } from "./useSourceList";
import { useContextUsage } from "./useContextUsage";
import { useQueryClient } from "@tanstack/react-query";
import { MODEL_CONFIGS, ModelName, Provider, ReasoningLevel } from "@/lib/types";

export function useStreamPrompt(sessionId: string) {
  const queryClient = useQueryClient();
  const {
    setStreamingTurn,
    updateStreamingAIResponse,
    updateCompletedAIResponse,
    appendToStreamingAIResponse,
    completeStreamingTurn,
    clearStreamingTurn,
    swapMessageId,
    setStreamState,
    clearStreamState,
    addToolExecution,
    completeToolExecution,
    failToolExecution,
    clearToolExecutions,
    cancelStreaming,
    startSummarization,
    completeSummarization,
    failSummarization,
    updateWorkflowState,
    updateThinking,
    updatePlan,
    updateTaskProgress,
    clearWorkflowState
  } = useChatMessages();
  const { setSearchResults, setLoading } = useSourceList();
  
  // Store the cancel function so we can call it from outside
  let activeCancelFunction: (() => void) | null = null;

  // Event handlers for user messages
  const handleUserMessageInit = (data: { client_temp_id: string; server_id: string }) => {
    swapMessageId(sessionId, data.client_temp_id, data.server_id);
  };

  // Event handlers for regular chat mode
  const handleResponseCreated = (data: ResponseCreatedEvent) => {
    updateStreamingAIResponse(sessionId, {
      id: data.response.id,
      text: '',
      isLoading: true,
      lastSeq: data.sequence_number
    });
  };

  const handleResponseOutputTextDelta = (data: ResponseOutputTextDeltaEvent) => {
    appendToStreamingAIResponse(sessionId, data.delta, data.sequence_number);
  };

  const handleResponseCompleted = (data: ResponseCompletedEvent) => {
    updateStreamingAIResponse(sessionId, {
      isLoading: false,
      isComplete: true,
      meta: {
        token_count: data.response.usage?.total_tokens,
        finish_reason: 'completed',
        model_used: data.response.model
      }
    });
    
    completeStreamingTurn(sessionId);
    queryClient.invalidateQueries({ queryKey: ["sessions/conversation", sessionId] });
    
    // Refetch quota immediately after stream completes (backend increments quota at this point)
    queryClient.refetchQueries({ queryKey: ['quota/info'] });
    
    setTimeout(() => {
      window.dispatchEvent(new CustomEvent('focus-message-input'));
    }, 200);
  };

  const handleResponseFailed = (data: ResponseFailedEvent) => {
    updateStreamingAIResponse(sessionId, {
      isLoading: false,
      isComplete: false,
      error: data.error || 'Response generation failed'
    });
    console.error('Stream failed:', data.error);
    
    // Refetch quota on error in case it was quota-related
    queryClient.refetchQueries({ queryKey: ['quota/info'] });
  };

  // Event handlers for agent mode
  const handleAgentRunStarted = (data: AgentRunStartedEvent) => {
    const currentTurn = useChatMessages.getState().getCurrentStreamingTurn(sessionId);
    const existingMeta = currentTurn?.aiResponse?.meta || {};
    
    updateStreamingAIResponse(sessionId, {
      id: data.run.id,
      text: '',
      isLoading: true,
      lastSeq: data.sequence_number,
      toolExecutions: [],
      timeline: [],
      meta: existingMeta // Preserve existing meta including model_used
    });
  };

  const handleAgentToolExecutionStarted = (data: AgentToolExecutionStartedEvent) => {
    addToolExecution(sessionId, data.tool_call_id, data.tool_name, data.tool_args);
  };

  const handleAgentToolExecutionCompleted = (data: AgentToolExecutionCompletedEvent) => {
    completeToolExecution(sessionId, data.tool_call_id, data.output);
  };

  const handleAgentToolExecutionFailed = (data: AgentToolExecutionFailedEvent) => {
    console.error(`Tool ${data.tool_name} failed:`, data.error);
    failToolExecution(sessionId, data.tool_call_id, data.error);
  };

  const handleAgentRunCompleted = (data: AgentRunCompletedEvent) => {
    // If final_output exists and is different from accumulated text, use it
    if (data.final_output) {
      updateStreamingAIResponse(sessionId, {
        text: data.final_output,
        isLoading: false,
        isComplete: true
      });
    } else {
      updateStreamingAIResponse(sessionId, {
        isLoading: false,
        isComplete: true
      });
    }
    
    clearToolExecutions(sessionId);
    completeStreamingTurn(sessionId);
    queryClient.invalidateQueries({ queryKey: ["sessions/conversation", sessionId] });
    
    // Refetch quota immediately after agent run completes (backend increments quota at this point)
    queryClient.refetchQueries({ queryKey: ['quota/info'] });
    
    setTimeout(() => {
      window.dispatchEvent(new CustomEvent('focus-message-input'));
    }, 200);
  };

  const handleAgentRunFailed = (data: AgentRunFailedEvent) => {
    console.error('[Agent Run Failed]', data.error);
    
    // Mark AI response as failed (NOT cancelled - this is an error, not user cancellation)
    // Note: Don't call cancelStreaming here - that's for user-initiated cancellations only
    updateStreamingAIResponse(sessionId, {
      isLoading: false,
      isComplete: false,
      error: data.error || 'Agent execution failed'
    });
    
    // Complete the streaming turn so it gets saved to conversation history
    completeStreamingTurn(sessionId);
    queryClient.invalidateQueries({ queryKey: ["sessions/conversation", sessionId] });
    
    // Refetch quota on error in case it was quota-related
    queryClient.refetchQueries({ queryKey: ['quota/info'] });
  };

  // Workflow event handlers (multi-agent workflow)
  const handleWorkflowStarted = (data: any) => {
    // Get current AI response to check if ID is already set (from response.created event)
    const currentAIResponse = useChatMessages.getState().currentStreamingTurnBySession[sessionId]?.aiResponse;
    
    // Initialize the streaming AI response (this is like agent.run.started)
    // IMPORTANT: Don't overwrite ID if it's already set by response.created event (database ID)
    updateStreamingAIResponse(sessionId, {
      id: currentAIResponse?.id || data.trace_id || crypto.randomUUID(), // Preserve database ID if set
      text: '',
      isLoading: true,
      lastSeq: data.sequence_number,
      toolExecutions: [],
      timeline: []
    });
    
    // Set workflow state
    updateWorkflowState(sessionId, {
      traceId: data.trace_id
    });
  };

  const handleWorkflowStatusChanged = (data: any) => {
    const statusMap: Record<string, string> = {
      orchestrating: 'CLASSIFYING',
      researching: 'KNOWLEDGE_SEARCH',
      planning: 'PLANNING',
      executing: 'EXECUTING',
      evaluating: 'EVALUATING',
      summarizing: 'SUMMARIZING',
      completed: 'COMPLETED',
      failed: 'FAILED',
      out_of_scope: 'OUT_OF_SCOPE',
    };
    const raw = (data.status || '').toLowerCase();
    const mappedStatus = statusMap[raw] || data.status;
    // Safety check: Initialize AI response if not already initialized
    const currentTurn = useChatMessages.getState().currentStreamingTurnBySession[sessionId];
    if (!currentTurn?.aiResponse) {
      updateStreamingAIResponse(sessionId, {
        id: crypto.randomUUID(),
        text: '',
        isLoading: true,
        lastSeq: data.sequence_number,
        toolExecutions: [],
        timeline: []
      });
    }
    
    updateWorkflowState(sessionId, {
      status: mappedStatus,
      agentName: data.agent_name
    });
  };

  const handleWorkflowCompleted = (data: any) => {
    // Mark workflow as completed
    updateWorkflowState(sessionId, {
      status: 'COMPLETED',
      traceId: data.trace_id
    });
    
    // Mark AI response as complete (like agent.run.completed)
    const currentMeta = useChatMessages.getState().currentStreamingTurnBySession[sessionId]?.aiResponse?.meta ?? {};
    updateStreamingAIResponse(sessionId, {
      isLoading: false,
      isComplete: true,
      meta: {
        ...currentMeta,
        ...data.meta,
        trace_id: data.trace_id
      }
    });
    
    // Clear workflow-specific state (thinking, plan, task progress)
    clearWorkflowState(sessionId);
    
    // Complete the streaming turn and save to conversation history
    completeStreamingTurn(sessionId);
    queryClient.invalidateQueries({ queryKey: ["sessions/conversation", sessionId] });
    
    // Refetch quota immediately after workflow completes (backend increments quota at this point)
    queryClient.refetchQueries({ queryKey: ['quota/info'] });
    
    setTimeout(() => {
      window.dispatchEvent(new CustomEvent('focus-message-input'));
    }, 200);
  };

  const handleWorkflowFailed = (data: any) => {
    console.error('[Workflow Failed]', data.error);
    
    // Mark AI response as failed (NOT cancelled - this is an error, not user cancellation)
    // Note: Don't call cancelStreaming here - that's for user-initiated cancellations only
    updateStreamingAIResponse(sessionId, {
      isLoading: false,
      isComplete: false,
      error: data.error || 'Workflow execution failed'
    });
    
    // Clear workflow-specific state (thinking, plan, task progress) but keep error on aiResponse
    clearWorkflowState(sessionId);
    
    // Complete the streaming turn so it gets saved to conversation history
    completeStreamingTurn(sessionId);
    queryClient.invalidateQueries({ queryKey: ["sessions/conversation", sessionId] });
    
    // Refetch quota on error in case it was quota-related
    queryClient.refetchQueries({ queryKey: ['quota/info'] });
  };

  const handleAgentThinking = (data: any) => {
    // Safety check: Initialize AI response if not already initialized
    const currentTurn = useChatMessages.getState().currentStreamingTurnBySession[sessionId];
    if (!currentTurn?.aiResponse) {
      updateStreamingAIResponse(sessionId, {
        id: crypto.randomUUID(),
        text: '',
        isLoading: true,
        lastSeq: data.sequence_number,
        toolExecutions: [],
        timeline: []
      });
    }
    
    // Get current timeline
    const currentResponse = useChatMessages.getState().currentStreamingTurnBySession[sessionId]?.aiResponse;
    const timeline = [...(currentResponse?.timeline || [])];
    
    // Find the last thinking event for this agent
    let lastThinkingIndex = -1;
    for (let i = timeline.length - 1; i >= 0; i--) {
      const event = timeline[i];
      if (event.type === 'thinking' && event.agent === data.agent_name && !event.isComplete) {
        lastThinkingIndex = i;
        break;
      }
    }
    
    if (data.is_complete) {
      // Thinking is complete - mark the last thinking event as complete with full text
      if (lastThinkingIndex >= 0) {
        const existingEvent = timeline[lastThinkingIndex];
        if (existingEvent.type === 'thinking') {
          timeline[lastThinkingIndex] = {
            type: 'thinking',
            timestamp: existingEvent.timestamp,
            sequence: data.sequence_number,
            agent: existingEvent.agent,
            text: data.thinking_text,
            isComplete: true
          };
        }
      } else {
        // No existing thinking event, add a new completed one
        timeline.push({
          type: 'thinking' as const,
          timestamp: Date.now(),
          sequence: data.sequence_number,
          agent: data.agent_name,
          text: data.thinking_text,
          isComplete: true
        });
      }
      
      updateStreamingAIResponse(sessionId, {
        timeline,
        lastSeq: data.sequence_number
      });
    } else {
      // Thinking is streaming - update or create thinking event in timeline
      if (lastThinkingIndex >= 0) {
        // Update existing thinking event
        const existingEvent = timeline[lastThinkingIndex];
        if (existingEvent.type === 'thinking') {
          timeline[lastThinkingIndex] = {
            type: 'thinking',
            timestamp: existingEvent.timestamp,
            sequence: data.sequence_number,
            agent: existingEvent.agent,
            text: existingEvent.text + data.thinking_text,
            isComplete: false
          };
        }
      } else {
        // Create new thinking event
        timeline.push({
          type: 'thinking' as const,
          timestamp: Date.now(),
          sequence: data.sequence_number,
          agent: data.agent_name,
          text: data.thinking_text,
          isComplete: false
        });
      }
      
      updateStreamingAIResponse(sessionId, {
        timeline,
        lastSeq: data.sequence_number
      });
    }
  };

  const handleAgentTextOutput = (data: any) => {
    // If text is provided, append it to the response
    if (data.delta) {
      appendToStreamingAIResponse(sessionId, data.delta, data.sequence_number);
    }
  };

  const handleAgentPlanning = (data: any) => {
    updatePlan(sessionId, data.plan);
  };

  const handleAgentTaskProgress = (data: any) => {
    updateTaskProgress(sessionId, {
      currentTaskId: data.task_id,
      currentTaskIndex: data.current_task_index,
      totalTasks: data.total_tasks,
      taskDescription: data.task_description,
      status: data.status
    });
  };

  const handleAgentTransition = (data: any) => {
    const currentResponse = useChatMessages.getState().currentStreamingTurnBySession[sessionId]?.aiResponse;
    const timeline = [...(currentResponse?.timeline || [])];
    timeline.push({
      type: 'agent_transition' as const,
      timestamp: Date.now(),
      sequence: data.sequence_number,
      fromAgent: data.from_agent,
      toAgent: data.to_agent,
      toolName: data.tool_name,
      completed: data.completed,
    });
    updateStreamingAIResponse(sessionId, {
      timeline,
      lastSeq: data.sequence_number,
    });
  };

  const handleAgentOutOfScope = (data: any) => {
    updateWorkflowState(sessionId, {
      status: 'OUT_OF_SCOPE'
    });
  };

  // Media search handlers (can be called during streaming or after completion)
  const handleMediaSearchStart = (data: MediaSearchStartEvent) => {
    // Update the most recent completed response
    updateCompletedAIResponse(sessionId, data.server_id, { lookingForMedia: true });

    // Also try streaming response in case it comes during streaming
    const currentStreamingTurn = useChatMessages.getState().currentStreamingTurnBySession[sessionId];
    if (currentStreamingTurn?.aiResponse) {
      updateStreamingAIResponse(sessionId, { lookingForMedia: true });
    }
  };

  const handleMediaSearchCompleted = (data: MediaSearchCompletedEvent) => {
    // Update the most recent completed response
    updateCompletedAIResponse(sessionId, data.server_id, {
      lookingForMedia: false,
      media_links: data.media_data
    });

    // Also try streaming response in case it comes during streaming
    const currentStreamingTurn = useChatMessages.getState().currentStreamingTurnBySession[sessionId];
    if (currentStreamingTurn?.aiResponse) {
      updateStreamingAIResponse(sessionId, {
        lookingForMedia: false,
        mediaData: data.media_data
      });
    }
  };

  // Search results handler (Perplexity Web Search)
  const handleResponseSearchResults = (data: ResponseSearchResultsEvent) => {
    updateStreamingAIResponse(sessionId, {
      searchResults: data.search_results
    });
    // Also update the source list
    setSearchResults(data.search_results);
    setLoading(false);
  };

  // Context usage handler
  const handleContextUsageUpdate = (data: ContextUsageUpdateEvent) => {
    // Only update if this event is for the current session
    if (data.session_id === sessionId) {
      useContextUsage.getState().updateContextUsage(data);
    }
  };

  // Context summarizing handler (pruning in progress)
  const handleContextSummarizing = (data: ContextSummarizingEvent) => {
    // Only update if this event is for the current session
    if (data.session_id === sessionId) {
      startSummarization(sessionId);
    }
  };

  // Context pruning completed handler
  const handleContextPruningCompleted = (data: ContextPruningCompletedEvent) => {
    // Only update if this event is for the current session
    if (data.session_id === sessionId) {
      completeSummarization(sessionId);
    }
  };

  // Context pruning error handler
  const handleContextPruningError = (data: ContextPruningErrorEvent) => {
    console.error('[Context Pruning Error]', data);
    // Only update if this event is for the current session
    if (data.session_id === sessionId) {
      failSummarization(sessionId, data.error || 'Failed to summarize');
    }
  };

  async function start(
    body: StreamPromptRequest,
    opts?: {
      onChunk?: (text: string) => void;
      onDone?: () => void;
      onError?: (e: Error) => void;
    }
  ) {
    try {
      // Create abort controller for this stream
      const abortController = new AbortController();
      
      // Set stream state in global store
      setStreamState({
        isStreaming: true,
        streamAbortController: abortController,
        streamSessionId: sessionId
      });
      
      // Set loading state for source list
      setLoading(true);

      // Step 1: Get direct stream URL and token from Vercel (quick request)
      const setupRes = await fetch(`/api/v1/chat/sessions/stream/${sessionId}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal: abortController.signal,
      });

      if (!setupRes.ok) {
        let errorMessage = 'Failed to setup stream';
        try {
          const errorData = await setupRes.json();
          errorMessage = errorData.error || errorData.detail || errorMessage;
          
          if (setupRes.status === 400 && errorMessage.toLowerCase().includes('quota')) {
            errorMessage = 'You have reached your question limit. Please contact your administrator.';
          }
        } catch (e) {
          console.error('Failed to parse error response:', e);
        }
        
        updateStreamingAIResponse(sessionId, {
          isLoading: false,
          isComplete: true,
          error: errorMessage // Use actual error from backend
        });
        
        throw new Error(errorMessage);
      }

      const { streamUrl, token } = await setupRes.json();

      // Step 2: Connect directly to AWS backend (bypasses Vercel limits)
      const res = await fetch(streamUrl, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify(body),
        signal: abortController.signal,
      });

      if (!res.ok || !res.body) {
        
        let errorMessage = 'Stream start failed';
        try {
          const errorData = await res.json();
          errorMessage = errorData.detail || errorData.message || errorMessage;
          
          if (res.status === 400 && errorMessage.toLowerCase().includes('quota')) {
            errorMessage = 'You have reached your question limit. Please contact your administrator.';
          }
        } catch (e) {
          console.error('Failed to parse error response:', e);
        }
        
        updateStreamingAIResponse(sessionId, {
          isLoading: false,
          isComplete: true,
          error: errorMessage // Use actual error from backend
        });
        
        throw new Error(errorMessage);
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let cancelled = false;
      let buffer = '';

      // Listen for offline events to abort the stream gracefully
      const handleOffline = () => {
        console.log('[Stream] Network went offline - aborting stream');
        cancelled = true;
        abortController.abort();
        
        // Cancel streaming - this marks tools as cancelled and sets isCancelled: true
        cancelStreaming(sessionId);
        
        // Clear workflow state (plan, task progress, thinking)
        clearWorkflowState(sessionId);
        
        // Add the error message to the response
        updateStreamingAIResponse(sessionId, {
          error: 'Connection lost while generating response. Please retry when back online.'
        });
        
        // Clear stream state
        clearStreamState();
        setLoading(false);
        
        opts?.onError?.(new Error('network_interrupted'));
      };
      
      window.addEventListener('offline', handleOffline);

      (async () => {
        try {
          while (!cancelled && !abortController.signal.aborted) {
            const { done, value } = await reader.read();
            
            if (done) {
              break;
            }

            buffer += decoder.decode(value, { stream: true });

            // Split on SSE event boundary
            let boundary;
            while ((boundary = buffer.indexOf('\n\n')) !== -1) {
              const rawEvent = buffer.slice(0, boundary);
              buffer = buffer.slice(boundary + 2); // drop separator

              // Parse SSE event
              const lines = rawEvent.split('\n');
              let eventType = '';
              let eventData = '';

              for (const line of lines) {
                if (line.startsWith('event:')) {
                  eventType = line.slice(6).trim();
                } else if (line.startsWith('data:')) {
                  eventData = line.slice(5).trim();
                }
              }

              if (!eventType || !eventData) {
                continue;
              }

              try {
                const data = JSON.parse(eventData);
                
                // Handle different event types
                switch (eventType) {
                  // Common events
                  case 'user_message.init':
                    handleUserMessageInit(data);
                    break;
                  case 'stream.error':
                    const errorMessage = data.error || 'Stream error occurred';
                    const assistantServerId = data.assistant_server_id;
                    
                    // Check if this is a device connection error
                    const isDeviceError = errorMessage.toLowerCase().includes('device') && 
                                          (errorMessage.toLowerCase().includes('not connected') || 
                                           errorMessage.toLowerCase().includes('not found') ||
                                           errorMessage.toLowerCase().includes('unavailable'));
                    
                    if (isDeviceError) {
                      // Dispatch custom event for device connection error
                      window.dispatchEvent(new CustomEvent('device-disconnected'));
                    }
                    
                    updateStreamingAIResponse(sessionId, {
                      id: assistantServerId, // Set the ID so feedback buttons show
                      isLoading: false,
                      isComplete: true, // Mark as complete so feedback buttons show
                      error: errorMessage // Use actual error from backend
                    });
                    opts?.onError?.(new Error(errorMessage));
                    return;
                  
                  // Regular chat events
                  case 'response.created':
                    handleResponseCreated(data);
                    break;
                  case 'response.output_text.delta':
                    handleResponseOutputTextDelta(data);
                    opts?.onChunk?.(data.delta);
                    break;
                  case 'response.completed':
                    handleResponseCompleted(data);
                    opts?.onDone?.();
                    break;
                  case 'response.failed':
                    handleResponseFailed(data);
                    opts?.onError?.(new Error(data.error || 'Response failed'));
                    break;
                  
                  // Agent mode events
                  case 'agent.run.started':
                    handleAgentRunStarted(data);
                    break;
                  case 'agent.tool_execution.started':
                    handleAgentToolExecutionStarted(data);
                    break;
                  case 'agent.tool_execution.completed':
                    handleAgentToolExecutionCompleted(data);
                    break;
                  case 'agent.tool_execution.failed':
                    handleAgentToolExecutionFailed(data);
                    break;
                  case 'agent.run.completed':
                    handleAgentRunCompleted(data);
                    opts?.onDone?.();
                    break;
                  case 'agent.run.failed':
                    handleAgentRunFailed(data);
                    opts?.onError?.(new Error(data.error || 'Agent run failed'));
                    break;
                  
                  // Search results events (Perplexity)
                  case 'response.search_results':
                    handleResponseSearchResults(data);
                    break;
                    
                  // Multi-agent workflow events
                  case 'agent.workflow.started':
                    handleWorkflowStarted(data);
                    break;
                  case 'agent.workflow.status_changed':
                    handleWorkflowStatusChanged(data);
                    break;
                  case 'agent.workflow.completed':
                    handleWorkflowCompleted(data);
                    break;
                  case 'agent.workflow.failed':
                    handleWorkflowFailed(data);
                    break;
                  case 'agent.thinking':
                    handleAgentThinking(data);
                    break;
                  case 'agent.message.delta':
                    handleAgentTextOutput(data);
                    break;
                  case 'agent.planning':
                    handleAgentPlanning(data);
                    break;
                  case 'agent.task_progress':
                    handleAgentTaskProgress(data);
                    break;
                  case 'agent.transition':
                    handleAgentTransition(data);
                    break;
                  case 'agent.out_of_scope':
                    handleAgentOutOfScope(data);
                    break;
                  
                  // Future media events
                  case 'media.search_start':
                    handleMediaSearchStart(data);
                    break;
                  case 'media.search_completed':
                    handleMediaSearchCompleted(data);
                    break;
                  
                  // Context usage events
                  case 'context.usage':
                    handleContextUsageUpdate(data);
                    break;
                  
                  // Context pruning/summarization events
                  case 'context.summarizing':
                    handleContextSummarizing(data);
                    break;
                  
                  case 'context.pruning_completed':
                    handleContextPruningCompleted(data);
                    break;
                  
                  case 'context.pruning_error':
                    handleContextPruningError(data);
                    break;
                  
                  // Heartbeat events - keepalive during long operations
                  case 'agent.heartbeat':
                    // No action needed - just receiving the event keeps the connection alive
                    break;
                  
                  default:
                    // Silently ignore unknown event types in production
                    break;
                }
              } catch (err) {
                // Don't kill the entire stream for a single bad event - continue processing
                continue;
              }
            }
          }
        } catch (e: any) {
          // Check if this is a network error
          const isNetworkError = !navigator.onLine || 
            e.name === 'TypeError' || 
            e.message?.includes('network') ||
            e.message?.includes('fetch') ||
            e.message?.includes('Failed to fetch');
          
          if (!abortController.signal.aborted) {
            // Cancel streaming - this marks tools as cancelled and sets isCancelled: true
            cancelStreaming(sessionId);
            
            // Clear workflow state (plan, task progress, thinking)
            clearWorkflowState(sessionId);
            
            if (isNetworkError) {
              console.log('[Stream] Network error detected:', e.message);
              updateStreamingAIResponse(sessionId, {
                error: 'Connection lost while generating response. Please retry when back online.'
              });
              opts?.onError?.(new Error('network_interrupted'));
            } else {
              opts?.onError?.(e);
            }
          }
        } finally {
          // Clean up offline event listener
          window.removeEventListener('offline', handleOffline);
          reader.releaseLock();
          clearStreamState();
          setLoading(false);
          // Only clear streaming turn if it wasn't completed normally
          // (completion is handled in handleAssistantCompleted)
        }
      })();

      const cancelFn = () => {
        // 1. Clean up the offline event listener
        window.removeEventListener('offline', handleOffline);
        
        // 2. Cancel the reader FIRST to interrupt any pending read operations
        try { 
          reader.cancel(); 
        } catch (e) {
          // Ignore cancel errors
        }
        
        // 3. Set cancelled flag and abort the controller
        cancelled = true;
        abortController.abort();
        
        // 4. Mark the streaming turn as cancelled (not just stopped)
        cancelStreaming(sessionId);
        
        // 5. Clear stream state in the store
        clearStreamState();
        
        // 6. Clear the active cancel function reference
        activeCancelFunction = null;
      };
      
      // Store the cancel function so it can be called from outside
      activeCancelFunction = cancelFn;
      
      // Update the stream state to include the cancel function
      setStreamState({
        streamCancelFunction: cancelFn
      });
      
      return cancelFn;
    } catch (e: any) {
      clearStreamState();
      setLoading(false);
      
      // Don't clear the streaming turn - keep it so the error can be displayed
      // Mark as complete since the request has definitively ended (even with error)
      updateStreamingAIResponse(sessionId, {
        isLoading: false,
        isComplete: true,
        error: e.message || 'Failed to start stream'
      });
      
      // Complete the streaming turn so it moves to message history
      completeStreamingTurn(sessionId);
      
      opts?.onError?.(e);
      return () => {};
    }
  }

  // Function to add optimistic user message and start streaming
  function sendMessage(
    text: string, 
    sources: string[], 
    modelName?: string,
    isAgentMode?: boolean,
    deviceId?: string | null,
    isWebSearchEnabled?: boolean,
    reasoningLevelOverride?: ReasoningLevel
  ) {
    // If there's already a stream for this session, abort it first
    const { streamState } = useChatMessages.getState();
    if (streamState.isStreaming && streamState.streamSessionId === sessionId) {
      streamState.streamAbortController?.abort();
      clearStreamState();
    }
    
    // Clear any previous sources and set loading
    setSearchResults([]);
    setLoading(true);

    // Look up model configuration to get provider name
    const modelConfig = MODEL_CONFIGS[modelName as ModelName] || MODEL_CONFIGS[ModelName.CLAUDE_HAIKU_4_5]; // Default to Claude Haiku 4.5 if no model specified
    const providerName = modelConfig?.provider || Provider.ANTHROPIC;
    
    // Only use reasoning level for GPT-5 and Anthropic models, default to medium if not specified
    // Note: xAI uses model name transformation instead of reasoning_effort parameter
    let reasoningLevel: string | null = null;
    if (modelName === ModelName.GPT5_2 || modelName === ModelName.CLAUDE_HAIKU_4_5) {
      const { reasoningLevel: stateReasoningLevel } = useModelSelection.getState();
      reasoningLevel = reasoningLevelOverride || stateReasoningLevel || ReasoningLevel.MEDIUM;
    }
    
    // For xAI models, transform the model name based on reasoning level (not reasoning_effort param)
    let finalModelName = modelName;
    if (modelName === ModelName.XAI_GROK_4_1_FAST) {
      const { reasoningLevel: stateReasoningLevel } = useModelSelection.getState();
      const xaiReasoning = reasoningLevelOverride || stateReasoningLevel || ReasoningLevel.NONE;
      // Transform model name: None -> non-reasoning, Medium -> reasoning
      finalModelName = xaiReasoning === ReasoningLevel.NONE || xaiReasoning === ReasoningLevel.LOW
        ? 'grok-4-1-fast-non-reasoning'
        : 'grok-4-1-fast-reasoning';
    }
    
    // Generate temp IDs and idempotency key
    const tempUserId = crypto.randomUUID();
    const idempotencyKey = crypto.randomUUID();
    
    // Create streaming turn with optimistic user message
    const userMessage: import('@/lib/types').UserMessageDto = {
      id: tempUserId,
      message_text: text,
      status: 'pending',
      sources_requested: sources,
      created_at: new Date(),
      client_temp_id: tempUserId,
      idempotency_key: idempotencyKey
    };
    
    setStreamingTurn(sessionId, { 
      userMessage,
      aiResponse: {
        id: '',
        text: '',
        isLoading: true,
        isComplete: false,
        meta: {
          model_used: modelName || ModelName.CLAUDE_HAIKU_4_5
        }
      }
    });
    
    const requestBody = { 
      prompt: text, 
      source_selections: sources,
      client_temp_id: tempUserId,
      idempotency_key: idempotencyKey,
      model_name: finalModelName || ModelName.CLAUDE_HAIKU_4_5, // Use transformed model name (for xAI) or default
      provider_name: providerName,
      is_agent_mode: isAgentMode || false,
      device_id: deviceId || null,
      is_web_search_enabled: isWebSearchEnabled || false,
      reasoning: reasoningLevel  // null for xAI since model name changes instead
    };
    
    // Start streaming with new protocol
    return start(requestBody);
  }

  // Function to cancel the active stream
  function cancelStream() {
    if (activeCancelFunction) {
      activeCancelFunction();
    }
  }

  return { start, sendMessage, cancelStream };
}
