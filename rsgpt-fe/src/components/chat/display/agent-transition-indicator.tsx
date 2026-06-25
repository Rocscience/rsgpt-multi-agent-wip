import React from 'react';
import { ArrowRightIcon } from '@heroicons/react/24/outline';

export interface AgentTransitionIndicatorProps {
  fromAgent: string;
  toAgent: string;
  toolName?: string;
  completed?: boolean;
}

export function AgentTransitionIndicator({
  fromAgent,
  toAgent,
  toolName,
  completed = false,
}: AgentTransitionIndicatorProps) {
  const label = completed
    ? `${fromAgent} responded to ${toAgent}`
    : `${fromAgent} asked ${toAgent}`;

  return (
    <div className="flex items-center gap-2 px-2 py-1.5 rounded-md bg-default-50 border border-default-200">
      <span className="text-xs text-default-500 font-medium shrink-0">
        {label}
      </span>
      <ArrowRightIcon className="w-3 h-3 text-default-400 shrink-0" />
      <span className="text-xs text-default-600 truncate">
        {fromAgent}
        <span className="text-default-400 mx-1">→</span>
        {toAgent}
      </span>
      {toolName && (
        <span className="text-xs text-default-400 truncate ml-auto">
          {toolName}
        </span>
      )}
    </div>
  );
}
