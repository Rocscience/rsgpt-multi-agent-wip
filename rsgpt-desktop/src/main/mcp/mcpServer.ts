import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { Client } from '@modelcontextprotocol/sdk/client/index.js';
import { StdioClientTransport } from '@modelcontextprotocol/sdk/client/stdio.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
  Tool,
} from '@modelcontextprotocol/sdk/types.js';
import * as fs from 'fs/promises';
import * as fsSync from 'fs';
import * as path from 'path';
import { exec } from 'child_process';
import { promisify } from 'util';

const execAsync = promisify(exec);

// Get user data directory for logs
// Note: This server runs as a standalone Node.js process, so we can't use Electron's app module
let LOG_DIR: string;

try {
  // Try to get Electron app path (only works when running from main process)
  const { app } = require('electron');
  LOG_DIR = path.join(app.getPath('userData'), 'mcp-logs');
} catch (err) {
  // When running as child process, use temp directory or working directory
  const os = require('os');
  LOG_DIR = path.join(os.tmpdir(), 'rsinsight-mcp-logs');
}

// Ensure log directory exists
if (!fsSync.existsSync(LOG_DIR)) {
  try {
    fsSync.mkdirSync(LOG_DIR, { recursive: true });
  } catch (err) {
    console.error(`[Gateway] Failed to create log directory: ${err}`);
    // Fallback to current directory
    LOG_DIR = path.join(process.cwd(), 'mcp-logs');
    fsSync.mkdirSync(LOG_DIR, { recursive: true });
  }
}

interface PythonServerInstance {
  id: string;
  client: Client;
  logFile?: string;
}

interface ServerConfig {
  id: string;
  command: string;
  args: string[];
  enabled?: boolean;
}

interface MCPServersConfig {
  servers: ServerConfig[];
}

/**
 * Server status tracking for individual MCP servers
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
 * Gateway MCP Server - manages both built-in tools and Python sub-servers
 * Provides essential file system tools and routes to Python servers
 */
export class CoreMCPServer {
  private server: Server;
  private pythonServers: Map<string, PythonServerInstance> = new Map();
  private toolToServerMap: Map<string, string> = new Map(); // toolName -> serverId
  private serverStatuses: Map<string, ServerStatus> = new Map(); // serverId -> status
  private logFilePath: string;

  /**
   * Write a log entry to the MCP operations log file
   */
  private logOperation(operation: string, data: any): void {
    const timestamp = new Date().toISOString();
    const logEntry = {
      timestamp,
      operation,
      ...data,
    };
    
    const logLine = JSON.stringify(logEntry, null, 2) + '\n' + '-'.repeat(80) + '\n';
    
    try {
      fsSync.appendFileSync(this.logFilePath, logLine);
    } catch (error) {
      console.error('[Gateway] Failed to write to log file:', error);
    }
  }

  constructor() {
    this.logFilePath = path.join(process.cwd(), 'mcp-operations.log');
    
    this.server = new Server(
      {
        name: 'rsinsight-core',
        version: '0.1.0',
      },
      {
        capabilities: {
          tools: {},
        },
      }
    );

    this.setupToolHandlers();
  }

