import { app } from 'electron';
import axios from 'axios';
import * as fs from 'fs';
import * as path from 'path';
import * as crypto from 'crypto';
import { EventEmitter } from 'events';
import { apiFetchService, MCPRegistryListResponse, MCPDownloadResponse } from './apiFetchService';
import { getDeviceId } from './deviceService';
import { checkVersionCompatibility } from './versionService';

const MCP_SERVERS_DIR = 'python-servers';
const MCP_CONFIG_FILE = 'mcp-servers.json';

/**
 * Backend model: MCPRegistrySummary from /list endpoint
 */
export interface MCPToolSummary {
  id: string; // UUID
  name: string; // Tool identifier (e.g., "rs2-dynamic")
  display_name: string;
  description?: string;
  category?: string;
  author?: string;
  latest_version: string;
  downloads_count: number;
  is_official: boolean;
  // Rocscience application version compatibility (optional - from backend)
  rocscience_app?: string;           // e.g., "RS2", "RSPile", "Slide2"
  required_app_version?: string;     // e.g., "11.0.2.7"
  rocscience_app_path?: string;      // e.g., "C:\Program Files\Rocscience\RS2\RS2.exe"
}

/**
 * Frontend model: Enriched with local installation status
 */
export interface MCPTool extends MCPToolSummary {
  // Local installation info
  exe_path?: string;
  installed_at?: string;
  enabled?: boolean;
  installed_version?: string;
}

/**
 * Local MCP server configuration (mcp-servers.json)
 */
interface MCPServerConfig {
  id: string; // Tool name (not UUID)
  command: string;
  args: string[];
  enabled?: boolean; // Optional for backwards compatibility
  installed_version?: string; // Version installed locally
  // Version compatibility fields (persisted from install for startup validation)
  rocscience_app?: string;           // e.g., "RS2", "RSPile", "Slide2"
  required_app_version?: string;     // e.g., "11.0.2.7"
  rocscience_app_path?: string;      // e.g., "C:\Program Files\Rocscience\RS2\RS2.exe"
}

interface MCPServersConfig {
  servers: MCPServerConfig[];
}

/**
 * Installation progress event
 */
export interface InstallProgress {
  mcpId: string; // Tool name
  status: 'Downloading' | 'Verifying' | 'Installing' | 'Complete' | 'Error';
  progress: number; // 0-100
  message: string;
  error?: string;
}

/**
 * MCP Service - manages MCP tool registry, installation, and configuration
 */
export class MCPService extends EventEmitter {
  private registry: MCPRegistryListResponse | null = null;
  private installationInProgress: Set<string> = new Set();
  private mcpClientStopCallback: (() => void) | null = null;
  private mcpClientStartCallback: (() => Promise<void>) | null = null;
  private autoRefreshTimer: NodeJS.Timeout | null = null;

  constructor() {
    super();
  }

  /**
   * Set callbacks for stopping and starting the MCP client
   * This is needed to restart the client when updating tools on Windows
   */
  setMCPClientCallbacks(stopCallback: () => void, startCallback: () => Promise<void>): void {
    this.mcpClientStopCallback = stopCallback;
    this.mcpClientStartCallback = startCallback;
  }

  /**
   * Check if running in development mode
   */
  private isDev(): boolean {
    return process.env.NODE_ENV === 'development' || process.env.ELECTRON_IS_DEV === '1' || !app.isPackaged;
  }

  /**
   * Get the user-writable base path for downloaded MCP servers and config
   * In production, this uses AppData which doesn't require admin privileges
   * In development, this uses the current working directory
   */
  private getUserDataBasePath(): string {
    if (this.isDev()) {
      return process.cwd();
    } else {
      // Use AppData for user-writable data (downloaded servers, config)
      // This avoids needing admin privileges to write to Program Files
      return app.getPath('userData');
    }
  }

  /**
   * Get path to MCP servers directory (user-writable location for downloads)
   */
  private getMCPServersPath(): string {
    return path.join(this.getUserDataBasePath(), MCP_SERVERS_DIR);
  }

  /**
   * Get path to MCP configuration file (user-writable location)
   */
  private getMCPConfigPath(): string {
    return path.join(this.getUserDataBasePath(), MCP_CONFIG_FILE);
  }

