import { useMemo } from 'react';
import type { StreamingAIResponse } from './useChatMessages';
import type { TimelineBlock, ThinkingBlock, MessageBlock, ToolExecutionBlock, SummarizationBlock, AgentTransitionBlock } from '@/lib/types';

// Timeline event types
export type TimelineEvent = {
  type: 'text' | 'thinking' | 'tool_start' | 'tool_complete' | 'tool_fail' | 'summarization_start' | 'summarization_complete' | 'summarization_cancelled' | 'summarization_failed' | 'agent_transition';
  timestamp?: number;
  sequence?: number;
  content?: string;
  agent?: string;
  text?: string;
  isComplete?: boolean;
  toolCallId?: string;
  toolName?: string;
  toolArgs?: Record<string, any>;
  error?: string;
  fromAgent?: string;
  toAgent?: string;
  completed?: boolean;
};

// Processed group types for rendering
export type ProcessedGroup = 
  | { type: 'text'; content: string; startIndex: number }
  | { type: 'thinking'; content: ThinkingGroupContent; startIndex: number }
  | { type: 'tool'; content: ToolGroupContent; startIndex: number }
  | { type: 'summarization'; content: SummarizationGroupContent; startIndex: number }
  | { type: 'agent_transition'; content: AgentTransitionGroupContent; startIndex: number };

export type AgentTransitionGroupContent = {
  fromAgent: string;
  toAgent: string;
  toolName?: string;
  completed?: boolean;
};

export type ThinkingGroupContent = {
  agent: string;
  thinkingSessions: Array<{ sequence?: number; text: string; isComplete: boolean; isCancelled?: boolean }>;
  sessionCount: number;
  isComplete: boolean;
  isCancelled?: boolean;
  durationMs?: number;
};

export type ToolGroupContent = {
  toolName: string;
  toolCallId: string;
  toolArgs: Record<string, any>;
  state: 'running' | 'completed' | 'failed' | 'cancelled';
  durationMs?: number;
};

export type SummarizationGroupContent = {
  status: 'in_progress' | 'completed' | 'cancelled' | 'failed';
  agent: string;
  durationMs?: number;
  error?: string;
};

// Internal types for tracking during processing
type ThinkingGroup = { 
  agent: string; 
  thinkingSessions: any[]; 
  startIndex: number; 
  allComplete: boolean;
};

// NEW: Convert blocks directly to ProcessedGroups (most efficient for stored messages)
function blocksToProcessedGroups(blocks: TimelineBlock[]): ProcessedGroup[] {
  const groups: ProcessedGroup[] = [];

  blocks.forEach((block) => {
    switch (block.type) {
      case 'thinking_block':
        const thinkingBlock = block as ThinkingBlock;
        const isComplete = thinkingBlock.is_cancelled ? false : (thinkingBlock.is_complete ?? false);
        groups.push({
          type: 'thinking' as const,
          content: {
            agent: thinkingBlock.agent_name,
            thinkingSessions: [{
              sequence: block.sequence,
              text: thinkingBlock.content,
              isComplete: isComplete,
              isCancelled: thinkingBlock.is_cancelled
            }],
            sessionCount: 1,
            isComplete: isComplete,
            durationMs: block.timestamp_end - block.timestamp_start,
            isCancelled: thinkingBlock.is_cancelled
          },
          startIndex: block.sequence
        });
        break;

      case 'message_block':
        const messageBlock = block as MessageBlock;
        groups.push({
          type: 'text' as const,
          content: messageBlock.content,
          startIndex: block.sequence
        });
        break;

      case 'tool_execution_block':
        const toolBlock = block as ToolExecutionBlock;
        groups.push({
          type: 'tool' as const,
          content: {
            toolCallId: toolBlock.tool_call_id,
            toolName: toolBlock.tool_name,
            toolArgs: toolBlock.tool_args,
            state: (toolBlock.status === 'success' ? 'completed' : toolBlock.status) as 'running' | 'completed' | 'failed' | 'cancelled',
            durationMs: block.timestamp_end - block.timestamp_start
          },
          startIndex: block.sequence
        });
        break;
      
      case 'summarization_block':
        const summarizationBlock = block as SummarizationBlock;
        groups.push({
          type: 'summarization' as const,
          content: {
            status: summarizationBlock.status,
            agent: summarizationBlock.agent_name,
            durationMs: block.timestamp_end - block.timestamp_start
          },
          startIndex: block.sequence
        });
        break;

      case 'agent_transition_block':
        const transitionBlock = block as AgentTransitionBlock;
        groups.push({
          type: 'agent_transition' as const,
          content: {
            fromAgent: transitionBlock.from_agent,
            toAgent: transitionBlock.to_agent,
            toolName: transitionBlock.tool_name,
            completed: transitionBlock.completed,
          },
          startIndex: block.sequence,
        });
        break;

      case 'status_block':
        // Skip status blocks - they're metadata, not for display
        break;

      case 'workflow_start':
      case 'workflow_end':
        // Skip workflow blocks - they're metadata, not for display
        break;

      default:
        // Unknown block types - skip them
        break;
    }
  });

  return groups;
}