  private setupToolHandlers(): void {
    // List available tools - aggregate from all sources
    this.server.setRequestHandler(ListToolsRequestSchema, async () => {
      const startTime = Date.now();
      const tools: Tool[] = [];
      const serverTools: Record<string, string[]> = { internal: [] };
      
      // Add built-in tools
      const builtInTools = this.getTools();
      tools.push(...builtInTools);
      serverTools.internal = builtInTools.map(t => t.name);
      
      // Register built-in tools in the map
      builtInTools.forEach(tool => {
        this.toolToServerMap.set(tool.name, 'internal');
      });
      
      // Query tools from each server and build the routing map
      for (const [serverId, instance] of this.pythonServers) {
        try {
          const response = await instance.client.listTools(undefined, { timeout: 1800000 }); // 30 minutes
          tools.push(...response.tools);
          serverTools[serverId] = response.tools.map(t => t.name);
          
          // Register each tool in the routing map
          response.tools.forEach(tool => {
            this.toolToServerMap.set(tool.name, serverId);
          });
        } catch (error) {
          console.error(`[Gateway] Failed to get tools from ${serverId}:`, error);
          serverTools[serverId] = [`ERROR: ${error instanceof Error ? error.message : String(error)}`];
          // Continue with other servers
        }
      }
      
      const duration = Date.now() - startTime;
      
      // Log the operation
      this.logOperation('list_tools', {
        totalTools: tools.length,
        serverTools,
        duration_ms: duration,
        toolNames: tools.map(t => t.name),
      });
      
      return { tools };
    });

    // Handle tool calls - route directly using the tool-to-server map
    this.server.setRequestHandler(CallToolRequestSchema, async (request) => {
      const { name, arguments: args } = request.params;
      const startTime = Date.now();
      let serverId: string | undefined;
      let result: any;

      try {
        // Look up which server handles this tool
        serverId = this.toolToServerMap.get(name);
        
        if (!serverId) {
          throw new Error(`Unknown tool: ${name}`);
        }
        
        // Route to the appropriate server
        if (serverId === 'internal') {
          // Execute built-in tool
          result = await this.executeTool(name, args || {});
        } else {
          // Route to external server
          const server = this.pythonServers.get(serverId);
          if (!server) {
            throw new Error(`Server ${serverId} not available`);
          }
          
          result = await server.client.callTool(
            {
              name,
              arguments: args || {},
            },
            undefined,
            { timeout: 1800000 } // 30 minutes
          );
        }
        
        // Log successful tool call
        this.logOperation('call_tool', {
          toolName: name,
          arguments: args || {},
          serverId,
          duration_ms: Date.now() - startTime,
          result,
          success: true,
        });
        
        return result;
      } catch (error) {
        const errorResult = {
          content: [
            {
              type: 'text',
              text: `Error executing tool: ${error instanceof Error ? error.message : String(error)}`,
            },
          ],
          isError: true,
        };
        
        // Log failed tool call
        this.logOperation('call_tool', {
          toolName: name,
          arguments: args || {},
          serverId: serverId || 'unknown',
          duration_ms: Date.now() - startTime,
          error: error instanceof Error ? error.message : String(error),
          success: false,
        });
        
        return errorResult;
      }
    });
  }

  private getTools(): Tool[] {
    return [
      {
        name: 'get_server_statuses',
        description: 'Get the status of all configured MCP servers (running, failed, disabled)',
        inputSchema: {
          type: 'object',
          properties: {},
          required: [],
        },
      },
    ];
  }

  private async executeTool(
    name: string,
    args: Record<string, unknown>
  ): Promise<{ content: Array<{ type: string; text: string }>; isError?: boolean }> {
    if (name === 'get_server_statuses') {
      const statuses = Array.from(this.serverStatuses.values());
      return {
        content: [
          {
            type: 'text',
            text: JSON.stringify(statuses, null, 2),
          },
        ],
      };
    }
    throw new Error(`Unknown tool: ${name}`);
  }

  /**
   * Get all server statuses (public method for direct access)
   */
  getServerStatuses(): ServerStatus[] {
    return Array.from(this.serverStatuses.values());
  }

