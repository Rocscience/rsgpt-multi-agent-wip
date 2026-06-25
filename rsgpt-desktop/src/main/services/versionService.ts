import { exec } from 'child_process';
import { promisify } from 'util';
import * as fs from 'fs';
import * as path from 'path';
import { ROCSCIENCE_APP_PATHS, getAppDownloadUrl } from '../constants';

const execAsync = promisify(exec);

/**
 * Resolve a path pattern with wildcards to an actual file path
 * @param pathPattern - Path with optional wildcards (e.g., "C:\\...\\Dips*\\Dips.exe")
 * @returns Resolved path if found, or original pattern if no wildcards or not found
 */
function resolveWildcardPath(pathPattern: string): string {
  // If no wildcard, return as-is
  if (!pathPattern.includes('*')) {
    return pathPattern;
  }

  try {
    // Split into directory and filename
    const dirname = path.dirname(pathPattern);
    const filename = path.basename(pathPattern);

    // Check if the directory itself has a wildcard
    if (dirname.includes('*')) {
      // Get parent directory and pattern
      const parentDir = path.dirname(dirname);
      const dirPattern = path.basename(dirname);

      if (!fs.existsSync(parentDir)) {
        return pathPattern;
      }

      // Find matching subdirectories
      const entries = fs.readdirSync(parentDir, { withFileTypes: true });
      const matchingDirs = entries
        .filter(entry => entry.isDirectory())
        .filter(entry => {
          const pattern = dirPattern.replace(/\*/g, '.*');
          return new RegExp(`^${pattern}$`).test(entry.name);
        })
        .map(entry => entry.name);

      // Try each matching directory
      for (const dir of matchingDirs) {
        const fullPath = path.join(parentDir, dir, filename);
        if (fs.existsSync(fullPath)) {
          return fullPath;
        }
      }
    } else {
      // Only filename has wildcard
      if (!fs.existsSync(dirname)) {
        return pathPattern;
      }

      const entries = fs.readdirSync(dirname);
      const pattern = filename.replace(/\*/g, '.*');
      const match = entries.find(entry => new RegExp(`^${pattern}$`).test(entry));

      if (match) {
        return path.join(dirname, match);
      }
    }
  } catch (error) {
    console.error(`Failed to resolve wildcard path ${pathPattern}:`, error);
  }

  return pathPattern; // Return original if resolution fails
}

export interface AppVersionInfo {
  fileVersion: string;
  productVersion: string;
  productName: string;
  companyName: string;
  exists: boolean;
}

/**
 * Extract version information from a Windows executable using PowerShell
 * @param exePath - Full path to the executable
 * @returns AppVersionInfo object with version details and exists flag
 */
