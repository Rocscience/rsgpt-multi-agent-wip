import React, { useEffect, useState, useCallback } from 'react';
import {
  Modal,
  ModalContent,
  ModalHeader,
  ModalBody,
  ModalFooter,
  Button,
  Card,
  CardBody,
  CardHeader,
  Divider,
  Chip,
  Progress,
  Spinner,
  Tabs,
  Tab,
  Switch,
} from '@heroui/react';

interface StoreModalProps {
  isOpen: boolean;
  onClose: () => void;
  initialTab?: 'available' | 'installed';
}

interface ToolCardProps {
  tool: MCPTool;
  isInstalling: boolean;
  installProgress?: InstallProgress;
  onInstall: () => void;
  onUninstall: () => void;
  onToggle: (enabled: boolean) => void;
  onUpdate: () => void;
}

interface ToolListItemProps {
  tool: MCPTool;
  onUninstall: () => void;
  onToggle: (enabled: boolean) => void;
  onUpdate: () => void;
  isToggling?: boolean;
  isUpdating?: boolean;
  isUninstalling?: boolean;
  isInstalling?: boolean;
  wasRecentlyUpdated?: boolean;
}

const ToolCard: React.FC<ToolCardProps> = ({
  tool,
  isInstalling,
  installProgress,
  onInstall,
  onUninstall,
  onToggle,
  onUpdate,
}) => {
  const isInstalled = !!tool.exe_path;

  const getStatusChip = () => {
    // Check installation state first, before progress
    if (!isInstalled) {
      // Only show progress if actively installing (not complete/error)
      if (isInstalling && installProgress &&
          installProgress.status.toLowerCase() !== 'complete' &&
          installProgress.status.toLowerCase() !== 'error') {
        return (
          <Chip color="warning" variant="flat" size="sm">
            {installProgress.status}
          </Chip>
        );
      }
      return;
    }
    // Tool is installed - show progress only if actively installing/updating
    if (isInstalling && installProgress &&
        installProgress.status.toLowerCase() !== 'complete' &&
        installProgress.status.toLowerCase() !== 'error') {
      return (
        <Chip color="warning" variant="flat" size="sm">
          {installProgress.status}
        </Chip>
      );
    }
    if (tool.enabled === false) {
      return (
        <Chip color="default" variant="flat" size="sm">
          Disabled
        </Chip>
      );
    }
    return (
      <Chip color="success" variant="flat" size="sm">
        Installed
      </Chip>
    );
  };

  const renderActions = () => {
    if (isInstalling) {
      return null;
    }

    if (!isInstalled) {
      return (
        <Button color="primary" size="sm" onClick={onInstall}>
          Install
        </Button>
      );
    }

    // For installed tools in the card view (Available Connectors tab),
    // don't show action buttons - they're managed in the Installed tab
    return null;
  };

  return (
    <Card className="w-full">
      <CardHeader className="flex justify-between items-start pb-2">
        <div className="flex flex-col flex-1">
          <div className="flex items-center gap-2">
            <h4 className="text-lg font-semibold text-foreground">{tool.display_name}</h4>
            {tool.is_official && (
              <Chip color="primary" size="sm" variant="bordered" className="text-primary">
                Official
              </Chip>
            )}
          </div>
          <p className="text-xs text-default-500">
            v{isInstalled && tool.installed_version ? tool.installed_version : tool.latest_version}
            {tool.author && ` • ${tool.author}`}
            {tool.category && ` • ${tool.category}`}
          </p>
        </div>
        {getStatusChip()}
      </CardHeader>
      <Divider />
      <CardBody className="gap-3">
        {tool.description && (
          <p className="text-sm text-default-600">{tool.description}</p>
        )}
        
        {tool.category && (
          <Chip size="sm" variant="bordered" className="w-fit">
            {tool.category}
          </Chip>
        )}
        
        {isInstalling && installProgress && (
          <div className="space-y-2">
            <Progress
              size="sm"
              value={installProgress.progress}
              color={installProgress.status === 'error' ? 'danger' : 'primary'}
              className="w-full"
            />
            <p className="text-xs text-default-500">{installProgress.message}</p>
            {installProgress.error && (
              installProgress.error.toLowerCase().includes('version') ||
              installProgress.error.toLowerCase().includes('not found at') ? (
                <div className="bg-danger-50 border border-danger-200 rounded-lg p-3 space-y-2">
                  <div className="flex items-center gap-2">
                    <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-danger flex-shrink-0">
                      <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/>
                      <path d="M12 9v4"/><path d="M12 17h.01"/>
                    </svg>
                    <span className="text-xs font-semibold text-danger">Version Incompatibility</span>
                  </div>
                  <p className="text-xs text-danger-700">{installProgress.error}</p>
                  <button
                    type="button"
                    onClick={() => {
                      const urlMatch = installProgress.error?.match(/https:\/\/www\.rocscience\.com\S+/);
                      const url = urlMatch ? urlMatch[0] : 'https://www.rocscience.com/support/program-downloads';
                      window.electron.shell.openExternal(url);
                    }}
                    className="inline-flex items-center gap-1 text-xs text-primary hover:underline cursor-pointer bg-transparent border-none p-0"
                  >
                    Download Update
                    <svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
                      <polyline points="15 3 21 3 21 9"/>
                      <line x1="10" y1="14" x2="21" y2="3"/>
                    </svg>
                  </button>
                </div>
              ) : (
                <p className="text-xs text-danger">{installProgress.error}</p>
              )
            )}
          </div>
        )}

        {!isInstalling && (
          <div className="flex justify-between items-center">
            <div className="text-xs text-default-500" />
            {renderActions()}
          </div>
        )}
      </CardBody>
    </Card>
  );
};

