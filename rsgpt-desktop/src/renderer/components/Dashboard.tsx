import React, { useState, useEffect } from 'react';
import {
  Card,
  CardBody,
  CardHeader,
  Divider,
  Button
} from '@heroui/react';
import { StoreModal } from './StoreModal';
import { UserInfoCard } from './UserInfo';
import { DeviceStatusCard } from './DeviceStatus';
import { MCPToolsList } from './MCPToolsList';

interface DashboardProps {
  profile: UserProfile;
}

export const Dashboard: React.FC<DashboardProps> = ({ profile }) => {
  const [isStoreModalOpen, setIsStoreModalOpen] = useState(false);
  const [storeInitialTab, setStoreInitialTab] = useState<'available' | 'installed'>('available');
  const [versionWarnings, setVersionWarnings] = useState<VersionWarning[]>([]);
  const [warningsDismissed, setWarningsDismissed] = useState(false);

  useEffect(() => {
    // Listen for version warnings pushed from main process at startup
    const cleanup = window.electron.mcp.onVersionWarnings((warnings) => {
      setVersionWarnings(warnings);
      setWarningsDismissed(false);
    });

    // Also fetch on mount in case the event was sent before this component mounted
    window.electron.mcp.getVersionWarnings().then((result) => {
      if (result.success && result.warnings && result.warnings.length > 0) {
        setVersionWarnings(result.warnings);
      }
    });

    return cleanup;
  }, []);

  return (
    <div className="space-y-6">
      {/* Top Row: Page Title and User Info */}
      <div className="flex flex-row justify-between gap-6 items-center">
        <h1 className="text-3xl font-bold text-foreground w-full">Welcome to RSInsight Desktop</h1>
        <UserInfoCard profile={profile} />
      </div>

      {/* Middle Row: Device Status and Connector Store */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <DeviceStatusCard />
        <Card className="shadow-md">
          <CardHeader className="pb-3">
            <div className="flex flex-col">
              <h3 className="text-xl font-semibold text-foreground">Discover</h3>
            </div>
          </CardHeader>
          <Divider />
          <CardBody>
            <div className="flex flex-row md:flex-col gap-4 justify-between items-center">
              <div>
                <h4 className="text-base font-medium text-foreground mb-1">MCP Store</h4>
                <p className="text-sm text-default-500">
                  Explore available MCP Tools to extend RSInsight's capabilities
                </p>
              </div>
              <Button
                color="default"
                className="w-auto md:w-full"
                variant="flat"
                size="md"
                onClick={() => {
                  setStoreInitialTab('available');
                  setIsStoreModalOpen(true);
                }}
              >
                Browse
              </Button>
            </div>
          </CardBody>
        </Card>
      </div>

      {/* Version Compatibility Warnings Banner */}
      {versionWarnings.length > 0 && !warningsDismissed && (
        <Card className="shadow-md border-2 border-warning">
          <CardBody className="py-3 px-4">
            <div className="flex items-start justify-between">
              <div className="flex items-start gap-3">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="20"
                  height="20"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className="text-warning mt-0.5 flex-shrink-0"
                >
                  <path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/>
                  <path d="M12 9v4"/><path d="M12 17h.01"/>
                </svg>
                <div>
                  <h4 className="text-sm font-semibold text-foreground mb-2">
                    Tool Compatibility Issues
                  </h4>
                  <ul className="text-xs text-default-600 space-y-1 mb-2">
                    {versionWarnings.map((w) => (
                      <li key={w.serverId} className="flex items-center gap-1 flex-wrap">
                        <span>
                          <strong>{w.displayName}</strong>: requires {w.rocscienceApp} v{w.requiredVersion}
                          {w.appExists
                            ? ` (you have v${w.localVersion})`
                            : ' (not installed)'}
                        </span>
                        <button
                          type="button"
                          onClick={() => {
                            const urlMatch = w.errorMessage?.match(/https:\/\/www\.rocscience\.com\S+/);
                            const url = urlMatch ? urlMatch[0] : 'https://www.rocscience.com/support/program-downloads';
                            window.electron.shell.openExternal(url);
                          }}
                          className="inline-flex items-center gap-1 text-xs text-primary hover:underline cursor-pointer bg-transparent border-none p-0"
                        >
                          — Download Update
                          <svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
                            <polyline points="15 3 21 3 21 9"/>
                            <line x1="10" y1="14" x2="21" y2="3"/>
                          </svg>
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
              <Button
                size="sm"
                variant="light"
                isIconOnly
                onPress={() => setWarningsDismissed(true)}
                aria-label="Dismiss warnings"
                className="flex-shrink-0"
              >
                <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="18" y1="6" x2="6" y2="18"/>
                  <line x1="6" y1="6" x2="18" y2="18"/>
                </svg>
              </Button>
            </div>
          </CardBody>
        </Card>
      )}

      {/* Bottom Row: MCP Tools - Full Width */}
      <MCPToolsList onOpenStore={() => {
        setStoreInitialTab('installed');
        setIsStoreModalOpen(true);
      }} />

      {/* MCP Store Modal */}
      <StoreModal
        isOpen={isStoreModalOpen}
        onClose={() => setIsStoreModalOpen(false)}
        initialTab={storeInitialTab}
      />
    </div>
  );
};
