/**
 * Application constants
 */

// Custom protocol scheme for deep linking (Auth0 callbacks, etc.)
export const PROTOCOL_SCHEME = 'com.rocscience.rsinsight';

// Client type header value for X-Client-Type
export const CLIENT_TYPE_DESKTOP = 'desktop';

// MCP service name for unified token lookup
export const MCP_SERVICE_NAME = 'mcp';

// Refresh token 5 minutes before it expires
export const TOKEN_REFRESH_BUFFER_MS = 5 * 60 * 1000;

/**
 * Known Rocscience application paths on Windows
 * Used for version compatibility checks with MCP servers
 *
 * Paths can include wildcards (*) for version-agnostic matching.
 * The versionService will attempt to resolve wildcards to actual paths.
 */
export const ROCSCIENCE_APP_PATHS: Record<string, string> = {
  'RS2': 'C:\\Program Files\\Rocscience\\RS2\\RS2.exe',
  'RS3': 'C:\\Program Files\\Rocscience\\RS3\\RS3.exe',
  'RSPile': 'C:\\Program Files\\Rocscience\\RSPile\\RSPile.exe',
  'Slide2': 'C:\\Program Files\\Rocscience\\Slide2\\Slide2.exe',
  'Slide3': 'C:\\Program Files\\Rocscience\\Slide3\\Slide3.exe',
  'Settle3': 'C:\\Program Files\\Rocscience\\Settle3\\Settle3.exe',
  'RocFall2': 'C:\\Program Files\\Rocscience\\RocFall2\\RocFall2.exe',
  'RocFall3': 'C:\\Program Files\\Rocscience\\RocFall3\\RocFall3.exe',
  'Dips': 'C:\\Program Files\\Rocscience\\Dips 9.0\\Dips.exe',
  'SWedge': 'C:\\Program Files\\Rocscience\\SWedge\\SWedge.exe',
  'UnWedge': 'C:\\Program Files\\Rocscience\\UnWedge\\UnWedge.exe',
  'RocSupport': 'C:\\Program Files\\Rocscience\\RocSupport\\RocSupport.exe',
  'EX3': 'C:\\Program Files\\Rocscience\\EX3\\EX3.exe',
  'RocSlope2': 'C:\\Program Files\\Rocscience\\RocSlope2\\RocSlope2.exe',
  'RocSlope3': 'C:\\Program Files\\Rocscience\\RocSlope3\\RocSlope3.exe',
};

// Rocscience download URL for version mismatch notifications
export const ROCSCIENCE_DOWNLOAD_URL = 'https://www.rocscience.com/support/program-downloads';

// Per-app download/release-notes pages for version mismatch notifications
export const ROCSCIENCE_APP_DOWNLOAD_URLS: Record<string, string> = {
  'RS2': 'https://www.rocscience.com/support/rs2/release-notes',
  'RS3': 'https://www.rocscience.com/support/rs3/release-notes',
  'RSPile': 'https://www.rocscience.com/support/rspile/release-notes',
  'Settle3': 'https://www.rocscience.com/support/settle3/release-notes',
  'Dips': 'https://www.rocscience.com/support/dips/release-notes',
  'Slide2': 'https://www.rocscience.com/support/slide2/release-notes',
  'Slide3': 'https://www.rocscience.com/support/slide3/release-notes',
  'RocFall2': 'https://www.rocscience.com/support/rocfall2/release-notes',
  'RocFall3': 'https://www.rocscience.com/support/rocfall3/release-notes',
  'SWedge': 'https://www.rocscience.com/support/swedge/release-notes',
  'UnWedge': 'https://www.rocscience.com/support/unwedge/release-notes',
  'RocSupport': 'https://www.rocscience.com/support/rocsupport/release-notes',
  'EX3': 'https://www.rocscience.com/support/ex3/release-notes',
  'RocSlope2': 'https://www.rocscience.com/support/rocslope2/release-notes',
  'RocSlope3': 'https://www.rocscience.com/support/rocslope3/release-notes',
};

/**
 * Get the app-specific download URL, falling back to the generic downloads page.
 */
export function getAppDownloadUrl(appName: string): string {
  return ROCSCIENCE_APP_DOWNLOAD_URLS[appName] || ROCSCIENCE_DOWNLOAD_URL;
}
