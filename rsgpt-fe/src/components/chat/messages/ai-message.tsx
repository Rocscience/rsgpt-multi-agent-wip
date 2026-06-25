import { useMemo, useRef, useEffect } from 'react';
import ReactMarkdown from 'react-markdown';
import type { Components } from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import { motion } from 'framer-motion';
import SourceCarousel from '../sources/source-carousel';
import { MarkdownHeroTable } from '../display/markdown-hero-table';
import { UserFeedbackButtons } from '../feedback/user-feedback-buttons';
import { ToolExecutionIndicator } from '../display/tool-execution-indicator';
import { AnimatedStreamingText } from '../display/animated-streaming-text';
import {Link, Card, CardBody, Divider, Code, Snippet, Alert, Chip, Tooltip } from '@heroui/react';
import { ArrowTopRightOnSquareIcon, PencilIcon } from '@heroicons/react/24/outline';
import { ThinkingIndicator } from '../display/thinking-indicator';
import { PlanDisplay } from '../display/plan-display';
import { WorkflowStatusBar } from '../display/workflow-status-bar';
import { AgentTransitionIndicator } from '../display/agent-transition-indicator';
import Image from 'next/image';
import type { AIResponseDto, MediaData, TimelineBlock, ErrorBlock, WorkflowEndBlock } from '@/lib/types';
import type { StreamingAIResponse } from '@/hooks/useChatMessages';
import { MODEL_CONFIGS, ModelName } from '@/lib/types';

// Helper function to extract error message from timeline blocks
function extractErrorFromTimeline(blocks?: TimelineBlock[]): string | undefined {
  if (!blocks || blocks.length === 0) return undefined;
  
  // Look for error_block first (most specific error info)
  const errorBlock = blocks.find(b => b.type === 'error_block') as ErrorBlock | undefined;
  if (errorBlock?.error_message) {
    return errorBlock.error_message;
  }
  
  // Fall back to workflow_end with failed status
  const workflowEndBlock = blocks.find(b => b.type === 'workflow_end' && (b as WorkflowEndBlock).status === 'failed') as WorkflowEndBlock | undefined;
  if (workflowEndBlock?.error) {
    return workflowEndBlock.error;
  }
  
  return undefined;
}
import { useCitationHighlight } from '@/contexts/CitationHighlightContext';
import { useTimelineProcessor } from '@/hooks/useTimelineProcessor';

type Props = {
  aiResponse?: AIResponseDto;
  streamingResponse?: StreamingAIResponse;
  sessionId: string;
  isLoading?: boolean;
  isComplete?: boolean;
  lookingForMedia?: boolean;
  mediaData?: MediaData;
  isTemp?: boolean;
  isAgentMode?: boolean;
  searchResults?: Array<{
    title?: string,
    url?: string,
    date?: string,
    lastUpdated?: string,
    snippet?: string,
    source?: string,
  }>;
};

// Helper function to extract domain from URL (without TLD)
function extractDomain(url: string): string {
  try {
    const urlObj = new URL(url);
    // Remove 'www.' prefix if present
    const hostname = urlObj.hostname.replace(/^www\./, '');
    // Extract just the domain name (first part before any dot)
    // For example: "rocscience.com" -> "rocscience", "example.co.uk" -> "example"
    const domainParts = hostname.split('.');
    return domainParts[0] || hostname;
  } catch {
    // Fallback: try to extract domain manually
    const match = url.match(/https?:\/\/(?:www\.)?([^\/]+)/);
    if (match) {
      const hostname = match[1].replace(/^www\./, '');
      // Extract just the domain name (first part before any dot)
      const domainParts = hostname.split('.');
      return domainParts[0] || hostname;
    }
    return url; // Return original URL if parsing fails
  }
}

