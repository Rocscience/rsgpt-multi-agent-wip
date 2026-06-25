import { app, BrowserWindow, ipcMain, Tray, Menu, nativeImage, Notification, dialog, shell } from 'electron';
import path from 'path';
import * as fs from 'fs';
import { createAuthWindow, createLogoutWindow } from './authProcess';
import * as authService from './services/authService';
import { PROTOCOL_SCHEME } from './constants';
import * as deviceService from './services/deviceService';
import { webSocketService } from './services/webSocketService';
import { MCPClient } from './mcp/mcpClient';
import { mcpService } from './services/mcpService';
import { sessionService } from './services/sessionService';
import { autoUpdateService } from './services/autoUpdateService';

let window: BrowserWindow | null = null;
let mcpClient: MCPClient | null = null;
let tray: Tray | null = null;
let isQuitting = false;
let isLoggingOut = false;
let reconnectInProgress = false;

// Create log file in user data directory
const LOG_FILE = path.join(app.getPath('userData'), 'mcp-debug.log');

// Logger function that writes to both console and file
function logToFile(message: string, isError = false) {
  const timestamp = new Date().toISOString();
  const logMessage = `[${timestamp}] ${message}\n`;

  // Write to console
  if (isError) {
    console.error(message);
  } else {
    console.log(message);
  }

  // Write to file
  try {
    fs.appendFileSync(LOG_FILE, logMessage);
  } catch (err) {
    console.error('Failed to write to log file:', err);
  }
}

// Notification deduplication tracking
let lastDisconnectNotification = 0;
let lastErrorNotification = 0;
const NOTIFICATION_COOLDOWN_MS = 60000; // 1 minute cooldown between similar notifications

/** Send in-app toast to renderer so user sees it even when OS notifications are silenced. */
function sendToastToRenderer(options: { title: string; body: string; urgency?: 'normal' | 'critical' | 'low' }, webContents?: Electron.WebContents) {
  const target = webContents ?? window?.webContents;
  if (target && !target.isDestroyed()) {
    target.send('notification:toast', { title: options.title, body: options.body, urgency: options.urgency ?? 'normal' });
  }
}

// Track if WebSocket has ever connected successfully in this session
let hasEverConnected = false;

// Handle auth callback from custom protocol URL
async function handleAuthProtocolUrl(url: string): Promise<void> {
  console.log('[Auth] Received protocol callback URL:', url);
  
  try {
    await authService.handleAuthCallback(url);
    console.log('[Auth] Protocol callback handled successfully');
    
    // Focus the main window after successful auth
    if (window) {
      if (!window.isVisible()) window.show();
      window.focus();
    }
  } catch (error) {
    console.error('[Auth] Failed to handle protocol callback:', error);
  }
}

// Check if a URL is our custom protocol callback
function isAuthProtocolUrl(url: string): boolean {
  return url.startsWith(`${PROTOCOL_SCHEME}://callback`);
}

// Handle command line arguments
const handleCommandLineArgs = (args: string[]) => {
  console.log('Handling command line args:', args);

  // Check for auth protocol URL in args (Windows passes URL as argument)
  const protocolUrl = args.find(arg => isAuthProtocolUrl(arg));
  if (protocolUrl) {
    handleAuthProtocolUrl(protocolUrl);
    return; // Don't process other args if this is an auth callback
  }

  if (args.includes('--show-window')) {
    if (window) {
      window.show();
      window.focus();
    } else {
      createWindow();
    }
  }

  if (args.includes('--reconnect')) {
    console.log('Reconnecting services from taskbar task...');
    // Attempt to reconnect device and websocket
    deviceService.registerDevice()
      .then(() => webSocketService.connect())
      .then(() => {
        console.log('Services reconnected successfully');
        if (updateTrayMenu) updateTrayMenu();
      })
      .catch(error => {
        console.error('Failed to reconnect services:', error);
      });
  }
};

// Prevent multiple instances - focus existing instance instead
const gotTheLock = app.requestSingleInstanceLock();

if (!gotTheLock) {
  // Another instance is already running, quit this one
  app.quit();
} else {
  // Handle second instance attempts (e.g., from Jump List tasks or protocol URLs)
  app.on('second-instance', (_event, commandLine, _workingDirectory) => {
    console.log('Second instance detected with args:', commandLine);

    // Check for auth protocol URL first (Windows passes URL as command line argument)
    const protocolUrl = commandLine.find(arg => isAuthProtocolUrl(arg));
    if (protocolUrl) {
      console.log('[Auth] Protocol URL received via second-instance:', protocolUrl);
      handleAuthProtocolUrl(protocolUrl);
      return;
    }

    // Handle other command line arguments
    handleCommandLineArgs(commandLine);

    // Show and focus the window if it exists
    if (window) {
      if (window.isMinimized()) window.restore();
      if (!window.isVisible()) window.show();
      window.focus();
    }
  });
}

