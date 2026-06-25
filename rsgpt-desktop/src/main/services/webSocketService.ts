import { EventEmitter } from 'events';
import WebSocket from 'ws';
import { getAccessToken } from './authService';
import { getDeviceId } from './deviceService';
import { MCPClient } from '../mcp/mcpClient';
import { config } from '../config/environment';
import { CLIENT_TYPE_DESKTOP } from '../constants';

const API_AI_BASE_URL = config.API_AI_BASE_URL;
const WS_BASE_URL = API_AI_BASE_URL.replace('http', 'ws');

interface WebSocketMessage {
  type: string;
  id?: string;
  data?: any;
  timestamp?: string;
  device_id?: string;
  message?: string;
  reason?: string;
  tool_name?: string;
  tool_args?: Record<string, unknown>;
  output?: string;
}

export class WebSocketService extends EventEmitter {
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectInterval = 5000; // 5 seconds
  private reconnectTimer: NodeJS.Timeout | null = null;
  private heartbeatTimer: NodeJS.Timeout | null = null;
  private heartbeatInterval = 30000; // 30 seconds
  private isConnecting = false;
  private shouldConnect = false;
  private mcpClient: MCPClient | null = null;

  constructor() {
    super();
  }

  /**
   * Set the MCP client for handling tool operations
   */
  setMCPClient(client: MCPClient): void {
    this.mcpClient = client;
  }

