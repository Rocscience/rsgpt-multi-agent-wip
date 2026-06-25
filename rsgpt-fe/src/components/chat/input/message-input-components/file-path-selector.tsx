'use client';

import { useState } from 'react';
import { Button, Tooltip } from '@heroui/react';
import { AtSymbolIcon } from '@heroicons/react/24/outline';
import { useDeviceSelection } from '@/hooks/useDeviceSelection';

interface FilePathSelectorProps {
  onFileSelect: (filePath: string) => void;
  disabled?: boolean;
  filePathCount?: number;
}

const MAX_FILE_PATHS = 5;

export const FilePathSelector = ({ onFileSelect, disabled = false, filePathCount = 0 }: FilePathSelectorProps) => {
  const { selectedDeviceId } = useDeviceSelection();
  const [isLoading, setIsLoading] = useState(false);

  const handleButtonClick = async () => {
    if (!selectedDeviceId) {
      alert('Please select a device first');
      return;
    }

    if (filePathCount >= MAX_FILE_PATHS) {
      alert(`You can only attach up to ${MAX_FILE_PATHS} file paths per message`);
      return;
    }

    setIsLoading(true);

    try {
      // Get browser window position to hint where dialog should appear
      const screenInfo = {
        screenX: window.screenX,
        screenY: window.screenY,
        screenWidth: window.screen.width,
        screenHeight: window.screen.height,
        windowWidth: window.innerWidth,
        windowHeight: window.innerHeight,
      };
      
      const response = await fetch(`/api/v1/device/${selectedDeviceId}/file-path`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({ screenInfo }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        const errorMessage = errorData.error || 'Failed to request file path';
        
        // Check if this is a device not connected error
        if (response.status === 404 && errorMessage.toLowerCase().includes('not connected')) {
          // Dispatch the device-disconnected event to show the alert
          window.dispatchEvent(new Event('device-disconnected'));
          return;
        }
        
        // Check if this is a device timeout error
        if (response.status === 504 || errorMessage.toLowerCase().includes('timed out') || errorMessage.toLowerCase().includes('did not respond')) {
          // Dispatch the device-timeout event to show the alert
          window.dispatchEvent(new Event('device-timeout'));
          return;
        }
        
        throw new Error(errorMessage);
      }

      const data = await response.json();

      if (data.error) {
        alert(`Error: ${data.error}`);
        return;
      }

      if (data.canceled) {
        return;
      }

      if (data.file_path) {
        // Format single file path
        const formattedPath = `@[${data.file_path}]`;
        onFileSelect(formattedPath);
      }
    } catch (error) {
      console.error('Error requesting file path:', error);
      
      const errorMessage = error instanceof Error ? error.message : 'Failed to request file path';
      
      // Check if this is a device not connected error
      if (errorMessage.toLowerCase().includes('not connected')) {
        window.dispatchEvent(new Event('device-disconnected'));
        return;
      }
      
      // Check if this is a device timeout error
      if (errorMessage.toLowerCase().includes('timed out') || errorMessage.toLowerCase().includes('did not respond')) {
        window.dispatchEvent(new Event('device-timeout'));
        return;
      }
      
      alert(errorMessage);
    } finally {
      setIsLoading(false);
    }
  };

  // Determine tooltip content based on state
  const getTooltipContent = () => {
    if (!selectedDeviceId) return "Select a device first";
    if (filePathCount >= MAX_FILE_PATHS) return `Maximum ${MAX_FILE_PATHS} file paths per message`;
    return "Attach file path";
  };

  const isAtLimit = filePathCount >= MAX_FILE_PATHS;

  return (
    <>
      <Tooltip 
        content={getTooltipContent()} 
        placement="top" 
        size="sm"
      >
        <Button
          variant="light"
          isIconOnly
          radius="full"
          size="sm"
          aria-label="Attach file path"
          className="text-default-500 data-[hover=true]:bg-default-200"
          onPress={handleButtonClick}
          isDisabled={disabled || !selectedDeviceId || isLoading || isAtLimit}
          isLoading={isLoading}
        >
          {!isLoading && <AtSymbolIcon className="w-4 h-4" />}
        </Button>
      </Tooltip>
    </>
  );
};

FilePathSelector.displayName = 'FilePathSelector';