  /**
   * Ensure MCP servers directory exists
   */
  private ensureMCPDirectory(): void {
    const dir = this.getMCPServersPath();
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
  }

  /**
   * Load MCP configuration from file
   */
  private loadMCPConfig(): MCPServersConfig {
    try {
      const configPath = this.getMCPConfigPath();
      if (fs.existsSync(configPath)) {
        const data = fs.readFileSync(configPath, 'utf-8');
        const config = JSON.parse(data);
        // Ensure backwards compatibility: default enabled to true if not set
        config.servers = config.servers.map((server: MCPServerConfig) => ({
          ...server,
          enabled: server.enabled !== undefined ? server.enabled : true
        }));
        return config;
      }
    } catch (error) {
      console.error('Failed to load MCP config:', error);
    }
    return { servers: [] };
  }

  /**
   * Save MCP configuration to file
   */
  private saveMCPConfig(config: MCPServersConfig): void {
    try {
      const configPath = this.getMCPConfigPath();
      fs.writeFileSync(configPath, JSON.stringify(config, null, 2), 'utf-8');
      console.log('MCP configuration saved');
    } catch (error) {
      console.error('Failed to save MCP config:', error);
      throw error;
    }
  }

  /**
   * Emit installation progress event
   */
  private emitProgress(progress: InstallProgress): void {
    this.emit('install-progress', progress);
  }

  /**
   * Fetch MCP registry from backend
   */
  async fetchRegistry(): Promise<MCPRegistryListResponse> {
    try {
      console.log('Fetching MCP registry from backend...');

      const response = await apiFetchService.fetchMCPRegistry({
        page: 1,
        limit: 100,
        official_only: false
      });

      this.registry = response;
      console.log('MCP registry fetched:', response.mcps.length, 'tools');

      return response;
    } catch (error) {
      console.error('Failed to fetch MCP registry:', error);
      throw new Error(`Failed to fetch MCP registry: ${error instanceof Error ? error.message : String(error)}`);
    }
  }

  /**
   * Force refresh registry from backend (ignores cache)
   */
  async refreshRegistry(): Promise<MCPRegistryListResponse> {
    console.log('Force refreshing MCP registry from backend...');
    this.registry = null; // Clear cache to force fresh fetch
    return this.fetchRegistry();
  }

  /**
   * List all MCP tools with enriched local installation status
   * Returns a dictionary keyed by tool name for easy access
   */
  async listTools(): Promise<Record<string, MCPTool>> {
    if (!this.registry) {
      await this.fetchRegistry();
    }
  
    if (!this.registry) {
      return {};
    }
  
    // Get locally installed tools
    const config = this.loadMCPConfig();
    const installedToolNames = new Set(config.servers.map(s => s.id));
  
    // Enrich tools with local installation status and convert to dictionary
    const toolsDict: Record<string, MCPTool> = {};
  
    for (const toolSummary of this.registry.mcps) {
      const isInstalled = installedToolNames.has(toolSummary.name);

      // Check if executable exists locally and get enabled status + version
      let exePath: string | undefined;
      let enabled: boolean | undefined;
      let installedVersion: string | undefined;
      if (isInstalled) {
        const serverConfig = config.servers.find(s => s.id === toolSummary.name);
        if (serverConfig) {
          const fullPath = path.join(this.getUserDataBasePath(), serverConfig.command);
          if (fs.existsSync(fullPath)) {
            exePath = serverConfig.command;
          }
          // Get enabled status (defaults to true if not set)
          enabled = serverConfig.enabled !== undefined ? serverConfig.enabled : true;
          // Get installed version
          installedVersion = serverConfig.installed_version;
        }
      }

      // Key by tool name for easy access
      toolsDict[toolSummary.name] = {
        ...toolSummary,
        exe_path: exePath,
        enabled: enabled,
        installed_version: installedVersion,
      };
    }
  
    return toolsDict;
  }

  /**
   * Get list of installed MCP server names (for deviceService)
   */
  getInstalledMCPServerIds(): string[] {
    const config = this.loadMCPConfig();
    return config.servers.map(server => server.id);
  }

  /**
   * Check if a tool is currently installed
   */
  isToolInstalled(toolName: string): boolean {
    const config = this.loadMCPConfig();
    return config.servers.some(server => server.id === toolName);
  }

