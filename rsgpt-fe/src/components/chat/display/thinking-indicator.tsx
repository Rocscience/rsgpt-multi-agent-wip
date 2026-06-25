import React, { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import { 
  ChevronDownIcon,
  ChevronUpIcon,
  SparklesIcon
} from '@heroicons/react/24/outline';
import {Link, Card, CardBody, Divider, Code, Snippet, Chip } from '@heroui/react';
import { ArrowTopRightOnSquareIcon } from '@heroicons/react/24/outline';

export interface ThinkingIndicatorProps {
  agent: string;
  text: string;
  isComplete: boolean;
  isCancelled?: boolean; // Whether thinking was cancelled/interrupted
  isStreaming?: boolean; // Whether content is currently streaming
  sessionCount?: number; // Number of thinking sessions grouped together
  durationMs?: number; // Duration in milliseconds from start to completion
}

// Map agent names to display labels (present and past tense)
const AGENT_DISPLAY_NAMES: Record<string, { present: string; past: string }> = {
  'Classify': { present: 'Classifying request', past: 'Classified request' },
  'Knowledge': { present: 'Searching knowledge', past: 'Searched knowledge' },
  'High Level Planner': { present: 'Planning next moves', past: 'Planned next moves' },
  'Executor': { present: 'Executing tasks', past: 'Executed tasks' },
  'Evaluator': { present: 'Evaluating results', past: 'Evaluated results' },
  'Summarizer': { present: 'Summarizing results', past: 'Summarized results' }
};

// Helper function to format duration in a human-readable way
const formatDuration = (durationMs: number): string => {
  const seconds = Math.round(durationMs / 1000);
  if (seconds < 1) {
    return '< 1s';
  } else if (seconds === 1) {
    return '1s';
  } else {
    return `${seconds}s`;
  }
};

export function ThinkingIndicator({ agent, text, isComplete, isCancelled, isStreaming, sessionCount, durationMs }: ThinkingIndicatorProps) {
  const [isExpanded, setIsExpanded] = useState(false);

  const agentLabels = AGENT_DISPLAY_NAMES[agent];
  let displayLabel = agentLabels
    ? (isCancelled ? `${agentLabels.present} (cancelled)` : (isComplete ? agentLabels.past : agentLabels.present))
    : (isCancelled ? 'Thinking (cancelled)' : (isComplete ? 'Thought' : 'Thinking'));
  
  // Add duration to completed labels
  if (isComplete && durationMs !== undefined) {
    displayLabel += ` for ${formatDuration(durationMs)}`;
  }
  
  // Disable accordion if no text content yet, but allow expansion once streaming starts
  const hasContent = text && text.trim().length > 0;
  const canExpand = hasContent || isStreaming;
  
  return (
    <div className="flex flex-col gap-1 mb-4">
      {/* Main thinking indicator */}
      <button
        onClick={() => canExpand && setIsExpanded(!isExpanded)}
        disabled={!canExpand}
        className={`inline-flex items-center gap-1.5 px-2 py-1 rounded-md transition-colors ${
          canExpand 
            ? 'hover:bg-default-100 cursor-pointer' 
            : 'cursor-not-allowed opacity-50'
        }`}
      >
        <div className={`inline-flex items-center gap-1.5 ${!isComplete && !isCancelled ? 'animate-pulse' : ''}`}>
          {/* Brain/sparkles icon */}
          <SparklesIcon className="w-3.5 h-3.5 text-default-400" />
          
          {/* Thinking label */}
          <span className="text-xs text-default-500 font-normal">
            {displayLabel}{!isComplete && '...'}
          </span>
        </div>
        
        {/* Expand/collapse icon */}
        {canExpand && (
          isExpanded ? (
            <ChevronUpIcon className="w-3 h-3 text-default-400" />
          ) : (
            <ChevronDownIcon className="w-3 h-3 text-default-400" />
          )
        )}
      </button>
      
      {/* Reasoning text accordion */}
      {isExpanded && hasContent && (
        <div className="ml-6 pl-3 border-l-2 border-default-200 py-2">
          <div className="prose prose-sm prose-gray max-w-none [&>*:first-child]:mt-0 [&>*:last-child]:mb-0 text-xs">
            <ReactMarkdown
              remarkPlugins={[remarkGfm, remarkMath]}
              rehypePlugins={[rehypeKatex]}
              components={{
                // Links as Chips with external link icon
                a: ({ href, children, title }) => {
                  const isExternal = href?.startsWith('http') || href?.startsWith('mailto:');
                  
                  return (
                    <Chip
                      as="a"
                      href={href}
                      target={isExternal ? "_blank" : undefined}
                      rel={isExternal ? "noopener noreferrer" : undefined}
                      color="default"
                      variant="flat"
                      size="sm"
                      className="ms-1 inline-flex items-center cursor-pointer gap-1 hover:bg-default-700 hover:text-default-50 text-xs mt-1"
                      endContent={isExternal ? <ArrowTopRightOnSquareIcon className="w-3 h-3" /> : undefined}
                    >
                      {children}
                    </Chip>
                  );
                },

                // Inline code vs blocks
                code: ({ children, className, ...props }: any) => {
                  const isInline = !className || !className.startsWith('language-');
                  if (isInline) {
                    return <Code size="sm" color="default" className="mx-1 align-middle text-xs">{children}</Code>;
                  }
                  return (
                    <div className="my-2">
                      <Snippet variant="bordered" color="default" className="w-full text-xs" copyButtonProps={{ size: 'sm', variant: 'light' }}>
                        <pre className="text-xs overflow-x-auto"><code {...props}>{children}</code></pre>
                      </Snippet>
                    </div>
                  );
                },

                // Headings with appropriate sizing for thinking content
                h1: ({ children }) => <h1 className="text-sm font-bold text-foreground mb-2">{children}</h1>,
                h2: ({ children }) => <h2 className="text-sm font-semibold text-foreground mb-2">{children}</h2>,
                h3: ({ children }) => <h3 className="text-xs font-semibold text-foreground mb-1">{children}</h3>,
                h4: ({ children }) => <h4 className="text-xs font-medium text-foreground mb-1">{children}</h4>,
                h5: ({ children }) => <h5 className="text-xs font-medium text-foreground mb-1">{children}</h5>,
                h6: ({ children }) => <h6 className="text-xs font-medium text-foreground mb-1 uppercase tracking-wide">{children}</h6>,

                // Paragraphs
                p: ({ children }) => <p className="leading-relaxed my-2 text-xs text-default-500">{children}</p>,

                // Lists
                ul: ({ children }) => <ul className="list-disc pl-4 my-2 space-y-1 text-xs leading-relaxed">{children}</ul>,
                ol: ({ children }) => <ol className="list-decimal pl-4 my-2 space-y-1 text-xs leading-relaxed">{children}</ol>,
                li: ({ children }) => <li className="pl-1 text-default-500">{children}</li>,

                // Blockquotes
                blockquote: ({ children }) => (
                  <Card className="my-2 bg-secondary text-secondary-foreground border-l-4 border-l-primary" radius="md" shadow="sm">
                    <CardBody className="py-2 px-3">
                      <div className="italic text-default-600 text-xs">{children}</div>
                    </CardBody>
                  </Card>
                ),

                // Strong/bold text
                strong: ({ children }) => <strong className="font-semibold text-foreground">{children}</strong>,

                // Emphasis/italic text  
                em: ({ children }) => <em className="italic">{children}</em>,

                // Horizontal rules
                hr: () => <hr className="border-divider my-2" />,
              }}
            >
              {text}
            </ReactMarkdown>
          </div>
        </div>
      )}
    </div>
  );
}

