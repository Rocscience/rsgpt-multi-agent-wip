import { safeStorage } from 'electron';
import axios from 'axios';
import * as https from 'https';
import { jwtDecode } from 'jwt-decode';
import * as crypto from 'crypto';
import { config } from '../config/environment';
import { sessionService } from './sessionService';
import { TOKEN_REFRESH_BUFFER_MS, PROTOCOL_SCHEME } from '../constants';

// Create axios instance that prefers IPv4 to avoid IPv6 timeout issues
const httpsAgent = new https.Agent({
  family: 4, // Force IPv4
});
const axiosClient = axios.create({
  httpsAgent,
});

interface TokenResponse {
  access_token: string;
  id_token: string;
  refresh_token?: string;
}

interface UserProfile {
  name: string;
  picture: string;
  email?: string;
  [key: string]: any;
}


interface ServiceTokensResponse {
  mcp_credentials: {
    [key: string]: { token: string };
  };
}

const auth0Domain = config.AUTH0_DOMAIN;
const clientId = config.AUTH0_CLIENT_ID;
const audience = config.AUTH0_AUDIENCE;

const redirectUri = `${PROTOCOL_SCHEME}://callback`;
const STORAGE_KEY = 'electron-auth-refresh-token';

let accessToken: string | null = null;
let profile: UserProfile | null = null;
let refreshToken: string | null = null;
let tokenRefreshTimeout: NodeJS.Timeout | null = null;

// PKCE state
let codeVerifier: string | null = null;
let pendingAuthCallback: ((success: boolean) => void) | null = null;

/**
 * Generate a cryptographically random code verifier for PKCE
 */
function generateCodeVerifier(): string {
  return crypto.randomBytes(32).toString('base64url');
}

/**
 * Generate code challenge from verifier using SHA256 (S256 method)
 */
function generateCodeChallenge(verifier: string): string {
  return crypto.createHash('sha256').update(verifier).digest('base64url');
}


export function getAccessToken(): string | null {
  return accessToken;
}

/**
 * Schedule silent token refresh based on JWT expiry time
 * Sets a timeout to refresh 5 minutes before the token expires
 */
export function scheduleTokenRefresh(): void {
  cancelScheduledTokenRefresh(); // Clear any existing timeout

  if (!accessToken) {
    console.log('[Auth] No access token, skipping refresh schedule');
    return;
  }

  try {
    const decoded = jwtDecode<{ exp: number }>(accessToken);
    const expiresAtMs = decoded.exp * 1000;
    const refreshAtMs = expiresAtMs - TOKEN_REFRESH_BUFFER_MS;
    const timeUntilRefreshMs = refreshAtMs - Date.now();

    if (timeUntilRefreshMs <= 0) {
      // Token already expired or expiring very soon, refresh immediately
      console.log('[Auth] Token already expired or expiring soon, refreshing now...');
      performSilentRefresh();
      return;
    }

    const refreshInMinutes = Math.round(timeUntilRefreshMs / 1000 / 60);
    console.log(`[Auth] ✓ Token refresh scheduled in ${refreshInMinutes} minutes (at ${new Date(refreshAtMs).toLocaleString()})`);

    tokenRefreshTimeout = setTimeout(() => {
      performSilentRefresh();
    }, timeUntilRefreshMs);

  } catch (error) {
    console.error('[Auth] Failed to decode token for refresh scheduling:', error);
  }
}

/**
 * Cancel any scheduled token refresh
 */
export function cancelScheduledTokenRefresh(): void {
  if (tokenRefreshTimeout) {
    clearTimeout(tokenRefreshTimeout);
    tokenRefreshTimeout = null;
    console.log('[Auth] Scheduled token refresh cancelled');
  }
}

/**
 * Perform silent token refresh
 * If successful, schedules the next refresh
 * If failed, triggers session expiration
 */
async function performSilentRefresh(): Promise<void> {
  console.log('[Auth] Performing silent token refresh...');

  try {
    await refreshTokens();
    console.log('[Auth] ✓ Token refreshed silently - user stays logged in');
    // refreshTokens() calls scheduleTokenRefresh() after getting new token
  } catch (error) {
    console.error('[Auth] ✗ Silent refresh failed:', error);
    // Refresh token is invalid/expired - user must re-login
    await handleSessionExpired();
  }
}

/**
 * Handle session expiration - notify main process to stop MCP and show login
 * Called when refresh token is invalid and user must re-authenticate
 */
async function handleSessionExpired(): Promise<void> {
  cancelScheduledTokenRefresh();

  // Emit event for main process to handle MCP cleanup
  const { app, BrowserWindow } = require('electron');
  app.emit('auth:session-expired');

  // Notify renderer to show login screen
  const mainWindow = BrowserWindow.getAllWindows()[0];
  if (mainWindow) {
    mainWindow.webContents.send('auth:session-expired');
  }
}

export function getProfile(): UserProfile | null {
  return profile;
}

