import { app, BrowserWindow } from 'electron';
import axios from 'axios';
import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';
import * as crypto from 'crypto';
import { getAccessToken } from './authService';
import { config } from '../config/environment';

const API_BASE_URL = config.API_BASE_URL;
const DEVICE_CONFIG_FILE = 'device-config.json';
const HEARTBEAT_INTERVAL = 5 * 60 * 1000; // 5 minutes

interface DeviceConfig {
  deviceToken: string;
  deviceId?: string;
}

interface RegisterDeviceResponse {
  device_id: string;
  status: string;
  message: string;
  is_new_device: boolean;
}

let deviceToken: string | null = null;
let deviceId: string | null = null;
let heartbeatInterval: NodeJS.Timeout | null = null;
let isRegisteredThisSession: boolean = false;

/**
 * Helper function to trigger session expiration in renderer
 */
function triggerSessionExpired(): void {
  const mainWindow = BrowserWindow.getAllWindows()[0];
  if (mainWindow) {
    console.log('Triggering session expiration due to 401 error');
    mainWindow.webContents.send('auth:session-expired');
  }
}

/**
 * Get or create device token (persistent UUID for this device)
 */
function getOrCreateDeviceToken(): string {
  if (deviceToken) {
    return deviceToken;
  }

  const config = loadDeviceConfig();
  
  if (config?.deviceToken) {
    deviceToken = config.deviceToken;
    return deviceToken;
  }

  // Generate new device token (UUID v4)
  deviceToken = crypto.randomUUID();
  saveDeviceConfig({ deviceToken });
  
  console.log('Generated new device token:', deviceToken);
  return deviceToken;
}

/**
 * Get stored device ID (from backend)
 */
export function getDeviceId(): string | null {
  if (deviceId) {
    return deviceId;
  }

  const config = loadDeviceConfig();
  if (config?.deviceId) {
    deviceId = config.deviceId;
    return deviceId;
  }

  return null;
}

/**
 * Check if device successfully registered in this session
 */
export function isDeviceRegisteredThisSession(): boolean {
  return isRegisteredThisSession;
}

/**
 * Save device ID to local config
 */
function saveDeviceId(id: string): void {
  deviceId = id;
  const config = loadDeviceConfig() || { deviceToken: getOrCreateDeviceToken() };
  config.deviceId = id;
  saveDeviceConfig(config);
}

/**
 * Clear device data (on logout)
 */
export function clearDeviceData(): void {
  deviceId = null;
  isRegisteredThisSession = false;
  // Keep deviceToken - it's permanent for this installation
  const cfg = loadDeviceConfig();
  if (cfg) {
    delete (cfg as any).deviceId;
    saveDeviceConfig(cfg);
  }
  stopHeartbeat();
}

/**
 * Get device configuration file path
 */
function getDeviceConfigPath(): string {
  const userDataPath = app.getPath('userData');
  return path.join(userDataPath, DEVICE_CONFIG_FILE);
}

/**
 * Load device config from file
 */
function loadDeviceConfig(): DeviceConfig | null {
  try {
    const configPath = getDeviceConfigPath();
    if (fs.existsSync(configPath)) {
      const data = fs.readFileSync(configPath, 'utf-8');
      return JSON.parse(data);
    }
  } catch (error) {
    console.error('Failed to load device config:', error);
  }
  return null;
}

/**
 * Save device config to file
 */
function saveDeviceConfig(config: DeviceConfig): void {
  try {
    const configPath = getDeviceConfigPath();
    fs.writeFileSync(configPath, JSON.stringify(config, null, 2), 'utf-8');
  } catch (error) {
    console.error('Failed to save device config:', error);
  }
}

/**
 * Get list of installed MCP servers
 */
function getInstalledMCPServers(): string[] {
  try {
    const { mcpService } = require('./mcpService');
    return mcpService.getInstalledMCPServerIds();
  } catch (error) {
    console.error('Failed to get installed MCP servers:', error);
    return [];
  }
}

/**
 * Get device type based on platform
 */
function getDeviceType(): 'macos' | 'windows' {
  return process.platform === 'darwin' ? 'macos' : 'windows';
}

/**
 * Register device with backend (or update if already exists)
 * Called on app launch
 */