// Helper function to detect consecutive citations in text
function findConsecutiveCitations(text: string, searchResults: any[]) {
  const rankToResult = new Map<number, any>();
  searchResults.forEach((result, idx) => {
    const rank = (result as any).rank ?? (idx + 1);
    rankToResult.set(rank, result);
  });

  // Find all citation patterns
  const combinedPattern = /(?:\[(\d+)\]|\[Entry\s+(\d+)\](?!\())/gi;
  const citations: Array<{ match: string; rank: number; start: number; end: number }> = [];
  let match;
  
  combinedPattern.lastIndex = 0;
  while ((match = combinedPattern.exec(text)) !== null) {
    const rank = parseInt(match[1] || match[2], 10);
    citations.push({
      match: match[0],
      rank,
      start: match.index,
      end: match.index + match[0].length
    });
  }
  
  // Group consecutive citations
  const groupedCitations: Array<{ 
    start: number; 
    end: number; 
    citations: Array<{ match: string; rank: number; start: number; end: number }> 
  }> = [];
  
  if (citations.length > 0) {
    let currentGroup = [citations[0]];
    
    for (let i = 1; i < citations.length; i++) {
      const current = citations[i];
      const previous = citations[i - 1];
      
      const gap = current.start - previous.end;
      if (gap <= 1) {
        currentGroup.push(current);
      } else {
        if (currentGroup.length > 0) {
          groupedCitations.push({
            start: currentGroup[0].start,
            end: currentGroup[currentGroup.length - 1].end,
            citations: [...currentGroup]
          });
        }
        currentGroup = [current];
      }
    }
    
    if (currentGroup.length > 0) {
      groupedCitations.push({
        start: currentGroup[0].start,
        end: currentGroup[currentGroup.length - 1].end,
        citations: [...currentGroup]
      });
    }
  }
  
  return groupedCitations;
}

export function AIMessage({ 
  aiResponse, 
  streamingResponse,
  sessionId, 
  isTemp,
  searchResults
}: Props) {
  const { highlightedUrl } = useCitationHighlight();

  // Parse tool, thinking, and summarization markers from message text and reconstruct timeline
  const parseToolMarkers = (messageText: string) => {
    const timeline: any[] = [];
    const toolStates = new Map<string, 'running' | 'completed' | 'failed'>();
    const toolInfo = new Map<string, { toolName: string; toolArgs: Record<string, any> }>();
    
    // Split by tool, thinking, and summarization markers while preserving the text
    // Use .*? (non-greedy) instead of [^>]+ to handle > characters inside JSON
    const parts = messageText.split(/(<!-- (?:TOOL_(?:START|COMPLETE|FAIL)|THINKING_(?:START|COMPLETE)|SUMMARIZATION_(?:START|COMPLETE|CANCELLED|FAILED)):.*? -->)/);
    
    // Track thinking events to reconstruct complete thinking blocks
    const thinkingBlocks = new Map<string, { agent: string; sequence: number; text: string; isComplete: boolean; startTimestamp?: number }>();
    let currentThinkingKey = '';
    let collectingThinkingText = false;
    
    parts.forEach((part) => {
      if (part.startsWith('<!-- TOOL_START:')) {
        // Parse tool start marker (with optional timestamp)
        const match = part.match(/<!-- TOOL_START:([^:]+):([^:]+):(.+?)(?::(\d+))? -->/);
        if (match) {
          const [_, toolName, toolCallId, argsJson, timestampStr] = match;
          try {
            const toolArgs = JSON.parse(argsJson);
            const timestamp = timestampStr ? parseInt(timestampStr, 10) : Date.now();
            
            // Store tool info for later completion/fail events
            toolInfo.set(toolCallId, { toolName, toolArgs });
            
            timeline.push({
              type: 'tool_start',
              toolCallId,
              toolName,
              toolArgs,
              timestamp,
              sequence: 0 // Marker-based events don't have sequence numbers
            });
            toolStates.set(toolCallId, 'running');
          } catch (e) {
            console.error('Failed to parse tool args:', e);
          }
        }
      } else if (part.startsWith('<!-- TOOL_COMPLETE:')) {
        // Parse tool complete marker (with optional timestamp)
        const match = part.match(/<!-- TOOL_COMPLETE:([^:]+)(?::(\d+))? -->/);
        if (match) {
          const [_, toolCallId, timestampStr] = match;
          const info = toolInfo.get(toolCallId);
          const timestamp = timestampStr ? parseInt(timestampStr, 10) : Date.now();
          
          timeline.push({
            type: 'tool_complete',
            toolCallId,
            toolName: info?.toolName || 'unknown',
            toolArgs: info?.toolArgs || {},
            timestamp,
            sequence: 0 // Marker-based events don't have sequence numbers
          });
          toolStates.set(toolCallId, 'completed');
        }
      } else if (part.startsWith('<!-- TOOL_FAIL:')) {
        // Parse tool fail marker (with optional timestamp)
        const match = part.match(/<!-- TOOL_FAIL:([^:]+):(.+?)(?::(\d+))? -->/);
        if (match) {
          const [_, toolCallId, error, timestampStr] = match;
          const info = toolInfo.get(toolCallId);
          const timestamp = timestampStr ? parseInt(timestampStr, 10) : Date.now();
          
          timeline.push({
            type: 'tool_fail',
            toolCallId,
            toolName: info?.toolName || 'unknown',
            toolArgs: info?.toolArgs || {},
            error,
            timestamp,
            sequence: 0 // Marker-based events don't have sequence numbers
          });
          toolStates.set(toolCallId, 'failed');
        }
      } else if (part.startsWith('<!-- THINKING_START:')) {
        // Parse thinking start marker (with optional timestamp)
        const match = part.match(/<!-- THINKING_START:([^:]+):([^:]+)(?::(\d+))? -->/);
        if (match) {
          const [_, agent, sequence, timestampStr] = match;
          const sequenceNum = parseInt(sequence, 10);
          const timestamp = timestampStr ? parseInt(timestampStr, 10) : Date.now();
          currentThinkingKey = `${agent}-${sequenceNum}`;
          collectingThinkingText = true;
          
          thinkingBlocks.set(currentThinkingKey, {
            agent,
            sequence: sequenceNum,
            text: '',
            isComplete: false,
            startTimestamp: timestamp
          });
        }
      } else if (part.startsWith('<!-- THINKING_COMPLETE:')) {
        // Parse thinking complete marker (with optional timestamp)
        const match = part.match(/<!-- THINKING_COMPLETE:([^:]+):([^:]+)(?::(\d+))? -->/);
        if (match) {
          const [_, agent, sequence, timestampStr] = match;
          const sequenceNum = parseInt(sequence, 10);
          const timestamp = timestampStr ? parseInt(timestampStr, 10) : Date.now();
          const thinkingKey = `${agent}-${sequenceNum}`;
          
          const thinkingBlock = thinkingBlocks.get(thinkingKey);
          if (thinkingBlock) {
            thinkingBlock.isComplete = true;
            
            // Add complete thinking event to timeline
            timeline.push({
              type: 'thinking',
              agent: thinkingBlock.agent,
              text: thinkingBlock.text.trim(),
              isComplete: true,
              sequence: thinkingBlock.sequence,
              timestamp: thinkingBlock.startTimestamp || timestamp
            });
          }
          
          collectingThinkingText = false;
          currentThinkingKey = '';
        }
      } else if (part.startsWith('<!-- SUMMARIZATION_START:')) {
        const match = part.match(/<!-- SUMMARIZATION_START:(\d+):(\d+) -->/);
        if (match) {
          timeline.push({
            type: 'summarization_start',
            timestamp: parseInt(match[1], 10),
            sequence: parseInt(match[2], 10)
          });
        }
      } else if (part.startsWith('<!-- SUMMARIZATION_COMPLETE:')) {
        const match = part.match(/<!-- SUMMARIZATION_COMPLETE:(\d+) -->/);
        if (match) {
          timeline.push({
            type: 'summarization_complete',
            timestamp: parseInt(match[1], 10),
            sequence: 0
          });
        }
      } else if (part.startsWith('<!-- SUMMARIZATION_CANCELLED:')) {
        const match = part.match(/<!-- SUMMARIZATION_CANCELLED:(\d+) -->/);
        if (match) {
          timeline.push({
            type: 'summarization_cancelled',
            timestamp: parseInt(match[1], 10),
            sequence: 0
          });
        }
      } else if (part.startsWith('<!-- SUMMARIZATION_FAILED:')) {
        const match = part.match(/<!-- SUMMARIZATION_FAILED:(\d+):?(.*) -->/);
        if (match) {
          timeline.push({
            type: 'summarization_failed',
            timestamp: parseInt(match[1], 10),
            sequence: 0,
            error: match[2] || undefined
          });
        }
      } else if (part.trim()) {
        if (collectingThinkingText && currentThinkingKey) {
          // This is thinking content between THINKING_START and THINKING_COMPLETE
          const thinkingBlock = thinkingBlocks.get(currentThinkingKey);
          if (thinkingBlock) {
            thinkingBlock.text += part;
          }
        } else {
          // Regular text
          timeline.push({
            type: 'text',
            content: part,
            timestamp: Date.now(),
            sequence: 0 // Marker-based events don't have sequence numbers
          });
        }
      }
    });
    
    return { timeline, toolStates };
  };

  // Determine which response to use and extract data
  const responseData = useMemo(() => {
    if (streamingResponse) {
      return {
        id: streamingResponse.id,
        text: streamingResponse.text,
        sources_used: [],
        response_time_ms: undefined,
        model_used: streamingResponse.meta?.model_used,
        token_count: streamingResponse.meta?.token_count,
        isLoading: streamingResponse.isLoading,
        isComplete: streamingResponse.isComplete,
        isCancelled: streamingResponse.isCancelled, // NEW: Track cancellation
        error: streamingResponse.error, // Track streaming errors
        lookingForMedia: streamingResponse.lookingForMedia,
        mediaData: streamingResponse.mediaData,
        searchResults: streamingResponse.searchResults || searchResults,
        status: undefined, // Streaming responses don't have status from DB
        timeline: streamingResponse.timeline // Use streaming timeline
      };
    } else if (aiResponse) {
      // NEW: Check if we have block-based timeline (preferred)
      if (aiResponse.timeline?.blocks?.length) {
        return {
          id: aiResponse.id,
          text: aiResponse.message_text,
          sources_used: aiResponse.sources_used,
          response_time_ms: aiResponse.response_time_ms,
          model_used: aiResponse.model_used,
          token_count: aiResponse.token_count,
          isLoading: false,
          isComplete: true,
          lookingForMedia: false,
          mediaData: aiResponse.media_links,
          searchResults: aiResponse.search_results || searchResults,
          status: aiResponse.status,
          is_agent_mode: aiResponse.is_agent_mode,
          timeline: undefined, // No events to parse
          timelineBlocks: aiResponse.timeline.blocks, // Pre-coalesced blocks from timeline.blocks
          toolStates: {}, // Block-based doesn't need toolStates
          // For errored responses, extract error from timeline blocks (not message_text which contains the AI response)
          error: aiResponse.status === 'errored' ? extractErrorFromTimeline(aiResponse.timeline?.blocks) || 'An error occurred while processing your request' : undefined
        };
      } else {
        // LEGACY: Parse tool markers from message text for history rendering
        const { timeline, toolStates } = parseToolMarkers(aiResponse.message_text);

        return {
          id: aiResponse.id,
          text: aiResponse.message_text,
          sources_used: aiResponse.sources_used,
          response_time_ms: aiResponse.response_time_ms,
          model_used: aiResponse.model_used,
          token_count: aiResponse.token_count,
          isLoading: false,
          isComplete: true,
          lookingForMedia: false,
          mediaData: aiResponse.media_links,
          searchResults: aiResponse.search_results || searchResults,
          status: aiResponse.status,
          is_agent_mode: aiResponse.is_agent_mode,
          timeline: timeline.length > 0 ? timeline : undefined,
          timelineBlocks: undefined,
          toolStates,
          // For errored responses, don't use message_text (it contains the AI response, not the error)
          // Legacy responses don't have timeline blocks, so just show a generic error
          error: aiResponse.status === 'errored' ? 'An error occurred while processing your request' : undefined
        };
      }
    }
    return null;
  }, [streamingResponse, aiResponse, searchResults]);

  // Process timeline events or blocks into renderable groups
  const processedGroups = useTimelineProcessor(
    responseData?.timeline,    // Events (streaming/legacy)
    streamingResponse,         // Streaming response
    responseData?.timelineBlocks // Blocks (new history)
  );

  // Calculate tool count for copy functionality
  const toolCount = processedGroups.filter(group => group.type === 'tool').length;

  // Log search results once per message ID to avoid spam
  useEffect(() => {
    if (!responseData?.id || !responseData?.searchResults || responseData.searchResults.length === 0) {
      return;
    }
    
  }, [responseData?.id, responseData?.searchResults]);

  // Helper function to convert citation references to clickable markdown links
  const processCitations = useMemo(() => {
    const searchResults = responseData?.searchResults || [];
    
    // Create a map of original rank (from Perplexity) to search result
    // The backend stores the original rank in the 'rank' field before sorting
    const rankToResult = new Map<number, typeof searchResults[0]>();
    searchResults.forEach((result, idx) => {
      // Use rank field if available (Perplexity's original order), otherwise fall back to array index + 1
      const rank = (result as any).rank ?? (idx + 1);
      rankToResult.set(rank, result);
    });
    
    return (text: string): string => {
      if (!text || searchResults.length === 0) {
        return text;
      }
      
      // First, find all consecutive citation patterns and group them
      const groupedCitations = findConsecutiveCitations(text, searchResults);
      
      // Process grouped citations (replace with special markers)
      let processedText = text;
      let offset = 0;
      
      groupedCitations.forEach((group) => {
        if (group.citations.length >= 2) {
          // Group of 2 or more consecutive citations
          const primaryCitation = group.citations[0];
          const additionalCitations = group.citations.slice(1);
          
          const primaryResult = rankToResult.get(primaryCitation.rank);
          if (primaryResult?.url) {
            const primaryUrl = primaryResult.url;
            const primaryTitle = primaryResult.title || `Source ${primaryCitation.rank}`;
            const primaryDomain = extractDomain(primaryUrl);
            
            // Create additional citation data
            const additionalData = additionalCitations.map(citation => {
              const result = rankToResult.get(citation.rank);
              if (result?.url) {
                return {
                  url: result.url,
                  title: result.title || `Source ${citation.rank}`,
                  domain: extractDomain(result.url)
                };
              }
              return null;
            }).filter(Boolean);
            
            // Create a special grouped citation link with encoded additional data
            try {
              const additionalDataJson = JSON.stringify(additionalData);
              
              // Use encodeURIComponent instead of btoa to handle Unicode characters safely
              const encodedAdditionalData = encodeURIComponent(additionalDataJson);
              
              const groupedLink = `[${primaryDomain} +${additionalCitations.length}](${primaryUrl} "${primaryTitle} | AdditionalData: ${encodedAdditionalData}")`;
              
              // Replace the grouped citations with the special link
              const beforeGroup = processedText.substring(0, group.start + offset);
              const afterGroup = processedText.substring(group.end + offset);
              processedText = beforeGroup + groupedLink + afterGroup;
              
              // Adjust offset for next replacement
              offset += groupedLink.length - (group.end - group.start);
            } catch (error) {
              console.error('Error encoding grouped citation:', error);
              // Skip this grouping if encoding fails
            }
          }
        }
      });
      
      // Process remaining single citations
      // Pattern 1: [1], [2], [3], etc. (simple numeric citations)
      processedText = processedText.replace(/\[(\d+)\](?!\()/g, (match, numStr) => {
        const citationRank = parseInt(numStr, 10);
        const result = rankToResult.get(citationRank);
        if (result?.url) {
          const url = result.url;
          const title = result.title || `Source ${numStr}`;
          const domain = extractDomain(url);
          return `[${domain}](${url} "${title}")`;
        }
        return match; // Return original if no matching result
      });
      
      // Pattern 2: [Entry 1], [Entry 2], etc. (Perplexity entry format)
      processedText = processedText.replace(/\[Entry\s+(\d+)\](?!\()/gi, (match, numStr) => {
        const citationRank = parseInt(numStr, 10);
        const result = rankToResult.get(citationRank);
        if (result?.url) {
          const url = result.url;
          const title = result.title || `Source ${numStr}`;
          const domain = extractDomain(url);
          return `[${domain}](${url} "${title}")`;
        }
        return match; // Return original if no matching result
      });
      
      return processedText;
    };
  }, [responseData?.searchResults]);

  // Process text to convert citation references to clickable links
  const cleanText = useMemo(() => {
    const text = responseData?.text || '';
    
    // First, clean up redundant citation text BEFORE processing citations
    let processed = text;
    
    // Remove redundant citation text after markdown links
    // Handles patterns like:
    // - [Link Text](URL) [Rocscience Documentation] → [Link Text](URL)
    // - Text: [URL](URL) [Documentation] → Text: [URL](URL)
    // - [Title](URL) [Source] → [Title](URL)
    
    // More comprehensive regex to handle various patterns
    processed = processed.replace(/(\[([^\]]+)\]\([^)]+\))\s*\[([^\]]*(?:Documentation|Source|Reference|Help|Guide)[^\]]*)\]/gi, '$1');
    
    // Also handle broader citation patterns (any bracketed text after links)
    processed = processed.replace(/(\[([^\]]+)\]\([^)]+\))\s*\[([^\]]+)\]/gi, (match: string, linkPart: string, linkText: string, citation: string) => {
      // Only remove if citation looks like a source attribution
      if (/(?:documentation|source|reference|help|guide|rocscience)/i.test(citation)) {
        return linkPart;
      }
      return match; // Keep original if not a source citation
    });
    
    // Then process citations (convert [1] to links)
    processed = processCitations(processed);
    
    // Fix markdown section boundaries that got concatenated
    // Handle punctuation, citation links, and other text endings
    processed = processed.replace(/([.!?)\]])\s*##\s/g, '$1\n\n## ');
    processed = processed.replace(/([.!?)\]])\s*#\s/g, '$1\n\n# ');
    
    return processed;
  }, [responseData?.text, processCitations]);


  //  Show interrupted response alert for interrupted responses (if saved to DB & status=streaming, then the stream was interrupted)
  if (responseData?.status === 'streaming') {
    return (
      <div className="w-full mb-8 sm:mb-12">
      <div className="w-full bg-transparent text-foreground px-0 py-0">
        <Alert 
          variant="flat" 
          color="warning" 
          className="mb-4 bg-transparent text-xs"
          hideIconWrapper={true}
          title="Stream interrupted, try refreshing the page"
        />
        </div>
      </div>
    )
  }
  
  // Show cancelled state during streaming (user pressed stop button), but still render timeline if available
  if (responseData?.isCancelled && !responseData?.text && !responseData?.timeline && !responseData?.timelineBlocks) {
    // Determine the appropriate message based on error
    const cancelMessage = responseData?.error?.includes('Connection lost') 
      ? responseData.error 
      : "Response was interrupted";
    
    return (
      <div className="w-full mb-8 sm:mb-12">
        <div className="w-full bg-transparent text-foreground px-0 py-0">
          <Alert 
            variant="flat" 
            color="warning" 
            className="mb-4 bg-transparent text-xs"
            hideIconWrapper={true}
            title={cancelMessage}
          />
          {/* Show feedback buttons even with empty response */}
          <UserFeedbackButtons messageId={responseData.id} sessionId={sessionId} messageText={''} />
        </div>
      </div>
    )
  }
  
  // Show cancelled state with empty text (from DB), but still render timeline if available
  if (responseData?.status === 'cancelled' && !responseData?.text && !responseData?.timelineBlocks) {
    return (
      <div className="w-full mb-8 sm:mb-12">
        <div className="w-full bg-transparent text-foreground px-0 py-0">
          <Alert 
            variant="flat" 
            color="warning" 
            className="mb-4 bg-transparent text-xs"
            hideIconWrapper={true}
            title="Response was interrupted"
          />
          {/* Show feedback buttons even with empty response */}
          <UserFeedbackButtons messageId={responseData.id} sessionId={sessionId} messageText={''} />
        </div>
      </div>
    )
  }
  
  // Show loading state (but not for cancelled, errored, or workflow mode)
  // For workflow mode, we want to show the workflow UI components instead of just the loading GIF
  const hasWorkflowState = streamingResponse?.workflowState || streamingResponse?.currentPlan || (responseData?.timeline && responseData.timeline.length > 0);
  
  if (responseData?.status !== 'errored' && !responseData?.error && responseData?.status !== 'cancelled' && !responseData?.isCancelled && (responseData?.isLoading || !responseData?.text)) {
    // If we have workflow state, skip the simple loading GIF and show workflow UI instead
    if (!hasWorkflowState) {
      return (
        <div className="w-full mb-8 sm:mb-12">
          <div className="w-full bg-transparent text-foreground px-0 py-0">
            <div className="flex justify-start items-center py-4">
              <Image 
                src="/images/rsinsight-logo.gif" 
                alt="Loading..." 
                className="w-8 h-8"
                width={32}
                height={32}
                unoptimized
              />
            </div>
          </div>
        </div>
      );
    }
    // Fall through to main render to show workflow UI
  }

  return (
    <div className="w-full mb-8 sm:mb-12">
      <div className="w-full bg-transparent text-foreground px-0 py-0">
        {/* Show cancelled alert for cancelled responses from database */}
        {responseData?.status === 'cancelled' && (
          <Alert 
            variant="flat" 
            color="warning" 
            className="bg-transparent text-xs mb-4"
            hideIconWrapper={true}
            title="Response was interrupted"
          />
        )}
        
        {/* Show cancelled alert for streaming responses (client-side) */}
        {streamingResponse?.isCancelled && !streamingResponse?.isComplete && (
          <Alert 
            variant="flat" 
            color="warning" 
            className="bg-transparent text-xs mb-4"
            hideIconWrapper={true}
            title={streamingResponse?.error?.includes('Connection lost') ? streamingResponse.error : "Response was interrupted"}
          />
        )}
        
        {/* Show error alert for errored responses (streaming or completed) - but not if cancelled */}
        {(responseData?.status === 'errored' || responseData?.error) && 
         !streamingResponse?.isCancelled && 
         responseData?.status !== 'cancelled' && (
          <Alert 
            variant="flat" 
            color="danger" 
            className="bg-transparent text-xs mb-4"
            hideIconWrapper={true}
            title={responseData?.error || "There was a problem with this request"}
          />
        )}
        
        
        {/* Show error alert for failed workflows */}
        {streamingResponse?.workflowState?.status === 'FAILED' && streamingResponse?.workflowState?.error && (
          <Alert 
            variant="flat" 
            color="danger" 
            className="bg-transparent text-xs mb-4"
            hideIconWrapper={true}
            title={`Workflow failed: ${streamingResponse.workflowState.error}`}
          />
        )}
        
        
        {/* Show loading indicator if still loading but no workflow state yet */}
        {responseData?.isLoading && !responseData?.error && !streamingResponse?.workflowState && !streamingResponse?.currentPlan && !(responseData?.timeline && responseData.timeline.length > 0) && (
          <div className="flex justify-start items-center py-4 mb-4">
            <Image 
              src="/images/rsinsight-logo.gif" 
              alt="Loading..." 
              className="w-8 h-8"
              width={32}
              height={32}
              unoptimized
            />
          </div>
        )}
        
        {/* Workflow status during multi-agent streaming */}
        {streamingResponse?.workflowState && (
          <WorkflowStatusBar
            workflowState={streamingResponse.workflowState}
            taskProgress={streamingResponse.taskProgress}
          />
        )}

        {/* Plan Display - show once when created */}
        {streamingResponse?.currentPlan && (
          <PlanDisplay
            plan={streamingResponse.currentPlan}
            currentTaskId={streamingResponse.taskProgress?.currentTaskId}
          />
        )}
        
        {/* Render timeline (interleaves text, thinking, and tool executions) - works for both streaming and history */}
        {processedGroups.length > 0 ? (
          <div className="space-y-3">
            {processedGroups.map((group, idx) => {
              if (group.type === 'thinking') {
                  // Render thinking indicator
                  const content = group.content as any;
                  
                  // Handle grouped thinking vs individual thinking
                  if (content.thinkingSessions) {
                    // Grouped thinking - combine all sessions' text
                    const combinedText = content.thinkingSessions
                      .map((session: any) => session.text)
                      .join('\n\n---\n\n');
                    
                    // Determine if this thinking group is currently streaming
                    const isCurrentlyStreaming = streamingResponse?.isLoading && !content.isComplete;
                    return (
                      <ThinkingIndicator
                        key={`thinking-group-${content.agent}-${idx}`}
                        agent={content.agent}
                        text={combinedText}
                        isComplete={content.isCancelled ? false : (content.isComplete ?? false)}
                        isCancelled={content.isCancelled}
                        isStreaming={isCurrentlyStreaming}
                        sessionCount={content.sessionCount}
                        durationMs={content.durationMs}
                      />
                    );
                  } else {
                    // Individual thinking (fallback for legacy format)
                    const isCurrentlyStreaming = streamingResponse?.isLoading && !content.isComplete;
                    
                    return (
                      <ThinkingIndicator
                        key={`thinking-${content.agent}-${content.sequence}`}
                        agent={content.agent}
                        text={content.text}
                        isComplete={content.isCancelled ? false : (content.isComplete ?? false)}
                        isCancelled={content.isCancelled}
                        isStreaming={isCurrentlyStreaming}
                        durationMs={content.durationMs}
                      />
                    );
                  }
                } else if (group.type === 'text') {
                    // First, clean up redundant citation text BEFORE processing citations
                    let processedText = group.content;
                    
                    // Remove redundant citation text after markdown links
                    // Handles patterns like:
                    // - [Link Text](URL) [Rocscience Documentation] → [Link Text](URL)
                    // - Text: [URL](URL) [Documentation] → Text: [URL](URL)
                    // - [Title](URL) [Source] → [Title](URL)
                    processedText = processedText.replace(/(\[([^\]]+)\]\([^)]+\))\s*\[([^\]]*(?:Documentation|Source|Reference)[^\]]*)\]/gi, '$1');
                    
                    // Also handle broader citation patterns (any bracketed text after links)
                    processedText = processedText.replace(/(\[([^\]]+)\]\([^)]+\))\s*\[([^\]]+)\]/gi, (match: string, linkPart: string, linkText: string, citation: string) => {
                      // Only remove if citation looks like a source attribution
                      if (/(?:documentation|source|reference|help|guide|rocscience)/i.test(citation)) {
                        return linkPart;
                      }
                      return match; // Keep original if not a source citation
                    });
                    
                    // Then process citations (convert [1] to links)
                    processedText = processCitations(processedText);
                    
                    // Fix markdown section boundaries that got concatenated
                    // Handle punctuation, citation links, and other text endings
                    processedText = processedText.replace(/([.!?)\]])\s*##\s/g, '$1\n\n## ');
                    processedText = processedText.replace(/([.!?)\]])\s*#\s/g, '$1\n\n# ');
                    
                    // Determine if this is an actively streaming message
                    const isActivelyStreaming = !!(streamingResponse?.isLoading && !streamingResponse?.isComplete);
                    
                    // Define markdown components for reuse
                    const markdownComponents: Components = {
                          // Use the same markdown components
                          table: ({ node }: any) => (
                            <div className="my-4">
                              <MarkdownHeroTable node={node as any} />
                            </div>
                          ),
                          blockquote: ({ children }: any) => (
                            <Card className="my-4 bg-secondary text-secondary-foreground border-l-4 border-l-primary" radius="md" shadow="sm">
                              <CardBody className="py-3 px-4">
                                <div className="italic text-default-600">{children}</div>
                              </CardBody>
                            </Card>
                          ),
                          a: ({ href, children, title }: any) => {
                            const isExternal = href?.startsWith('http') || href?.startsWith('mailto:');
                            const isHighlighted = highlightedUrl === href;
                            
                            // Check if this is a grouped citation (has +X in the text and additional data in title)
                            const childrenStr = String(children);
                            const isGrouped = childrenStr.includes(' +') && title?.includes(' | AdditionalData:');
                            
                            if (isGrouped) {
                              // Parse the additional citations from the encoded data
                              const additionalDataStr = title?.split(' | AdditionalData: ')[1] || '';
                              let additionalData = [];
                              
                              try {
                                const decodedData = decodeURIComponent(additionalDataStr);
                                additionalData = JSON.parse(decodedData);
                              } catch (error) {
                                console.error('Failed to decode additional citation data:', error);
                              }
                              
                              return (
                                <Tooltip 
                                  content={
                                    <div className="flex flex-col space-y-2 p-1">
                                      <div className="text-sm font-medium">Sources • {additionalData.length + 1} </div>
                                      <Link isExternal showAnchorIcon isBlock color="foreground" href={href} className="text-xs text-foreground cursor-pointer transition-colors">{title?.split(' | AdditionalData:')[0]}</Link>
                                      
                                      {additionalData.length > 0 && (
                                        <>
                                          <div className="flex flex-col space-y-2">
                                            {additionalData.map((citation: any, index: number) => (
                                              <Link
                                                isExternal
                                                showAnchorIcon
                                                isBlock
                                                color="foreground"
                                                key={index}
                                                href={citation.url}
                                                className="text-xs text-foreground cursor-pointer transition-colors"
                                                onClick={(e) => e.stopPropagation()}
                                              >
                                                {citation.title}
                                              </Link>
                                            ))}
                                          </div>
                                        </>
                                      )}
                                    </div>
                                  } 
                                  placement="bottom-start" 
                                  delay={300}
                                >
                                  <Chip
                                    as="a"
                                    href={href}
                                    target={isExternal ? "_blank" : undefined}
                                    rel={isExternal ? "noopener noreferrer" : undefined}
                                    color={isHighlighted ? "primary" : "default"}
                                    variant="flat"
                                    size="sm"
                                    className={`ms-1 inline-flex items-center cursor-pointer gap-1 hover:bg-default-700 hover:text-default-50 text-xs mt-1 ${isHighlighted ? 'text-primary' : ''}`}
                                    endContent={<ArrowTopRightOnSquareIcon className="w-3 h-3" />}
                                  >
                                    {children}
                                  </Chip>
                                </Tooltip>
                              );
                            }
                            
                            return (
                              <Chip
                                as="a"
                                href={href}
                                target={isExternal ? "_blank" : undefined}
                                rel={isExternal ? "noopener noreferrer" : undefined}
                                color={isHighlighted ? "primary" : "default"}
                                variant="flat"
                                size="sm"
                                className={`ms-1 inline-flex items-center cursor-pointer gap-1 hover:bg-default-700 hover:text-default-50 text-xs mt-1 ${isHighlighted ? 'text-primary' : ''}`}
                                endContent={isExternal ? <ArrowTopRightOnSquareIcon className="w-3 h-3" /> : undefined}
                              >
                                {children}
                              </Chip>
                            );
                          },
                          code: ({ children, className, ...props }: any) => {
                            const isInline = !className || !className.startsWith('language-');
                            if (isInline) {
                              return <Code size="sm" color="default" className="mx-1 align-middle break-all inline-block whitespace-normal">{children}</Code>;
                            }
                            return (
                              <div className="my-4">
                                <Snippet variant="bordered" color="default" className="w-full" copyButtonProps={{ size: 'sm', variant: 'light' }}>
                                  <pre className="text-sm overflow-x-auto"><code {...props}>{children}</code></pre>
                                </Snippet>
                              </div>
                            );
                          },
                          h1: ({ children }: any) => (
                            <div className="my-6">
                              <h1 className="text-2xl font-bold text-foreground mb-3">{children}</h1>
                              <Divider className="my-2" />
                            </div>
                          ),
                          h2: ({ children }: any) => (
                            <div className="my-5">
                              <h2 className="text-xl font-semibold text-foreground mb-2">{children}</h2>
                              <Divider className="my-2" />
                            </div>
                          ),
                          h3: ({ children }: any) => <h3 className="text-lg font-semibold text-foreground mt-6 mb-2">{children}</h3>,
                          h4: ({ children }: any) => <h4 className="text-base font-semibold text-foreground mt-5 mb-2">{children}</h4>,
                          h5: ({ children }: any) => <h5 className="text-sm font-semibold text-foreground mt-4 mb-1">{children}</h5>,
                          h6: ({ children }: any) => <h6 className="text-xs font-semibold text-foreground mt-3 mb-1 uppercase tracking-wide">{children}</h6>,
                          p: ({ children }: any) => <p className="leading-relaxed my-4 text-[0.975rem]">{children}</p>,
                          hr: () => <hr className="border-divider" />,
                          img: ({ src, alt, title }: any) => (
                            <Card className="my-4" shadow="sm">
                              <CardBody className="p-0">
                                <Image src={src as string} alt={(alt as string) || ''} title={(title as string) || (alt as string) || ''} className="w-full h-auto rounded-lg" loading="lazy" width={260} height={160} />
                                {alt && (
                                  <div className="p-3 text-center">
                                    <span className="text-xs text-default-500">{alt}</span>
                                  </div>
                                )}
                              </CardBody>
                            </Card>
                          ),
                          ul: ({ children }: any) => <ul className="list-disc pl-6 my-4 space-y-1 text-[0.975rem] leading-relaxed">{children}</ul>,
                          ol: ({ children }: any) => <ol className="list-decimal pl-6 my-4 space-y-1 text-[0.975rem] leading-relaxed">{children}</ol>,
                          li: ({ children }: any) => <li className="pl-1">{children}</li>,
                          pre: ({ children }: any) => (
                            <Card className="my-4 bg-default-100" radius="md" shadow="sm">
                              <CardBody className="p-4">
                                <pre className="text-sm font-mono text-foreground overflow-x-auto whitespace-pre-wrap">{children}</pre>
                              </CardBody>
                            </Card>
                          ),
                    };
                    
                  return (
                    <AnimatedStreamingText
                      key={`text-${idx}`}
                      text={processedText}
                      isStreaming={isActivelyStreaming}
                      markdownComponents={markdownComponents}
                      className="prose prose-base prose-gray max-w-none [&>*:first-child]:mt-0 [&>*:last-child]:mb-0"
                    />
                  );
                } else if (group.type === 'tool') {
                  // Render tool execution indicator
                  const content = group.content as any;
                  
                  return (
                    <ToolExecutionIndicator
                      key={`tool-${content.toolCallId}-${idx}`}
                      toolName={content.toolName}
                      toolArgs={content.toolArgs}
                      state={content.state}
                      durationMs={content.durationMs}
                    />
                  );
                } else if (group.type === 'agent_transition') {
                  const content = group.content as any;
                  return (
                    <AgentTransitionIndicator
                      key={`transition-${idx}`}
                      fromAgent={content.fromAgent}
                      toAgent={content.toAgent}
                      toolName={content.toolName}
                      completed={content.completed}
                    />
                  );
                } else if (group.type === 'summarization') {
                  // Render summarization status - aligned with thinking/tool indicators
                  const content = group.content as any;
                  const isInProgress = content.status === 'in_progress';
                  const isCancelled = content.status === 'cancelled';
                  const isFailed = content.status === 'failed';
                  
                  let statusText = 'Chat context summarized';
                  if (isInProgress) {
                    statusText = 'Summarizing chat context...';
                  } else if (isCancelled) {
                    statusText = 'Context summarization cancelled.';
                  } else if (isFailed) {
                    statusText = 'Failed to summarize.';
                  }
                  
                  return (
                    <div key={`summarization-${idx}`} className="flex flex-col gap-1 mb-4">
                      {/* Aligned with ThinkingIndicator and ToolExecutionIndicator */}
                      <div className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md">
                        <div className={`inline-flex items-center gap-1.5 ${isInProgress ? 'animate-pulse' : ''}`}>
                          <PencilIcon className={`w-3.5 h-3.5 ${isFailed ? 'text-danger-400' : 'text-default-400'}`} />
                          <span className={`text-xs font-normal ${isFailed ? 'text-danger-500' : 'text-default-500'} ${isCancelled ? 'line-through' : ''}`}>
                            {statusText}
                          </span>
                        </div>
                      </div>
                    </div>
                  );
                } else {
                  return null;
                }
              })}
          </div>
        ) : (
          /* Fallback for messages without timeline (legacy or plain text) */
          <div className="space-y-3">
            <div 
              className="prose prose-base prose-gray max-w-none [&>*:first-child]:mt-0 [&>*:last-child]:mb-0"
            >
              <ReactMarkdown
                remarkPlugins={[remarkGfm, remarkMath]}
                rehypePlugins={[rehypeKatex]}
                components={{
              // Tables with HeroUI wrapper
              table: ({ node }) => (
                <div className="my-4">
                  <MarkdownHeroTable node={node as any} />
                </div>
              ),

              // Blockquotes with Card
              blockquote: ({ children }) => (
                <Card className="my-4 bg-secondary text-secondary-foreground border-l-4 border-l-primary" radius="md" shadow="sm">
                  <CardBody className="py-3 px-4">
                    <div className="italic text-default-600">{children}</div>
                  </CardBody>
                </Card>
              ),

              // Links as Chips with external link icon
              a: ({ href, children, title }) => {
                try {
                  const isExternal = href?.startsWith('http') || href?.startsWith('mailto:');
                  const isHighlighted = highlightedUrl === href;
                  
                  // Check if this is a grouped citation (has +X in the text and additional data in title)
                  const childrenStr = String(children);
                  const isGrouped = childrenStr.includes(' +') && title?.includes(' | AdditionalData:');
                  
                  if (isGrouped) {
                    // Parse the additional citations from the encoded data
                    const additionalDataStr = title?.split(' | AdditionalData: ')[1] || '';
                    let additionalData = [];
                    
                    try {
                      // Use decodeURIComponent instead of atob to handle Unicode characters safely
                      const decodedData = decodeURIComponent(additionalDataStr);
                      additionalData = JSON.parse(decodedData);
                    } catch (error) {
                      console.error('Failed to decode additional citation data:', error);
                    }
                  
                  return (
                    <Tooltip 
                      content={
                        <div className="max-w-xs">
                          <div className="text-sm font-medium mb-2">{title?.split(' | AdditionalData:')[0]}</div>
                          <div className="text-xs text-default-400 mb-3">{href}</div>
                          
                          {additionalData.length > 0 && (
                            <>
                              <div className="text-xs font-medium mb-2">Additional sources:</div>
                              <div className="space-y-2">
                                {additionalData.map((citation: any, index: number) => (
                                  <a
                                    key={index}
                                    href={citation.url}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="block text-xs text-primary-500 hover:text-primary-400 hover:underline cursor-pointer transition-colors"
                                    onClick={(e) => e.stopPropagation()}
                                  >
                                    {citation.title}
                                  </a>
                                ))}
                              </div>
                            </>
                          )}
                        </div>
                      } 
                      placement="top" 
                      delay={300}
                    >
                      <Chip
                        as="a"
                        href={href}
                        target={isExternal ? "_blank" : undefined}
                        rel={isExternal ? "noopener noreferrer" : undefined}
                        color={isHighlighted ? "primary" : "default"}
                        variant="flat"
                        size="sm"
                        className="inline-flex items-center cursor-pointer gap-1 hover:bg-default-700 hover:text-default-50 text-xs my-1"
                        endContent={<ArrowTopRightOnSquareIcon className="w-3 h-3" />}
                      >
                        {children}
                      </Chip>
                    </Tooltip>
                  );
                }
                
                  return (
                    <Chip
                      as="a"
                      href={href}
                      target={isExternal ? "_blank" : undefined}
                      rel={isExternal ? "noopener noreferrer" : undefined}
                      color={isHighlighted ? "primary" : "default"}
                      variant="flat"
                      size="sm"
                      className="inline-flex items-center cursor-pointer gap-1 hover:bg-default-700 hover:text-default-50 text-xs my-1"
                      endContent={isExternal ? <ArrowTopRightOnSquareIcon className="w-3 h-3" /> : undefined}
                    >
                      {children}
                    </Chip>
                  );
                } catch (error) {
                  console.error('Error rendering link component:', error);
                  // Fallback: render as simple link
                  return (
                    <a href={href} target="_blank" rel="noopener noreferrer" className="text-primary-500 hover:underline">
                      {children}
                    </a>
                  );
                }
              },

              // Inline code vs blocks
              code: ({ children, className, ...props }: any) => {
                const isInline = !className || !className.startsWith('language-');
                if (isInline) {
                  return (
                    <Code size="sm" color="default" className="mx-1 align-middle break-all inline-block whitespace-normal">
                      {children}
                    </Code>
                  );
                }
                return (
                  <div className="my-4">
                    <Snippet
                      variant="bordered"
                      color="default"
                      className="w-full"
                      copyButtonProps={{ size: 'sm', variant: 'light' }}
                    >
                      <pre className="text-sm overflow-x-auto">
                        <code {...props}>{children}</code>
                      </pre>
                    </Snippet>
                  </div>
                );
              },

              // Headings with consistent spacing; divider only for h1/h2
              h1: ({ children }) => (
                <div className="my-6">
                  <h1 className="text-2xl font-bold text-foreground mb-3">{children}</h1>
                  <Divider className="my-2" />
                </div>
              ),
              h2: ({ children }) => (
                <div className="my-5">
                  <h2 className="text-xl font-semibold text-foreground mb-2">{children}</h2>
                  <Divider className="my-2" />
                </div>
              ),
              h3: ({ children }) => (
                <h3 className="text-lg font-semibold text-foreground mt-6 mb-2">{children}</h3>
              ),
              h4: ({ children }) => (
                <h4 className="text-base font-semibold text-foreground mt-5 mb-2">{children}</h4>
              ),
              h5: ({ children }) => (
                <h5 className="text-sm font-semibold text-foreground mt-4 mb-1">{children}</h5>
              ),
              h6: ({ children }) => (
                <h6 className="text-xs font-semibold text-foreground mt-3 mb-1 uppercase tracking-wide">{children}</h6>
              ),

              // Paragraphs
              p: ({ children }) => (
                <p className="leading-relaxed my-4 text-[0.975rem]">{children}</p>
              ),

              // Borders
              hr: () => (
                <hr className="border-divider" />
              ),

              // Images with better styling
              img: ({ src, alt, title }) => (
                <Card className="my-4" shadow="sm">
                  <CardBody className="p-0">
                    <Image
                      src={src as string}
                      alt={(alt as string) || ''}
                      title={(title as string) || (alt as string) || ''}
                      className="w-full h-auto rounded-lg"
                      loading="lazy"
                      width={260}
                      height={160}
                    />
                    {alt && (
                      <div className="p-3 text-center">
                        <span className="text-xs text-default-500">{alt}</span>
                      </div>
                    )}
                  </CardBody>
                </Card>
              ),

              ul: ({ children }) => (
                  <ul className="list-disc pl-6 my-4 space-y-1 text-[0.975rem] leading-relaxed">
                      {children}
                  </ul>
              ),
              ol: ({ children }) => (
                  <ol className="list-decimal pl-6 my-4 space-y-1 text-[0.975rem] leading-relaxed">
                      {children}
                  </ol>
              ),
              li: ({ children }) => (
                  <li className="pl-1">
                      {children}
                  </li>
              ),

              // Pre tags (rare when not fenced)
              pre: ({ children }) => (
                <Card className="my-4 bg-default-100" radius="md" shadow="sm">
                  <CardBody className="p-4">
                    <pre className="text-sm font-mono text-foreground overflow-x-auto whitespace-pre-wrap">
                      {children}
                    </pre>
                  </CardBody>
                </Card>
              ),
            }}
          >
            {cleanText}
          </ReactMarkdown>
            </div>
          </div>
        )}

          {/* Show pulsing text when lookingForMedia is true or when we have search results but no media yet */}
          {(responseData?.lookingForMedia && !responseData?.mediaData) ||
           (responseData?.searchResults && responseData?.searchResults.length > 0 &&
            !responseData?.mediaData?.images && !responseData?.mediaData?.videos) && (
            <div className="mt-4 w-full">
              <div className="text-sm text-default-600 animate-pulse">
                Searching the Web for Media
              </div>
            </div>
          )}
          
        {/* Show media carousel if available */}
        {responseData?.mediaData?.images && <SourceCarousel sources={responseData.mediaData} />}
        

        
        {/* User feedback buttons for completed, cancelled, or errored messages */}
        {(responseData?.isComplete || responseData?.isCancelled || responseData?.status === 'cancelled' || responseData?.error) && (!isTemp || responseData?.isCancelled || responseData?.status === 'cancelled' || responseData?.error) && responseData?.id && (() => {
          // Safely get display name - only show if model exists in config
          let displayName: string | undefined;
          if (responseData.model_used) {
            const modelConfig = MODEL_CONFIGS[responseData.model_used as ModelName];
            // Show raw model ID as fallback
            displayName = modelConfig?.displayName || responseData.model_used;
          }
          
          return (
            <UserFeedbackButtons
              messageText={cleanText}
              messageId={responseData.id}
              sessionId={sessionId}
              sourcesUsed={responseData.sources_used}
              responseTimeMs={responseData.response_time_ms}
              toolCount={toolCount}
              tokenCount={responseData.token_count}
              displayName={displayName}
              isAgentMode={responseData.is_agent_mode}
              searchResults={responseData.searchResults}
            />
          );
        })()}
      </div>
    </div>
  );
}