// Create Application Menu Function
function createApplicationMenu() {
  const template: Electron.MenuItemConstructorOptions[] = [
    {
      label: 'Help',
      submenu: [
        {
          label: 'About RSInsight',
          click: () => {
            if (window) {
              window.webContents.send('app:show-about');
            }
          }
        }
      ]
    }
  ];

  const menu = Menu.buildFromTemplate(template);
  Menu.setApplicationMenu(menu);
}

function createWindow() {
  window = new BrowserWindow({
    width: 800,
    height: 700,
    autoHideMenuBar: false,
    icon: path.join(__dirname, '../../build/icons/512x512.png'),
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, '../preload/index.js')
    }
  });

  // Load the React app from webpack dev server in development, or from file in production
  // app.isPackaged is false in development, true in production builds
  const isDev = !app.isPackaged;

  if (isDev) {
    window.loadURL('http://localhost:5173');
    // Open DevTools in development
    window.webContents.openDevTools();
  } else {
    const rendererPath = path.join(__dirname, '../renderer/index.html');
    window.loadFile(rendererPath);
  }

  // Hide window instead of closing when user clicks X
  window.on('close', (event) => {
    console.log('Window close event triggered, isQuitting:', isQuitting);
    if (!isQuitting) {
      event.preventDefault();
      window?.hide();

      // Show notification on first hide
      if (Notification.isSupported()) {
        new Notification({
          title: 'RSInsight Running in Background',
          body: 'RSInsight is still running.',
          icon: path.join(__dirname, '../../build/icons/64x64.png')
        }).show();
      }
      sendToastToRenderer({ title: 'RSInsight Running in Background', body: 'RSInsight is still running.' });

      return false;
    }
  });

  // Add event listeners to track window visibility changes
  window.on('hide', () => {
    console.log('Window hide event triggered');
  });

  window.on('show', () => {
    console.log('Window show event triggered');
  });

  window.on('minimize', () => {
    console.log('Window minimize event triggered');
  });

  window.on('restore', () => {
    console.log('Window restore event triggered');
  });

  window.on('closed', () => {
    window = null;
  });

  // Initialize auto-updater (only in production)
  if (app.isPackaged) {
    autoUpdateService.initialize(window);
    // Check for updates after a short delay to allow the app to fully load
    setTimeout(() => {
      autoUpdateService.checkForUpdates();
    }, 5000);
  }
}

function createTray() {
  try {
    // Use 16x16 or 32x32 for Windows tray, macOS handles scaling
    const iconPath = process.platform === 'win32'
      ? path.join(__dirname, '../../build/icons/32x32.png')
      : path.join(__dirname, '../../build/icons/64x64.png');

    console.log('Creating tray with icon path:', iconPath);

    const icon = nativeImage.createFromPath(iconPath);

    if (icon.isEmpty()) {
      console.error('Tray icon is empty! Path:', iconPath);
      // Fallback: try to create from app icon
      const appIcon = app.getAppPath() + '/build/icons/32x32.png';
      console.log('Trying fallback icon path:', appIcon);
      const fallbackIcon = nativeImage.createFromPath(appIcon);
      if (!fallbackIcon.isEmpty()) {
        tray = new Tray(fallbackIcon);
      } else {
        console.error('Fallback icon also empty, creating tray without icon');
        tray = new Tray(nativeImage.createEmpty());
      }
    } else {
      tray = new Tray(icon);
      console.log('Tray created successfully');
    }

    updateTrayMenu();
    tray.setToolTip('RSInsight Desktop Gateway');

    // Double-click or click to show window (platform dependent)
    tray.on('click', () => {
      if (window) {
        if (window.isVisible()) {
          window.hide();
        } else {
          window.show();
          window.focus();
        }
      } else {
        createWindow();
      }
    });

    tray.on('double-click', () => {
      if (window) {
        window.show();
        window.focus();
      } else {
        createWindow();
      }
    });
  } catch (error) {
    console.error('Error creating tray:', error);
  }
}