export async function registerDevice(): Promise<void> {
  const accessToken = getAccessToken();
  
  if (!accessToken) {
    throw new Error('No access token available. User must be authenticated.');
  }

  const token = getOrCreateDeviceToken();
  const deviceData = {
    device_token: token,
    device_name: os.hostname(),
    device_type: getDeviceType(),
    os_name: os.platform(),
    os_version: os.release(),
    app_version: app.getVersion(),
    mcp_servers: getInstalledMCPServers()
  };

  try {
    console.log('Registering device with backend...');
    
    const response = await axios.post<RegisterDeviceResponse>(
      `${API_BASE_URL}/device/register`,
      deviceData,
      {
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'Content-Type': 'application/json'
        }
      }
    );

    saveDeviceId(response.data.device_id);
    isRegisteredThisSession = true;
    
    if (response.data.is_new_device) {
      console.log('Device registered successfully:', response.data.device_id);
    } else {
      console.log('Device reconnected:', response.data.device_id);
    }

    // Start heartbeat after successful registration
    startHeartbeat();

  } catch (error) {
    isRegisteredThisSession = false;
    if (axios.isAxiosError(error)) {
      console.error('Failed to register device:', error.response?.data);
      
      // Handle 401 - trigger session expiration
      if (error.response?.status === 401) {
        triggerSessionExpired();
      }
      
      throw new Error(`Device registration failed: ${error.response?.data?.detail || error.message}`);
    }
    throw error;
  }
}

/**
 * Update device status (heartbeat or MCP server changes)
 */
export async function updateDeviceStatus(mcpServers?: string[]): Promise<void> {
  const accessToken = getAccessToken();
  const id = getDeviceId();
  
  if (!accessToken || !id) {
    console.warn('Cannot update device status: missing token or device ID');
    return;
  }

  try {
    const updateData: any = {};
    
    if (mcpServers !== undefined) {
      updateData.mcp_servers = mcpServers;
    } else {
      updateData.mcp_servers = getInstalledMCPServers();
    }

    await axios.put(
      `${API_BASE_URL}/device/${id}/status`,
      updateData,
      {
        headers: {
          'Authorization': `Bearer ${accessToken}`,
          'Content-Type': 'application/json'
        }
      }
    );

    console.log('Device status updated');

  } catch (error) {
    if (axios.isAxiosError(error)) {
      console.error('Failed to update device status:', error.response?.data);
      
      // Handle 401 - trigger session expiration
      if (error.response?.status === 401) {
        triggerSessionExpired();
      }
    } else {
      console.error('Failed to update device status:', error);
    }
  }
}

/**
 * Deactivate device (on logout)
 */
export async function deactivateDevice(): Promise<void> {
  const accessToken = getAccessToken();
  const id = getDeviceId();
  
  if (!accessToken || !id) {
    console.warn('Cannot deactivate device: missing token or device ID');
    return;
  }

  try {
    await axios.delete(
      `${API_BASE_URL}/device/${id}`,
      {
        headers: {
          'Authorization': `Bearer ${accessToken}`
        }
      }
    );

    console.log('Device deactivated successfully');
    clearDeviceData();

  } catch (error) {
    if (axios.isAxiosError(error)) {
      console.error('Failed to deactivate device:', error.response?.data);
    } else {
      console.error('Failed to deactivate device:', error);
    }
  }
}

/**
 * Start periodic heartbeat
 */
export function startHeartbeat(): void {
  // Clear any existing interval
  stopHeartbeat();

  console.log('Starting device heartbeat...');
  
  heartbeatInterval = setInterval(async () => {
    try {
      await updateDeviceStatus();
    } catch (error) {
      console.error('Heartbeat failed:', error);
    }
  }, HEARTBEAT_INTERVAL);
}

/**
 * Stop periodic heartbeat
 */
export function stopHeartbeat(): void {
  if (heartbeatInterval) {
    clearInterval(heartbeatInterval);
    heartbeatInterval = null;
    console.log('Device heartbeat stopped');
  }
}

/**
 * Handle MCP server installation/removal
 * Call this when user adds/removes MCP servers
 */
export async function onMCPServerChanged(mcpServers: string[]): Promise<void> {
  await updateDeviceStatus(mcpServers);
}

