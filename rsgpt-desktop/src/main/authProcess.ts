import { BrowserWindow, shell } from 'electron';
import * as authService from './services/authService';

let authWindow: BrowserWindow | null = null;

/**
 * Start the login flow by opening Auth0 in the system browser.
 * The callback will be handled via custom protocol by the main process.
 */
export function createAuthWindow(onSuccess: () => void): void {
  destroyAuthWindow();

  // Set up callback for when auth completes
  authService.setPendingAuthCallback((success) => {
    destroyAuthWindow();
    if (success) {
      onSuccess();
    }
  });

  // Create a hidden window (kept for potential future use/cleanup tracking)
  authWindow = new BrowserWindow({
    width: 1,
    height: 1,
    show: false,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
    },
  });

  const authUrl = authService.getAuthenticationURL();
  
  // Open the Auth0 login page in the user's default browser
  shell.openExternal(authUrl);

  authWindow.on('closed', () => {
    authWindow = null;
  });
}

function destroyAuthWindow(): void {
  if (!authWindow) return;
  authWindow.close();
  authWindow = null;
}

export function createLogoutWindow(onComplete: () => void): void {
  const logoutWindow = new BrowserWindow({
    show: false,
  });

  logoutWindow.loadURL(authService.getLogOutUrl());

  logoutWindow.on('ready-to-show', async () => {
    await authService.logout();
    logoutWindow.close();
    onComplete();
  });
}