  /**
   * Download and install an MCP tool
   * @param toolName - The tool's name (e.g., "rs2-dynamic"), not UUID
   */
  async installTool(toolName: string, version?: string): Promise<void> {
    // Input validation
    this.validateToolInput(toolName, version);

    // Check if already installing
    if (this.installationInProgress.has(toolName)) {
      throw new Error(`Installation already in progress for ${toolName}`);
    }


    // Get the tool from registry to find its UUID
    const tools = await this.listTools();
    const tool = tools[toolName];
    
    if (!tool) {
      throw new Error(`Tool ${toolName} not found in registry`);
    }

    this.installationInProgress.add(toolName);
    this.ensureMCPDirectory();

    try {
      // Step 0: Check Rocscience application version compatibility (if required)
      if (tool.rocscience_app && tool.required_app_version) {
        this.emitProgress({
          mcpId: toolName,
          status: 'Verifying',
          progress: 2,
          message: `Checking ${tool.rocscience_app} version compatibility...`
        });

        const versionCheck = await checkVersionCompatibility(
          tool.rocscience_app,
          tool.required_app_version,
          tool.rocscience_app_path // Optional custom path from backend
        );

        if (!versionCheck.isCompatible) {
          // Version mismatch or app not found - block installation
          const errorMessage = versionCheck.errorMessage ||
            `Incompatible ${tool.rocscience_app} version`;

          console.error('Version compatibility check failed:', errorMessage);

          this.emitProgress({
            mcpId: toolName,
            status: 'Error',
            progress: 0,
            message: errorMessage,
            error: errorMessage
          });

          throw new Error(errorMessage);
        }

        // Version is compatible - log and continue
        console.log(`Version check passed: ${tool.rocscience_app} ${versionCheck.localVersion} matches required ${tool.required_app_version}`);

        this.emitProgress({
          mcpId: toolName,
          status: 'Verifying',
          progress: 5,
          message: `${tool.rocscience_app} version ${versionCheck.localVersion} verified`
        });
      }

      // Step 1: Get download URL and checksum from backend using UUID
      this.emitProgress({
        mcpId: toolName,
        status: 'Downloading',
        progress: 6,
        message: 'Getting download information...'
      });

      const downloadInfoResponse = await apiFetchService.fetchMCPDownloadInfo(tool.id, version);

      const { download_url, checksum_sha256, filename } = downloadInfoResponse;
      console.log('Download URL obtained:', filename);

      // Step 2: Download the file
      this.emitProgress({
        mcpId: toolName,
        status: 'Downloading',
        progress: 10,
        message: `Downloading ${filename}...`
      });

      const response = await axios.get(download_url, {
        responseType: 'arraybuffer',
        timeout: 300000,
        onDownloadProgress: (progressEvent) => {
          if (progressEvent.total) {
            const percentCompleted = Math.round((progressEvent.loaded * 70) / progressEvent.total) + 10;
            this.emitProgress({
              mcpId: toolName,
              status: 'Downloading',
              progress: percentCompleted,
              message: `Downloading ${filename}... ${percentCompleted}%`
            });
          }
        }
      });

      const buffer = Buffer.from(response.data);
      console.log('File downloaded, size:', buffer.length);

      // Step 3: Verify checksum
      if (checksum_sha256) {
        this.emitProgress({
          mcpId: toolName,
          status: 'Verifying',
          progress: 80,
          message: 'Verifying file integrity...'
        });

        const hash = crypto.createHash('sha256').update(buffer).digest('hex');
        if (hash !== checksum_sha256) {
          throw new Error('Checksum mismatch! File may be corrupted.');
        }

        console.log('Checksum verified successfully');
      }

      // Step 4: Save the file
      this.emitProgress({
        mcpId: toolName,
        status: 'Installing',
        progress: 90,
        message: 'Installing...'
      });

      const targetPath = path.join(this.getMCPServersPath(), filename);
      fs.writeFileSync(targetPath, buffer);
      
      // Make executable (on Unix-like systems)
      if (process.platform !== 'win32') {
        fs.chmodSync(targetPath, 0o755);
      }

      console.log('File saved to:', targetPath);

      // Step 5: Update configuration (use tool name as ID)
      const config = this.loadMCPConfig();

      // Remove existing entry if present
      config.servers = config.servers.filter(s => s.id !== toolName);

      // Add new entry with version and compatibility info
      config.servers.push({
        id: toolName,
        command: path.join(MCP_SERVERS_DIR, filename),
        args: [],
        enabled: true, // Default to enabled
        installed_version: version || tool.latest_version, // Store the installed version
        // Persist version compatibility info for startup validation
        rocscience_app: tool.rocscience_app,
        required_app_version: tool.required_app_version,
        rocscience_app_path: tool.rocscience_app_path
      });

      this.saveMCPConfig(config);

      // Step 6: Log installation to backend
      try {
        const deviceId = getDeviceId();
        if (deviceId) {
          await apiFetchService.logMCPInstall(tool.id, version || tool.latest_version, deviceId, 'install');
          console.log('Installation logged to backend');
        }
      } catch (logError) {
        // Don't fail installation if logging fails
        console.warn('Failed to log installation to backend:', logError);
      }

      // Step 7: Complete
      this.emitProgress({
        mcpId: toolName,
        status: 'Complete',
        progress: 100,
        message: 'Installation complete!'
      });

      console.log('MCP tool installed successfully:', toolName);

    } catch (error) {
      console.error('Failed to install MCP tool:', error);
      
      const errorMessage = error instanceof Error ? error.message : String(error);
      this.emitProgress({
        mcpId: toolName,
        status: 'Error',
        progress: 0,
        message: 'Installation failed',
        error: errorMessage
      });

      throw error;
    } finally {
      this.installationInProgress.delete(toolName);
    }
  }

