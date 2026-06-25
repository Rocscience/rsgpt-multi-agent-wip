import { contextBridge, ipcRenderer } from 'electron';

// Expose protected methods that allow the renderer process to use
// limited electron APIs without exposing the entire API surface
contextBridge.exposeInMainWorld('electron', {
  versions: {
    node: process.versions.node,
    chrome: process.versions.chrome,
    electron: process.versions.electron,
    getApp: () => ipcRenderer.invoke('app:get-version')
  },
  auth: {
    getProfile: () => ipcRenderer.invoke('auth:get-profile'),
    login: () => ipcRenderer.invoke('auth:login'),
    logOut: () => ipcRenderer.send('auth:log-out'),
    onSessionExpired: (callback: () => void) => {
      ipcRenderer.on('auth:session-expired', callback);
      return () => ipcRenderer.removeListener('auth:session-expired', callback);
    },
  },
  device: {
    getStatus: () => ipcRenderer.invoke('device:get-status'),
    reconnect: () => ipcRenderer.invoke('device:reconnect'),
    onStatusChanged: (callback: () => void) => {
      ipcRenderer.on('device:status-changed', callback);
      return () => ipcRenderer.removeListener('device:status-changed', callback);
    },
  },
  websocket: {
    getStatus: () => ipcRenderer.invoke('websocket:get-status'),
    reconnect: () => ipcRenderer.invoke('websocket:reconnect'),
    onConnected: (callback: () => void) => {
      ipcRenderer.on('websocket:connected', callback);
      return () => ipcRenderer.removeListener('websocket:connected', callback);
    },
    onDisconnected: (callback: (data: any) => void) => {
      const handler = (_event: Electron.IpcRendererEvent, data: any) => callback(data);
      ipcRenderer.on('websocket:disconnected', handler);
      return () => ipcRenderer.removeListener('websocket:disconnected', handler);
    },
  },
  notification: {
    show: (options: { title: string; body: string; urgency?: 'normal' | 'critical' | 'low' }) =>
      ipcRenderer.invoke('notification:show', options),
    onToast: (callback: (options: { title: string; body: string; urgency?: 'normal' | 'critical' | 'low' }) => void) => {
      const handler = (_event: Electron.IpcRendererEvent, options: { title: string; body: string; urgency?: 'normal' | 'critical' | 'low' }) => callback(options);
      ipcRenderer.on('notification:toast', handler);
      return () => ipcRenderer.removeListener('notification:toast', handler);
    },
  },
  mcp: {
    getStatus: (): Promise<MCPStatus> =>
      ipcRenderer.invoke('mcp:get-status') as Promise<MCPStatus>,
    listTools: () => ipcRenderer.invoke('mcp:list-tools'),
    installTool: (toolName: string, version?: string) => ipcRenderer.invoke('mcp:install-tool', toolName, version),
    uninstallTool: (toolName: string) => ipcRenderer.invoke('mcp:uninstall-tool', toolName),
    toggleTool: (toolName: string, enabled: boolean) => ipcRenderer.invoke('mcp:toggle-tool', toolName, enabled),
    updateTool: (toolName: string, newVersion: string) => ipcRenderer.invoke('mcp:update-tool', toolName, newVersion),
    refreshRegistry: () => ipcRenderer.invoke('mcp:refresh-registry'),
    onStatus: (callback: (status: MCPStatusUpdate) => void) => {
      const handler = (_event: Electron.IpcRendererEvent, status: MCPStatusUpdate) => callback(status);
      ipcRenderer.on('mcp:status', handler);
      return () => ipcRenderer.removeListener('mcp:status', handler);
    },
    onInstallProgress: (callback: (progress: InstallProgress) => void) => {
      const handler = (_event: Electron.IpcRendererEvent, progress: InstallProgress) => callback(progress);
      ipcRenderer.on('mcp:install-progress', handler);
      return () => ipcRenderer.removeListener('mcp:install-progress', handler);
    },
    getVersionWarnings: () => ipcRenderer.invoke('mcp:get-version-warnings'),
    onVersionWarnings: (callback: (warnings: VersionWarning[]) => void) => {
      const handler = (_event: Electron.IpcRendererEvent, warnings: VersionWarning[]) => callback(warnings);
      ipcRenderer.on('mcp:version-warnings', handler);
      return () => ipcRenderer.removeListener('mcp:version-warnings', handler);
    },
  },
  shell: {
    openExternal: (url: string) => ipcRenderer.invoke('shell:open-external', url),
  },
  app: {
    showAbout: (callback: () => void) => {
      ipcRenderer.on('app:show-about', callback);
      return () => ipcRenderer.removeListener('app:show-about', callback);
    }
  },
  autoUpdate: {
    // Check for updates
    checkForUpdates: () => ipcRenderer.invoke('auto-update:check'),
    // Download available update
    downloadUpdate: () => ipcRenderer.invoke('auto-update:download'),
    // Install downloaded update (will quit and restart)
    installUpdate: () => ipcRenderer.invoke('auto-update:install'),
    // Get current update status
    getStatus: () => ipcRenderer.invoke('auto-update:status'),
    // Event listeners
    onChecking: (callback: () => void) => {
      ipcRenderer.on('update-checking', callback);
      return () => ipcRenderer.removeListener('update-checking', callback);
    },
    onUpdateAvailable: (callback: (info: { version: string; releaseDate: string; releaseNotes?: string }) => void) => {
      const handler = (_event: Electron.IpcRendererEvent, info: any) => callback(info);
      ipcRenderer.on('update-available', handler);
      return () => ipcRenderer.removeListener('update-available', handler);
    },
    onUpdateNotAvailable: (callback: (info: { currentVersion: string; latestVersion: string }) => void) => {
      const handler = (_event: Electron.IpcRendererEvent, info: any) => callback(info);
      ipcRenderer.on('update-not-available', handler);
      return () => ipcRenderer.removeListener('update-not-available', handler);
    },
    onDownloadProgress: (callback: (progress: { percent: number; transferred: number; total: number; bytesPerSecond: number }) => void) => {
      const handler = (_event: Electron.IpcRendererEvent, progress: any) => callback(progress);
      ipcRenderer.on('update-download-progress', handler);
      return () => ipcRenderer.removeListener('update-download-progress', handler);
    },
    onUpdateDownloaded: (callback: (info: { version: string }) => void) => {
      const handler = (_event: Electron.IpcRendererEvent, info: any) => callback(info);
      ipcRenderer.on('update-downloaded', handler);
      return () => ipcRenderer.removeListener('update-downloaded', handler);
    },
    onError: (callback: (error: { message: string }) => void) => {
      const handler = (_event: Electron.IpcRendererEvent, error: any) => callback(error);
      ipcRenderer.on('update-error', handler);
      return () => ipcRenderer.removeListener('update-error', handler);
    },
  }
});

