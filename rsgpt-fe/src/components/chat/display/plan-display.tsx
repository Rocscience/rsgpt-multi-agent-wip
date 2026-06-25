import React, { useState } from 'react';
import { 
  ChevronDownIcon,
  ChevronUpIcon,
  ClipboardDocumentListIcon,
  CheckCircleIcon,
  ClockIcon,
  XCircleIcon
} from '@heroicons/react/24/outline';
import type { WorkflowPlan, WorkflowTask } from '@/hooks/useChatMessages';

export interface PlanDisplayProps {
  plan: WorkflowPlan;
  currentTaskId?: number;
}

// Get icon for task status
const getTaskIcon = (task: WorkflowTask, isCurrentTask: boolean) => {
  if (task.status === 'completed') {
    return <CheckCircleIcon className="w-4 h-4 text-success-500 flex-shrink-0" />;
  } else if (task.status === 'failed') {
    return <XCircleIcon className="w-4 h-4 text-danger-500 flex-shrink-0" />;
  } else if (task.status === 'in_progress' || isCurrentTask) {
    return <ClockIcon className="w-4 h-4 text-warning-500 flex-shrink-0 animate-pulse" />;
  } else {
    // Pending
    return <div className="w-4 h-4 rounded-full border-2 border-default-300 flex-shrink-0" />;
  }
};

export function PlanDisplay({ plan, currentTaskId }: PlanDisplayProps) {
  const [isExpanded, setIsExpanded] = useState(true); // Default expanded to show plan
  
  return (
    <div className="flex flex-col gap-2 mb-4">
      {/* Header */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md transition-colors hover:bg-default-100 cursor-pointer"
      >
        <div className="inline-flex items-center gap-1.5">
          {/* Plan icon */}
          <ClipboardDocumentListIcon className="w-3.5 h-3.5 text-default-400" />
          
          {/* Plan label */}
          <span className="text-xs text-default-500 font-medium">
            Execution Plan
          </span>
          
          {/* Task count */}
          <span className="text-xs text-default-400">
            ({plan.tasks.filter(t => t.status === 'completed').length}/{plan.tasks.length} completed)
          </span>
        </div>
        
        {/* Expand/collapse icon */}
        {isExpanded ? (
          <ChevronUpIcon className="w-3 h-3 text-default-400" />
        ) : (
          <ChevronDownIcon className="w-3 h-3 text-default-400" />
        )}
      </button>
      
      {/* Plan details */}
      {isExpanded && (
        <div className="ml-6 pl-3 border-l-2 border-default-200 space-y-3">
          {/* Goal */}
          <div className="space-y-1">
            <span className="text-xs text-default-400 font-medium">Goal:</span>
            <p className="text-xs text-default-600 whitespace-pre-wrap break-words">
              {plan.goal}
            </p>
          </div>
          
          {/* Assumptions (if any) */}
          {plan.assumptions && plan.assumptions.length > 0 && (
            <div className="space-y-1">
              <span className="text-xs text-default-400 font-medium">Assumptions:</span>
              <ul className="list-disc list-inside space-y-0.5 ml-2">
                {plan.assumptions.map((assumption, idx) => (
                  <li key={idx} className="text-xs text-default-500">
                    {assumption}
                  </li>
                ))}
              </ul>
            </div>
          )}
          
          {/* Tasks */}
          <div className="space-y-1">
            <span className="text-xs text-default-400 font-medium">Tasks:</span>
            <div className="space-y-2">
              {plan.tasks.map((task) => {
                const isCurrentTask = currentTaskId === task.id;
                
                return (
                  <div
                    key={task.id}
                    className={`flex items-start gap-2 p-2 rounded-md transition-colors ${
                      isCurrentTask ? 'bg-warning-50 dark:bg-warning-100/10' : ''
                    }`}
                  >
                    {/* Status icon */}
                    {getTaskIcon(task, isCurrentTask)}
                    
                    {/* Task content */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-start gap-1.5">
                        <span className="text-xs text-default-400 font-medium flex-shrink-0">
                          {task.id}.
                        </span>
                        <p className={`text-xs ${
                          isCurrentTask ? 'text-default-700 font-medium' : 'text-default-600'
                        } whitespace-pre-wrap break-words`}>
                          {task.description}
                        </p>
                      </div>
                      
                      {/* Additional task details (if current task) */}
                      {isCurrentTask && (
                        <div className="mt-1 space-y-0.5">
                          {task.success_criteria && (
                            <p className="text-xs text-default-400">
                              <span className="font-medium">Success:</span> {task.success_criteria}
                            </p>
                          )}
                          {task.hints && (
                            <p className="text-xs text-default-400">
                              <span className="font-medium">Hint:</span> {task.hints}
                            </p>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
          
          {/* Notes (if any) */}
          {plan.notes && (
            <div className="space-y-1">
              <span className="text-xs text-default-400 font-medium">Notes:</span>
              <p className="text-xs text-default-500 whitespace-pre-wrap break-words">
                {plan.notes}
              </p>
            </div>
          )}
          
          {/* Followup indicator */}
          {plan.requires_followup && (
            <div className="px-2 py-1 bg-warning-50 dark:bg-warning-100/10 rounded-md">
              <p className="text-xs text-warning-600 dark:text-warning-500">
                ⚠️ This plan may require follow-up actions
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