  /**
   * Start an MCP server executable as a sub-server
   */
  private async startPythonServer(id: string, command: string, args: string[]): Promise<void> {
    const startTime = Date.now();
    try {
      console.error(`\n╔════════════════════════════════════════════════════════════`);
      console.error(`║ [MCP] Starting server: ${id}`);
      console.error(`║ Command: ${command}`);
      console.error(`║ Args: ${JSON.stringify(args)}`);
      console.error(`╚════════════════════════════════════════════════════════════\n`);

      // Create MCP client to connect to the server
      const client = new Client(
        {
          name: 'rsinsight-gateway-client',
          version: '0.1.0',
        },
        {
          capabilities: {},
        }
      );

      console.error(`[MCP] [${id}] Creating transport...`);
      console.error(`[MCP] [${id}] Executable path: ${command}`);
      console.error(`[MCP] [${id}] File exists: ${fsSync.existsSync(command)}`);

      // Check if file is executable
      try {
        const stats = fsSync.statSync(command);
        console.error(`[MCP] [${id}] File size: ${stats.size} bytes`);
        console.error(`[MCP] [${id}] Is file: ${stats.isFile()}`);
      } catch (err) {
        console.error(`[MCP] [${id}] Error checking file: ${err}`);
      }

      // Create log file for this server
      const logFile = path.join(LOG_DIR, `${id}.log`);
      console.error(`[MCP] [${id}] Log file: ${logFile}`);

      // Clear previous log
      try {
        fsSync.writeFileSync(logFile, `=== ${id} MCP Server Log ===\n`);
        fsSync.appendFileSync(logFile, `Started at: ${new Date().toISOString()}\n`);
        fsSync.appendFileSync(logFile, `Command: ${command}\n`);
        fsSync.appendFileSync(logFile, `Args: ${JSON.stringify(args)}\n`);
        fsSync.appendFileSync(logFile, `${'='.repeat(50)}\n\n`);
      } catch (err) {
        console.error(`[MCP] [${id}] Failed to create log file: ${err}`);
      }

      // Log unified MCP service token being passed to MCP servers
      console.error(`[MCP] [${id}] Checking service token in process.env:`);
      console.error(`[MCP] [${id}]   MCP_SERVICE_TOKEN: ${process.env.MCP_SERVICE_TOKEN ? '✓ present' : '✗ missing'}`);

      // Create transport - StdioClientTransport manages the child process internally
      // Keep ELECTRON_TYPE to ensure the MCP SDK can detect Electron and hide terminal windows
      const rs3Python =
        process.env.RS3_PYTHON ??
        'C:\\Users\\KexuanZhang\\AppData\\Local\\Programs\\Python\\Python313\\python.exe';
      const transport = new StdioClientTransport({
        command: command,
        args: args,
        env: {
          ...process.env,
          PYTHONUNBUFFERED: '1',
          ELECTRON_RUN_AS_NODE: '1',
          // Keep electron type to enable windowsHide in SDK
          ...(process.type && { ELECTRON_TYPE: process.type }),
          ...(id === 'rs3-server' && { RS3_PYTHON: rs3Python })
        }
      });

      console.error(`[MCP] [${id}] Connecting to server...`);

      // Slide2 (and other heavy PyInstaller exes) can take ~90s on cold start.
      const MCP_CONNECT_TIMEOUT_MS = 180_000;
      const connectPromise = client.connect(transport);
      const timeoutPromise = new Promise((_, reject) =>
        setTimeout(
          () => reject(new Error(`Connection timeout after ${MCP_CONNECT_TIMEOUT_MS / 1000} seconds`)),
          MCP_CONNECT_TIMEOUT_MS
        )
      );

      await Promise.race([connectPromise, timeoutPromise]);
      console.error(`[MCP] [${id}] ✓ Connected successfully`);

      // Verify server is responding by querying tools
      console.error(`[MCP] [${id}] Querying available tools...`);
      const response = await client.listTools();
      const duration = Date.now() - startTime;

      console.error(`\n╔════════════════════════════════════════════════════════════`);
      console.error(`║ [MCP] ✓ Server '${id}' READY`);
      console.error(`║ Tools available: ${response.tools.length}`);
      console.error(`║ Startup time: ${duration}ms`);
      console.error(`║ Tool names: ${response.tools.map(t => t.name).join(', ')}`);
      console.error(`╚════════════════════════════════════════════════════════════\n`);

      // Store server instance (tools are queried dynamically on demand)
      // Note: StdioClientTransport manages the process lifecycle internally
      this.pythonServers.set(id, {
        id,
        client,
        logFile: logFile,
      });

      // Record successful status
      this.serverStatuses.set(id, {
        id,
        status: 'running',
        toolCount: response.tools.length,
        toolNames: response.tools.map(t => t.name),
        startupTime: duration,
      });

      console.error(`[MCP] [${id}] ℹ️  Server logs available at: ${logFile}`);

    } catch (error) {
      const duration = Date.now() - startTime;
      const errorMessage = error instanceof Error ? error.message : String(error);
      
      console.error(`\n╔════════════════════════════════════════════════════════════`);
      console.error(`║ [MCP] ✗ Server '${id}' FAILED`);
      console.error(`║ Time elapsed: ${duration}ms`);
      console.error(`║ Error: ${errorMessage}`);
      console.error(`╚════════════════════════════════════════════════════════════\n`);
      if (error instanceof Error && error.stack) {
        console.error(error.stack);
      }

      // Record failed status
      this.serverStatuses.set(id, {
        id,
        status: 'failed',
        error: errorMessage,
        startupTime: duration,
      });

      // Don't throw - continue with other servers
    }
  }

