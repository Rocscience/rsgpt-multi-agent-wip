import { autoUpdater, UpdateInfo } from 'electron-updater';
import { app, BrowserWindow, ipcMain } from 'electron';
import * as path from 'path';
import * as fs from 'fs';

// Log file for auto-updater (trigger v1.0.35 build)
const LOG_FILE = path.join(app.getPath('userData'), 'auto-update.log');

function log(message: string) {
  const timestamp = new Date().toISOString();
  const logMessage = `[${timestamp}] [AutoUpdate] ${message}\n`;
  console.log(`[AutoUpdate] ${message}`);
  try {
    fs.appendFileSync(LOG_FILE, logMessage);
  } catch (err) {
    console.error('Failed to write to auto-update log:', err);
  }
}

/**
 * Auto-update service for RSInsight Desktop
 * Uses electron-updater with generic provider pointing to S3 bucket
 */
class AutoUpdateService {
  private mainWindow: BrowserWindow | null = null;
  private updateAvailable = false;
  private updateDownloaded = false;
  private updateInfo: UpdateInfo | null = null;
  private updateCheckInterval: NodeJS.Timeout | null = null;

  /**
   * Initialize the auto-updater with configuration and event handlers
   */
  initialize(mainWindow: BrowserWindow): void {
    this.mainWindow = mainWindow;

    // Configure auto-updater
    autoUpdater.autoDownload = false; // Don't auto-download, let user decide
    autoUpdater.autoInstallOnAppQuit = true; // Install on quit if downloaded

    // Set up logging
    autoUpdater.logger = {
      info: (message: string) => log(`INFO: ${message}`),
      warn: (message: string) => log(`WARN: ${message}`),
      error: (message: string) => log(`ERROR: ${message}`),
      debug: (message: string) => log(`DEBUG: ${message}`),
    };

    this.setupEventHandlers();
    this.setupIPCHandlers();
    this.startPeriodicUpdateChecks();

    log('Auto-updater initialized');
  }

  /**
   * Start periodic update checks (every 24 hours)
   */
  private startPeriodicUpdateChecks(): void {
    // Check every 24 hours (86400000 ms)
    const CHECK_INTERVAL = 24 * 60 * 60 * 1000;

    this.updateCheckInterval = setInterval(() => {
      log('Performing periodic update check (24-hour interval)');
      this.checkForUpdates();
    }, CHECK_INTERVAL);

    log('Periodic update checks enabled (every 24 hours)');
  }

  /**
   * Stop periodic update checks (cleanup)
   */
  private stopPeriodicUpdateChecks(): void {
    if (this.updateCheckInterval) {
      clearInterval(this.updateCheckInterval);
      this.updateCheckInterval = null;
      log('Periodic update checks stopped');
    }
  }

  /**
   * Set up electron-updater event handlers
   */
  private setupEventHandlers(): void {
    autoUpdater.on('checking-for-update', () => {
      log('Checking for updates...');
      this.sendToRenderer('update-checking');
    });

    autoUpdater.on('update-available', (info: UpdateInfo) => {
      log(`Update available: v${info.version}`);
      this.updateAvailable = true;
      this.updateInfo = info;
      this.sendToRenderer('update-available', {
        version: info.version,
        releaseDate: info.releaseDate,
        releaseNotes: info.releaseNotes,
      });
    });

    autoUpdater.on('update-not-available', (info: UpdateInfo) => {
      log(`No update available. Current version: v${app.getVersion()}, Latest: v${info.version}`);
      this.updateAvailable = false;
      this.sendToRenderer('update-not-available', {
        currentVersion: app.getVersion(),
        latestVersion: info.version,
      });
    });

    autoUpdater.on('download-progress', (progress) => {
      const logMessage = `Download progress: ${progress.percent.toFixed(1)}% (${formatBytes(progress.transferred)}/${formatBytes(progress.total)})`;
      log(logMessage);
      this.sendToRenderer('update-download-progress', {
        percent: progress.percent,
        transferred: progress.transferred,
        total: progress.total,
        bytesPerSecond: progress.bytesPerSecond,
      });
    });

    autoUpdater.on('update-downloaded', (info: UpdateInfo) => {
      log(`Update downloaded: v${info.version}`);
      this.updateDownloaded = true;
      this.sendToRenderer('update-downloaded', {
        version: info.version,
      });
    });

    autoUpdater.on('error', (error: Error) => {
      log(`Update error: ${error.message}`);
      this.sendToRenderer('update-error', {
        message: error.message,
      });
    });
  }

  /**
   * Set up IPC handlers for renderer communication
   */
  private setupIPCHandlers(): void {
    // Check for updates
    ipcMain.handle('auto-update:check', async () => {
      log('Manual update check requested');
      try {
        const result = await autoUpdater.checkForUpdates();
        return {
          success: true,
          updateAvailable: this.updateAvailable,
          updateInfo: result?.updateInfo ? {
            version: result.updateInfo.version,
            releaseDate: result.updateInfo.releaseDate,
          } : null,
        };
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : String(error);
        log(`Check for updates failed: ${errorMessage}`);
        return {
          success: false,
          error: errorMessage,
        };
      }
    });

    // Download update
    ipcMain.handle('auto-update:download', async () => {
      log('Download update requested');
      if (!this.updateAvailable) {
        return { success: false, error: 'No update available' };
      }
      try {
        await autoUpdater.downloadUpdate();
        return { success: true };
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : String(error);
        log(`Download failed: ${errorMessage}`);
        return { success: false, error: errorMessage };
      }
    });

    // Install update (quit and install)
    ipcMain.handle('auto-update:install', async () => {
      log('Install update requested');
      if (!this.updateDownloaded) {
        return { success: false, error: 'Update not downloaded yet' };
      }
      // This will quit the app and install the update
      autoUpdater.quitAndInstall(false, true);
      return { success: true };
    });

    // Get current update status
    ipcMain.handle('auto-update:status', () => {
      return {
        currentVersion: app.getVersion(),
        updateAvailable: this.updateAvailable,
        updateDownloaded: this.updateDownloaded,
        updateInfo: this.updateInfo ? {
          version: this.updateInfo.version,
          releaseDate: this.updateInfo.releaseDate,
        } : null,
      };
    });
  }

  /**
   * Send message to renderer process
   */
  private sendToRenderer(channel: string, data?: any): void {
    if (this.mainWindow && !this.mainWindow.isDestroyed()) {
      this.mainWindow.webContents.send(channel, data);
    }
  }

  /**
   * Check for updates (can be called programmatically)
   */
  async checkForUpdates(): Promise<void> {
    log('Checking for updates...');
    try {
      await autoUpdater.checkForUpdates();
    } catch (error) {
      log(`Failed to check for updates: ${error instanceof Error ? error.message : String(error)}`);
    }
  }
}

/**
 * Format bytes to human-readable string
 */
function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

// Export singleton instance
export const autoUpdateService = new AutoUpdateService();