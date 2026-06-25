import React, { useEffect, useState, useCallback } from 'react';
import { 
  Card, 
  CardBody, 
  CardHeader, 
  Divider, 
  Chip,
  Button,
  Spinner
} from '@heroui/react';

interface MCPToolsListProps {
  onOpenStore: () => void;
}

export const MCPToolsList: React.FC<MCPToolsListProps> = ({ onOpenStore }) => {
  const [tools, setTools] = useState<Record<string, MCPTool>>({});
  const [loading, setLoading] = useState(true);
  const [isInitialLoad, setIsInitialLoad] = useState(true);
  const [mcpStatus, setMcpStatus] = useState<MCPStatus>({ ready: false });
  const [isRetrying, setIsRetrying] = useState(false);

  const loadTools = useCallback(async (showLoading = false) => {
    if (showLoading) {
      setLoading(true);
    }
    try {
      const response = await window.electron.mcp.listTools();
      if (response.success && response.tools) {
        setTools(response.tools);
      }
      
      // Also get MCP server status
      const status = await window.electron.mcp.getStatus();
      setMcpStatus(status);
    } catch (err) {
      console.error('Failed to load tools:', err);
    } finally {
      if (showLoading) {
        setLoading(false);
      }
      if (isInitialLoad) {
        setIsInitialLoad(false);
      }
    }
  }, [isInitialLoad]);

  const handleRetry = async () => {
    setIsRetrying(true);
    try {
      // Force reload tools and status
      await loadTools(false);
      
      await window.electron.notification.show({
        title: 'Refreshing Tool Status',
        body: 'Checking tool server status...',
        urgency: 'normal',
      });
    } catch (err) {
      console.error('Failed to retry:', err);
      await window.electron.notification.show({
        title: 'Retry Failed',
        body: 'Failed to refresh tool status',
        urgency: 'critical',
      });
    } finally {
      setIsRetrying(false);
    }
  };

  useEffect(() => {
    // Initial load with loading state
    loadTools(true);

    // Set up listener for tool changes (install/update/uninstall)
    // Silent updates - no loading state
    const cleanupProgress = window.electron.mcp.onInstallProgress(() => {
      loadTools(false);
    });

    // Listen for MCP status updates to refresh tool statuses
    const cleanupStatus = window.electron.mcp.onStatus(async () => {
      const status = await window.electron.mcp.getStatus();
      setMcpStatus(status);
    });

    return () => {
      cleanupProgress();
      cleanupStatus();
    };
  }, [loadTools]);

  // Reload tools periodically to catch toggle and other state changes
  // Silent updates - no loading state
  useEffect(() => {
    if (isInitialLoad) return; // Don't start interval until after initial load

    const interval = setInterval(() => {
      loadTools(false);
    }, 5000); // Refresh every 5 seconds

    return () => clearInterval(interval);
  }, [loadTools, isInitialLoad]);

  // Filter to show only installed AND enabled tools
  const enabledTools = Object.entries(tools).filter(([_, tool]) => tool.exe_path && tool.enabled !== false);

  // Helper to get status for a specific tool
  const getToolStatus = (toolName: string): { status: string; label: string; color: string; error?: string } => {
    // If MCP gateway is not ready yet, all servers are starting
    if (!mcpStatus.ready) {
      return { status: 'starting', label: 'Starting', color: 'warning' };
    }
    
    // If there's an error with the gateway itself, show error state
    if (mcpStatus.error) {
      return { status: 'error', label: 'Error', color: 'danger', error: mcpStatus.error };
    }
    
    // Look up the specific server status for this tool
    const serverStatus = mcpStatus.serverStatuses?.find(s => s.id === toolName);
    
    if (!serverStatus) {
      // No status found - might be a new tool not yet tracked
      return { status: 'unknown', label: 'Unknown', color: 'default' };
    }
    
    switch (serverStatus.status) {
      case 'running':
        return { status: 'ready', label: 'Ready', color: 'success' };
      case 'failed':
        return { status: 'error', label: 'Error', color: 'danger', error: serverStatus.error };
      case 'disabled':
        return { status: 'disabled', label: 'Disabled', color: 'default' };
      case 'not_found':
        return { status: 'error', label: 'Not Found', color: 'danger', error: serverStatus.error };
      default:
        return { status: 'unknown', label: 'Unknown', color: 'default' };
    }
  };

  return (
    <Card className="shadow-md">
      <CardHeader className="pb-3">
        <div className="flex justify-between items-center w-full">
          <h3 className="text-xl font-semibold text-foreground">Tools</h3>
          {enabledTools.length > 0 && (
            <Button
              size="sm"
              color="default"
              variant="flat"
              onClick={onOpenStore}
            >
              Manage
            </Button>
          )}
        </div>
      </CardHeader>
      <Divider />
      <CardBody>
        {loading ? (
          <div className="flex justify-center items-center py-8">
            <Spinner size="md" color="primary" label="Loading tools..." />
          </div>
        ) : enabledTools.length === 0 ? (
          <div className="text-center py-8">
            <p className="text-sm text-default-500 mb-4">
              No enabled MCP Tools. Install and enable tools to get started.
            </p>
            <Button
              color="default"
              variant="flat"
              size="sm"
              onClick={onOpenStore}
            >
              Browse MCP Store
            </Button>
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            {enabledTools.map(([name, tool]) => {
              const toolStatus = getToolStatus(name);
              return (
                <div
                  key={name}
                  className="flex items-center justify-between p-3 border border-default-200 rounded-lg hover:bg-default-50 transition-colors"
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <h4 className="text-sm font-semibold text-foreground">{tool.display_name}</h4>
                    </div>
                    <div className="flex items-center gap-3 text-xs text-default-500">
                      <span>v{tool.installed_version || tool.latest_version}</span>
                      {tool.author && (
                        <>
                          <span>•</span>
                          <span>{tool.author}</span>
                        </>
                      )}
                      {tool.category && (
                        <>
                          <span>•</span>
                          <span>{tool.category}</span>
                        </>
                      )}
                    </div>
                    {toolStatus.error && (
                      toolStatus.error.toLowerCase().includes('version') ||
                      toolStatus.error.toLowerCase().includes('not found at') ||
                      toolStatus.error.toLowerCase().includes('please install') ? (
                        <div className="mt-1 space-y-1">
                          <div className="flex items-start gap-1">
                            <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-warning flex-shrink-0 mt-0.5">
                              <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/>
                              <path d="M12 9v4"/><path d="M12 17h.01"/>
                            </svg>
                            <span className="text-xs text-warning-600">{toolStatus.error}</span>
                          </div>
                          <button
                            type="button"
                            onClick={() => {
                              const urlMatch = toolStatus.error?.match(/https:\/\/www\.rocscience\.com\S+/);
                              const url = urlMatch ? urlMatch[0] : 'https://www.rocscience.com/support/program-downloads';
                              window.electron.shell.openExternal(url);
                            }}
                            className="text-xs text-primary hover:underline ml-4 cursor-pointer bg-transparent border-none p-0"
                          >
                            Download Update
                          </button>
                        </div>
                      ) : (
                        <div className="text-xs text-danger mt-1 truncate" title={toolStatus.error}>
                          {toolStatus.error}
                        </div>
                      )
                    )}
                  </div>
                  <div className="flex items-center gap-2 ml-4">
                    <Chip 
                      color={toolStatus.color as any} 
                      size="sm" 
                      variant="light"
                      className="flex gap-1"
                      endContent={
                        toolStatus.status === 'starting' ? (
                          <Spinner size="sm" color="current" />
                        ) : toolStatus.status === 'ready' ? (
                          <svg
                            xmlns="http://www.w3.org/2000/svg"
                            width="16"
                            height="16"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="2"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          >
                            <polyline points="20 6 9 17 4 12"></polyline>
                          </svg>
                        ) : toolStatus.status === 'error' ? (
                          <svg
                            xmlns="http://www.w3.org/2000/svg"
                            width="16"
                            height="16"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="2"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          >
                            <line x1="18" y1="6" x2="6" y2="18"></line>
                            <line x1="6" y1="6" x2="18" y2="18"></line>
                          </svg>
                        ) : undefined
                      }
                    >
                      {toolStatus.label}
                    </Chip>
                    {(toolStatus.status === 'error') && (
                      <Button
                        size="sm"
                        variant="flat"
                        color="default"
                        isIconOnly
                        onClick={handleRetry}
                        isLoading={isRetrying}
                        isDisabled={isRetrying}
                        aria-label="Retry connection"
                      >
                        {!isRetrying && (
                          <svg
                            xmlns="http://www.w3.org/2000/svg"
                            width="16"
                            height="16"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="2"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          >
                            <path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4.3M22 12.5a10 10 0 0 1-18.8 4.2" />
                          </svg>
                        )}
                      </Button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </CardBody>
    </Card>
  );
};

