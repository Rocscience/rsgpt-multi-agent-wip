import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';
import { EventEmitter } from 'events';
import path from 'path';
import * as fs from 'fs';
import { app } from 'electron';
import { sessionService } from '../services/sessionService';
import { MCP_SERVICE_NAME } from '../constants';

interface MCPTool {
  name: string;
  description?: string;
  inputSchema: Record<string, unknown>;
}

interface MCPToolResult {
  content: Array<{ type: string; text: string }>;
  isError?: boolean;
}

/**
 * Server status from the Gateway
 */
export interface ServerStatus {
  id: string;
  status: 'running' | 'failed' | 'disabled' | 'not_found';
  error?: string;
  toolCount?: number;
  toolNames?: string[];
  startupTime?: number;
}

/**
 * Client to communicate with the bundled MCP server
 * Uses the MCP SDK client for protocol-compliant communication
 */
export class MCPClient extends EventEmitter {
  private client: Client | null = null;
  private isInitialized = false;
  private logFile: string | null = null;

  constructor() {
    super();
  }

  /**
   * Set the log file path to write diagnostic logs
   */
  setLogFile(logFilePath: string): void {
    this.logFile = logFilePath;
  }

  /**
   * Write to log file (same mechanism as main process)
   */
  private log(message: string): void {
    const timestamp = new Date().toISOString();
    const logMessage = `[${timestamp}] ${message}\n`;

    // Always write to console.error for immediate visibility
    console.error(message);

    // Also write to file if set
    if (this.logFile) {
      try {
        fs.appendFileSync(this.logFile, logMessage);
      } catch (err) {
        console.error('Failed to write to log file:', err);
      }
    }
  }

  /**
   * Start the MCP gateway server process and connect
   */
  async start(): Promise<void> {
    this.log('[MCPClient] ========== START CALLED ==========');
    this.log(`[MCPClient] Node version: ${process.version}`);
    this.log(`[MCPClient] Platform: ${process.platform}`);

    // Connect to the Gateway server (which manages multiple sub-servers)
    // In development: dist/main/mcp/mcpServer.js
    // In production: resources/app.asar.unpacked/dist/main/mcp/mcpServer.js

    let gatewayPath: string;

    // __dirname in compiled code points to app.asar/dist/main/mcp or app.asar.unpacked/dist/main/mcp
    this.log(`[MCPClient] __dirname: ${__dirname}`);
    this.log(`[MCPClient] process.cwd(): ${process.cwd()}`);
    this.log(`[MCPClient] process.resourcesPath: ${process.resourcesPath || 'undefined'}`);

    // Build possible paths - Gateway MUST be in app.asar.unpacked to be executable as child process
    // IMPORTANT: Check unpacked paths FIRST because files in app.asar cannot be executed by Node
    const possiblePaths = [
      // Production unpacked path (MUST CHECK FIRST)
      process.resourcesPath
        ? path.join(process.resourcesPath, 'app.asar.unpacked', 'dist', 'main', 'mcp', 'mcpServer.js')
        : null,
      // Alternative if __dirname is in app.asar, replace with unpacked
      (typeof __dirname !== 'undefined' && __dirname.includes('app.asar'))
        ? path.join(__dirname.replace('app.asar', 'app.asar.unpacked'), 'mcpServer.js')
        : null,
      // Development path (last resort)
      typeof __dirname !== 'undefined'
        ? path.join(__dirname, 'mcpServer.js')
        : null,
    ].filter((p): p is string => p !== null); // Remove null values and type guard

    this.log(`[MCPClient] Searching for Gateway server in ${possiblePaths.length} locations...`);

    let foundPath = '';
    for (const testPath of possiblePaths) {
      this.log(`[MCPClient] Checking: ${testPath}`);
      if (fs.existsSync(testPath)) {
        foundPath = testPath;
        this.log(`[MCPClient] ✓ Found at: ${testPath}`);
        break;
      } else {
        this.log(`[MCPClient] ✗ Not found: ${testPath}`);
      }
    }

    if (!foundPath) {
      const error = `[MCPClient] FATAL: Gateway server not found in any location`;
      this.log(error);
      throw new Error(error);
    }

    gatewayPath = foundPath;
    this.log(`[MCPClient] Using Gateway server: ${gatewayPath}`);

    // Create MCP client with stdio transport
    this.log('[MCPClient] Creating MCP SDK client...');
    this.client = new Client(
      {
        name: 'rsinsight-desktop',
        version: '0.1.0',
      },
      {
        capabilities: {},
      }
    );

    // Connect to the gateway server process via Node
    this.log(`[MCPClient] Spawning Gateway server: node ${gatewayPath}`);

    // Set NODE_PATH to include node_modules from app.asar.unpacked so unpacked scripts can find dependencies
    // node_modules must also be unpacked for child processes to access them
    const nodeModulesPath = process.resourcesPath
      ? path.join(process.resourcesPath, 'app.asar.unpacked', 'node_modules')
      : path.join(__dirname, '..', '..', '..', 'node_modules'); // Fallback for development
    this.log(`[MCPClient] Setting NODE_PATH to: ${nodeModulesPath}`);

    // Use Electron's Node.js runtime instead of system Node (which may not exist)
    // process.execPath points to the Electron executable which can run Node scripts
    const nodeExecutable = process.execPath;
    this.log(`[MCPClient] Using Node executable: ${nodeExecutable}`);

    this.log('[MCPClient] Attempting MCP SDK connection...');

    try {
      // The MCP SDK already sets windowsHide: true when running in Electron
      // It checks if('type' in process) to detect Electron
      // However, ELECTRON_RUN_AS_NODE strips Electron-specific properties from child processes
      // We need to keep 'type' in the env to signal this is still Electron

      // Get unified MCP service token from sessionService (fetched after Auth0 login)
      // This single token is used by all MCP servers (RS2, RSPile, etc.)
      const mcpServiceToken = sessionService.getMCPToken(MCP_SERVICE_NAME) || process.env.MCP_SERVICE_TOKEN;

      this.log(`[MCPClient] MCP Service Token: ${mcpServiceToken ? '✓ available' : '✗ not available (user may not be logged in)'}`);

      // Determine the working directory for the gateway process
      // In production, use AppData where MCPs and config are stored
      // In development, use current working directory
      const isDev = !app.isPackaged;
      const gatewayCwd = isDev ? process.cwd() : app.getPath('userData');
      this.log(`[MCPClient] Gateway working directory: ${gatewayCwd} (isDev: ${isDev})`);

      const transport = new StdioClientTransport({
        command: nodeExecutable,
        args: [gatewayPath],
        cwd: gatewayCwd,  // Ensure gateway process can find mcp-servers.json and python-servers
        env: {
          ...process.env,
          NODE_PATH: nodeModulesPath,
          ELECTRON_RUN_AS_NODE: '1',
          ...(process.type && { ELECTRON_TYPE: process.type }),
          ...(mcpServiceToken && { MCP_SERVICE_TOKEN: mcpServiceToken })
        },
        stderr: 'pipe'  // Capture stderr to debug child process errors
      });

      // Log any stderr output from the gateway process
      if (transport.stderr) {
        transport.stderr.on('data', (data: Buffer) => {
          const stderrText = data.toString();
          this.log(`[MCPClient] [Gateway stderr] ${stderrText}`);
        });
      }

      this.log('[MCPClient] Connecting to Gateway server via transport...');
      // Gateway loads Python servers (Slide2 ~90s cold start) before responding unless
      // servers load in background; allow ample time for sequential startup.
      const MCP_GATEWAY_CONNECT_TIMEOUT_MS = 300_000;
      await this.client.connect(transport, { timeout: MCP_GATEWAY_CONNECT_TIMEOUT_MS });

      this.log('[MCPClient] ✓ Successfully connected to Gateway server');
      this.isInitialized = true;
      this.emit('ready');
    } catch (error) {
      this.log(`[MCPClient] ✗ Connection failed: ${error}`);
      this.log(`[MCPClient] Error details: ${JSON.stringify(error)}`);
      throw error;
    }
  }