const ToolListItem: React.FC<ToolListItemProps> = ({ 
  tool, 
  onUninstall, 
  onToggle, 
  onUpdate, 
  isToggling = false, 
  isUpdating = false, 
  isUninstalling = false, 
  isInstalling = false,
  wasRecentlyUpdated = false 
}) => {
  const hasUpdate = tool.installed_version &&
                    tool.latest_version &&
                    tool.installed_version !== tool.latest_version;

  // Any operation in progress should disable all actions
  const hasOperationInProgress = isToggling || isUpdating || isUninstalling || isInstalling;

  return (
    <div className="flex flex-col p-4 border border-default-200 rounded-xl hover:bg-default-50 transition-colors">
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <h4 className="text-base font-semibold text-foreground">{tool.display_name}</h4>
            {tool.is_official && (
              <Chip color="primary" size="sm" variant="bordered" className="text-primary">
                Official
              </Chip>
            )}
            {hasUpdate && (
              <Chip color="warning" size="sm" variant="flat">
                Update Available (v{tool.latest_version})
              </Chip>
            )}
          </div>
          <div className="flex items-center gap-3 text-xs text-default-500">
            <span>v{tool.installed_version || tool.latest_version}</span>
            {tool.author && (
              <>
                <span>•</span>
                <span>{tool.author}</span>
              </>
            )}

          </div>
          {tool.description && (
            <p className="text-sm text-default-600 mt-2 line-clamp-1">{tool.description}</p>
          )}
        </div>
        <div className="ml-4 flex-shrink-0 flex gap-2 items-center">
          {wasRecentlyUpdated ? (
            <Chip color="success" size="sm" variant="flat" startContent={
              <svg
                xmlns="http://www.w3.org/2000/svg"
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <polyline points="20 6 9 17 4 12"></polyline>
              </svg>
            }>
              Updated
            </Chip>
          ) : hasUpdate ? (
            <Button 
              color="primary" 
              size="sm" 
              variant="solid" 
              onClick={onUpdate}
              isLoading={isUpdating}
              isDisabled={hasOperationInProgress}
            >
              Update
            </Button>
          ) : null}
          <Button 
            className="bg-default-800 text-default-50" 
            size="sm" 
            variant="solid" 
            onClick={onUninstall}
            isLoading={isUninstalling}
            isDisabled={hasOperationInProgress}
          >
            Uninstall
          </Button>
        </div>
      </div>
      <div className="flex items-center gap-2">
        <span className="text-xs text-default-600">
          {tool.enabled !== false ? 'On' : 'Off'}
        </span>
        <Switch
          size="sm"
          color={tool.enabled !== false ? "success" : "default"}
          isSelected={tool.enabled !== false}
          onValueChange={onToggle}
          aria-label="Enable/Disable tool"
          isDisabled={hasOperationInProgress}
        />
      </div>
    </div>
  );
};

