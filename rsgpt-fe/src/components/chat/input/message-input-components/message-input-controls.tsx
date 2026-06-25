'use client';

import { Button, Tooltip } from '@heroui/react';
import { ChevronUpIcon } from '@heroicons/react/24/outline';
import { StopIcon } from '@heroicons/react/24/solid';

interface MessageInputControlsProps {
  isStreaming: boolean;
  shouldDisableSubmit: boolean;
  hasText: boolean;
  onStop: () => void;
}

/**
 * Send/Stop button controls for MessageInput
 */
export const MessageInputControls = ({
  isStreaming,
  shouldDisableSubmit,
  hasText,
  onStop,
}: MessageInputControlsProps) => {
  return (
    <div className="order-3 flex justify-end">
      {isStreaming ? (
        <Tooltip content="Stop generating" placement="top">
          <Button
            type="button"
            isIconOnly
            radius="full"
            size="sm"
            className="bg-default-400 text-primary-foreground hover:opacity-90 shrink-0 min-w-[40px] min-h-[40px]"
            onClick={onStop}
            aria-label="Stop"
          >
            <StopIcon className="w-4 h-4" />
          </Button>
        </Tooltip>
      ) : (
        <Tooltip content="Send message" placement="top">
          <Button
            type="submit"
            isIconOnly
            radius="full"
            size="sm"
            className="bg-primary text-primary-foreground hover:opacity-90 shrink-0 min-w-[40px] min-h-[40px]"
            isDisabled={shouldDisableSubmit || !hasText}
            aria-label="Send"
          >
            <ChevronUpIcon className="w-4 h-4" />
          </Button>
        </Tooltip>
      )}
    </div>
  );
};

MessageInputControls.displayName = 'MessageInputControls';

