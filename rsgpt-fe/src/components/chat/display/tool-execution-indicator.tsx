import React, { useState } from 'react';
import { Spinner } from '@heroui/react';
import { 
  CheckCircleIcon, 
  XCircleIcon,
  BoltIcon,
  WrenchIcon,
  MagnifyingGlassIcon,
  GlobeAltIcon,
  DocumentTextIcon,
  PencilSquareIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  CogIcon
} from '@heroicons/react/24/outline';

type ToolExecutionState = 'running' | 'completed' | 'failed' | 'cancelled';

interface ToolExecutionIndicatorProps {
  toolName: string;
  toolArgs?: Record<string, any>;
  state: ToolExecutionState;
  durationMs?: number; // Duration in milliseconds from start to completion
}

// Map tool names to user-friendly display info with heroicons (present and past tense)
const TOOL_INFO: Record<string, { Icon: React.ComponentType<{ className?: string }>; present: string; past: string }> = {
  'search_knowledge': { Icon: MagnifyingGlassIcon, present: 'Searching knowledge base', past: 'Searched knowledge base' },
  'list_tools': { Icon: WrenchIcon, present: 'Discovering available tools', past: 'Discovered available tools' },
  'invoke_tool': { Icon: BoltIcon, present: 'Invoking tool', past: 'Invoked tool' },
  'web_search': { Icon: GlobeAltIcon, present: 'Searching the web', past: 'Searched the web' },
  'read_file': { Icon: DocumentTextIcon, present: 'Reading file', past: 'Read file' },
  'write_file': { Icon: PencilSquareIcon, present: 'Writing file', past: 'Wrote file' }
};

// Technical fields to hide from user
const HIDDEN_FIELDS = ['device_id', 'user_id', 'session_id', 'api_key', 'token'];

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

// Format tool arguments for display
const formatVisibleArgs = (args: Record<string, any>): Array<[string, any]> => {
  if (!args || Object.keys(args).length === 0) {
    return [];
  }
  
  // Filter out technical/hidden fields
  const visibleArgs = Object.entries(args).filter(
    ([key]) => !HIDDEN_FIELDS.some(hidden => key.toLowerCase().includes(hidden))
  );
  
  return visibleArgs;
};

// Format key from snake_case to Title Case
const formatKey = (key: string): string => {
  return key
    .split('_')
    .map(word => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ');
};

// Format value for display
const formatValue = (value: any): string => {
  if (typeof value === 'string') {
    return value.length > 100 ? value.substring(0, 100) + '...' : value;
  } else if (typeof value === 'object') {
    return JSON.stringify(value, null, 2);
  }
  return String(value);
};

export function ToolExecutionIndicator({ toolName, toolArgs, state, durationMs }: ToolExecutionIndicatorProps) {
  const [isExpanded, setIsExpanded] = useState(false);
  
  const toolInfo = TOOL_INFO[toolName];
  const ToolIcon = toolInfo?.Icon || CogIcon;
  let toolLabel = toolInfo
    ? (state === 'completed' || state === 'failed' || state === 'cancelled' ? toolInfo.past : toolInfo.present)
    : (state === 'completed' || state === 'failed' || state === 'cancelled' ? `Ran ${toolName}` : `Running ${toolName}`);

  // Add state info to cancelled tools
  if (state === 'cancelled') {
    toolLabel += ' (cancelled)';
  }

  // Add duration to completed/failed/cancelled labels
  if ((state === 'completed' || state === 'failed' || state === 'cancelled') && durationMs !== undefined) {
    toolLabel += ` in ${formatDuration(durationMs)}`;
  }
  
  const visibleArgs = formatVisibleArgs(toolArgs || {});
  const hasArgs = visibleArgs.length > 0;
  
  // Get state icon
  const StateIcon = () => {
    switch (state) {
      case 'running':
        return <Spinner size="sm" color="default" />;
      case 'completed':
        return <CheckCircleIcon className="w-5 h-5 text-success-500" />;
      case 'failed':
        return <XCircleIcon className="w-5 h-5 text-danger-500" />;
      case 'cancelled':
        return <XCircleIcon className="w-5 h-5 text-warning-500" />;
    }
  };
  
  return (
    <div className="flex flex-col gap-1 mb-4">
      {/* Main tool indicator */}
      <button
        onClick={() => hasArgs && setIsExpanded(!isExpanded)}
        className={`inline-flex items-center gap-1.5 px-2 py-1 rounded-md transition-colors ${
          hasArgs ? 'hover:bg-default-100 cursor-pointer' : 'cursor-default'
        }`}
        disabled={!hasArgs}
      >
        <div className={`inline-flex items-center gap-1.5 ${state === 'running' ? 'animate-pulse' : ''}`}>
          {/* Tool icon */}
          <ToolIcon className="w-3.5 h-3.5 text-default-400" />
          
          {/* State indicator */}
          <StateIcon />
          
          {/* Tool label */}
          <span className="text-xs text-default-500 font-normal">
            {toolLabel}
          </span>
        </div>
        
        {/* Expand/collapse icon if has args */}
        {hasArgs && (
          isExpanded ? (
            <ChevronUpIcon className="w-3 h-3 text-default-400" />
          ) : (
            <ChevronDownIcon className="w-3 h-3 text-default-400" />
          )
        )}
      </button>
      
      {/* Arguments accordion */}
      {hasArgs && isExpanded && (
        <div className="ml-6 pl-3 border-l-2 border-default-200 space-y-1">
            {visibleArgs.map(([key, value]) => (
              <div key={key} className="text-xs">
                <span className="text-default-400 font-medium">{formatKey(key)}:</span>{' '}
                <span className="text-default-500 font-mono break-all">{formatValue(value)}</span>
              </div>
            ))}
        </div>
      )}
    </div>
  );
}