export function getAuthenticationURL(): string {
  // Generate PKCE code verifier and challenge
  codeVerifier = generateCodeVerifier();
  const codeChallenge = generateCodeChallenge(codeVerifier);

  const params = new URLSearchParams({
    scope: 'openid profile email offline_access',
    response_type: 'code',
    client_id: clientId!,
    redirect_uri: redirectUri,
    code_challenge: codeChallenge,
    code_challenge_method: 'S256',
  });

  // Only add audience if it's a valid URL/identifier (not the template placeholder)
  if (audience && !audience.includes('<') && !audience.includes('OPTIONAL')) {
    params.append('audience', audience);
  }

  return `https://${auth0Domain}/authorize?${params.toString()}`;
}

/**
 * Set callback for pending auth flow
 */
export function setPendingAuthCallback(callback: (success: boolean) => void): void {
  pendingAuthCallback = callback;
}

/**
 * Handle the auth callback URL from custom protocol
 * Called by main process when protocol URL is received
 */
export async function handleAuthCallback(callbackUrl: string): Promise<void> {
  try {
    console.log('[Auth] Handling protocol callback URL');
    await loadTokens(callbackUrl);
    
    // Notify pending callback of success
    if (pendingAuthCallback) {
      pendingAuthCallback(true);
      pendingAuthCallback = null;
    }
  } catch (error) {
    console.error('[Auth] Protocol callback error:', error);
    
    // Notify pending callback of failure
    if (pendingAuthCallback) {
      pendingAuthCallback(false);
      pendingAuthCallback = null;
    }
    throw error;
  }
}

export async function refreshTokens(): Promise<void> {
  // Try in-memory token first (for same-session refresh), then fall back to disk
  const storedToken = refreshToken || loadRefreshToken();

  if (!storedToken) {
    throw new Error('No available refresh token.');
  }
  console.log(`[Auth] Using ${refreshToken ? 'in-memory' : 'disk-stored'} refresh token`);

    const refreshOptions = {
      method: 'POST',
      url: `https://${auth0Domain!}/oauth/token`,
      headers: { 'content-type': 'application/json' },
      data: {
        grant_type: 'refresh_token',
        client_id: clientId!,
        refresh_token: storedToken,
      },
    };

  try {
    const response = await axiosClient(refreshOptions);
    accessToken = response.data.access_token;
    profile = jwtDecode<UserProfile>(response.data.id_token);

    // Log token expiration for debugging
    if (accessToken) {
      const decoded = jwtDecode<{ exp: number }>(accessToken);
      console.log(`[Auth] ✓ Token refreshed. Expires at: ${new Date(decoded.exp * 1000).toLocaleString()}`);
    }

    // Fetch service tokens after refreshing access token
    await fetchServiceTokens();

    // Schedule the next refresh based on new token's expiry
    scheduleTokenRefresh();
  } catch (error) {
    await logout();
    throw error;
  }
}

/**
 * Fetch service tokens from backend after Auth0 login
 * Requires valid JWT access token
 */
async function fetchServiceTokens(): Promise<void> {
  if (!accessToken) {
    console.error('Cannot fetch service tokens: No access token available');
    return;
  }

  try {
    console.log('Fetching service tokens from backend...');

    const response = await axiosClient.get<ServiceTokensResponse>(
      `${config.API_BASE_URL}/auth/service-tokens`,
      {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
      }
    );

    // Store tokens in session service
    sessionService.setServiceTokens(response.data);
    console.log('✓ Service tokens fetched and stored successfully');
  } catch (error) {
    console.error('Failed to fetch service tokens:', error);
    if (axios.isAxiosError(error)) {
      console.error('Response status:', error.response?.status);
      console.error('Response data:', error.response?.data);
    }
    // Don't throw - allow login to continue even if token fetch fails
    // The app can still work with user auth, just service-to-service calls might fail
  }
}

export async function loadTokens(callbackURL: string): Promise<void> {
  const url = new URL(callbackURL);
  const code = url.searchParams.get('code');
  const error = url.searchParams.get('error');
  const errorDescription = url.searchParams.get('error_description');

  if (error) {
    codeVerifier = null; // Clear PKCE state on error
    throw new Error(`Auth0 error: ${error} - ${errorDescription || 'No description'}`);
  }

  if (!code) {
    codeVerifier = null; // Clear PKCE state on error
    throw new Error('No authorization code found in callback URL');
  }

  if (!codeVerifier) {
    throw new Error('No code verifier found - PKCE flow was not initiated properly');
  }

  console.log('Exchanging authorization code for tokens with PKCE...');

  const exchangeOptions: Record<string, string> = {
    grant_type: 'authorization_code',
    client_id: clientId!,
    code: code,
    redirect_uri: redirectUri,
    code_verifier: codeVerifier,
  };

  // Clear code verifier after using it
  codeVerifier = null;

  const options = {
    method: 'POST',
    url: `https://${auth0Domain!}/oauth/token`,
    headers: {
      'content-type': 'application/json',
    },
    data: exchangeOptions,
  };

  try {
    const response = await axiosClient<TokenResponse>(options);

    accessToken = response.data.access_token;
    profile = jwtDecode<UserProfile>(response.data.id_token);
    refreshToken = response.data.refresh_token || null;

    console.log('[Auth] Successfully obtained tokens');
    console.log('[Auth] Profile:', profile);

    // Log token expiration for debugging
    const decoded = jwtDecode<{ exp: number }>(accessToken);
    console.log(`[Auth] ✓ Token obtained. Expires at: ${new Date(decoded.exp * 1000).toLocaleString()}`);

    // Schedule silent token refresh based on JWT expiry
    scheduleTokenRefresh();

    if (refreshToken) {
      saveRefreshToken(refreshToken);
      console.log('Refresh token saved securely');
    }

    // Fetch service tokens from backend
    await fetchServiceTokens();
  } catch (error) {
    console.error('Token exchange failed:', error);
    if (axios.isAxiosError(error)) {
      console.error('Response data:', error.response?.data);
      console.error('Response status:', error.response?.status);
      throw new Error(`Token exchange failed: ${error.response?.data?.error_description || error.message}`);
    }
    await logout();
    throw error;
  }
}

