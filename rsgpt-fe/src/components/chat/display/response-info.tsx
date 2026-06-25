'use client';

import { Popover, PopoverTrigger, PopoverContent, Button } from '@heroui/react';
import { EllipsisHorizontalIcon } from '@heroicons/react/24/outline';

type Props = {
  sourcesUsed?: string[];
  responseTimeMs?: number;
  tokenCount?: number;
  displayName?: string; // model name
  isAgentMode?: boolean;
};

export function ResponseInfo({ sourcesUsed, responseTimeMs, tokenCount, displayName, isAgentMode }: Props) {
  const hasSources = sourcesUsed && sourcesUsed.length > 0;
  const hasMetadata = responseTimeMs || tokenCount;

  // Don't render if there's nothing to show
  if (!hasSources && !hasMetadata && !displayName && !isAgentMode) {
    return null;
  }

  return (
    <Popover placement="top-end" size="sm">
      <PopoverTrigger>
        <Button
          size="sm"
          variant="light"
          isIconOnly
          className="min-w-0 w-10 h-10 text-muted-foreground hover:bg-muted"
          aria-label="Response information"
        >
          <EllipsisHorizontalIcon className="w-4 h-4" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="p-4">
        <div className="space-y-3">
          
          {/* Show sources used */}
          {hasSources && (
            <div className="space-y-2">
              <h4 className="text-xs font-medium text-secondary-foreground uppercase tracking-wide">Sources</h4>
              <div className="text-xs text-default-700">
                {sourcesUsed.join(', ')}
              </div>
            </div>
          )}
          
          {/* Show response metadata */}
          {hasMetadata && (
            <div className="space-y-2">
              <h4 className="text-xs font-medium text-secondary-foreground uppercase tracking-wide">Performance</h4>
              <div className="text-xs text-default-700 space-y-1">
                {responseTimeMs && (
                  <div>Response time: {(responseTimeMs / 1000).toFixed(2)} sec</div>
                )}
                {tokenCount && (
                  <div>Tokens: {tokenCount}</div>
                )}
              </div>
            </div>
          )}

          {/* Show model used */}
          {displayName && (
            <div className="space-y-2">
              <h4 className="text-xs font-medium text-secondary-foreground uppercase tracking-wide">Model</h4>
              <div className="text-xs text-default-700">{displayName}</div>
            </div>
          )}

          {/* Show agent mode */}
          {isAgentMode && (
            <div className="space-y-2">
              <h4 className="text-xs font-medium text-secondary-foreground uppercase tracking-wide">Agent Mode</h4>
              <div className="text-xs text-default-700">Enabled</div>
            </div>
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}