  private validateToolInput(toolName: string, version?: string): void {

    // Validate tool name
    if (!toolName || typeof toolName !== 'string') {
      throw new Error('Tool name is required and must be a string');
    }

    if (toolName.trim() === '') {
      throw new Error('Tool name cannot be empty');
    }

    // Check for path traversal vulnerability
    const pathTraversalPatterns = [
      '../', '..\\', '..%2f', '..%5c', '%2e%2e%2f', '%2e%2e%5c',
      '....//', '....\\\\', '..%252f', '..%255c'
    ];

    const toolNameLower = toolName.toLowerCase();
    for (const pattern of pathTraversalPatterns) {
      if (toolNameLower.includes(pattern)) {
        throw new Error(`Invalid tool name`);
      }
    }
    // Check for other dangerous characters
    const dangerousChars = ['<', '>', ':', '"', '|', '?', '*', '\0'];
    for (const char of dangerousChars) {
      if (toolName.includes(char)) {
        throw new Error(`Invalid tool name`);
      }
    }

    // Validate version if provided
    if (version !== undefined) {
      if (typeof version !== 'string') {
        throw new Error('Version must be a string');
      }

      if (version.trim() === '') {
        throw new Error('Version cannot be empty');
      }

      // Check for path traversal in version
      const versionLower = version.toLowerCase();
      for (const pattern of pathTraversalPatterns) {
        if (versionLower.includes(pattern)) {
          throw new Error(`Invalid version`);
        }
      }
    }
  }

  /**
   * Toggle an MCP tool's enabled state
   */
  async toggleTool(toolName: string, enabled: boolean): Promise<void> {
    const config = this.loadMCPConfig();
    const serverIndex = config.servers.findIndex(s => s.id === toolName);

    if (serverIndex === -1) {
      throw new Error(`Tool ${toolName} is not installed`);
    }

    // Update enabled state
    config.servers[serverIndex].enabled = enabled;
    this.saveMCPConfig(config);

    console.log(`Tool ${toolName} ${enabled ? 'enabled' : 'disabled'}`);
  }