export async function getExeVersion(exePath: string): Promise<AppVersionInfo> {
  // Check if file exists first
  if (!fs.existsSync(exePath)) {
    return {
      fileVersion: '',
      productVersion: '',
      productName: '',
      companyName: '',
      exists: false
    };
  }

  // Escape single quotes in path for PowerShell
  const escapedPath = exePath.replace(/'/g, "''");

  const psCommand = `$info = (Get-Item '${escapedPath}').VersionInfo; @{ FileVersion = $info.FileVersion; ProductVersion = $info.ProductVersion; ProductName = $info.ProductName; CompanyName = $info.CompanyName } | ConvertTo-Json`;

  try {
    const { stdout } = await execAsync(
      `powershell -NoProfile -Command "${psCommand.replace(/"/g, '\\"')}"`,
      { timeout: 10000 }
    );

    const parsed = JSON.parse(stdout.trim());
    return {
      fileVersion: parsed.FileVersion || '',
      productVersion: parsed.ProductVersion || '',
      productName: parsed.ProductName || '',
      companyName: parsed.CompanyName || '',
      exists: true
    };
  } catch (error) {
    console.error(`Failed to extract version from ${exePath}:`, error);
    throw new Error(`Failed to extract version from ${exePath}: ${error}`);
  }
}

/**
 * Compare two version strings for exact match
 * @param localVersion - Version installed locally
 * @param requiredVersion - Version required by MCP
 * @returns true if versions match exactly
 */
export function compareVersionsExact(localVersion: string, requiredVersion: string): boolean {
  return localVersion.trim() === requiredVersion.trim();
}

/**
 * Search Windows Registry for a Rocscience application's install location.
 * Queries both 64-bit and 32-bit uninstall registry keys as a fallback
 * when the app is not found at the default hardcoded path.
 * @param appName - Name of the app (e.g., "RS2", "Settle3")
 * @returns Full path to the exe if found in registry, or null
 */
async function findAppInRegistry(appName: string): Promise<string | null> {
  try {
    const psCommand = `$paths = @('HKLM:\\\\SOFTWARE\\\\Microsoft\\\\Windows\\\\CurrentVersion\\\\Uninstall\\\\*','HKLM:\\\\SOFTWARE\\\\WOW6432Node\\\\Microsoft\\\\Windows\\\\CurrentVersion\\\\Uninstall\\\\*'); $app = Get-ItemProperty $paths -ErrorAction SilentlyContinue | Where-Object { $_.DisplayName -like '*${appName}*' -and $_.InstallLocation } | Select-Object -First 1; if ($app) { $app.InstallLocation } else { '' }`;

    const { stdout } = await execAsync(
      `powershell -NoProfile -Command "${psCommand.replace(/"/g, '\\"')}"`,
      { timeout: 10000 }
    );

    const installLocation = stdout.trim();
    if (!installLocation) {
      return null;
    }

    // Construct exe path: <InstallLocation>\<AppName>.exe
    const exePath = path.join(installLocation, `${appName}.exe`);
    if (fs.existsSync(exePath)) {
      console.log(`[Version Check] Found ${appName} via registry at: ${exePath}`);
      return exePath;
    }

    return null;
  } catch (error) {
    console.warn(`[Version Check] Registry lookup failed for ${appName}:`, error);
    return null;
  }
}

/**
 * Get the exe path for a Rocscience application.
 * First tries the hardcoded default path (with wildcard resolution),
 * then falls back to searching the Windows Registry for non-default installs.
 * @param appName - Name of the Rocscience application (e.g., "RS2", "RSPile")
 * @returns Full path to the executable, or undefined if app name is unknown
 */
export async function getRocscienceAppPath(appName: string): Promise<string | undefined> {
  const pathPattern = ROCSCIENCE_APP_PATHS[appName];
  if (!pathPattern) {
    return undefined;
  }

  const resolvedPath = resolveWildcardPath(pathPattern);

  // Fast path: hardcoded/wildcard path exists on disk
  if (fs.existsSync(resolvedPath)) {
    return resolvedPath;
  }

  // Fallback: search Windows Registry for non-default install locations
  const registryPath = await findAppInRegistry(appName);
  if (registryPath) {
    return registryPath;
  }

  // Return the original resolved path (will trigger "not found" error downstream)
  return resolvedPath;
}

/**
 * Check if a Rocscience application is installed and get its version
 * @param appName - Name of the Rocscience application
 * @returns AppVersionInfo or null if app name is unknown
 */
export async function checkRocscienceAppVersion(appName: string): Promise<AppVersionInfo | null> {
  const appPath = await getRocscienceAppPath(appName);
  if (!appPath) {
    console.warn(`Unknown Rocscience application: ${appName}`);
    return null;
  }
  return getExeVersion(appPath);
}

export interface VersionCheckResult {
  isCompatible: boolean;
  localVersion: string;
  requiredVersion: string;
  appExists: boolean;
  appPath: string;
  errorMessage?: string;
}

/**
 * Full version compatibility check for MCP installation
 * @param appName - Name of the Rocscience application (e.g., "RS2")
 * @param requiredVersion - Version required by the MCP
 * @param customAppPath - Optional custom path to the exe (overrides default)
 * @returns VersionCheckResult with compatibility status and details
 */
export async function checkVersionCompatibility(
  appName: string,
  requiredVersion: string,
  customAppPath?: string
): Promise<VersionCheckResult> {
  // If customAppPath is provided but doesn't exist, fall back to getRocscienceAppPath (which includes registry crawler)
  let appPath: string | undefined;
  if (customAppPath && fs.existsSync(customAppPath)) {
    appPath = customAppPath;
  } else {
    appPath = await getRocscienceAppPath(appName);
  }

  if (!appPath) {
    return {
      isCompatible: false,
      localVersion: '',
      requiredVersion,
      appExists: false,
      appPath: '',
      errorMessage: `Unknown Rocscience application: ${appName}. Cannot determine installation path.`
    };
  }

  const versionInfo = await getExeVersion(appPath);

  if (!versionInfo.exists) {
    return {
      isCompatible: false,
      localVersion: '',
      requiredVersion,
      appExists: false,
      appPath,
      errorMessage: `${appName} not found. Please install the latest version of ${appName} from ${getAppDownloadUrl(appName)}`
    };
  }

  const isCompatible = compareVersionsExact(versionInfo.fileVersion, requiredVersion);

  if (!isCompatible) {
    return {
      isCompatible: false,
      localVersion: versionInfo.fileVersion,
      requiredVersion,
      appExists: true,
      appPath,
      errorMessage: `This MCP requires ${appName} version ${requiredVersion}, but you have version ${versionInfo.fileVersion} installed. Please update ${appName} from ${getAppDownloadUrl(appName)}`
    };
  }

  return {
    isCompatible: true,
    localVersion: versionInfo.fileVersion,
    requiredVersion,
    appExists: true,
    appPath
  };
}