/**
 * Hook to process timeline events or blocks into renderable groups.
 *
 * This hook takes raw timeline events or pre-coalesced blocks and organizes them for rendering:
 * - Consecutive thinking events from the same agent → grouped into one ThinkingIndicator
 * - Individual tool executions → each rendered as a separate ToolExecutionIndicator
 * - Consecutive text events → combined into one text block
 *
 * For blocks: Directly converts pre-coalesced blocks to groups (most efficient)
 * For events: Processes raw events into groups (streaming/real-time)
 *
 * Groups are broken when interrupted by a different event type, ensuring chronological accuracy.
 */
export function useTimelineProcessor(
  timeline: TimelineEvent[] | undefined,
  streamingResponse?: StreamingAIResponse,
  blocks?: TimelineBlock[]
): ProcessedGroup[] {
  return useMemo(() => {
    // If blocks are provided (from DB), convert directly to ProcessedGroups
    if (blocks && blocks.length > 0) {
      return blocksToProcessedGroups(blocks);
    }

    // Process timeline events (streaming or parsed from markers)
    if (!timeline || timeline.length === 0) {
      return [];
    }

    const groups: ProcessedGroup[] = [];
    
    // Helper function to calculate duration from timeline events
    const calculateDuration = (startIndex: number, endIndex: number): number | undefined => {
      if (!timeline) return undefined;
      const startEvent = timeline[startIndex];
      const endEvent = timeline[endIndex];
      if (startEvent?.timestamp && endEvent?.timestamp) {
        return endEvent.timestamp - startEvent.timestamp;
      }
      return undefined;
    };

    // Helper function to flush the current thinking group
    const flushThinkingGroup = (
      group: ThinkingGroup,
      endIndex: number
    ) => {
      const durationMs = group.allComplete ? calculateDuration(group.startIndex, endIndex) : undefined;
      const isCancelled = streamingResponse?.isCancelled && !group.allComplete;
      groups.push({
        type: 'thinking',
        content: {
          agent: group.agent,
          thinkingSessions: group.thinkingSessions,
          sessionCount: group.thinkingSessions.length,
          isComplete: group.allComplete && !isCancelled,
          isCancelled: isCancelled,
          durationMs
        },
        startIndex: group.startIndex
      });
    };

    // Track active groups
    let currentThinkingGroup: ThinkingGroup | null = null;
    let textBuffer = '';
    let lastTextIndex = -1;

    // Track active tool executions for state management
    const activeTools = new Map<string, { 
      toolCallId: string; 
      toolName: string; 
      toolArgs: Record<string, any>; 
      state: string; 
      startIndex: number; 
      allEvents: any[] 
    }>();
    
    // Track active summarization for state management
    let activeSummarization: { 
      status: 'in_progress' | 'completed' | 'cancelled' | 'failed';
      startIndex: number; 
      startTimestamp: number;
      allEvents: any[] 
    } | null = null;

    timeline.forEach((event: TimelineEvent, idx: number) => {
      if (event.type === 'text') {
        // ===== TEXT EVENT =====
        // Flush any pending thinking group (text interrupts thinking sequence)
        if (currentThinkingGroup && currentThinkingGroup.allComplete) {
          flushThinkingGroup(currentThinkingGroup, idx - 1);
          currentThinkingGroup = null;
        }
        
        // Start or continue text buffer
        if (!textBuffer) {
          lastTextIndex = idx;
        }
        textBuffer += event.content || '';
        
      } else if (event.type === 'thinking') {
        // ===== THINKING EVENT =====
        // Flush text buffer if we have any
        if (textBuffer) {
          groups.push({ type: 'text', content: textBuffer, startIndex: lastTextIndex });
          textBuffer = '';
          lastTextIndex = -1;
        }
        
        const agent = event.agent || 'unknown';
        const isThinkingComplete = event.isComplete !== false;
        const isCancelled = streamingResponse?.isCancelled;
        
        // Handle thinking grouping for consecutive same-agent thinking
        if (isThinkingComplete) {
          // Check if this thinking should be grouped with the current group
          if (currentThinkingGroup && currentThinkingGroup.agent === agent) {
            const sessions = currentThinkingGroup.thinkingSessions;
            const lastSession = sessions[sessions.length - 1];
            if (lastSession && lastSession.sequence === event.sequence) {
              lastSession.text = event.text || '';
              lastSession.isComplete = true;
            } else {
              sessions.push({
                sequence: event.sequence,
                text: event.text || '',
                isComplete: true
              });
            }
            currentThinkingGroup.allComplete = true;
          } else {
            // Flush current group if it exists and is complete
            if (currentThinkingGroup && currentThinkingGroup.allComplete) {
              flushThinkingGroup(currentThinkingGroup, idx - 1);
            }
            
            // Start new group
            currentThinkingGroup = {
              agent,
              thinkingSessions: [{
                sequence: event.sequence,
                text: event.text || '',
                isComplete: true
              }],
              startIndex: idx,
              allComplete: true
            };
          }
        } else {
          // Incomplete thinking - handle streaming case
          if (currentThinkingGroup && currentThinkingGroup.agent === agent) {
            // Update the last session in the current group
            const lastSession = currentThinkingGroup.thinkingSessions[currentThinkingGroup.thinkingSessions.length - 1];
            if (lastSession && lastSession.sequence === event.sequence) {
              lastSession.text = event.text || '';
              lastSession.isComplete = false;
            } else {
              // New session in the group
              currentThinkingGroup.thinkingSessions.push({
                sequence: event.sequence,
                text: event.text || '',
                isComplete: false
              });
            }
            currentThinkingGroup.allComplete = false;
          } else {
            // Flush current group if complete
            if (currentThinkingGroup && currentThinkingGroup.allComplete) {
              flushThinkingGroup(currentThinkingGroup, idx - 1);
            }
            
            // Start new group with incomplete session
            currentThinkingGroup = {
              agent,
              thinkingSessions: [{
                sequence: event.sequence,
                text: event.text || '',
                isComplete: false
              }],
              startIndex: idx,
              allComplete: false
            };
          }
        }
        
      } else if (event.type === 'tool_start' || event.type === 'tool_complete' || event.type === 'tool_fail') {
        // ===== TOOL EVENT =====
        // Flush text buffer if we have any
        if (textBuffer) {
          groups.push({ type: 'text', content: textBuffer, startIndex: lastTextIndex });
          textBuffer = '';
          lastTextIndex = -1;
        }
        
        // Flush current thinking group (tool interrupts thinking sequence)
        if (currentThinkingGroup && currentThinkingGroup.allComplete) {
          flushThinkingGroup(currentThinkingGroup, idx - 1);
          currentThinkingGroup = null;
        }
        
        const toolCallId = event.toolCallId || 'unknown';
        const toolName = event.toolName || 'unknown';
        
        // Determine the state for this tool event
        let state: 'running' | 'completed' | 'failed' | 'cancelled' = 'completed';
        if (streamingResponse && streamingResponse.toolExecutions) {
          const toolExecution = streamingResponse.toolExecutions.find(t => t.toolCallId === toolCallId);
          state = toolExecution?.state || (event.type === 'tool_start' ? 'running' : event.type === 'tool_complete' ? 'completed' : 'failed');
        } else {
          state = event.type === 'tool_start' ? 'running' : event.type === 'tool_complete' ? 'completed' : 'failed';
        }
        
        // Track individual tool execution
        if (event.type === 'tool_start') {
          // Store new tool execution
          activeTools.set(toolCallId, {
            toolCallId,
            toolName,
            toolArgs: event.toolArgs || {},
            state: 'running',
            startIndex: idx,
            allEvents: [event]
          });
        } else if (event.type === 'tool_complete' || event.type === 'tool_fail') {
          // Tool completed - create the group and add to output
          const toolExecution = activeTools.get(toolCallId);
          if (toolExecution) {
            toolExecution.state = state;
            toolExecution.allEvents.push(event);
            
            // Calculate duration
            const durationMs = calculateDuration(toolExecution.startIndex, idx);
            
            // Add completed tool execution to groups
            groups.push({
              type: 'tool',
              content: {
                toolCallId: toolExecution.toolCallId,
                toolName: toolExecution.toolName,
                toolArgs: toolExecution.toolArgs,
                state: state,
                durationMs
              },
              startIndex: toolExecution.startIndex
            });
            
            // Remove from active tools
            activeTools.delete(toolCallId);
          }
        }
        
      } else if (event.type === 'summarization_start' || event.type === 'summarization_complete' || event.type === 'summarization_cancelled' || event.type === 'summarization_failed') {
        // ===== SUMMARIZATION EVENT =====
        // Flush text buffer if we have any
        if (textBuffer) {
          groups.push({ type: 'text', content: textBuffer, startIndex: lastTextIndex });
          textBuffer = '';
          lastTextIndex = -1;
        }
        
        // Flush current thinking group
        if (currentThinkingGroup && currentThinkingGroup.allComplete) {
          flushThinkingGroup(currentThinkingGroup, idx - 1);
          currentThinkingGroup = null;
        }
        
        if (event.type === 'summarization_start') {
          // Store new summarization
          activeSummarization = {
            status: 'in_progress',
            startIndex: idx,
            startTimestamp: event.timestamp || Date.now(),
            allEvents: [event]
          };
        } else if (event.type === 'summarization_complete' || event.type === 'summarization_cancelled' || event.type === 'summarization_failed') {
          // Summarization completed, cancelled, or failed
          if (activeSummarization) {
            // Map event type to status
            let status: 'completed' | 'cancelled' | 'failed';
            if (event.type === 'summarization_complete') {
              status = 'completed';
            } else if (event.type === 'summarization_failed') {
              status = 'failed';
            } else {
              status = 'cancelled';
            }
            activeSummarization.status = status;
            activeSummarization.allEvents.push(event);
            
            // Calculate duration
            const durationMs = (event.timestamp || Date.now()) - activeSummarization.startTimestamp;
            
            // Add completed summarization to groups
            groups.push({
              type: 'summarization',
              content: {
                status: activeSummarization.status,
                agent: 'RSInsight Agent',
                durationMs,
                error: event.type === 'summarization_failed' ? event.error : undefined
              },
              startIndex: activeSummarization.startIndex
            });
            
            // Clear active summarization
            activeSummarization = null;
          }
        }
      } else if (event.type === 'agent_transition') {
        if (textBuffer) {
          groups.push({ type: 'text', content: textBuffer, startIndex: lastTextIndex });
          textBuffer = '';
          lastTextIndex = -1;
        }
        if (currentThinkingGroup && currentThinkingGroup.allComplete) {
          flushThinkingGroup(currentThinkingGroup, idx - 1);
          currentThinkingGroup = null;
        }
        groups.push({
          type: 'agent_transition',
          content: {
            fromAgent: (event as any).fromAgent || '',
            toAgent: (event as any).toAgent || '',
            toolName: (event as any).toolName,
            completed: (event as any).completed,
          },
          startIndex: idx,
        });
      }
    });
    
    // Flush remaining text buffer
    if (textBuffer) {
      groups.push({ type: 'text', content: textBuffer, startIndex: lastTextIndex });
    }
    
    // Flush any remaining active tool executions (still running/streaming)
    activeTools.forEach((toolExecution) => {
      groups.push({
        type: 'tool',
        content: {
          toolCallId: toolExecution.toolCallId,
          toolName: toolExecution.toolName,
          toolArgs: toolExecution.toolArgs,
          state: (streamingResponse?.isCancelled ? 'cancelled' : toolExecution.state) as 'running' | 'completed' | 'failed' | 'cancelled',
          durationMs: undefined // Still running, no duration yet
        },
        startIndex: toolExecution.startIndex
      });
    });
    
    // Flush any remaining active summarization (still in progress/streaming)
    if (activeSummarization !== null) {
      const { startIndex } = activeSummarization;
      groups.push({
        type: 'summarization',
        content: {
          status: streamingResponse?.isCancelled ? 'cancelled' : 'in_progress',
          agent: 'RSInsight Agent',
          durationMs: undefined // Still running, no duration yet
        },
        startIndex
      });
    }
    
    // Flush any remaining thinking group
    if (currentThinkingGroup) {
      flushThinkingGroup(currentThinkingGroup, timeline.length - 1);
    }
    
    // Sort groups by their start index to maintain chronological order
    groups.sort((a, b) => a.startIndex - b.startIndex);
    
    return groups;
  }, [timeline, streamingResponse, blocks]);
}