export const StoreModal: React.FC<StoreModalProps> = ({ isOpen, onClose, initialTab = 'available' }) => {
  const [tools, setTools] = useState<Record<string, MCPTool>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [installingTools, setInstallingTools] = useState<Set<string>>(new Set());
  const [installProgress, setInstallProgress] = useState<Record<string, InstallProgress>>({});
  const [activeTab, setActiveTab] = useState<string>(initialTab);
  const [refreshing, setRefreshing] = useState(false);
  const [togglingTools, setTogglingTools] = useState<Set<string>>(new Set());
  const [updatingTools, setUpdatingTools] = useState<Set<string>>(new Set());
  const [uninstallingTools, setUninstallingTools] = useState<Set<string>>(new Set());
  const [recentlyUpdatedTools, setRecentlyUpdatedTools] = useState<Set<string>>(new Set());

  // Reset to initialTab when modal opens
  useEffect(() => {
    if (isOpen) {
      setActiveTab(initialTab);
    }
  }, [isOpen, initialTab]);

  const loadTools = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await window.electron.mcp.listTools();

      if (response.success && response.tools) {
        setTools(response.tools);
      } else {
        setError(response.error || 'Failed to load tools');
      }
    } catch (err) {
      console.error('Failed to load tools:', err);
      setError('Failed to load tools from backend');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isOpen) {
      loadTools();
    }
  }, [isOpen, loadTools]);

  useEffect(() => {
    // Set up progress listener
    const cleanup = window.electron.mcp.onInstallProgress((progress) => {
      console.log('Install progress:', progress);
      setInstallProgress((prev) => ({
        ...prev,
        [progress.mcpId]: progress,
      }));

      // Reload tools immediately when complete
      if (progress.status.toLowerCase() === 'complete') {
        loadTools().then(() => {
          // Check if this was an update (tool was in updatingTools)
          const wasUpdating = updatingTools.has(progress.mcpId);
          
          // After tools are loaded, wait 2 seconds to show "Complete" message, then clear
          setTimeout(() => {
            setInstallingTools((prev) => {
              const newSet = new Set(prev);
              newSet.delete(progress.mcpId);
              return newSet;
            });
            setUpdatingTools((prev) => {
              const newSet = new Set(prev);
              newSet.delete(progress.mcpId);
              return newSet;
            });
            setInstallProgress((prev) => {
              const newProgress = { ...prev };
              delete newProgress[progress.mcpId];
              return newProgress;
            });
            
            // If it was an update, show "Updated" message
            if (wasUpdating) {
              setRecentlyUpdatedTools((prev) => new Set(prev).add(progress.mcpId));
              // Clear the "Updated" message after 3 seconds
              setTimeout(() => {
                setRecentlyUpdatedTools((prev) => {
                  const newSet = new Set(prev);
                  newSet.delete(progress.mcpId);
                  return newSet;
                });
              }, 3000);
            }
          }, 2000);
        });
      } else if (progress.status.toLowerCase() === 'error') {
        // For version errors, keep visible longer so user can read instructions
        const isVersionError = progress.error && (
          progress.error.toLowerCase().includes('version') ||
          progress.error.toLowerCase().includes('not found at')
        );
        const clearDelay = isVersionError ? 15000 : 3000;

        setTimeout(() => {
          setInstallingTools((prev) => {
            const newSet = new Set(prev);
            newSet.delete(progress.mcpId);
            return newSet;
          });
          setUpdatingTools((prev) => {
            const newSet = new Set(prev);
            newSet.delete(progress.mcpId);
            return newSet;
          });
          setInstallProgress((prev) => {
            const newProgress = { ...prev };
            delete newProgress[progress.mcpId];
            return newProgress;
          });
        }, clearDelay);
      }
    });

    return cleanup;
  }, [loadTools]);

  const handleInstall = async (toolName: string) => {
    setInstallingTools((prev) => new Set(prev).add(toolName));
    
    try {
      const response = await window.electron.mcp.installTool(toolName);
      
      if (!response.success) {
        await window.electron.notification.show({
          title: 'Installation Failed',
          body: response.error || 'Failed to install tool',
          urgency: 'critical',
        });
        // Don't clear installingTools here — the progress listener's
        // timeout is the sole cleanup mechanism for error states.
        // Clearing here causes a race condition where the error card
        // disappears before the user can read it.
      }
    } catch (err) {
      console.error('Failed to install tool:', err);
      await window.electron.notification.show({
        title: 'Installation Failed',
        body: 'An error occurred during installation',
        urgency: 'critical',
      });
      // Don't clear installingTools here — let progress listener handle it
    }
  };

  const handleUninstall = async (toolName: string) => {
    if (!confirm(`Are you sure you want to uninstall ${toolName}?`)) {
      return;
    }

    setUninstallingTools((prev) => new Set(prev).add(toolName));
    try {
      const response = await window.electron.mcp.uninstallTool(toolName);

      if (response.success) {
        // Clear installing state and progress for this tool
        setInstallingTools((prev) => {
          const newSet = new Set(prev);
          newSet.delete(toolName);
          return newSet;
        });
        setInstallProgress((prev) => {
          const newProgress = { ...prev };
          delete newProgress[toolName];
          return newProgress;
        });

        await window.electron.notification.show({
          title: 'Tool Uninstalled',
          body: `${toolName} has been uninstalled`,
          urgency: 'normal',
        });
        await loadTools();
      } else {
        await window.electron.notification.show({
          title: 'Failed to Uninstall',
          body: response.error || 'Failed to uninstall tool',
          urgency: 'critical',
        });
      }
    } catch (err) {
      console.error('Failed to uninstall tool:', err);
    } finally {
      setUninstallingTools((prev) => {
        const newSet = new Set(prev);
        newSet.delete(toolName);
        return newSet;
      });
    }
  };

  const handleToggle = async (toolName: string, enabled: boolean) => {
    setTogglingTools((prev) => new Set(prev).add(toolName));
    try {
      const response = await window.electron.mcp.toggleTool(toolName, enabled);

      if (response.success) {
        await window.electron.notification.show({
          title: 'Tool Updated',
          body: `${toolName} has been ${enabled ? 'enabled' : 'disabled'}`,
          urgency: 'normal',
        });
        await loadTools();
      } else {
        await window.electron.notification.show({
          title: 'Failed to Update',
          body: response.error || 'Failed to toggle tool',
          urgency: 'critical',
        });
      }
    } catch (err) {
      console.error('Failed to toggle tool:', err);
      await window.electron.notification.show({
        title: 'Failed to Update',
        body: 'An error occurred while toggling tool',
        urgency: 'critical',
      });
    } finally {
      setTogglingTools((prev) => {
        const newSet = new Set(prev);
        newSet.delete(toolName);
        return newSet;
      });
    }
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    try {
      const response = await window.electron.mcp.refreshRegistry();

      if (response.success && response.tools) {
        setTools(response.tools);
        await window.electron.notification.show({
          title: 'Registry Refreshed',
          body: 'Tool registry has been updated',
          urgency: 'normal',
        });
      } else {
        throw new Error(response.error || 'Failed to refresh registry');
      }
    } catch (err) {
      console.error('Failed to refresh registry:', err);
      await window.electron.notification.show({
        title: 'Refresh Failed',
        body: 'Failed to refresh tool registry',
        urgency: 'critical',
      });
    } finally {
      setRefreshing(false);
    }
  };

  const handleUpdate = async (toolName: string, newVersion: string) => {
    setUpdatingTools((prev) => new Set(prev).add(toolName));
    setInstallingTools((prev) => new Set(prev).add(toolName));

    try {
      const response = await window.electron.mcp.updateTool(toolName, newVersion);

      if (!response.success) {
        await window.electron.notification.show({
          title: 'Update Failed',
          body: response.error || 'Failed to update tool',
          urgency: 'critical',
        });
        // Don't clear installingTools/updatingTools here — the progress
        // listener's timeout is the sole cleanup mechanism for error states.
      }
    } catch (err) {
      console.error('Failed to update tool:', err);
      await window.electron.notification.show({
        title: 'Update Failed',
        body: 'An error occurred during update',
        urgency: 'critical',
      });
      // Don't clear here — let progress listener handle it
    }
  };

  // Filter tools based on active tab
  const filteredTools = React.useMemo(() => {
    const toolsArray = Object.entries(tools);
    
    if (activeTab === 'installed') {
      // Show only installed tools (those with exe_path)
      return toolsArray.filter(([_, tool]) => tool.exe_path);
    }
    
    // Show all tools for "available" tab
    return toolsArray;
  }, [tools, activeTab]);

  const installedCount = Object.values(tools).filter(tool => tool.exe_path).length;

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      size="4xl"
      scrollBehavior="inside"
      backdrop="blur"
    >
      <ModalContent>
        <ModalHeader>
          <div className="flex flex-col gap-1">
            <h2 className="text-2xl font-bold">MCP Store</h2>
            <p className="text-sm text-default-500 font-normal">
              Install and manage MCP Tools to extend RSInsight's capabilities
            </p>
          </div>
        </ModalHeader>
        <Divider />
        <ModalBody className="py-6">
          {loading ? (
            <div className="flex justify-center items-center py-12">
              <Spinner size="lg" color="primary" label="Loading tools..." />
            </div>
          ) : error ? (
            <div className="flex flex-col items-center justify-center py-12 gap-4">
              <p className="text-danger text-center">{error}</p>
              <Button color="primary" onClick={loadTools}>
                Retry
              </Button>
            </div>
          ) : (
            <>
              <Tabs 
                selectedKey={activeTab} 
                onSelectionChange={(key) => setActiveTab(key as string)}
                color="default"
                variant="bordered"
                size="sm"
                classNames={{
                  tabList: "gap-6",
                  cursor: "w-full",
                  tabContent: " rounded-lg px-2 group-data-[selected=true]:bg-default-100",
                }}
              >
                <Tab 
                  key="available" 
                  title={
                    <div className="flex items-center gap-2">
                      <span>Available Tools</span>
                      <Chip size="sm" color="primary" variant="flat" className="text-primary">{Object.keys(tools).length}</Chip>
                    </div>
                  }
                />
                <Tab 
                  key="installed" 
                  title={
                    <div className="flex items-center gap-2">
                      <span>Installed Tools</span>
                      <Chip size="sm" variant="flat" color={installedCount > 0 ? "success" : "default"}>
                        {installedCount}
                      </Chip>
                    </div>
                  }
                />
              </Tabs>

              <div className="mt-4">
                {filteredTools.length === 0 ? (
                  <div className="flex items-center justify-center py-12">
                    <p className="text-default-500">
                      {activeTab === 'installed' 
                        ? "You haven't installed any MCP Tools yet." 
                        : 'No tools available'}
                    </p>
                  </div>
                ) : activeTab === 'installed' ? (
                  <div className="flex flex-col gap-3">
                    {filteredTools.map(([name, tool]) => (
                      <ToolListItem
                        key={name}
                        tool={tool}
                        onUninstall={() => handleUninstall(name)}
                        onToggle={(enabled) => handleToggle(name, enabled)}
                        onUpdate={() => handleUpdate(name, tool.latest_version)}
                        isToggling={togglingTools.has(name)}
                        isUpdating={updatingTools.has(name)}
                        isUninstalling={uninstallingTools.has(name)}
                        isInstalling={installingTools.has(name)}
                        wasRecentlyUpdated={recentlyUpdatedTools.has(name)}
                      />
                    ))}
                  </div>
                ) : (
                  <div className="flex flex-col gap-4">
                    {filteredTools.map(([name, tool]) => (
                      <ToolCard
                        key={name}
                        tool={tool}
                        isInstalling={installingTools.has(name)}
                        installProgress={installProgress[name]}
                        onInstall={() => handleInstall(name)}
                        onUninstall={() => handleUninstall(name)}
                        onToggle={(enabled) => handleToggle(name, enabled)}
                        onUpdate={() => handleUpdate(name, tool.latest_version)}
                      />
                    ))}
                  </div>
                )}
              </div>
            </>
          )}
        </ModalBody>
        <Divider />
        <ModalFooter className="flex justify-between">
          <Button
            size="sm"
            variant="flat"
            color="default"
            onClick={handleRefresh}
            isLoading={refreshing}
            disabled={refreshing}
            aria-label="Refresh registry"
            startContent={!refreshing && (
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
          >
            Refresh
          </Button>
          <Button size="sm" color="default" variant="flat" onPress={onClose}>
            Close
          </Button>
        </ModalFooter>
      </ModalContent>
    </Modal>
  );
};