  /**
   * Update an MCP tool to a new version
   */
  async updateTool(toolName: string, newVersion: string): Promise<void> {
    // Input validation
    this.validateToolInput(toolName, newVersion);

    // Check if already installing/updating
    if (this.installationInProgress.has(toolName)) {
      throw new Error(`Installation/update already in progress for ${toolName}`);
    }

    // Get the tool from registry
    const tools = await this.listTools();
    const tool = tools[toolName];

    if (!tool || !tool.exe_path) {
      throw new Error(`Tool ${toolName} is not installed`);
    }

    this.installationInProgress.add(toolName);
    this.ensureMCPDirectory();

    try {
      // Step 1: Get download URL and checksum for the new version
      this.emitProgress({
        mcpId: toolName,
        status: 'Downloading',
        progress: 0,
        message: `Updating to version ${newVersion}...`
      });

      const downloadInfoResponse = await apiFetchService.fetchMCPDownloadInfo(tool.id, newVersion);
      const { download_url, checksum_sha256, filename } = downloadInfoResponse;
      console.log('Update download URL obtained:', filename);

      // Step 2: Download the new version
      this.emitProgress({
        mcpId: toolName,
        status: 'Downloading',
        progress: 10,
        message: `Downloading ${filename}...`
      });

      const response = await axios.get(download_url, {
        responseType: 'arraybuffer',
        timeout: 300000,
        onDownloadProgress: (progressEvent) => {
          if (progressEvent.total) {
            const percentCompleted = Math.round((progressEvent.loaded * 70) / progressEvent.total) + 10;
            this.emitProgress({
              mcpId: toolName,
              status: 'Downloading',
              progress: percentCompleted,
              message: `Downloading ${filename}... ${percentCompleted}%`
            });
          }
        }
      });

      const buffer = Buffer.from(response.data);
      console.log('New version downloaded, size:', buffer.length);

      // Step 3: Verify checksum
      if (checksum_sha256) {
        this.emitProgress({
          mcpId: toolName,
          status: 'Verifying',
          progress: 80,
          message: 'Verifying file integrity...'
        });

        const hash = crypto.createHash('sha256').update(buffer).digest('hex');
        if (hash !== checksum_sha256) {
          throw new Error('Checksum mismatch! File may be corrupted.');
        }

        console.log('Checksum verified successfully');
      }

      // Step 4: Stop MCP client to release file locks (Windows requirement)
      this.emitProgress({
        mcpId: toolName,
        status: 'Installing',
        progress: 85,
        message: 'Stopping MCP services...'
      });

      if (this.mcpClientStopCallback) {
        this.mcpClientStopCallback();
        // Wait a bit to ensure the process has fully terminated and file locks released
        await new Promise(resolve => setTimeout(resolve, 1000));
        console.log('MCP client stopped before update');
      }

      // Step 5: Delete old executable and save new one
      this.emitProgress({
        mcpId: toolName,
        status: 'Installing',
        progress: 90,
        message: 'Installing update...'
      });

      // Delete old executable with retry logic
      const oldFilename = path.basename(tool.exe_path);
      const oldPath = path.join(this.getMCPServersPath(), oldFilename);

      if (fs.existsSync(oldPath)) {
        const deleted = await this.deleteFileWithRetry(oldPath);

        if (!deleted) {
          // If we still can't delete after retries, rename it as backup
          try {
            const backupPath = `${oldPath}.old`;
            fs.renameSync(oldPath, backupPath);
            console.log('Could not delete after retries, renamed old version to:', backupPath);
          } catch (renameError) {
            console.warn('Could not delete or rename old file, new version will overwrite:', oldPath);
          }
        }
      }

      // Save new executable
      const targetPath = path.join(this.getMCPServersPath(), filename);
      fs.writeFileSync(targetPath, buffer);

      // Make executable (on Unix-like systems)
      if (process.platform !== 'win32') {
        fs.chmodSync(targetPath, 0o755);
      }

      console.log('New version saved to:', targetPath);

      // Step 6: Update configuration with new version
      const config = this.loadMCPConfig();
      const serverIndex = config.servers.findIndex(s => s.id === toolName);

      if (serverIndex !== -1) {
        config.servers[serverIndex] = {
          ...config.servers[serverIndex],
          command: path.join(MCP_SERVERS_DIR, filename),
          installed_version: newVersion
        };
      }

      this.saveMCPConfig(config);

      // Step 7: Log update to backend
      try {
        const deviceId = getDeviceId();
        if (deviceId) {
          await apiFetchService.logMCPInstall(tool.id, newVersion, deviceId, 'update');
          console.log('Update logged to backend');
        }
      } catch (logError) {
        console.warn('Failed to log update to backend:', logError);
      }

      // Step 8: Restart MCP client to load the updated tool
      if (this.mcpClientStartCallback) {
        this.emitProgress({
          mcpId: toolName,
          status: 'Installing',
          progress: 95,
          message: 'Restarting MCP services...'
        });

        await this.mcpClientStartCallback();
        console.log('MCP client restarted with updated tool');
      }

      // Step 9: Complete
      this.emitProgress({
        mcpId: toolName,
        status: 'Complete',
        progress: 100,
        message: `Updated to version ${newVersion}!`
      });

      console.log('MCP tool updated successfully:', toolName, 'to version', newVersion);

    } catch (error) {
      console.error('Failed to update MCP tool:', error);

      const errorMessage = error instanceof Error ? error.message : String(error);
      this.emitProgress({
        mcpId: toolName,
        status: 'Error',
        progress: 0,
        message: 'Update failed',
        error: errorMessage
      });

      throw error;
    } finally {
      this.installationInProgress.delete(toolName);
    }
  }

