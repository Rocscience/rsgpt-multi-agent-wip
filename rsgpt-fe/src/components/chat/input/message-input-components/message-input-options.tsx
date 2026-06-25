'use client';

import { useEffect, useRef, useState } from 'react';
import { Button, Dropdown, DropdownItem, DropdownMenu, DropdownTrigger, Switch, Tooltip, Chip } from '@heroui/react';
import { GlobeAltIcon, ComputerDesktopIcon, EllipsisHorizontalIcon, CursorArrowRippleIcon, ChatBubbleLeftIcon, ChevronDownIcon } from '@heroicons/react/24/outline';
import { CheckIcon } from '@heroicons/react/24/solid';
import { useAgentMode } from '@/hooks/useAgentMode';
import { useGetDeviceInfo } from '@/hooks/useGetDeviceInfo';
import { useGetUserSettings } from '@/hooks/useGetUserSettings';
import { useUser } from '@auth0/nextjs-auth0';
import { useDeviceSelection } from '@/hooks/useDeviceSelection';
import { useRSLogConnectionStatus, useRSLogEnable, useRSLogDisconnect, useRSLogRefresh } from '@/hooks/useRSLogConnection';
import { RSLogIcon } from '@/components/icons/rslog-icon';
import { RSLogConnectionModal } from '@/components/rslog/rslog-connection-modal';
import { SourceSelector } from './source-selector';
import { ModelSelector } from './model-selector';
import { MessageInputControls } from './message-input-controls';
import { ContextUsageDisplay } from './context-usage-display';
import { FilePathSelector } from './file-path-selector';

interface MessageInputOptionsProps {
  shouldDisableSubmit: boolean;
  sources: string[];
  onSourcesChange: (sources: string[]) => void;
  isStreaming: boolean;
  hasText: boolean;
  onStop: () => void;
  onFilePathSelect?: (filePath: string) => void;
  filePathCount?: number;
}