  /**
   * Connect to WebSocket server
   */
  async connect(): Promise<void> {
    if (this.isConnecting || (this.ws && this.ws.readyState === WebSocket.OPEN)) {
      return;
    }

    const accessToken = getAccessToken();
    const deviceId = getDeviceId();

    if (!accessToken) {
      throw new Error('No access token available. User must be authenticated.');
    }

    if (!deviceId) {
      throw new Error('No device ID available. Device must be registered first.');
    }

    this.isConnecting = true;
    this.shouldConnect = true;

    try {
      const wsUrl = `${WS_BASE_URL}/api/v1/ws/device/${deviceId}`;

      // Pass access token and client type headers
      // X-Client-Type identifies this as a Desktop client (vs Backend)
      const headers = {
        'Authorization': `Bearer ${accessToken}`,
        'X-Client-Type': CLIENT_TYPE_DESKTOP
      };

      console.log('Connecting to WebSocket:', wsUrl.replace(/token=[^&]+/, 'token=***'));
      
      this.ws = new WebSocket(wsUrl, { headers });

      this.ws.on('open', () => {
        console.log('WebSocket connected successfully');
        this.isConnecting = false;
        this.reconnectAttempts = 0;
        this.emit('connected');
        this.startHeartbeat();
      });

      this.ws.on('message', (data) => {
        try {
          const message: WebSocketMessage = JSON.parse(data.toString());
          this.handleMessage(message);
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error);
        }
      });

      this.ws.on('close', (code, reason) => {
        console.log('WebSocket disconnected:', code, reason.toString());
        this.isConnecting = false;
        this.stopHeartbeat();
        this.emit('disconnected', { code, reason: reason.toString() });
        
        if (this.shouldConnect) {
          this.scheduleReconnect();
        }
      });

      this.ws.on('error', (error) => {
        console.error('WebSocket error:', error);
        this.isConnecting = false;
        this.emit('error', error);
      });

    } catch (error) {
      console.error('Failed to create WebSocket connection:', error);
      this.isConnecting = false;
      throw error;
    }
  }

  /**
   * Disconnect from WebSocket server
   */
  disconnect(): void {
    this.shouldConnect = false;
    this.stopReconnectTimer();
    this.stopHeartbeat();

    if (this.ws) {
      this.ws.close(1000, 'Client initiated disconnect');
      this.ws = null;
    }

    this.emit('disconnected', { code: 1000, reason: 'Client initiated disconnect' });
  }

  /**
   * Send a message to the server
   */
  send(message: WebSocketMessage): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      console.warn('WebSocket not connected. Cannot send message:', message);
      return;
    }

    try {
      const messageWithTimestamp = {
        ...message,
        timestamp: new Date().toISOString()
      };
      
      this.ws.send(JSON.stringify(messageWithTimestamp));
    } catch (error) {
      console.error('Failed to send WebSocket message:', error);
    }
  }

  /**
   * Check if WebSocket is connected
   */
  isConnected(): boolean {
    return this.ws !== null && this.ws.readyState === WebSocket.OPEN;
  }

  /**
   * Handle incoming messages
   */
  private handleMessage(message: WebSocketMessage): void {
    console.log('Received WebSocket message:', message.type);

    switch (message.type) {
      case 'connection_established':
        console.log('Connection established for device:', message.device_id);
        this.emit('connection_established', message);
        break;

      case 'heartbeat_ack':
        // Heartbeat acknowledged
        break;

      case 'pong':
        console.log('Received pong from server');
        break;

      case 'disconnect':
        console.log('Server requested disconnect:', message.reason);
        this.emit('server_disconnect', message);
        break;

      case 'error':
        console.error('Server error:', message.message);
        this.emit('server_error', message);
        break;

      case 'notification':
        console.log('Received notification:', message.data);
        this.emit('notification', message.data);
        break;

      case 'command':
        console.log('Received command:', message.data);
        this.emit('command', message.data);
        break;

      case 'status_request':
        console.log('Server requested status update');
        this.sendStatusUpdate();
        break;

      case 'list_tools':
        console.log('Server requested tools list');
        this.handleListTools(message);
        break;

      case 'invoke_tool':
        console.log('Server requested tool invocation:', message.tool_name);
        this.handleInvokeTool(message);
        break;

      case 'request_file_path':
        this.emit('request_file_path', message);
        break;

      case 'agent_response':
        console.log('Received agent response');
        this.emit('agent_response', message);
        break;

      default:
        console.log('Unknown message type:', message.type);
        this.emit('message', message);
        break;
    }
  }

  /**
   * Handle list_tools request from server
   */
  private async handleListTools(message: WebSocketMessage): Promise<void> {
    if (!this.mcpClient || !this.mcpClient.isReady()) {
      console.warn('MCP client not ready, cannot list tools');
      this.send({
        type: 'list_tools_response',
        id: message.id,
        data: { tools: [], error: 'MCP client not ready' },
      });
      return;
    }

    try {
      const tools = await this.mcpClient.listTools();
      
      const toolsList = tools.map((tool) => ({
        name: tool.name,
        description: tool.description,
        input_schema: tool.inputSchema,
      }));

      this.send({
        type: 'list_tools_response',
        id: message.id,
        data: { tools: toolsList },
      });
    } catch (error) {
      console.error('Failed to list tools:', error);
      this.send({
        type: 'list_tools_response',
        id: message.id,
        data: {
          tools: [],
          error: error instanceof Error ? error.message : String(error),
        },
      });
    }
  }

  /**
   * Handle invoke_tool request from server
   */
  private async handleInvokeTool(message: WebSocketMessage): Promise<void> {
    if (!this.mcpClient || !this.mcpClient.isReady()) {
      console.warn('MCP client not ready, cannot invoke tool');
      this.send({
        type: 'invoke_tool_response',
        id: message.id,
        data: { error: 'MCP client not ready' },
      });
      return;
    }

    if (!message.tool_name) {
      this.send({
        type: 'invoke_tool_response',
        id: message.id,
        data: { error: 'Tool name not provided' },
      });
      return;
    }

    try {
      const result = await this.mcpClient.callTool(
        message.tool_name,
        message.tool_args || {}
      );

      // Extract text content from result
      const content = result.content.map((item) => item.text);

      this.send({
        type: 'invoke_tool_response',
        id: message.id,
        data: {
          result: {
            content,
            is_error: result.isError || false,
          },
        },
      });
    } catch (error) {
      console.error('Failed to invoke tool:', error);
      this.send({
        type: 'invoke_tool_response',
        id: message.id,
        data: {
          error: error instanceof Error ? error.message : String(error),
        },
      });
    }
  }

  /**
   * Send heartbeat to server
   */
  private sendHeartbeat(): void {
    this.send({
      type: 'heartbeat'
    });
  }

  /**
   * Send ping to server
   */
  ping(): void {
    this.send({
      type: 'ping'
    });
  }

  /**
   * Send status update to server
   */
  private sendStatusUpdate(): void {
    // Get current application status
    const status = {
      timestamp: new Date().toISOString(),
      // Add any relevant status information here
    };

    this.send({
      type: 'status_update',
      data: status
    });
  }

  /**
   * Start heartbeat timer
   */
  private startHeartbeat(): void {
    this.stopHeartbeat();
    
    this.heartbeatTimer = setInterval(() => {
      if (this.isConnected()) {
        this.sendHeartbeat();
      }
    }, this.heartbeatInterval);
  }

  /**
   * Stop heartbeat timer
   */
  private stopHeartbeat(): void {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
  }

  /**
   * Schedule reconnection attempt
   */
  private scheduleReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('Max reconnection attempts reached. Giving up.');
      this.emit('max_reconnect_attempts_reached');
      return;
    }

    this.reconnectAttempts++;
    const delay = this.reconnectInterval * Math.pow(2, Math.min(this.reconnectAttempts - 1, 5)); // Exponential backoff

    console.log(`Scheduling reconnection attempt ${this.reconnectAttempts} in ${delay}ms`);

    this.reconnectTimer = setTimeout(async () => {
      try {
        await this.connect();
      } catch (error) {
        console.error('Reconnection attempt failed:', error);
        this.scheduleReconnect();
      }
    }, delay);
  }

  /**
   * Stop reconnection timer
   */
  private stopReconnectTimer(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }
}

// Global WebSocket service instance
export const webSocketService = new WebSocketService();
