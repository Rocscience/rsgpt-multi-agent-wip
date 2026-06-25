// Global type declarations for the renderer process
declare module '*.svg' {
  const content: string;
  export default content;
}

declare module '*.png' {
  const content: string;
  export default content;
}

declare module '*.jpg' {
  const content: string;
  export default content;
}

declare module '*.jpeg' {
  const content: string;
  export default content;
}

interface UserProfile {
  name: string;
  picture: string;
  email?: string;
  [key: string]: any;
}

interface DeviceStatus {
  isRegistered: boolean;
  deviceId: string | null;
  deviceName: string;
  osName: string;
  osVersion: string;
}

interface WebSocketStatus {
  isConnected: boolean;
}

interface ConnectionResponse {
  success: boolean;
  error?: string;
}

interface NotificationOptions {
  title: string;
  body: string;
  urgency?: 'normal' | 'critical' | 'low';
}

interface MCPTool {
  id: string; // UUID
  name: string; // Tool identifier
  display_name: string;
  description?: string;
  category?: string;
  author?: string;
  latest_version: string;
  downloads_count: number;
  is_official: boolean;
  // Local installation info
  exe_path?: string;
  installed_at?: string;
  enabled?: boolean; // Tool enabled state
  installed_version?: string; // Version installed locally
}

interface InstallProgress {
  mcpId: string;
  status: 'downloading' | 'verifying' | 'installing' | 'complete' | 'error';
  progress: number; // 0-100
  message: string;
  error?: string;
}

interface MCPResponse<T = any> {
  success: boolean;
  error?: string;
  tools?: Record<string, MCPTool>;
  details?: T;
}

/**
 * Individual MCP server status
 */
interface MCPServerStatus {
  id: string;
  status: 'running' | 'failed' | 'disabled' | 'not_found';
  error?: string;
  toolCount?: number;
  toolNames?: string[];
  startupTime?: number;
}

interface MCPStatus {
  ready: boolean;
  toolCount?: number;
  tools?: Array<{ name: string; description?: string }>;
  error?: string;
  serverStatuses?: MCPServerStatus[];
}

interface MCPStatusUpdate {
  status: 'starting' | 'ready' | 'error';
  message: string;
}

/**
 * Version compatibility warning for an MCP server
 * Returned by startup validation when a server's required Rocscience app
 * version doesn't match the locally installed version.
 */
interface VersionWarning {
  serverId: string;
  displayName: string;
  rocscienceApp: string;
  requiredVersion: string;
  localVersion: string;
  appExists: boolean;
  errorMessage: string;
  wasEnabled: boolean;
}

interface Window {
  electron: {
    versions: {
      node: string;
      chrome: string;
      electron: string;
      getApp: () => Promise<string>;
    };
    auth: {
      getProfile: () => Promise<UserProfile | null>;
      login: () => Promise<UserProfile | null>;
      logOut: () => void;
      onSessionExpired: (callback: () => void) => () => void;
    };
    device: {
      getStatus: () => Promise<DeviceStatus>;
      reconnect: () => Promise<ConnectionResponse>;
      onStatusChanged: (callback: () => void) => () => void;
    };
    websocket: {
      getStatus: () => Promise<WebSocketStatus>;
      reconnect: () => Promise<ConnectionResponse>;
      onConnected: (callback: () => void) => () => void;
      onDisconnected: (callback: (data: any) => void) => () => void;
    };
    notification: {
      show: (options: NotificationOptions) => Promise<void>;
      onToast: (callback: (options: NotificationOptions) => void) => () => void;
    };
    mcp: {
      getStatus: () => Promise<MCPStatus>;
      listTools: () => Promise<MCPResponse>;
      installTool: (toolName: string, version?: string) => Promise<ConnectionResponse>;
      uninstallTool: (toolName: string) => Promise<ConnectionResponse>;
      toggleTool: (toolName: string, enabled: boolean) => Promise<ConnectionResponse>;
      updateTool: (toolName: string, newVersion: string) => Promise<ConnectionResponse>;
      refreshRegistry: () => Promise<MCPResponse>;
      onStatus: (callback: (status: MCPStatusUpdate) => void) => () => void;
      onInstallProgress: (callback: (progress: InstallProgress) => void) => () => void;
      getVersionWarnings: () => Promise<{ success: boolean; warnings?: VersionWarning[]; error?: string }>;
      onVersionWarnings: (callback: (warnings: VersionWarning[]) => void) => () => void;
    };
    shell: {
      openExternal: (url: string) => Promise<{ success: boolean; error?: string }>;
    };
    app: {
      showAbout: (callback: () => void) => () => void;
    };
    autoUpdate: {
      checkForUpdates: () => Promise<{ success: boolean; updateAvailable?: boolean; updateInfo?: { version: string; releaseDate: string } | null; error?: string }>;
      downloadUpdate: () => Promise<{ success: boolean; error?: string }>;
      installUpdate: () => Promise<{ success: boolean; error?: string }>;
      getStatus: () => Promise<{ currentVersion: string; updateAvailable: boolean; updateDownloaded: boolean; updateInfo: { version: string; releaseDate: string } | null }>;
      onChecking: (callback: () => void) => () => void;
      onUpdateAvailable: (callback: (info: { version: string; releaseDate: string; releaseNotes?: string }) => void) => () => void;
      onUpdateNotAvailable: (callback: (info: { currentVersion: string; latestVersion: string }) => void) => () => void;
      onDownloadProgress: (callback: (progress: { percent: number; transferred: number; total: number; bytesPerSecond: number }) => void) => () => void;
      onUpdateDownloaded: (callback: (info: { version: string }) => void) => () => void;
      onError: (callback: (error: { message: string }) => void) => () => void;
    };
  };
}

