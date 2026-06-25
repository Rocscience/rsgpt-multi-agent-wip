import { useMemo } from 'react';
import { Chip, Tooltip } from '@heroui/react';
import type { UserMessageDto } from '@/lib/types';

type Props = {
  userMessage: UserMessageDto;
  isTemp?: boolean;
};

// Regex to find file paths in format @[filepath]
const FILE_PATH_REGEX = /@\[([^\]]+)\]/g;

export function UserMessage({ userMessage }: Props) {
  // Parse message text and extract file paths
  const messageContent = useMemo(() => {
    const text = userMessage.message_text;
    const parts: Array<{ type: 'text' | 'filepath'; content: string; filename?: string }> = [];
    let lastIndex = 0;

    // Find all file path matches
    const matches = Array.from(text.matchAll(FILE_PATH_REGEX));

    if (matches.length === 0) {
      // No file paths found, return as plain text
      return [{ type: 'text' as const, content: text }];
    }

    // Split text into parts
    matches.forEach((match) => {
      const matchIndex = match.index!;
      const fullPath = match[1];
      const filename = fullPath.split(/[\\/]/).pop() || fullPath;

      // Add text before the match
      if (matchIndex > lastIndex) {
        parts.push({ type: 'text', content: text.slice(lastIndex, matchIndex) });
      }

      // Add the file path
      parts.push({ type: 'filepath', content: fullPath, filename });

      lastIndex = matchIndex + match[0].length;
    });

    // Add remaining text after last match
    if (lastIndex < text.length) {
      parts.push({ type: 'text', content: text.slice(lastIndex) });
    }

    return parts;
  }, [userMessage.message_text]);

  return (
    <div className="flex justify-end mb-8 sm:mb-12" data-user-message>
      <div className="max-w-[85%] sm:max-w-[75%] lg:max-w-[70%] bg-default/50 text-foreground px-3 sm:px-4 py-2 sm:py-3 rounded-2xl">
        <div className="whitespace-pre-wrap word-break inline-flex flex-wrap gap-1 items-center">
          {messageContent.map((part, index) => {
            if (part.type === 'filepath') {
              return (
                <Tooltip key={index} content={part.content} placement="top" size="sm">
                  <Chip
                    size="sm"
                    variant="flat"
                    color="default"
                    className="cursor-default text-foreground bg-default-300"
                  >
                    {part.filename}
                  </Chip>
                </Tooltip>
              );
            }
            return <span key={index}>{part.content}</span>;
          })}
        </div>
      </div>
    </div>
  );
}
