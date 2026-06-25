'use client';

import { forwardRef, useMemo } from 'react';
import { Textarea, Chip, Tooltip } from '@heroui/react';
import { XMarkIcon } from '@heroicons/react/24/outline';

interface ChipTextareaProps {
  value: string;
  onValueChange: (value: string) => void;
  isDisabled?: boolean;
  placeholder?: string;
  onKeyDown?: (e: React.KeyboardEvent<HTMLInputElement>) => void;
  className?: string;
  classNames?: any;
  minRows?: number;
  maxRows?: number;
  variant?: 'flat' | 'bordered' | 'faded' | 'underlined';
  tabIndex?: number;
  'aria-label'?: string;
}

// Regex to find file paths in format @[filepath]
const FILE_PATH_REGEX = /@\[([^\]]+)\]/g;

export const ChipTextarea = forwardRef<HTMLTextAreaElement, ChipTextareaProps>(
  (
    {
      value,
      onValueChange,
      isDisabled,
      placeholder,
      onKeyDown,
      className,
      classNames,
      minRows = 1,
      maxRows = 13,
      variant = 'flat',
      tabIndex = 0,
      'aria-label': ariaLabel,
    },
    ref
  ) => {
    // Extract file paths from the text
    const filePaths = useMemo(() => {
      const paths: Array<{ path: string; filename: string; fullMatch: string }> = [];
      const matches = value.matchAll(FILE_PATH_REGEX);
      
      for (const match of matches) {
        const fullPath = match[1];
        const filename = fullPath.split(/[\\/]/).pop() || fullPath;
        paths.push({
          path: fullPath,
          filename,
          fullMatch: match[0],
        });
      }
      
      return paths;
    }, [value]);

    // Remove a file path from the text
    const handleRemoveFilePath = (fullMatch: string) => {
      const newValue = value.replace(fullMatch, '').trim();
      onValueChange(newValue);
    };

    // Get display text (text without file path delimiters for the textarea)
    const displayText = useMemo(() => {
      return value.replace(FILE_PATH_REGEX, '').trimStart();
    }, [value]);

    return (
      <div className={`flex flex-col gap-2 w-full ${className || ''}`}>
        {/* File path chips */}
        {filePaths.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {filePaths.map((file, index) => (
              <Tooltip key={index} content={file.path} placement="top" size="sm">
                <Chip
                  size="sm"
                  variant="flat"
                  color="default"
                  className="cursor-default text-foreground bg-default-300"
                  endContent={
                    <button
                      type="button"
                      onClick={() => handleRemoveFilePath(file.fullMatch)}
                      className="ml-1 hover:opacity-80"
                      aria-label="Remove file path"
                    >
                      <XMarkIcon className="w-3 h-3" />
                    </button>
                  }
                >
                  {file.filename}
                </Chip>
              </Tooltip>
            ))}
          </div>
        )}

        {/* Textarea */}
        <Textarea
          ref={ref}
          tabIndex={tabIndex}
          aria-label={ariaLabel}
          value={displayText}
          onValueChange={(newValue) => {
            // Preserve file paths when updating text
            const filePathsStr = filePaths.map(f => f.fullMatch).join(' ');
            // Only add space between filepath and text if there's text and it doesn't start with space
            const separator = newValue && !newValue.startsWith(' ') ? ' ' : '';
            const combinedValue = filePathsStr ? `${filePathsStr}${separator}${newValue}` : newValue;
            onValueChange(combinedValue);
          }}
          isDisabled={isDisabled}
          placeholder={placeholder}
          minRows={minRows}
          maxRows={maxRows}
          variant={variant}
          className="w-full"
          classNames={classNames}
          onKeyDown={onKeyDown}
        />
      </div>
    );
  }
);

ChipTextarea.displayName = 'ChipTextarea';