export async function logout(): Promise<void> {
  cancelScheduledTokenRefresh();
  deleteRefreshToken();
  accessToken = null;
  profile = null;
  refreshToken = null;

  // Clear service tokens from session
  sessionService.clearServiceTokens();
}

export function getLogOutUrl(): string {
  return `https://${auth0Domain!}/v2/logout`;
}

/**
 * Secure token storage using OS-level encryption
 * - macOS: Keychain
 * - Windows: DPAPI (Data Protection API)
 * - Linux: Secret Service API / libsecret
 */

import { app } from 'electron';
import * as fs from 'fs';
import * as path from 'path';

function getTokenStoragePath(): string {
  const userDataPath = app.getPath('userData');
  return path.join(userDataPath, STORAGE_KEY);
}

/**
 * Saves refresh token encrypted with OS-level security
 */
function saveRefreshToken(token: string): void {
  if (!safeStorage.isEncryptionAvailable()) {
    console.error('OS-level encryption is not available. Token will not be saved.');
    throw new Error('Secure storage is not available on this system');
  }

  try {
    const encrypted = safeStorage.encryptString(token);
    const tokenPath = getTokenStoragePath();
    console.log(`[Auth] Saving refresh token to: ${tokenPath}`);

    // Ensure directory exists
    const dir = path.dirname(tokenPath);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }

    // Write encrypted token to disk with restricted permissions
    fs.writeFileSync(tokenPath, encrypted, { mode: 0o600 });

    // Verify the file was written
    if (fs.existsSync(tokenPath)) {
      const stats = fs.statSync(tokenPath);
      console.log(`[Auth] ✓ Refresh token saved (${stats.size} bytes) to: ${tokenPath}`);
    } else {
      console.error('[Auth] ✗ File write succeeded but file does not exist!');
    }
  } catch (error) {
    console.error('Failed to save refresh token:', error);
    throw new Error('Failed to save refresh token securely');
  }
}

/**
 * Loads and decrypts refresh token from OS-level secure storage
 */
function loadRefreshToken(): string | null {
  if (!safeStorage.isEncryptionAvailable()) {
    console.warn('[Auth] OS-level encryption is not available');
    return null;
  }

  try {
    const tokenPath = getTokenStoragePath();
    console.log(`[Auth] Loading refresh token from: ${tokenPath}`);

    if (!fs.existsSync(tokenPath)) {
      console.log(`[Auth] No saved refresh token found at: ${tokenPath}`);
      // List directory contents for debugging
      const dir = path.dirname(tokenPath);
      if (fs.existsSync(dir)) {
        const files = fs.readdirSync(dir);
        console.log(`[Auth] Files in ${dir}: ${files.join(', ') || '(empty)'}`);
      } else {
        console.log(`[Auth] Directory does not exist: ${dir}`);
      }
      return null;
    }

    const encryptedBuffer = fs.readFileSync(tokenPath);
    const decryptedToken = safeStorage.decryptString(encryptedBuffer);

    console.log('[Auth] ✓ Refresh token loaded from secure storage');
    return decryptedToken;
  } catch (error) {
    console.error('[Auth] Failed to load refresh token:', error);
    // If decryption fails, delete the corrupted token file
    deleteRefreshToken();
    return null;
  }
}

/**
 * Securely deletes the refresh token from storage
 */
function deleteRefreshToken(): void {
  try {
    const tokenPath = getTokenStoragePath();
    
    if (fs.existsSync(tokenPath)) {
      // Overwrite with zeros before deleting for extra security
      const stats = fs.statSync(tokenPath);
      const zeros = Buffer.alloc(stats.size, 0);
      fs.writeFileSync(tokenPath, zeros);
      fs.unlinkSync(tokenPath);
      console.log('Refresh token securely deleted');
    }
  } catch (error) {
    console.error('Error deleting refresh token:', error);
  }
}