  /**
   * Load and start all configured MCP servers (all as executables)
   */
  private async loadPythonServers(): Promise<void> {
    // Determine base path for user data (where downloaded servers and config are stored)
    // In production, this is AppData; in development, it's the current working directory
    let userDataBasePath: string;
    let isDev = false;

    try {
      // Try to get Electron app info (only works when called from main process)
      const { app } = require('electron');
      isDev = !app.isPackaged;
      // In production, use userData (AppData) for downloaded servers and config
      // In development, use current working directory
      userDataBasePath = isDev ? process.cwd() : app.getPath('userData');
    } catch (err) {
      // Running as child process - determine base path from environment or OS paths
      console.error('[Gateway] Running as standalone process (not in Electron main)');

      const os = require('os');
      // When running as child process in production, we need to find AppData
      // Windows only: C:\Users\<user>\AppData\Roaming\RSInsight Desktop
      const appName = 'RSInsight Desktop';
      const appDataPath = path.join(process.env.APPDATA || path.join(os.homedir(), 'AppData', 'Roaming'), appName);

      // Check possible paths for mcp-servers.json
      const possiblePaths = [
        process.cwd(), // Current working directory (dev mode)
        appDataPath, // User data directory (production)
        path.join(__dirname, '../../..'), // From dist/main/mcp to root
        path.join(__dirname, '../../../..'), // From resources/app.asar/dist/main/mcp
        path.join(process.execPath, '..', '..', 'app.asar.unpacked'), // Legacy packaged app location
      ];

      // Try to find mcp-servers.json
      for (const testPath of possiblePaths) {
        const testConfigPath = path.join(testPath, 'mcp-servers.json');
        console.error(`[Gateway] Checking for config at: ${testConfigPath}`);
        if (fsSync.existsSync(testConfigPath)) {
          userDataBasePath = testPath;
          console.error(`[Gateway] Found config at: ${userDataBasePath}`);
          break;
        }
      }

      if (!userDataBasePath!) {
        console.error('[Gateway] Could not find mcp-servers.json, using current directory');
        userDataBasePath = process.cwd();
      }
    }

    // Read server configuration from JSON file in user data directory
    const configPath = path.join(userDataBasePath, 'mcp-servers.json');

    console.error(`[Gateway] Loading MCP config from: ${configPath}`);
    console.error(`[Gateway] User data base path: ${userDataBasePath}`);
    console.error(`[Gateway] Is packaged: ${!isDev}`);
    console.error(`[Gateway] Server logs directory: ${LOG_DIR}`);

    try {
      const configFile = await fs.readFile(configPath, 'utf-8');
      const config: MCPServersConfig = JSON.parse(configFile);

      // Start all enabled servers from config
      for (const serverConfig of config.servers) {
        // Skip disabled servers (default to enabled if not specified)
        if (serverConfig.enabled === false) {
          console.error(`[Gateway] Skipping disabled server: ${serverConfig.id}`);
          // Record disabled status
          this.serverStatuses.set(serverConfig.id, {
            id: serverConfig.id,
            status: 'disabled',
          });
          continue;
        }

        try {
          // Resolve command path relative to user data base path
          const commandPath = path.join(userDataBasePath, serverConfig.command);
          console.error(`[Gateway] Checking for server at: ${commandPath}`);

          await fs.access(commandPath);
          console.error(`[Gateway] Found server: ${serverConfig.id}`);

          await this.startPythonServer(
            serverConfig.id,
            commandPath,
            serverConfig.args
          );
        } catch (error) {
          console.error(`[Gateway] Failed to start ${serverConfig.id}:`, error);
          // Record not_found status
          this.serverStatuses.set(serverConfig.id, {
            id: serverConfig.id,
            status: 'not_found',
            error: `Executable not found: ${serverConfig.command}`,
          });
          // Server not found, continue with others
        }
      }
    } catch (error) {
      console.error('[Gateway] Failed to load server configuration:', error);
    }
  }