function updateTrayMenu() {
  if (!tray) return;

  const isWsConnected = webSocketService.isConnected();
  const deviceStatus = deviceService.isDeviceRegisteredThisSession();

  // Update tray icon based on connection status
  let iconPath: string;
  if (isWsConnected && deviceStatus) {
    // Connected - use normal icon
    iconPath = process.platform === 'win32'
      ? path.join(__dirname, '../../build/icons/32x32.png')
      : path.join(__dirname, '../../build/icons/64x64.png');
  } else {
    // Disconnected - we could use a different icon or overlay
    // For now, keeping the same icon but the menu will show status
    iconPath = process.platform === 'win32'
      ? path.join(__dirname, '../../build/icons/32x32.png')
      : path.join(__dirname, '../../build/icons/64x64.png');
  }

  const icon = nativeImage.createFromPath(iconPath);
  tray.setImage(icon);

  const contextMenu = Menu.buildFromTemplate([
    {
      label: 'RSInsight Desktop Gateway',
      enabled: false,
      icon: nativeImage.createFromPath(path.join(__dirname, '../../build/icons/16x16.png'))
    },
    { type: 'separator' },
    {
      label: window?.isVisible() ? 'Hide Window' : 'Show Window',
      click: () => {
        if (window) {
          if (window.isVisible()) {
            window.hide();
          } else {
            window.show();
            window.focus();
          }
        } else {
          createWindow();
        }
      }
    },
    { type: 'separator' },
    {
      label: `Gateway: ${isWsConnected ? '🟢 Connected' : '🔴 Disconnected'}`,
      enabled: false
    },
    {
      label: `Device: ${deviceStatus ? '🟢 Registered' : '🔴 Not Registered'}`,
      enabled: false
    },
    { type: 'separator' },
    {
      label: 'Reconnect Services',
      enabled: (!isWsConnected || !deviceStatus) && !reconnectInProgress,
      click: async () => {
        if (reconnectInProgress) return;
        reconnectInProgress = true;
        updateTrayMenu();
        try {
          if (!deviceStatus) {
            await deviceService.registerDevice();
          }
          if (!isWsConnected) {
            await webSocketService.connect();
          }
        } catch (error) {
          console.error('Failed to reconnect services:', error);
        } finally {
          reconnectInProgress = false;
          updateTrayMenu();
        }
      }
    },
    { type: 'separator' },
    {
      label: 'Quit RSInsight',
      click: () => {
        isQuitting = true;
        // Cleanup and quit
        webSocketService.disconnect();
        deviceService.stopHeartbeat();
        if (mcpClient) mcpClient.stop();
        app.quit();
      }
    }
  ]);

  tray.setContextMenu(contextMenu);
}

async function initializeMCP() {
  // Initialize MCP client AFTER window is created
  try {
    logToFile('\n═══════════════════════════════════════════════════════', true);
    logToFile('  Initializing MCP Client', true);
    logToFile('═══════════════════════════════════════════════════════\n', true);
    logToFile(`Log file location: ${LOG_FILE}`, true);

    // Validate version compatibility of installed MCP servers before starting.
    // This checks each server's required Rocscience app version against the local install.
    // Incompatible servers are disabled in mcp-servers.json so the gateway won't start them.
    logToFile('[Version Check] Running startup version compatibility check...', true);
    const incompatibleServers = await mcpService.validateInstalledServersCompatibility();

    if (incompatibleServers.length > 0) {
      logToFile(`[Version Check] ${incompatibleServers.length} server(s) disabled due to version incompatibility`, true);

      // Send version warnings to renderer for in-app Dashboard banner
      if (window) {
        window.webContents.send('mcp:version-warnings', incompatibleServers);
      }

      // Also show OS notification as fallback for users with minimized/tray app
      const serverNames = incompatibleServers.map(s => s.displayName).join(', ');
      const versionNotificationPayload = {
        title: 'MCP Tool Compatibility Issues',
        body: `${incompatibleServers.length} tool(s) disabled: ${serverNames}. Open RSInsight for details.`,
        urgency: 'critical' as const
      };
      if (Notification.isSupported()) {
        new Notification({
          ...versionNotificationPayload,
          icon: path.join(__dirname, '../../build/icons/64x64.png')
        }).show();
      }
      sendToastToRenderer(versionNotificationPayload);
    } else {
      logToFile('[Version Check] All installed servers are compatible', true);
    }

    mcpClient = new MCPClient();

    // Set the log file so MCPClient writes to the same file
    mcpClient.setLogFile(LOG_FILE);
    logToFile('Set log file path for MCPClient', true);

    // Send status update to renderer
    if (window) {
      window.webContents.send('mcp:status', { status: 'starting', message: 'Starting MCP client...' });
      logToFile('Sent "starting" status to renderer', true);
    }

    logToFile('Calling mcpClient.start()...', true);
    logToFile(`app.isPackaged: ${app.isPackaged}`, true);
    logToFile(`app.getAppPath(): ${app.getAppPath()}`, true);
    logToFile(`process.resourcesPath: ${process.resourcesPath}`, true);
    logToFile(`__dirname: ${__dirname}`, true);

    await mcpClient.start();
    logToFile('mcpClient.start() completed', true);

    logToFile('\n═══════════════════════════════════════════════════════', true);
    logToFile('  ✓ MCP Client Started Successfully', true);
    logToFile('═══════════════════════════════════════════════════════\n', true);

    // Send success status to renderer
    if (window) {
      window.webContents.send('mcp:status', { status: 'ready', message: 'MCP client is ready' });
      logToFile('Sent "ready" status to renderer', true);
    }

    // Set MCP client on WebSocket service
    webSocketService.setMCPClient(mcpClient);
    logToFile('MCP client set on WebSocket service', true);

    // Set MCP client callbacks on mcpService for handling updates
    mcpService.setMCPClientCallbacks(
      () => {
        // Stop callback
        if (mcpClient) {
          mcpClient.stop();
        }
      },
      async () => {
        // Start callback
        if (mcpClient) {
          await mcpClient.start();
          // Re-set MCP client on WebSocket service after restart
          webSocketService.setMCPClient(mcpClient);
        }
      }
    );
    logToFile('MCP client callbacks set on mcpService', true);

    // Start auto-refresh of MCP registry (every 1 hour)
    mcpService.startAutoRefresh();
    logToFile('Started MCP registry auto-refresh (every 1 hour)', true);
  } catch (error) {
    logToFile('\n═══════════════════════════════════════════════════════', true);
    logToFile('  ✗ Failed to start MCP client', true);
    logToFile(`  Error: ${error}`, true);
    logToFile('═══════════════════════════════════════════════════════\n', true);

    if (error instanceof Error && error.stack) {
      logToFile(`Stack trace: ${error.stack}`, true);
    }

    // Send error status to renderer
    if (window) {
      window.webContents.send('mcp:status', {
        status: 'error',
        message: `Failed to start MCP: ${error instanceof Error ? error.message : String(error)}`
      });
      logToFile('Sent "error" status to renderer', true);
    }
  }
}