  /**
   * Attempt to delete a file with retry logic and exponential backoff
   * @param filePath - Path to the file to delete
   * @param maxRetries - Maximum number of retry attempts (default: 5)
   * @returns true if deleted successfully, false otherwise
   */
  private async deleteFileWithRetry(filePath: string, maxRetries: number = 5): Promise<boolean> {
    for (let attempt = 0; attempt < maxRetries; attempt++) {
      try {
        if (!fs.existsSync(filePath)) {
          console.log(`File already deleted: ${filePath}`);
          return true;
        }

        fs.unlinkSync(filePath);
        console.log(`Successfully deleted file on attempt ${attempt + 1}: ${filePath}`);
        return true;
      } catch (error: any) {
        const isLastAttempt = attempt === maxRetries - 1;

        if (isLastAttempt) {
          console.error(`Failed to delete file after ${maxRetries} attempts: ${filePath}`, error);
          return false;
        }

        // Exponential backoff: 1s, 2s, 4s, 8s, 16s
        const delayMs = Math.pow(2, attempt) * 1000;
        console.log(`Failed to delete file (attempt ${attempt + 1}/${maxRetries}), retrying in ${delayMs}ms...`, error.message);
        await new Promise(resolve => setTimeout(resolve, delayMs));
      }
    }

    return false;
  }

  /**
   * Uninstall an MCP tool (remove file and config)
   */
  async uninstallTool(toolName: string): Promise<void> {
    // Guard against concurrent operations
    if (this.installationInProgress.has(toolName)) {
      throw new Error(`Operation already in progress for ${toolName}`);
    }
    this.installationInProgress.add(toolName);

    try {
      const tools = await this.listTools();
      const tool = tools[toolName];

      if (!tool || !tool.exe_path) {
        throw new Error(`Tool ${toolName} is not installed`);
      }

      // Get file path before stopping client
      const filename = path.basename(tool.exe_path);
      const filePath = path.join(this.getMCPServersPath(), filename);

      // Stop MCP client to release file locks (Windows requirement)
      if (this.mcpClientStopCallback) {
        console.log('Stopping MCP client before uninstall...');
        this.mcpClientStopCallback();
        // Initial wait to ensure process termination starts
        await new Promise(resolve => setTimeout(resolve, 1000));
        console.log('MCP client stopped before uninstall');
      }

      // Delete the executable file with retry logic (handles Windows file lock delays)
      const deleted = await this.deleteFileWithRetry(filePath);

      if (!deleted) {
        console.warn(`File could not be deleted, but continuing with uninstall: ${filePath}`);
      }

      // Remove from configuration
      const config = this.loadMCPConfig();
      config.servers = config.servers.filter(s => s.id !== toolName);
      this.saveMCPConfig(config);

      // Log uninstallation to backend
      try {
        const deviceId = getDeviceId();
        if (deviceId) {
          await apiFetchService.logMCPInstall(tool.id, tool.latest_version, deviceId, 'uninstall');
          console.log('Uninstallation logged to backend');
        }
      } catch (logError) {
        // Don't fail uninstallation if logging fails
        console.warn('Failed to log uninstallation to backend:', logError);
      }

      // Restart MCP client after uninstall
      if (this.mcpClientStartCallback) {
        console.log('Restarting MCP client after uninstall...');
        await this.mcpClientStartCallback();
        console.log('MCP client restarted after uninstall');
      }

      console.log('Tool uninstalled:', toolName);
    } finally {
      // Always clean up, even if error occurs
      this.installationInProgress.delete(toolName);
    }
  }