  /**
   * Stop a specific MCP server
   * @param serverId - The ID of the server to stop
   */
  async stopServer(serverId: string): Promise<void> {
    const serverInstance = this.pythonServers.get(serverId);
    if (!serverInstance) {
      console.error(`[Gateway] Server ${serverId} not found or already stopped`);
      return;
    }

    try {
      console.error(`[Gateway] Stopping MCP server: ${serverId}`);

      // Close the client connection (this will terminate the spawned process)
      await serverInstance.client.close();

      // Remove from our tracking
      this.pythonServers.delete(serverId);

      // Remove tools from the routing map
      for (const [toolName, serverIdForTool] of this.toolToServerMap.entries()) {
        if (serverIdForTool === serverId) {
          this.toolToServerMap.delete(toolName);
        }
      }

      console.error(`[Gateway] Server ${serverId} stopped successfully`);
    } catch (error) {
      console.error(`[Gateway] Error stopping server ${serverId}:`, error);
      // Still remove it from our maps even if close failed
      this.pythonServers.delete(serverId);
    }
  }

  /**
   * Restart a specific MCP server with new configuration
   * @param serverId - The ID of the server to restart
   * @param command - The command path to the executable
   * @param args - Arguments to pass to the executable
   */
  async restartServer(serverId: string, command: string, args: string[]): Promise<void> {
    console.error(`[Gateway] Restarting MCP server: ${serverId}`);

    // Stop the server if it's running
    await this.stopServer(serverId);

    // Wait a bit to ensure the process has fully terminated
    await new Promise(resolve => setTimeout(resolve, 500));

    // Start it again with the new configuration
    await this.startPythonServer(serverId, command, args);
  }

  /**
   * Start the gateway MCP server with stdio transport
   */
  async start(): Promise<void> {
    // Accept Desktop connections immediately; load sub-servers in background so slow
    // starters (e.g. Slide2 ~90s cold start) don't block the MCP initialize handshake.
    const transport = new StdioServerTransport();
    await this.server.connect(transport);
    console.error('[Gateway] Core MCP Server started');

    this.loadPythonServers()
      .then(() => {
        const pythonServerCount = this.pythonServers.size;
        console.error(`[Gateway] Loaded ${pythonServerCount} Python MCP server(s)`);

        if (pythonServerCount === 0) {
          console.error('[Gateway] WARNING: No Python servers started successfully');
          console.error('[Gateway] Gateway will still provide built-in tools only');
        }
      })
      .catch((error) => {
        console.error('[Gateway] Failed to load Python servers:', error);
      });
  }
}

// Start server if run directly
if (require.main === module) {
  // Ensure process.type is set for Electron detection in MCP SDK
  // This allows windowsHide to work properly for spawned child processes
  if (!('type' in process)) {
    (process as any).type = 'browser';  // Mimic Electron main process
  }

  console.error('[Gateway] ========== GATEWAY SERVER STARTING ==========');
  console.error(`[Gateway] Node version: ${process.version}`);
  console.error(`[Gateway] Platform: ${process.platform}`);
  console.error(`[Gateway] __dirname: ${__dirname}`);
  console.error(`[Gateway] process.cwd(): ${process.cwd()}`);
  console.error(`[Gateway] process.argv: ${JSON.stringify(process.argv)}`);
  console.error(`[Gateway] Log directory: ${LOG_DIR}`);

  try {
    console.error('[Gateway] Creating CoreMCPServer instance...');
    const server = new CoreMCPServer();

    console.error('[Gateway] Starting server...');
    server.start().catch((error) => {
      console.error('[Gateway] ✗ Failed to start MCP server:', error);
      console.error('[Gateway] Error stack:', error.stack);
      process.exit(1);
    });
  } catch (error) {
    console.error('[Gateway] ✗ Exception during server creation:', error);
    console.error('[Gateway] Error stack:', (error as Error).stack);
    process.exit(1);
  }
}