  /**
   * List available tools from the MCP server
   */
  async listTools(): Promise<MCPTool[]> {
    if (!this.isInitialized || !this.client) {
      throw new Error('MCP client not initialized');
    }

    const response = await this.client.listTools(undefined, { timeout: 1800000 }); // 30 minutes
    return response.tools;
  }

  /**
   * Call a tool on the MCP server
   */
  async callTool(name: string, args: Record<string, unknown>): Promise<MCPToolResult> {
    if (!this.isInitialized || !this.client) {
      throw new Error('MCP client not initialized');
    }

    const response = await this.client.callTool(
      {
        name,
        arguments: args,
      },
      undefined,
      { timeout: 1800000 } // 30 minutes
    );

    return response as MCPToolResult;
  }

  /**
   * Stop the MCP server process
   */
  stop(): void {
    if (this.client) {
      this.client.close();
      this.client = null;
    }
    
    this.isInitialized = false;
  }

  /**
   * Check if the client is ready
   */
  isReady(): boolean {
    return this.isInitialized && this.client !== null;
  }

  /**
   * Get the status of all configured MCP servers from the Gateway
   */
  async getServerStatuses(): Promise<ServerStatus[]> {
    if (!this.isInitialized || !this.client) {
      throw new Error('MCP client not initialized');
    }

    try {
      const response = await this.client.callTool({
        name: 'get_server_statuses',
        arguments: {},
      });

      // Parse the JSON response from the tool
      const result = response as MCPToolResult;
      if (result.content && result.content.length > 0 && result.content[0].type === 'text') {
        return JSON.parse(result.content[0].text) as ServerStatus[];
      }
      
      return [];
    } catch (error) {
      this.log(`[MCPClient] Failed to get server statuses: ${error}`);
      return [];
    }
  }
}

