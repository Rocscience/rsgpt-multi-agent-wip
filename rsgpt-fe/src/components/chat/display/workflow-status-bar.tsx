import React from 'react';
import { 
  ChevronRightIcon,
  CheckCircleIcon
} from '@heroicons/react/24/outline';
import type { WorkflowState, WorkflowTaskProgress } from '@/hooks/useChatMessages';

export interface WorkflowStatusBarProps {
  workflowState?: WorkflowState;
  taskProgress?: WorkflowTaskProgress;
}

// Define workflow stages in order
const WORKFLOW_STAGES = [
  { key: 'CLASSIFYING', label: 'Classifying' },
  { key: 'KNOWLEDGE_SEARCH', label: 'Searching' },
  { key: 'PLANNING', label: 'Planning' },
  { key: 'EXECUTING', label: 'Executing' },
  { key: 'EVALUATING', label: 'Evaluating' },
  { key: 'SUMMARIZING', label: 'Summarizing' }
] as const;

export function WorkflowStatusBar({ workflowState, taskProgress }: WorkflowStatusBarProps) {
  if (!workflowState?.status) return null;
  
  // Don't show for terminal states
  if (workflowState.status === 'COMPLETED' || workflowState.status === 'OUT_OF_SCOPE' || workflowState.status === 'FAILED') {
    return null;
  }
  
  const currentStatus = workflowState.status;
  const currentStageIndex = WORKFLOW_STAGES.findIndex(s => s.key === currentStatus);
  
  return (
    <div className="mb-4">
      <div className="flex items-center gap-1.5 px-2 py-1.5 rounded-md bg-default-50 dark:bg-default-100/20 border border-default-200">
        {WORKFLOW_STAGES.map((stage, index) => {
          const isActive = stage.key === currentStatus;
          const isPast = index < currentStageIndex;
          const isFuture = index > currentStageIndex;
          
          return (
            <React.Fragment key={stage.key}>
              {/* Stage label */}
              <div className={`flex items-center gap-1 ${
                isActive ? 'text-primary-600 dark:text-primary-400 font-medium' :
                isPast ? 'text-success-500' :
                'text-default-400'
              }`}>
                {/* Checkmark for completed stages */}
                {isPast && (
                  <CheckCircleIcon className="w-3 h-3 flex-shrink-0" />
                )}
                
                {/* Stage label with progress (for executing stage) */}
                <span className="text-xs whitespace-nowrap">
                  {stage.label}
                  {isActive && stage.key === 'EXECUTING' && taskProgress && (
                    <span className="ml-1 text-default-500">
                      ({taskProgress.currentTaskIndex + 1}/{taskProgress.totalTasks})
                    </span>
                  )}
                  {isActive && stage.key !== 'EXECUTING' && (
                    <span className="ml-1 animate-pulse">...</span>
                  )}
                </span>
              </div>
              
              {/* Arrow separator (not after last stage) */}
              {index < WORKFLOW_STAGES.length - 1 && (
                <ChevronRightIcon className={`w-3 h-3 flex-shrink-0 ${
                  isPast ? 'text-success-500' :
                  isActive ? 'text-primary-500' :
                  'text-default-300'
                }`} />
              )}
            </React.Fragment>
          );
        })}
      </div>
    </div>
  );
}