async function initializeApp() {
  let hasValidSession = false;

  // Try to refresh tokens silently on startup
  try {
    await authService.refreshTokens();
    // Check if we have the MCP service token
    hasValidSession = sessionService.hasServiceTokens();

    if (hasValidSession) {
      // Register device after successful token refresh
      await deviceService.registerDevice();
      // Connect WebSocket after device registration
      await webSocketService.connect();
      logToFile('[Main] Valid session found, MCP will start after window loads');
    } else {
      logToFile('[Main] No MCP service token available after refresh');
    }
  } catch (err) {
    // No valid refresh token, user will need to login
    logToFile('[Main] No valid session, user must login');
    hasValidSession = false;
  }

  // Always create the window FIRST - let the renderer handle the UI state
  createWindow();

  // Wait for window to be ready before initializing MCP
  if (window) {
    window.webContents.once('did-finish-load', async () => {
      // ONLY start MCP if we have a valid session with service token
      if (hasValidSession) {
        logToFile('[Main] Window loaded, initializing MCP with service token...');
        await initializeMCP();
      } else {
        logToFile('[Main] Window loaded, MCP will start after user logs in');
      }
    });
  }

  // Handle command line arguments on first launch
  handleCommandLineArgs(process.argv);
}

app.whenReady().then(() => {
  // Register custom protocol handler for auth callbacks
  // Always register to ensure the protocol is available regardless of how the app was launched
  if (!app.isPackaged) {
    // Development mode: register with full path to electron and the app
    app.setAsDefaultProtocolClient(PROTOCOL_SCHEME, process.execPath, [
      path.resolve(process.argv[1])
    ]);
    console.log(`[Auth] Registered protocol handler for development: ${PROTOCOL_SCHEME}://`);
    console.log(`[Auth] Executable: ${process.execPath}`);
    console.log(`[Auth] App path: ${path.resolve(process.argv[1])}`);
  } else {
    // Production mode: register without arguments (uses the packaged exe)
    const registered = app.setAsDefaultProtocolClient(PROTOCOL_SCHEME);
    console.log(`[Auth] Protocol handler registration for production: ${registered ? 'success' : 'failed'}`);
  }

  // Handle protocol URL if app was launched via deep link (cold start on Windows)
  const protocolUrl = process.argv.find(arg => isAuthProtocolUrl(arg));
  if (protocolUrl) {
    console.log('[Auth] App launched via protocol URL:', protocolUrl);
    // Delay handling to ensure app is fully ready
    setTimeout(() => handleAuthProtocolUrl(protocolUrl), 100);
  }

  // Create application menu
  createApplicationMenu();

  // Create system tray
  console.log('App ready, creating tray...');
  createTray();
  console.log('Tray creation attempted, tray object:', tray !== null ? 'exists' : 'null');

  // Listen for session expiration (when refresh token is invalid)
  (app as NodeJS.EventEmitter).on('auth:session-expired', () => {
    logToFile('[Main] Session expired (refresh token invalid), cleaning up...');

    // Stop MCP servers
    if (mcpClient) {
      logToFile('[Main] Stopping MCP servers due to session expiration...');
      mcpClient.stop();
    }

    // Clear service tokens
    sessionService.clearServiceTokens();

    // Update tray menu
    updateTrayMenu();
  });

  // Set up WebSocket event listeners
  webSocketService.on('connected', () => {
    console.log('WebSocket connected successfully');

    // Mark that we've successfully connected at least once
    hasEverConnected = true;

    // Reset notification timers on successful connection
    lastDisconnectNotification = 0;
    lastErrorNotification = 0;

    // Update tray menu with new status
    updateTrayMenu();

    // Show notification
    if (Notification.isSupported()) {
      new Notification({
        title: 'Gateway Connected',
        body: 'Successfully connected to RSInsight Desktop Gateway.',
        icon: path.join(__dirname, '../../build/icons/64x64.png')
      }).show();
    }
    sendToastToRenderer({ title: 'Gateway Connected', body: 'Successfully connected to RSInsight Desktop Gateway.' });

    // Notify renderer about connection status if needed
    if (window) {
      window.webContents.send('websocket:connected');
    }
  });

  webSocketService.on('disconnected', (data) => {
    console.log('WebSocket disconnected:', data);

    // Update tray menu with new status
    updateTrayMenu();

    // Show notification for disconnection (with deduplication)
    const now = Date.now();
    const shouldShowNotification = (now - lastDisconnectNotification) >= NOTIFICATION_COOLDOWN_MS;

    if (Notification.isSupported() && shouldShowNotification && !isQuitting) {
      if (isLoggingOut) {
        // User is logging out, show informational message
        new Notification({
          title: 'Gateway Closed',
          body: 'RSInsight Desktop Gateway was closed.',
          icon: path.join(__dirname, '../../build/icons/64x64.png'),
          urgency: 'normal'
        }).show();
        sendToastToRenderer({ title: 'Gateway Closed', body: 'RSInsight Desktop Gateway was closed.', urgency: 'normal' });
        lastDisconnectNotification = now;
      } else if (!hasEverConnected) {
        // Initial connection failed
        new Notification({
          title: 'Connection Failed',
          body: 'Failed to connect to RSInsight gateway. Please check your connection.',
          icon: path.join(__dirname, '../../build/icons/64x64.png'),
          urgency: 'critical'
        }).show();
        sendToastToRenderer({ title: 'Connection Failed', body: 'Failed to connect to RSInsight gateway. Please check your connection.', urgency: 'critical' });
        lastDisconnectNotification = now;
      } else {
        // Connection was previously established but now lost
        new Notification({
          title: 'Gateway Disconnected',
          body: 'Connection to RSInsight Desktop Gateway lost. Will attempt to reconnect.',
          icon: path.join(__dirname, '../../build/icons/64x64.png'),
          urgency: 'critical'
        }).show();
        sendToastToRenderer({ title: 'Gateway Disconnected', body: 'Connection to RSInsight Desktop Gateway lost. Will attempt to reconnect.', urgency: 'critical' });
        lastDisconnectNotification = now;
      }
    } else if (!shouldShowNotification) {
      console.log('Skipping duplicate disconnect notification (cooldown active)');
    } else if (isQuitting) {
      console.log('Skipping disconnect notification (app is quitting)');
    }

    // Notify renderer about disconnection if needed
    if (window) {
      window.webContents.send('websocket:disconnected', data);
    }
  });

  webSocketService.on('notification', (data) => {
    console.log('Received notification from server:', data);
    // Forward notification to renderer
    if (window) {
      window.webContents.send('notification', data);
    }
  });

  webSocketService.on('command', (data) => {
    console.log('Received command from server:', data);
    // Forward command to renderer
    if (window) {
      window.webContents.send('command', data);
    }
  });

  webSocketService.on('request_file_path', async (message) => {
    if (!window) {
      console.warn('No window available, creating window...');
      createWindow();

      // Wait a bit for window to be ready
      await new Promise(resolve => setTimeout(resolve, 500));

      if (!window) {
        console.error('Failed to create window');
        webSocketService.send({
          type: 'file_path_response',
          id: message.id,
          data: { error: 'No window available' }
        });
        return;
      }
    }

    try {
      // Save original window position
      const originalBounds = window.getBounds();

      // If screen info was provided, move window to that screen
      const screenInfo = message.screen_info;
      if (screenInfo) {
        // Move window near the browser window (center of browser screen)
        const targetX = screenInfo.screenX + Math.floor(screenInfo.windowWidth / 2);
        const targetY = screenInfo.screenY + Math.floor(screenInfo.windowHeight / 2);

        window.setBounds({
          x: targetX,
          y: targetY,
          width: originalBounds.width,
          height: originalBounds.height
        });
      }

      // Set window to always on top temporarily so dialog inherits this and appears on top
      window.setAlwaysOnTop(true);

      // Focus the window to bring it (and the dialog) to the foreground
      window.focus();

      // Small delay to let focus and always-on-top take effect
      await new Promise(resolve => setTimeout(resolve, 100));

      // Open dialog with parent window so it appears on top of all other windows
      const result = await dialog.showOpenDialog(window, {
        properties: ['openFile'],
        filters: [
          { name: 'All Supported Files', extensions: ['fez', 'rspile2', 'dips9', 's3z', 's3d', 'sli', 'slmd', 'xlsx', 'xls', 'csv'] },
          { name: 'RS2 Program Files', extensions: ['fez'] },
          { name: 'RSPile2 Program Files', extensions: ['rspile2'] },
          { name: 'Dips Program Files', extensions: ['dips9'] },
          { name: 'Settle3 Program Files', extensions: ['s3z', 's3d'] },
          { name: 'Slide2 Program Files', extensions: ['sli', 'slmd'] },
          { name: 'Excel Files', extensions: ['xlsx', 'xls'] },
          { name: 'CSV Files', extensions: ['csv'] },
        ]
      });

      // Remove always on top after dialog closes
      window.setAlwaysOnTop(false);

      // Restore original window position
      window.setBounds(originalBounds);

      if (result.canceled || result.filePaths.length === 0) {
        webSocketService.send({
          type: 'file_path_response',
          id: message.id,
          data: { canceled: true }
        });
      } else {
        const filePath = result.filePaths[0];
        webSocketService.send({
          type: 'file_path_response',
          id: message.id,
          data: { filePath }
        });
      }
    } catch (error) {
      console.error('Error opening file dialog:', error);
      webSocketService.send({
        type: 'file_path_response',
        id: message.id,
        data: { error: error instanceof Error ? error.message : String(error) }
      });
    }
  });

  webSocketService.on('error', (error) => {
    console.error('WebSocket error:', error);

    // Show notification for errors only if not logging out or quitting (with deduplication)
    const now = Date.now();
    const shouldShowNotification = (now - lastErrorNotification) >= NOTIFICATION_COOLDOWN_MS;

    if (Notification.isSupported() && !isLoggingOut && !isQuitting && shouldShowNotification) {
      new Notification({
        title: 'Gateway Error',
        body: 'An error occurred with the gateway connection.',
        icon: path.join(__dirname, '../../build/icons/64x64.png'),
        urgency: 'critical'
      }).show();
      sendToastToRenderer({ title: 'Gateway Error', body: 'An error occurred with the gateway connection.', urgency: 'critical' });
      lastErrorNotification = now;
    } else if (!shouldShowNotification) {
      console.log('Skipping duplicate error notification (cooldown active)');
    } else if (isLoggingOut || isQuitting) {
      console.log('Skipping error notification (app is logging out or quitting)');
    }

    // Forward error to renderer if needed
    if (window) {
      window.webContents.send('websocket:error', error);
    }
  });

  webSocketService.on('agent_response', (message) => {
    console.log('Agent response received:', message.output);
    // Forward agent response to renderer
    if (window) {
      window.webContents.send('agent:response', message);
    }
  });

  // Set up IPC handlers for auth
  ipcMain.handle('auth:get-profile', () => {
    return authService.getProfile();
  });

  ipcMain.handle('auth:login', () => {
    return new Promise(async (resolve, reject) => {
      createAuthWindow(async () => {
        const profile = authService.getProfile();

        // Register device after successful login
        try {
          await deviceService.registerDevice();
          // Connect WebSocket after device registration
          await webSocketService.connect();
        } catch (error) {
          console.error('Failed to register device or connect WebSocket after login:', error);
        }

        // Resolve immediately so UI can proceed - don't wait for MCP
        resolve(profile);

        // Start or restart MCP servers in the background after login
        // Service tokens are fetched from backend during login and stored in sessionService
        if (mcpClient) {
          // MCP was already initialized, restart to pick up new tokens
          try {
            console.log('[Auth] Restarting MCP servers to apply service tokens...');
            mcpClient.stop();
            await mcpClient.start();
            // Re-set MCP client on WebSocket service after restart
            webSocketService.setMCPClient(mcpClient);
            console.log('[Auth] MCP servers restarted with service tokens');
          } catch (mcpError) {
            console.error('Failed to restart MCP servers after login:', mcpError);
          }
        } else {
          // First time login - MCP was never started, initialize it now
          try {
            console.log('[Auth] Starting MCP servers for first time after login...');
            await initializeMCP();
            console.log('[Auth] MCP servers started with service tokens');
          } catch (mcpError) {
            console.error('Failed to start MCP servers after login:', mcpError);
          }
        }
      });
    });
  });

  ipcMain.on('auth:log-out', async () => {
    // Set logout flag to suppress error notifications
    isLoggingOut = true;

    // Reset connection tracking
    hasEverConnected = false;

    // Stop MCP servers FIRST (before clearing tokens)
    if (mcpClient) {
      console.log('[Auth] Stopping MCP servers before logout...');
      mcpClient.stop();
    }

    // Disconnect WebSocket before deactivating device
    webSocketService.disconnect();

    // Stop heartbeat before deactivating
    deviceService.stopHeartbeat();

    // Deactivate device on backend
    try {
      await deviceService.deactivateDevice();
    } catch (error) {
      console.error('Failed to deactivate device on logout:', error);
    }

    // Update tray menu
    updateTrayMenu();

    // Temporarily allow window close for logout
    const tempQuitting = isQuitting;
    isQuitting = true;
    BrowserWindow.getAllWindows().forEach(win => win.close());
    isQuitting = tempQuitting;

    createLogoutWindow(() => {
      // After logout, show login screen again
      createWindow();
      // Reset logout flag after logout window closes
      isLoggingOut = false;
    });
  });

  // Set up IPC handlers for device status
  ipcMain.handle('device:get-status', () => {
    const deviceId = deviceService.getDeviceId();
    const isRegistered = deviceService.isDeviceRegisteredThisSession();
    return {
      isRegistered: isRegistered,
      deviceId: deviceId,
      deviceName: require('os').hostname(),
      osName: require('os').platform(),
      osVersion: require('os').release(),
    };
  });

  ipcMain.handle('device:reconnect', async () => {
    try {
      await deviceService.registerDevice();
      // Try to connect WebSocket after successful device registration
      try {
        await webSocketService.connect();
      } catch (wsError) {
        console.error('WebSocket connection failed after device registration:', wsError);
      }

      // Update tray menu with new status
      updateTrayMenu();

      // Notify renderer about successful registration
      if (window) {
        window.webContents.send('device:status-changed');
      }
      return { success: true };
    } catch (error) {
      console.error('Failed to reconnect device:', error);

      // Update tray menu
      updateTrayMenu();

      // Show notification for device registration failure only if not logging out
      if (Notification.isSupported() && !isLoggingOut) {
        new Notification({
          title: 'Device Registration Failed',
          body: 'Failed to register device with RSInsight Desktop Gateway.',
          icon: path.join(__dirname, '../../build/icons/64x64.png'),
          urgency: 'critical'
        }).show();
      }
      if (!isLoggingOut) {
        sendToastToRenderer({ title: 'Device Registration Failed', body: 'Failed to register device with RSInsight Desktop Gateway.', urgency: 'critical' });
      }

      // Notify renderer about failed registration
      if (window) {
        window.webContents.send('device:status-changed');
      }
      return { success: false, error: error instanceof Error ? error.message : String(error) };
    }
  });

  // Set up IPC handlers for websocket status
  ipcMain.handle('websocket:get-status', () => {
    return {
      isConnected: webSocketService.isConnected(),
    };
  });

  ipcMain.handle('websocket:reconnect', async () => {
    try {
      await webSocketService.connect();

      // Update tray menu with new status
      updateTrayMenu();

      return { success: true };
    } catch (error) {
      console.error('Failed to reconnect WebSocket:', error);

      // Update tray menu
      updateTrayMenu();

      return { success: false, error: error instanceof Error ? error.message : String(error) };
    }
  });

  // Set up IPC handler for showing notifications from renderer
  ipcMain.handle('notification:show', (event, options: { title: string; body: string; urgency?: 'normal' | 'critical' | 'low' }) => {
    if (Notification.isSupported()) {
      new Notification({
        title: options.title,
        body: options.body,
        icon: path.join(__dirname, '../../build/icons/64x64.png'),
        urgency: options.urgency || 'normal'
      }).show();
    }
    // Always show in-app toast so user sees it when OS notifications are silenced
    sendToastToRenderer(options, event.sender);
  });

  // Set up IPC handler for getting app version
  ipcMain.handle('app:get-version', () => {
    return app.getVersion();
  });

  // Set up IPC handler for MCP status
  ipcMain.handle('mcp:get-status', async () => {
    if (!mcpClient) {
      return { ready: false, error: 'MCP client not initialized' };
    }

    try {
      const isReady = mcpClient.isReady();
      if (isReady) {
        const tools = await mcpClient.listTools();
        // Also fetch individual server statuses
        const serverStatuses = await mcpClient.getServerStatuses();
        return {
          ready: true,
          toolCount: tools.length,
          tools: tools.map(t => ({ name: t.name, description: t.description })),
          serverStatuses: serverStatuses
        };
      } else {
        return { ready: false };
      }
    } catch (error) {
      return {
        ready: false,
        error: error instanceof Error ? error.message : String(error)
      };
    }
  });

  // Set up IPC handlers for MCP store
  ipcMain.handle('mcp:list-tools', async () => {
    try {
      const tools = await mcpService.listTools();
      return { success: true, tools };
    } catch (error) {
      console.error('Failed to list MCP tools:', error);
      return { success: false, error: error instanceof Error ? error.message : String(error) };
    }
  });

  ipcMain.handle('mcp:install-tool', async (_event, toolName: string, version?: string) => {
    try {
      await mcpService.installTool(toolName, version);

      // Restart MCP client to load the new tool
      if (mcpClient) {
        logToFile('Restarting MCP client to load new tools...');
        if (window) window.webContents.send('mcp:status', { status: 'starting', message: 'Restarting MCP…' });
        mcpClient.stop();
        await mcpClient.start();
        if (window) window.webContents.send('mcp:status', { status: 'ready', message: 'MCP client is ready' });
        logToFile('MCP client restarted successfully');
      }

      return { success: true };
    } catch (error) {
      console.error('Failed to install MCP tool:', error);
      return { success: false, error: error instanceof Error ? error.message : String(error) };
    }
  });

  ipcMain.handle('mcp:uninstall-tool', async (_event, toolName: string) => {
    try {
      // Note: mcpService.uninstallTool() handles MCP client restart internally via callbacks
      await mcpService.uninstallTool(toolName);

      return { success: true };
    } catch (error) {
      console.error('Failed to uninstall MCP tool:', error);
      return { success: false, error: error instanceof Error ? error.message : String(error) };
    }
  });

  ipcMain.handle('mcp:toggle-tool', async (_event, toolName: string, enabled: boolean) => {
    try {
      await mcpService.toggleTool(toolName, enabled);

      // Restart MCP client to apply changes
      if (mcpClient) {
        logToFile('Restarting MCP client after toggle...');
        if (window) window.webContents.send('mcp:status', { status: 'starting', message: 'Restarting MCP…' });
        mcpClient.stop();
        await mcpClient.start();
        // Re-set MCP client on WebSocket service after restart
        webSocketService.setMCPClient(mcpClient);
        if (window) window.webContents.send('mcp:status', { status: 'ready', message: 'MCP client is ready' });
        logToFile('MCP client restarted successfully');
      }

      return { success: true };
    } catch (error) {
      console.error('Failed to toggle MCP tool:', error);
      return { success: false, error: error instanceof Error ? error.message : String(error) };
    }
  });

  ipcMain.handle('mcp:update-tool', async (_event, toolName: string, newVersion: string) => {
    try {
      // updateTool will handle stopping/restarting the MCP client internally
      await mcpService.updateTool(toolName, newVersion);

      return { success: true };
    } catch (error) {
      console.error('Failed to update MCP tool:', error);
      return { success: false, error: error instanceof Error ? error.message : String(error) };
    }
  });

  ipcMain.handle('mcp:refresh-registry', async () => {
    try {
      await mcpService.refreshRegistry();
      const tools = await mcpService.listTools();
      return { success: true, tools };
    } catch (error) {
      console.error('Failed to refresh registry:', error);
      return { success: false, error: error instanceof Error ? error.message : String(error) };
    }
  });

  // IPC handler: Fetch current version warnings on demand (e.g., Dashboard mount)
  ipcMain.handle('mcp:get-version-warnings', async () => {
    try {
      const warnings = await mcpService.validateInstalledServersCompatibility();
      return { success: true, warnings };
    } catch (error) {
      console.error('Failed to get version warnings:', error);
      return { success: false, error: error instanceof Error ? error.message : String(error) };
    }
  });

  // Open external URLs in the user's default system browser
  ipcMain.handle('shell:open-external', async (_event, url: string) => {
    try {
      // Only allow rocscience.com URLs for security
      if (url.startsWith('https://www.rocscience.com/')) {
        await shell.openExternal(url);
        return { success: true };
      }
      return { success: false, error: 'URL not allowed' };
    } catch (error) {
      console.error('Failed to open external URL:', error);
      return { success: false, error: error instanceof Error ? error.message : String(error) };
    }
  });

  // Set up progress listener for MCP installations
  mcpService.on('install-progress', (progress) => {
    if (window) {
      window.webContents.send('mcp:install-progress', progress);
    }
  });

  initializeApp();
});

// Handle window close - don't quit, keep running in tray
app.on('window-all-closed', () => {
  // Don't quit the app - keep services running in background
  // User can quit via tray menu
});

// Handle app quit - cleanup before exiting
app.on('before-quit', () => {
  isQuitting = true;

  // Disconnect WebSocket and stop heartbeat when app closes
  webSocketService.disconnect();
  deviceService.stopHeartbeat();

  // Stop MCP registry auto-refresh
  mcpService.stopAutoRefresh();

  // Stop MCP client
  if (mcpClient) {
    mcpClient.stop();
  }
});

