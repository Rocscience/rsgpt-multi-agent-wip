import * as dotenv from 'dotenv';
import * as path from 'path';
import * as fs from 'fs';
import { app } from 'electron';

// Try to load .env file from multiple locations
function loadEnvFile() {
  const appPath = app.getAppPath();
  const unpackedAppPath = appPath && appPath.includes('app.asar')
    ? appPath.replace('app.asar', 'app.asar.unpacked')
    : appPath;

  const possiblePaths = [
    // Try unpacked paths first (production)
    unpackedAppPath ? path.join(unpackedAppPath, '.env') : null,
    unpackedAppPath ? path.join(path.dirname(unpackedAppPath), '.env') : null,
    process.resourcesPath ? path.join(process.resourcesPath, 'app.asar.unpacked', '.env') : null,
    // Development paths
    path.join(process.cwd(), '.env'),
    typeof __dirname !== 'undefined' ? path.join(__dirname, '../../../.env') : null,
    typeof __dirname !== 'undefined' ? path.join(__dirname, '../../.env') : null,
    // Original asar paths (fallback)
    appPath ? path.join(appPath, '.env') : null,
    appPath ? path.join(path.dirname(appPath), '.env') : null,
  ].filter((p): p is string => p !== null);

  console.log('Checking for .env file in:', possiblePaths);

  for (const envPath of possiblePaths) {
    if (fs.existsSync(envPath)) {
      console.log('✓ Loading .env from:', envPath);
      dotenv.config({ path: envPath });
      return true;
    }
  }

  console.warn('✗ No .env file found in any location');
  return false;
}

// Load env file if available
loadEnvFile();

export const config = {
  AUTH0_DOMAIN: process.env.AUTH0_DOMAIN as string,
  AUTH0_CLIENT_ID: process.env.AUTH0_CLIENT_ID as string,
  AUTH0_AUDIENCE: process.env.AUTH0_AUDIENCE as string,
  API_BASE_URL: process.env.API_BASE_URL as string,
  API_AI_BASE_URL: process.env.API_AI_BASE_URL as string,
  PINECONE_NAMESPACE: process.env.PINECONE_NAMESPACE as string,
  PINECONE_INDEX: process.env.PINECONE_INDEX as string,
  PINECONE_TOP_K: process.env.PINECONE_TOP_K as string,
  // Service tokens are now fetched from backend after Auth0 login
  // MCP_SERVICE_TOKEN: process.env.MCP_SERVICE_TOKEN as string,
  // MCP_RSPILE_SERVICE_TOKEN: process.env.MCP_RSPILE_SERVICE_TOKEN as string,
  // DESKTOP_SERVICE_TOKEN: process.env.DESKTOP_SERVICE_TOKEN as string,
};

console.log('Environment config loaded:', {
  AUTH0_DOMAIN: config.AUTH0_DOMAIN ? '***' : undefined,
  AUTH0_CLIENT_ID: config.AUTH0_CLIENT_ID ? '***' : undefined,
  AUTH0_AUDIENCE: config.AUTH0_AUDIENCE,
  API_BASE_URL: config.API_BASE_URL ? '***' : undefined,
  API_AI_BASE_URL: config.API_AI_BASE_URL ? '***' : undefined,
  // Service tokens are now fetched from backend after Auth0 login
});