export const MessageInputOptions = ({ shouldDisableSubmit, sources, onSourcesChange, isStreaming, hasText, onStop, onFilePathSelect, filePathCount = 0 }: MessageInputOptionsProps) => {
  const { user } = useUser();
  const { data: userSettings } = useGetUserSettings(!!user);
  const { isAgentMode, isWebSearch, setIsWebSearch, setIsAgentMode } = useAgentMode();
  
  // Check if user has opted in to agent mode
  const isAgentModeOptedIn = userSettings?.agent_mode_opt_in ?? false;
  
  // Only fetch device info when agent mode is active (saves unnecessary queries)
  const { data: deviceData } = useGetDeviceInfo(isAgentMode && isAgentModeOptedIn);
  const { selectedDeviceId, setSelectedDeviceId } = useDeviceSelection();
  
  // RSLog state and hooks
  const [isRSLogModalOpen, setIsRSLogModalOpen] = useState(false);
  const { data: rslogStatus, refetch: refetchRSLogStatus } = useRSLogConnectionStatus(isAgentMode);
  const rslogEnableMutation = useRSLogEnable();
  const rslogDisconnectMutation = useRSLogDisconnect();
  const rslogRefreshMutation = useRSLogRefresh();
  
  // Track previous agent mode state to detect changes
  const prevAgentModeRef = useRef<boolean>(isAgentMode);

  // Track which dropdown is currently open (only one at a time)
  const [openDropdown, setOpenDropdown] = useState<'mode' | 'model' | 'source' | 'device' | 'settings' | null>(null);

  // Auto-select first device when agent mode is enabled
  useEffect(() => {
    const wasAgentModeJustEnabled = !prevAgentModeRef.current && isAgentMode;
    
    if (wasAgentModeJustEnabled && deviceData?.devices && deviceData.devices.length > 0) {
      // Only auto-select if no device is currently selected
      if (!selectedDeviceId) {
        const firstDevice = deviceData.devices[0];
        console.log('Agent mode enabled - auto-selecting first device:', firstDevice.device_name);
        setSelectedDeviceId(firstDevice.device_id);
      }
    }
    
    // Update the ref to current state
    prevAgentModeRef.current = isAgentMode;
  }, [isAgentMode, deviceData?.devices, selectedDeviceId, setSelectedDeviceId]);

  // Check and refresh RSLog token when Agent Mode is enabled
  useEffect(() => {
    const wasAgentModeJustEnabled = !prevAgentModeRef.current && isAgentMode;
    
    if (wasAgentModeJustEnabled && rslogStatus?.is_connected && rslogStatus.needs_refresh) {
      console.log('Agent mode enabled - refreshing RSLog token');
      rslogRefreshMutation.mutate(undefined, {
        onError: (error) => {
          console.error('Failed to refresh RSLog token on Agent Mode activation:', error);
        },
        onSuccess: () => {
          console.log('RSLog token refreshed successfully on Agent Mode activation');
        }
      });
    }
  }, [isAgentMode, rslogStatus, rslogRefreshMutation]);

  // Clear device selection when agent mode is disabled
  useEffect(() => {
    if (!isAgentMode && selectedDeviceId) {
      console.log('Agent mode disabled - clearing device selection');
      setSelectedDeviceId(null);
    }
  }, [isAgentMode, selectedDeviceId, setSelectedDeviceId]);

  // RSLog handlers
  const handleRSLogConnect = () => {
    setIsRSLogModalOpen(true);
  };

  const handleRSLogToggle = async (enabled: boolean) => {
    if (enabled) {
      // Enable RSLog - check if we need to refresh token first
      if (rslogState.needsRefresh) {
        try {
          await rslogRefreshMutation.mutateAsync();
          console.log('RSLog token refreshed successfully');
        } catch (error) {
          console.error('Failed to refresh RSLog token:', error);
          // If refresh fails, disconnect
          await rslogDisconnectMutation.mutateAsync();
          return;
        }
      }
      
      // Enable RSLog connection (soft connect)
      try {
        await rslogEnableMutation.mutateAsync();
        console.log('RSLog enabled successfully');
      } catch (error) {
        console.error('Failed to enable RSLog:', error);
      }
    } else {
      // Disable RSLog - set is_connected to false but keep account info
      try {
        await rslogDisconnectMutation.mutateAsync();
        console.log('RSLog disabled successfully');
      } catch (error) {
        console.error('Failed to disable RSLog:', error);
      }
    }
  };

  const handleRSLogModalSuccess = async () => {
    try {
      await refetchRSLogStatus();
    } catch (error) {
      console.error('Failed to refetch RSLog status:', error);
    }
  };

  // Determine RSLog state for UI
  const getRSLogState = () => {
    if (!rslogStatus) return { hasAccount: false, connected: false, enabled: false, needsRefresh: false };
    
    // User has an RSLog account if they have company info (even if disconnected)
    const hasAccount = !!rslogStatus.company;
    
    return {
      hasAccount,
      connected: rslogStatus.is_connected,
      enabled: rslogStatus.is_connected && !rslogStatus.needs_refresh,
      needsRefresh: rslogStatus.needs_refresh,
    };
  };

  const rslogState = getRSLogState();

  // Handle mode selection change
  const handleModeChange = (value: string) => {
    setIsAgentMode(value === 'agent');
  };

  return (
    <div className="flex items-center order-2 justify-between w-full">
      <div className="flex items-center gap-1 justify-start">
        {/* Mode Selector */}
        <Dropdown 
          placement="bottom-start"
          size="sm"
          className="bg-background"
          isOpen={openDropdown === 'mode'}
          onOpenChange={(isOpen) => setOpenDropdown(isOpen ? 'mode' : null)}
        >
          <DropdownTrigger>
            <Button
              variant="flat"
              radius="full"
              size="sm"
              className={`cursor-pointer min-w-0 sm:min-w-[85px] flex-shrink-0 justify-start px-2 sm:px-3 ${isAgentMode ? 'text-blue-500 bg-blue-500/10 data-[hover=true]:bg-blue-500/20' : 'text-default-500 data-[hover=true]:bg-default-200'}`}
              aria-label="Select mode"
              endContent={<ChevronDownIcon className="w-3 h-3 opacity-60 hidden sm:block" />}
            >
              <Tooltip content={isAgentMode ? 'Agent mode' : 'Ask mode'} placement="top" size="sm">
                <div className="flex items-center gap-1.5 text-xs">
                  {isAgentMode ? (
                    <CursorArrowRippleIcon className="w-4 h-4 text-blue-500" />
                  ) : (
                    <ChatBubbleLeftIcon className="w-4 h-4 text-default-500" />
                  )}
                  <span className="hidden sm:inline">{isAgentMode ? 'Agent' : 'Ask'}</span>
                </div>
              </Tooltip>
            </Button>
          </DropdownTrigger>
          <DropdownMenu 
            variant="light"
            onAction={(key) => handleModeChange(key as string)}
          >
            <DropdownItem
              key="ask"
              startContent={<ChatBubbleLeftIcon className="w-4 h-4" />}
              endContent={!isAgentMode ? <CheckIcon className="w-4 h-4" /> : null}
            >
              <Tooltip 
                content="Ask RSInsight about documentation, product features, applications, and examples." 
                placement="right" 
                size="sm"
              >
                <span className="text-xs font-medium">Ask</span>
              </Tooltip>
            </DropdownItem>
            <DropdownItem
              key="agent"
              startContent={<CursorArrowRippleIcon className="w-4 h-4" />}
              endContent={isAgentMode ? <CheckIcon className="w-4 h-4" /> : null}
              isDisabled={!isAgentModeOptedIn}
            >
              <Tooltip 
                content={!isAgentModeOptedIn 
                  ? "Agent Mode requires consent. Enable it in Account Settings > Agent Mode." 
                  : "Ask RSInsight to perform tasks, answer questions, and provide insights on your project."
                } 
                placement="right" 
                size="sm"
              >
                <span className="text-xs font-medium">Agent</span>
              </Tooltip>
            </DropdownItem>
          </DropdownMenu>
        </Dropdown>

        {/* Model Selector */}
        <ModelSelector 
          isOpen={openDropdown === 'model'}
          onOpenChange={(isOpen) => setOpenDropdown(isOpen ? 'model' : null)}
        />
      </div>
        
      <div className="flex items-center gap-1 justify-end">
        {/* Source Selector */}
        <SourceSelector
          selected={sources}
          onChange={shouldDisableSubmit ? undefined : onSourcesChange}
          readOnly={shouldDisableSubmit}
          isOpen={openDropdown === 'source'}
          onOpenChange={(isOpen) => setOpenDropdown(isOpen ? 'source' : null)}
        />

        {/* Agent mode settings - only show when agent mode is enabled */}
        {isAgentMode && (
          <>
            {/* Device dropdown */}
            <Dropdown 
              placement="bottom-start"
              size="sm"
              className="bg-background"
              isOpen={openDropdown === 'device'}
              onOpenChange={(isOpen) => setOpenDropdown(isOpen ? 'device' : null)}
            >
              <DropdownTrigger>
                <Button
                  variant="light"
                  isIconOnly
                  radius="full"
                  size="sm"
                  aria-label="Device selector"
                  className={`${selectedDeviceId ? 'text-blue-500 data-[hover=true]:bg-blue-500/20' : 'text-default-500'}`}
                >
                  <Tooltip 
                    content={`${selectedDeviceId ? `Device: ${deviceData?.devices?.find(d => d.device_id === selectedDeviceId)?.device_name}` : 'Select device'}`}
                    placement="top"
                    size="sm"
                  >
                    <ComputerDesktopIcon className={`w-4 h-4 ${selectedDeviceId ? 'text-blue-500' : 'text-default-500'}`} />
                  </Tooltip>
                </Button>
              </DropdownTrigger>
              <DropdownMenu variant="light" onAction={(key) => {
                console.log('Device selected:', key);
                if (key === selectedDeviceId) {
                  setSelectedDeviceId(null);
                } else {
                  setSelectedDeviceId(key as string);
                }
              }}>
                {deviceData?.devices?.map((device) => (
                  <DropdownItem 
                    key={device.device_id} 
                    startContent={<ComputerDesktopIcon className="w-4 h-4" />}
                    endContent={selectedDeviceId === device.device_id ? <CheckIcon className="w-4 h-4" /> : null}
                  >
                    <span className="text-xs font-medium">{device.device_name}</span>
                  </DropdownItem>
                )) || []}
              </DropdownMenu>
            </Dropdown>

            {/* File Path Selector */}
            <FilePathSelector
              onFileSelect={onFilePathSelect || (() => {})}
              disabled={shouldDisableSubmit}
              filePathCount={filePathCount}
            />
            
            {/* Web search and RSLog settings dropdown */}
            <Dropdown 
              placement="bottom-start"
              size="sm"
              className="bg-background hidden" // hidden for now
              isOpen={openDropdown === 'settings'}
              onOpenChange={(isOpen) => setOpenDropdown(isOpen ? 'settings' : null)}
            >
              <DropdownTrigger>
                <Button
                  variant="light"
                  isIconOnly
                  radius="full"
                  size="sm"
                  aria-label="Additional settings"
                  className={`hidden ${isWebSearch ? 'text-blue-500 data-[hover=true]:bg-blue-500/20' : 'text-default-500'}`} // hidden for now
                >
                  <Tooltip 
                    content="Additional settings"
                    placement="top"
                    size="sm"
                  >
                    <EllipsisHorizontalIcon className={`w-4 h-4 ${isWebSearch ? 'text-blue-500' : 'text-default-500'}`} />
                  </Tooltip>
                </Button>
              </DropdownTrigger>
              <DropdownMenu variant="light">
                <DropdownItem 
                  key="web-search-toggle"
                  textValue="Web Search"
                  closeOnSelect={false}
                >
                  <div className="flex items-center justify-between w-full gap-4">
                    <div className="flex items-center gap-2">
                      <GlobeAltIcon className="w-4 h-4" />
                      <span className="text-xs font-medium">Web Search</span>
                    </div>
                    <Switch
                      size="sm"
                      isSelected={isWebSearch}
                      onValueChange={setIsWebSearch}
                      aria-label="Toggle web search"
                    />
                  </div>
                </DropdownItem>
                <DropdownItem 
                  key="rslog-toggle"
                  textValue="RSLog"
                  closeOnSelect={rslogState.hasAccount ? false : true}
                >
                  <div className="flex items-center justify-between w-full gap-4">
                    <div className="flex items-center gap-2">
                      <RSLogIcon className={`w-4 h-4 ${rslogState.enabled ? 'text-blue-500' : rslogState.needsRefresh ? 'text-warning-500' : 'text-default-500'}`} />
                      <div className="flex flex-col">
                        <span className="text-xs font-medium">RSLog</span>
                        {rslogState.connected && rslogStatus?.company && (
                          <span className="text-xs text-default-400">{rslogStatus.company}</span>
                        )}
                      </div>
                    </div>
                    {rslogState.hasAccount ? (
                      <div className="flex items-center gap-2">
                        {(rslogEnableMutation.isPending || rslogRefreshMutation.isPending || rslogDisconnectMutation.isPending) && (
                          <div className="w-4 h-4">
                            <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-primary"></div>
                          </div>
                        )}
                        <Switch
                          size="sm"
                          isSelected={rslogState.enabled}
                          onValueChange={handleRSLogToggle}
                          aria-label="Toggle RSLog"
                          color={rslogState.needsRefresh ? "warning" : "primary"}
                          isDisabled={rslogEnableMutation.isPending || rslogRefreshMutation.isPending || rslogDisconnectMutation.isPending}
                        />
                      </div>
                    ) : (
                      <Button
                        size="sm"
                        variant="light"
                        color="default"
                        className="text-xs text-secondary-foreground"
                        onPress={handleRSLogConnect}
                        isDisabled={shouldDisableSubmit}
                      >
                        Connect
                      </Button>
                    )}
                  </div>
                </DropdownItem>
              </DropdownMenu>
            </Dropdown>
          </>
        )}
        
        {/* RSLog Connection Modal */}
        <RSLogConnectionModal
          isOpen={isRSLogModalOpen}
          onClose={() => setIsRSLogModalOpen(false)}
          onSuccess={handleRSLogModalSuccess}
        />

        {/* Context Usage Display */}
        <ContextUsageDisplay />

        {/* Send/Stop Button */}
        <MessageInputControls
          isStreaming={isStreaming}
          shouldDisableSubmit={shouldDisableSubmit}
          hasText={hasText}
          onStop={onStop}
        />
      </div>
    </div>
  );
};

MessageInputOptions.displayName = 'MessageInputOptions';