  /**
   * Start automatic registry refresh every hour
   */
  startAutoRefresh(): void {
    // Clear any existing timer
    this.stopAutoRefresh();

    // Refresh every hour (3600000ms)
    this.autoRefreshTimer = setInterval(async () => {
      try {
        console.log('[Auto-refresh] Refreshing MCP registry...');
        await this.refreshRegistry();
        console.log('[Auto-refresh] Registry refreshed successfully');
      } catch (error) {
        console.warn('[Auto-refresh] Failed to refresh registry:', error);
        // Don't throw - just log and continue
      }
    }, 3600000); // 1 hour

    console.log('[Auto-refresh] Started - will refresh registry every hour');
  }

  /**
   * Stop automatic registry refresh
   */
  stopAutoRefresh(): void {
    if (this.autoRefreshTimer) {
      clearInterval(this.autoRefreshTimer);
      this.autoRefreshTimer = null;
      console.log('[Auto-refresh] Stopped');
    }
  }

  /**
   * Result of version compatibility validation for a single server
   */


  /**
   * Validate version compatibility for all installed MCP servers.
   * Called at startup before starting MCP servers.
   *
   * For each server with version requirements:
   * - If compatible: leave enabled
   * - If incompatible: disable the server and return it in the list
   * - If app not found: disable the server and return it in the list
   *
   * @returns Array of incompatible servers with details for notification
   */
  async validateInstalledServersCompatibility(): Promise<Array<{
    serverId: string;
    displayName: string;
    rocscienceApp: string;
    requiredVersion: string;
    localVersion: string;
    appExists: boolean;
    errorMessage: string;
    wasEnabled: boolean;
  }>> {
    // Only run on Windows (version check uses PowerShell)
    if (process.platform !== 'win32') {
      console.log('[Version Check] Skipping - not on Windows');
      return [];
    }

    console.log('[Version Check] Validating installed MCP servers...');

    const config = this.loadMCPConfig();
    const incompatibleServers: Array<{
      serverId: string;
      displayName: string;
      rocscienceApp: string;
      requiredVersion: string;
      localVersion: string;
      appExists: boolean;
      errorMessage: string;
      wasEnabled: boolean;
    }> = [];

    let configChanged = false;

    for (const server of config.servers) {
      // Skip servers without version requirements (legacy installs or no requirements)
      if (!server.rocscience_app || !server.required_app_version) {
        console.log(`[Version Check] ${server.id}: No version requirements, skipping`);
        continue;
      }

      // Check version compatibility
      const versionCheck = await checkVersionCompatibility(
        server.rocscience_app,
        server.required_app_version,
        server.rocscience_app_path
      );

      if (versionCheck.isCompatible) {
        // Compatible - if it was disabled due to previous incompatibility, re-enable it
        if (server.enabled === false) {
          console.log(`[Version Check] ${server.id}: Now compatible (${server.rocscience_app} ${versionCheck.localVersion}), re-enabling`);
          server.enabled = true;
          configChanged = true;
        } else {
          console.log(`[Version Check] ${server.id}: Compatible (${server.rocscience_app} ${versionCheck.localVersion})`);
        }
      } else {
        // Incompatible - disable the server
        const wasEnabled = server.enabled !== false;

        if (wasEnabled) {
          console.log(`[Version Check] ${server.id}: INCOMPATIBLE - ${versionCheck.errorMessage}`);
          server.enabled = false;
          configChanged = true;
        }

        // Get display name from server id (e.g., "rs2-server" -> "RS2 Server")
        const displayName = server.id
          .split('-')
          .map(word => word.charAt(0).toUpperCase() + word.slice(1))
          .join(' ');

        incompatibleServers.push({
          serverId: server.id,
          displayName,
          rocscienceApp: server.rocscience_app,
          requiredVersion: server.required_app_version,
          localVersion: versionCheck.localVersion,
          appExists: versionCheck.appExists,
          errorMessage: versionCheck.errorMessage || 'Version mismatch',
          wasEnabled
        });
      }
    }

    // Save config if any servers were disabled or re-enabled
    if (configChanged) {
      this.saveMCPConfig(config);
      console.log('[Version Check] Config updated with compatibility changes');
    }

    console.log(`[Version Check] Complete: ${incompatibleServers.length} incompatible server(s) found`);
    return incompatibleServers;
  }
}

// Singleton instance
export const mcpService = new MCPService();

